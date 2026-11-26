"""Meta WhatsApp Cloud API webhook, template catalog, and notification preferences routes."""

import hmac
import json
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import (
    NotificationLogRecord,
    NotificationPreferenceRecord,
    NotificationRepository,
    ProfileRepository,
    get_db,
    normalize_phone_digits,
)
from app.services import (
    SchedulePreviewResponse,
    SchedulerRunSummary,
    TemplateDefinition,
    WhatsAppClientError,
    WhatsAppCloudClient,
    WhatsAppTemplateName,
    build_pwa_deep_link,
    evaluate_due_notifications_for_user,
    list_template_definitions,
    parse_webhook_events,
    run_proactive_scheduler,
    verify_webhook_signature,
)

router = APIRouter(tags=["whatsapp", "notifications"])

_STOP_KEYWORDS = frozenset({"STOP", "UNSUBSCRIBE", "BAND", "OFF"})
_START_KEYWORDS = frozenset({"START", "SUBSCRIBE", "ON"})


def get_whatsapp_settings() -> Settings:
    """FastAPI dependency returning runtime settings for WhatsApp endpoints."""
    return get_settings()


def get_whatsapp_client(
    settings: Annotated[Settings, Depends(get_whatsapp_settings)],
) -> WhatsAppCloudClient:
    """FastAPI dependency returning the configured Meta WhatsApp Cloud API client."""
    return WhatsAppCloudClient(
        access_token=settings.whatsapp_access_token,
        phone_number_id=settings.whatsapp_phone_number_id,
        api_version=settings.whatsapp_api_version,
        pwa_base_url=settings.pwa_base_url,
    )


DbSession = Annotated[Session, Depends(get_db)]
WhatsAppSettingsDep = Annotated[Settings, Depends(get_whatsapp_settings)]
WhatsAppClientDep = Annotated[WhatsAppCloudClient, Depends(get_whatsapp_client)]


class WebhookAckResponse(BaseModel):
    """Structured acknowledgement returned to Meta webhook callbacks."""

    status: str = "ok"
    statuses_processed: int = 0
    messages_processed: int = 0


class NotificationPreferencesUpdateRequest(BaseModel):
    """Payload to update per-user WhatsApp opt-in settings, phone number, and quiet hours."""

    whatsapp_opt_in: bool = False
    whatsapp_phone: str | None = None
    meal_reminders: bool = True
    water_reminders: bool = True
    workout_reminders: bool = True
    night_summary: bool = True
    weekly_report: bool = True
    quiet_hours_start: str = "22:30"
    quiet_hours_end: str = "07:00"


class SendNotificationRequest(BaseModel):
    """Payload to trigger a template-based WhatsApp notification for an opted-in user."""

    template_name: WhatsAppTemplateName | str
    params: dict[str, Any] = Field(default_factory=dict)
    language_code: str = "en"
    query_params: dict[str, str] | None = None
    dry_run: bool = False


class SendNotificationResponse(BaseModel):
    """Persisted notification log plus rendered preview text."""

    log: NotificationLogRecord
    preview_text: str
    dry_run: bool


def _require_profile_phone(profile_phone: str | None) -> str | None:
    if not profile_phone or not profile_phone.strip():
        return None
    try:
        return normalize_phone_digits(profile_phone)
    except ValueError:
        return None


def _send_best_effort_reply(
    db: Session,
    whatsapp_client: WhatsAppCloudClient,
    *,
    recipient_phone: str,
    user_id: str | None,
    reply_text: str,
    deep_link: str | None = None,
) -> None:
    """Send an automated compliance or PWA redirect reply without failing webhook ACKs."""
    try:
        result = whatsapp_client.send_text_reply(recipient_phone, reply_text)
        NotificationRepository.log_notification(
            db,
            user_id=user_id,
            direction="outbound",
            status=result.status,
            recipient_phone=result.recipient_phone,
            provider_message_id=result.provider_message_id,
            deep_link=deep_link,
            payload={"reply_text": reply_text},
        )
    except (WhatsAppClientError, ValueError) as exc:
        NotificationRepository.log_notification(
            db,
            user_id=user_id,
            direction="outbound",
            status="failed",
            recipient_phone=recipient_phone,
            deep_link=deep_link,
            payload={"reply_text": reply_text},
            error_message=str(exc),
        )


