"""Meta WhatsApp Cloud API client, webhook HMAC signature verification, and event parser."""

import hashlib
import hmac
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

from app.config import get_settings
from app.db.repository import normalize_phone_digits
from app.services.whatsapp_templates import WhatsAppTemplateName, render_template_payload


class WhatsAppClientError(Exception):
    """Raised when sending a message through Meta WhatsApp Cloud API fails."""


class WhatsAppSendResult(BaseModel):
    """Normalized outcome of sending a WhatsApp template or reply."""

    delivered: bool
    dry_run: bool
    provider_message_id: str | None = None
    status: str
    recipient_phone: str
    template_name: str | None = None
    deep_link: str | None = None
    preview_text: str
    raw_response: dict[str, Any] = Field(default_factory=dict)


class WebhookStatusUpdate(BaseModel):
    """Delivery status update extracted from Meta WhatsApp webhook payloads."""

    provider_message_id: str
    recipient_phone: str
    status: str
    error_message: str | None = None


class WebhookIncomingMessage(BaseModel):
    """Inbound user message extracted from Meta WhatsApp webhook payloads."""

    provider_message_id: str
    sender_phone: str
    message_type: str
    text_body: str = ""


class ParsedWebhookBatch(BaseModel):
    """All status updates and inbound messages parsed from one Meta webhook POST."""

    statuses: list[WebhookStatusUpdate] = Field(default_factory=list)
    messages: list[WebhookIncomingMessage] = Field(default_factory=list)


def verify_webhook_signature(
    raw_body: bytes,
    signature_header: str | None,
    app_secret: str,
) -> bool:
    """Verify Meta's X-Hub-Signature-256 HMAC-SHA256 header against the raw request body."""
    secret = app_secret.strip()
    if not secret or not signature_header:
        return False

    header = signature_header.strip()
    prefix = "sha256="
    if not header.startswith(prefix):
        return False

    provided_digest = header[len(prefix) :]
    if not provided_digest:
        return False

    expected_digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_digest, provided_digest)


def _extract_status_error(status_entry: dict[str, Any]) -> str | None:
    """Extract a readable error string from a Meta webhook status error array, if present."""
    errors = status_entry.get("errors")
    if not isinstance(errors, list) or not errors:
        return None
    first = errors[0]
    if not isinstance(first, dict):
        return str(first)
    error_data = first.get("error_data")
    details = error_data.get("details") if isinstance(error_data, dict) else None
    message = first.get("message") or first.get("title") or details
    return str(message).strip() if message else None


def _extract_inbound_text(message_entry: dict[str, Any]) -> str:
    """Extract user text from text, button, or interactive reply webhook payloads."""
    text_obj = message_entry.get("text")
    if isinstance(text_obj, dict) and text_obj.get("body") is not None:
        return str(text_obj["body"]).strip()

    button_obj = message_entry.get("button")
    if isinstance(button_obj, dict):
        btn_text = button_obj.get("text") or button_obj.get("payload")
        if btn_text is not None:
            return str(btn_text).strip()

    interactive_obj = message_entry.get("interactive")
    if isinstance(interactive_obj, dict):
        for reply_key in ("button_reply", "list_reply"):
            reply_obj = interactive_obj.get(reply_key)
            if isinstance(reply_obj, dict) and reply_obj.get("title") is not None:
                return str(reply_obj["title"]).strip()

    return ""


def parse_webhook_events(payload: dict[str, Any]) -> ParsedWebhookBatch:
    """Parse delivery status callbacks and incoming user messages from Meta webhook JSON."""
    statuses: list[WebhookStatusUpdate] = []
    messages: list[WebhookIncomingMessage] = []

    entries = payload.get("entry")
    if not isinstance(entries, list):
        return ParsedWebhookBatch()

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes")
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue

            for status_entry in value.get("statuses") or []:
                if not isinstance(status_entry, dict):
                    continue
                msg_id = str(status_entry.get("id") or "").strip()
                status_val = str(status_entry.get("status") or "").strip()
                recipient = str(status_entry.get("recipient_id") or "").strip()
                if not msg_id or not status_val:
                    continue
                statuses.append(
                    WebhookStatusUpdate(
                        provider_message_id=msg_id,
                        recipient_phone=recipient,
                        status=status_val,
                        error_message=_extract_status_error(status_entry),
                    )
                )

            for message_entry in value.get("messages") or []:
                if not isinstance(message_entry, dict):
                    continue
                msg_id = str(message_entry.get("id") or "").strip()
                sender = str(message_entry.get("from") or "").strip()
                msg_type = str(message_entry.get("type") or "unknown").strip()
                if not msg_id or not sender:
                    continue
                messages.append(
                    WebhookIncomingMessage(
                        provider_message_id=msg_id,
                        sender_phone=sender,
                        message_type=msg_type,
                        text_body=_extract_inbound_text(message_entry),
                    )
                )

    return ParsedWebhookBatch(statuses=statuses, messages=messages)