@router.get("/webhooks/whatsapp", response_class=PlainTextResponse)
def verify_whatsapp_webhook(
    hub_mode: Annotated[str, Query(alias="hub.mode")],
    hub_verify_token: Annotated[str, Query(alias="hub.verify_token")],
    hub_challenge: Annotated[str, Query(alias="hub.challenge")],
    settings: WhatsAppSettingsDep,
) -> PlainTextResponse:
    """Verify the Meta WhatsApp Cloud API webhook subscription challenge."""
    expected_token = settings.whatsapp_verify_token.strip()
    if (
        expected_token
        and hub_mode == "subscribe"
        and hmac.compare_digest(hub_verify_token, expected_token)
    ):
        return PlainTextResponse(content=hub_challenge, status_code=status.HTTP_200_OK)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid WhatsApp webhook verification token",
    )


@router.post("/webhooks/whatsapp", response_model=WebhookAckResponse)
async def handle_whatsapp_webhook(
    request: Request,
    db: DbSession,
    settings: WhatsAppSettingsDep,
    whatsapp_client: WhatsAppClientDep,
) -> WebhookAckResponse:
    """Process Meta WhatsApp delivery statuses, STOP/START keywords, and PWA chat redirects."""
    raw_body = await request.body()
    app_secret = settings.whatsapp_app_secret.strip()
    if app_secret:
        signature = request.headers.get("X-Hub-Signature-256")
        if not verify_webhook_signature(raw_body, signature, app_secret):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid webhook signature",
            )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    batch = parse_webhook_events(payload)

    for status_evt in batch.statuses:
        NotificationRepository.update_delivery_status(
            db,
            status_evt.provider_message_id,
            status_evt.status,
            error_message=status_evt.error_message,
        )

    chat_deep_link = build_pwa_deep_link(settings.pwa_base_url, "/chat")

    for msg in batch.messages:
        profile = ProfileRepository.get_profile_by_phone(db, msg.sender_phone)
        user_id = profile.user_id if profile is not None else None
        try:
            normalized_sender = normalize_phone_digits(msg.sender_phone)
        except ValueError:
            normalized_sender = msg.sender_phone.strip()

        NotificationRepository.log_notification(
            db,
            user_id=user_id,
            direction="inbound",
            status="received",
            recipient_phone=normalized_sender,
            provider_message_id=msg.provider_message_id,
            payload={"message_type": msg.message_type, "text_body": msg.text_body},
        )

        tokens = msg.text_body.strip().upper().split()
        first_token = tokens[0].strip(".,!?") if tokens else ""

        if first_token in _STOP_KEYWORDS:
            NotificationRepository.set_opt_in_by_phone(db, normalized_sender, False)
            _send_best_effort_reply(
                db,
                whatsapp_client,
                recipient_phone=normalized_sender,
                user_id=user_id,
                reply_text=(
                    "FitSoul AI WhatsApp reminders band kar diye gaye hain. "
                    "Dubara shuru karne ke liye START likh kar bhejein."
                ),
            )
        elif first_token in _START_KEYWORDS:
            NotificationRepository.set_opt_in_by_phone(db, normalized_sender, True)
            _send_best_effort_reply(
                db,
                whatsapp_client,
                recipient_phone=normalized_sender,
                user_id=user_id,
                reply_text=(
                    "FitSoul AI WhatsApp notifications dubara active ho gayi hain! "
                    f"Apne coach se baat karne ke liye yahan aayein: {chat_deep_link}"
                ),
                deep_link=chat_deep_link,
            )
        else:
            _send_best_effort_reply(
                db,
                whatsapp_client,
                recipient_phone=normalized_sender,
                user_id=user_id,
                reply_text=(
                    "Assalam-o-Alaikum! FitSoul AI WhatsApp sirf reminders aur check-ins "
                    "bhejta hai. Full AI coach chat, meal plans aur workout player yahan "
                    f"kholein: {chat_deep_link}"
                ),
                deep_link=chat_deep_link,
            )

    return WebhookAckResponse(
        status="ok",
        statuses_processed=len(batch.statuses),
        messages_processed=len(batch.messages),
    )


@router.get("/api/v1/notifications/templates", response_model=list[TemplateDefinition])
def get_notification_templates() -> list[TemplateDefinition]:
    """List approved Meta WhatsApp notification templates supported by FitSoul AI."""
    return list_template_definitions()


@router.get(
    "/api/v1/notifications/{user_id}/preferences",
    response_model=NotificationPreferenceRecord,
)
def read_notification_preferences(user_id: str, db: DbSession) -> NotificationPreferenceRecord:
    """Return a user's WhatsApp notification preferences (or safe defaults if unset)."""
    profile = ProfileRepository.get_profile(db, user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    prefs = NotificationRepository.get_preferences(db, user_id)
    if prefs is not None:
        return prefs

    return NotificationPreferenceRecord(
        user_id=user_id,
        whatsapp_opt_in=False,
        whatsapp_phone=_require_profile_phone(profile.phone),
    )


@router.put(
    "/api/v1/notifications/{user_id}/preferences",
    response_model=NotificationPreferenceRecord,
)
def update_notification_preferences(
    user_id: str,
    payload: NotificationPreferencesUpdateRequest,
    db: DbSession,
) -> NotificationPreferenceRecord:
    """Create or update WhatsApp opt-in, phone number, reminder toggles, and quiet hours."""
    profile = ProfileRepository.get_profile(db, user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    try:
        return NotificationRepository.upsert_preferences(
            db,
            user_id,
            whatsapp_opt_in=payload.whatsapp_opt_in,
            whatsapp_phone=payload.whatsapp_phone,
            meal_reminders=payload.meal_reminders,
            water_reminders=payload.water_reminders,
            workout_reminders=payload.workout_reminders,
            night_summary=payload.night_summary,
            weekly_report=payload.weekly_report,
            quiet_hours_start=payload.quiet_hours_start,
            quiet_hours_end=payload.quiet_hours_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/api/v1/notifications/{user_id}/send",
    response_model=SendNotificationResponse,
)
def send_user_notification(
    user_id: str,
    payload: SendNotificationRequest,
    db: DbSession,
    whatsapp_client: WhatsAppClientDep,
) -> SendNotificationResponse:
    """Send an approved WhatsApp notification template to an opted-in user and log it."""
    profile = ProfileRepository.get_profile(db, user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    prefs = NotificationRepository.get_preferences(db, user_id)
    if prefs is None or not prefs.whatsapp_opt_in or not prefs.whatsapp_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has not opted in to WhatsApp notifications or has no phone number",
        )

    try:
        result = whatsapp_client.send_template(
            prefs.whatsapp_phone,
            payload.template_name,
            payload.params,
            language_code=payload.language_code,
            query_params=payload.query_params,
            dry_run=payload.dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except WhatsAppClientError as exc:
        NotificationRepository.log_notification(
            db,
            user_id=user_id,
            direction="outbound",
            status="failed",
            template_name=str(payload.template_name),
            recipient_phone=prefs.whatsapp_phone,
            payload={"params": payload.params},
            error_message=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    log = NotificationRepository.log_notification(
        db,
        user_id=user_id,
        direction="outbound",
        status=result.status,
        template_name=result.template_name,
        recipient_phone=result.recipient_phone,
        provider_message_id=result.provider_message_id,
        deep_link=result.deep_link,
        payload={"params": payload.params, "preview_text": result.preview_text},
    )
    return SendNotificationResponse(
        log=log, preview_text=result.preview_text, dry_run=result.dry_run
    )


@router.get(
    "/api/v1/notifications/{user_id}/logs",
    response_model=list[NotificationLogRecord],
)
def read_notification_logs(
    user_id: str,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[NotificationLogRecord]:
    """Fetch recent outbound and inbound WhatsApp notification logs for a user."""
    profile = ProfileRepository.get_profile(db, user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    return NotificationRepository.list_user_notifications(db, user_id, limit=limit)


class SchedulerRunRequest(BaseModel):
    """Payload to trigger a proactive notification scheduler sweep (cron or manual dry-run)."""

    user_id: str | None = None
    dry_run: bool = False
    at_utc: datetime | None = None


@router.get(
    "/api/v1/notifications/{user_id}/schedule-preview",
    response_model=SchedulePreviewResponse,
)
def preview_user_notification_schedule(
    user_id: str,
    db: DbSession,
    at_utc: Annotated[datetime | None, Query()] = None,
) -> SchedulePreviewResponse:
    """Preview a user's local schedule, quiet-hours status, and currently due notifications."""
    try:
        _jobs, _in_quiet, _dups, preview = evaluate_due_notifications_for_user(
            db,
            user_id,
            now=at_utc,
        )
        return preview
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/api/v1/notifications/scheduler/run",
    response_model=SchedulerRunSummary,
)
def trigger_notification_scheduler(
    request: Request,
    payload: SchedulerRunRequest,
    db: DbSession,
    settings: WhatsAppSettingsDep,
    whatsapp_client: WhatsAppClientDep,
) -> SchedulerRunSummary:
    """Run proactive scheduler across opted-in users (guarded by optional X-Scheduler-Secret)."""
    expected_secret = settings.scheduler_secret.strip()
    if expected_secret:
        provided_secret = (request.headers.get("X-Scheduler-Secret") or "").strip()
        if not hmac.compare_digest(provided_secret, expected_secret):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid scheduler secret",
            )

    try:
        return run_proactive_scheduler(
            db,
            whatsapp_client,
            now=payload.at_utc,
            user_id=payload.user_id,
            dry_run=payload.dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