class WhatsAppCloudClient:
    """Meta WhatsApp Cloud API client with safe local dry-run fallback when unconfigured."""

    def __init__(
        self,
        *,
        access_token: str | None = None,
        phone_number_id: str | None = None,
        api_version: str | None = None,
        pwa_base_url: str | None = None,
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        self.access_token = (
            settings.whatsapp_access_token if access_token is None else access_token
        ).strip()
        self.phone_number_id = (
            settings.whatsapp_phone_number_id if phone_number_id is None else phone_number_id
        ).strip()
        self.api_version = (
            settings.whatsapp_api_version if api_version is None else api_version
        ).strip() or "v22.0"
        self.pwa_base_url = (
            settings.pwa_base_url if pwa_base_url is None else pwa_base_url
        ).strip() or "http://localhost:3000"
        self.timeout_seconds = timeout_seconds
        self._client = client

    @property
    def is_configured(self) -> bool:
        """Return True when both Meta access token and phone number ID are configured."""
        return bool(self.access_token and self.phone_number_id)

    def _post_messages(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute HTTP POST against Meta Graph API /{phone_number_id}/messages."""
        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        try:
            if self._client is not None:
                response = self._client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()

            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WhatsAppClientError(f"WhatsApp Cloud API request failed: {exc}") from exc

    def send_template(
        self,
        recipient_phone: str,
        template_name: WhatsAppTemplateName | str,
        params: dict[str, Any],
        *,
        language_code: str = "en",
        query_params: dict[str, str] | None = None,
        dry_run: bool = False,
    ) -> WhatsAppSendResult:
        """Send an approved WhatsApp notification template or render a deterministic dry-run."""
        normalized_phone = normalize_phone_digits(recipient_phone)
        rendered = render_template_payload(
            template_name,
            params,
            base_url=self.pwa_base_url,
            recipient_phone=normalized_phone,
            language_code=language_code,
            query_params=query_params,
        )

        if dry_run or not self.is_configured:
            return WhatsAppSendResult(
                delivered=False,
                dry_run=True,
                provider_message_id=f"dryrun_{uuid4().hex[:12]}",
                status="dry_run",
                recipient_phone=normalized_phone,
                template_name=rendered.template_name.value,
                deep_link=rendered.deep_link,
                preview_text=rendered.preview_text,
                raw_response={"dry_run": True, "request_payload": rendered.request_payload},
            )

        raw = self._post_messages(rendered.request_payload)
        messages = raw.get("messages") or []
        provider_id = (
            str(messages[0].get("id"))
            if messages and isinstance(messages[0], dict) and messages[0].get("id")
            else None
        )
        return WhatsAppSendResult(
            delivered=True,
            dry_run=False,
            provider_message_id=provider_id,
            status="sent",
            recipient_phone=normalized_phone,
            template_name=rendered.template_name.value,
            deep_link=rendered.deep_link,
            preview_text=rendered.preview_text,
            raw_response=raw,
        )

    def send_text_reply(
        self,
        recipient_phone: str,
        text: str,
        *,
        dry_run: bool = False,
    ) -> WhatsAppSendResult:
        """Send a lightweight session text reply (e.g., STOP/START or PWA chat redirect)."""
        normalized_phone = normalize_phone_digits(recipient_phone)
        body_text = text.strip()
        if not body_text:
            raise ValueError("Reply text cannot be empty")

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": normalized_phone,
            "type": "text",
            "text": {"preview_url": True, "body": body_text},
        }

        if dry_run or not self.is_configured:
            return WhatsAppSendResult(
                delivered=False,
                dry_run=True,
                provider_message_id=f"dryrun_{uuid4().hex[:12]}",
                status="dry_run",
                recipient_phone=normalized_phone,
                template_name=None,
                deep_link=None,
                preview_text=body_text,
                raw_response={"dry_run": True, "request_payload": payload},
            )

        raw = self._post_messages(payload)
        messages = raw.get("messages") or []
        provider_id = (
            str(messages[0].get("id"))
            if messages and isinstance(messages[0], dict) and messages[0].get("id")
            else None
        )
        return WhatsAppSendResult(
            delivered=True,
            dry_run=False,
            provider_message_id=provider_id,
            status="sent",
            recipient_phone=normalized_phone,
            template_name=None,
            deep_link=None,
            preview_text=body_text,
            raw_response=raw,
        )
