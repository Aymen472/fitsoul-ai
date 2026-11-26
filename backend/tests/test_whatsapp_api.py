"""Unit and integration tests for Meta WhatsApp Cloud API templates, client, and webhook."""

import hashlib
import hmac
import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.whatsapp import get_whatsapp_client, get_whatsapp_settings
from app.config import Settings
from app.db import create_db_engine, get_db, init_db, normalize_phone_digits
from app.main import create_app
from app.services import (
    WhatsAppClientError,
    WhatsAppCloudClient,
    WhatsAppTemplateName,
    list_template_definitions,
    render_template_payload,
    verify_webhook_signature,
)


def _sign_body(raw_body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _create_user_profile(
    client: TestClient,
    user_id: str = "wa-aymen",
    phone: str | None = "0300-1234567",
) -> None:
    resp = client.post(
        "/api/v1/profiles",
        json={
            "user_id": user_id,
            "email": f"{user_id}@example.com",
            "full_name": "Aymen",
            "phone": phone,
            "profile": {
                "age": 28,
                "gender": "female",
                "height_cm": 165.0,
                "weight_kg": 75.0,
                "activity_level": "sedentary",
                "goal": "lose",
                "conditions": ["pcos"],
                "timezone": "Asia/Karachi",
            },
        },
    )
    assert resp.status_code == 201


@pytest.fixture
def whatsapp_env() -> Iterator[dict[str, Any]]:
    """Provide an isolated TestClient with mocked WhatsApp settings and HTTP transport."""
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    sent_requests: list[dict[str, Any]] = []
    mock_state: dict[str, Any] = {"fail": False, "counter": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if mock_state["fail"]:
            return httpx.Response(500, json={"error": {"message": "Graph outage"}})
        mock_state["counter"] += 1
        body = json.loads(request.content.decode("utf-8"))
        sent_requests.append(
            {
                "url": str(request.url),
                "auth": request.headers.get("authorization"),
                "payload": body,
            }
        )
        return httpx.Response(
            200,
            json={"messages": [{"id": f"wamid.TEST_{mock_state['counter']}"}]},
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)

    test_settings = Settings(
        whatsapp_verify_token="fitsoul-verify-secret",
        whatsapp_access_token="meta-access-token",
        whatsapp_phone_number_id="10987654321",
        whatsapp_app_secret="meta-app-secret",
        whatsapp_api_version="v22.0",
        pwa_base_url="https://app.fitsoul.pk",
    )

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    def override_get_settings() -> Settings:
        return test_settings

    def override_get_client() -> WhatsAppCloudClient:
        return WhatsAppCloudClient(
            access_token=test_settings.whatsapp_access_token,
            phone_number_id=test_settings.whatsapp_phone_number_id,
            api_version=test_settings.whatsapp_api_version,
            pwa_base_url=test_settings.pwa_base_url,
            client=http_client,
        )

    test_app = create_app(initialize_db=False)
    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_whatsapp_settings] = override_get_settings
    test_app.dependency_overrides[get_whatsapp_client] = override_get_client

    with TestClient(test_app) as client:
        yield {
            "client": client,
            "settings": test_settings,
            "sent_requests": sent_requests,
            "mock_state": mock_state,
        }

    test_app.dependency_overrides.clear()
    http_client.close()
    engine.dispose()


def test_normalize_phone_digits() -> None:
    assert normalize_phone_digits("+92 300 1234567") == "923001234567"
    assert normalize_phone_digits("0300-1234567") == "923001234567"
    assert normalize_phone_digits(" (92) 321-7654321 ") == "923217654321"

    for invalid in ("", "123", "+92-300-abc", "9" * 16):
        with pytest.raises(ValueError):
            normalize_phone_digits(invalid)


def test_all_templates_render_and_validate_params() -> None:
    definitions = list_template_definitions()
    assert len(definitions) == 7

    sample_params: dict[WhatsAppTemplateName, dict[str, Any]] = {
        WhatsAppTemplateName.MEAL_REMINDER: {
            "user_name": "Aymen",
            "meal_slot": "Lunch",
            "suggested_meal": "1 chapati + daal moong + kachumber salad",
            "target_kcal": 450,
        },
        WhatsAppTemplateName.WATER_REMINDER: {
            "user_name": "Aymen",
            "consumed_ml": 1000,
            "target_ml": 2500,
        },
        WhatsAppTemplateName.WORKOUT_NUDGE: {
            "user_name": "Aymen",
            "routine_name": "PCOS Low-Impact Walk & Tone",
            "duration_minutes": 15,
        },
        WhatsAppTemplateName.NIGHT_SUMMARY: {
            "user_name": "Aymen",
            "consumed_kcal": 1480,
            "target_kcal": 1550,
            "streak_days": 5,
        },
        WhatsAppTemplateName.WEEKLY_REPORT: {
            "user_name": "Aymen",
            "avg_kcal": 1510,
            "workouts_completed": 4,
            "weight_delta": "-0.6 kg",
        },
        WhatsAppTemplateName.PROACTIVE_SUPPORT: {
            "user_name": "Aymen",
            "support_message": "Raat ki chai cravings ke liye almonds + elaichi tea try karein.",
        },
        WhatsAppTemplateName.SUBSCRIPTION_RENEWAL: {
            "user_name": "Aymen",
            "days_remaining": 3,
            "plan_name": "Pro Monthly",
        },
    }

    for defn in definitions:
        rendered = render_template_payload(
            defn.name,
            sample_params[defn.name],
            base_url="https://app.fitsoul.pk/",
            recipient_phone="923001234567",
            query_params={"utm_source": "whatsapp"},
        )
        assert rendered.deep_link.startswith(f"https://app.fitsoul.pk{defn.default_path}")
        assert "utm_source=whatsapp" in rendered.deep_link
        assert rendered.request_payload["messaging_product"] == "whatsapp"
        assert rendered.request_payload["type"] == "template"
        components = rendered.request_payload["template"]["components"]
        assert len(components[0]["parameters"]) == len(defn.required_params)
        assert components[1]["type"] == "button"
        assert components[1]["parameters"][0]["text"].startswith(defn.default_path)

    with pytest.raises(ValueError, match="Missing required parameters"):
        render_template_payload(
            WhatsAppTemplateName.WATER_REMINDER,
            {"user_name": "Aymen", "consumed_ml": "   "},
            base_url="https://app.fitsoul.pk",
            recipient_phone="923001234567",
        )

    with pytest.raises(ValueError, match="Unknown WhatsApp template"):
        render_template_payload(
            "nonexistent_template",
            {},
            base_url="https://app.fitsoul.pk",
            recipient_phone="923001234567",
        )


def test_verify_webhook_signature() -> None:
    body = b'{"object":"whatsapp_business_account"}'
    secret = "super-secret"
    valid_sig = _sign_body(body, secret)

    assert verify_webhook_signature(body, valid_sig, secret) is True
    assert verify_webhook_signature(body + b" ", valid_sig, secret) is False
    assert verify_webhook_signature(body, valid_sig, "wrong-secret") is False
    assert verify_webhook_signature(body, "md5=1234", secret) is False
    assert verify_webhook_signature(body, None, secret) is False
    assert verify_webhook_signature(body, valid_sig, "") is False


def test_whatsapp_cloud_client_dry_run_and_live_transport() -> None:
    dry_client = WhatsAppCloudClient(
        access_token="",
        phone_number_id="",
        pwa_base_url="https://app.fitsoul.pk",
    )
    assert dry_client.is_configured is False
    dry_res = dry_client.send_template(
        "+92 300 1234567",
        WhatsAppTemplateName.WATER_REMINDER,
        {"user_name": "Aymen", "consumed_ml": 750, "target_ml": 2500},
    )
    assert dry_res.dry_run is True
    assert dry_res.delivered is False
    assert dry_res.status == "dry_run"
    assert dry_res.provider_message_id is not None
    assert dry_res.provider_message_id.startswith("dryrun_")

    captured: list[httpx.Request] = []

    def ok_handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.MOCK999"}]})

    with httpx.Client(transport=httpx.MockTransport(ok_handler)) as http_ok:
        live_client = WhatsAppCloudClient(
            access_token="tok-123",
            phone_number_id="5550001",
            api_version="v22.0",
            pwa_base_url="https://app.fitsoul.pk",
            client=http_ok,
        )
        assert live_client.is_configured is True
        live_res = live_client.send_template(
            "03001234567",
            WhatsAppTemplateName.WORKOUT_NUDGE,
            {"user_name": "Aymen", "routine_name": "Jawline Flow", "duration_minutes": 8},
        )
        assert live_res.dry_run is False
        assert live_res.delivered is True
        assert live_res.status == "sent"
        assert live_res.provider_message_id == "wamid.MOCK999"
        assert len(captured) == 1
        assert str(captured[0].url) == "https://graph.facebook.com/v22.0/5550001/messages"
        assert captured[0].headers["authorization"] == "Bearer tok-123"

    def err_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"})

    with httpx.Client(transport=httpx.MockTransport(err_handler)) as http_err:
        failing_client = WhatsAppCloudClient(
            access_token="tok-123",
            phone_number_id="5550001",
            client=http_err,
        )
        with pytest.raises(WhatsAppClientError):
            failing_client.send_template(
                "03001234567",
                WhatsAppTemplateName.WATER_REMINDER,
                {"user_name": "Aymen", "consumed_ml": 500, "target_ml": 2500},
            )


def test_webhook_challenge_verification(whatsapp_env: dict[str, Any]) -> None:
    client: TestClient = whatsapp_env["client"]

    ok_resp = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "fitsoul-verify-secret",
            "hub.challenge": "challenge-98765",
        },
    )
    assert ok_resp.status_code == 200
    assert ok_resp.text == "challenge-98765"

    bad_resp = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "challenge-98765",
        },
    )
    assert bad_resp.status_code == 403


def test_notification_preferences_send_and_logs(whatsapp_env: dict[str, Any]) -> None:
    client: TestClient = whatsapp_env["client"]
    mock_state: dict[str, Any] = whatsapp_env["mock_state"]

    assert client.get("/api/v1/notifications/missing-user/preferences").status_code == 404
    assert client.get("/api/v1/notifications/missing-user/logs").status_code == 404

    templates_resp = client.get("/api/v1/notifications/templates")
    assert templates_resp.status_code == 200
    assert len(templates_resp.json()) == 7

    _create_user_profile(client, "wa-user-1", phone="0300-1234567")

    prefs_resp = client.get("/api/v1/notifications/wa-user-1/preferences")
    assert prefs_resp.status_code == 200
    assert prefs_resp.json()["whatsapp_opt_in"] is False
    assert prefs_resp.json()["whatsapp_phone"] == "923001234567"

    # Cannot send while opted out
    blocked_send = client.post(
        "/api/v1/notifications/wa-user-1/send",
        json={
            "template_name": "fitsoul_workout_nudge",
            "params": {
                "user_name": "Aymen",
                "routine_name": "PCOS Low-Impact",
                "duration_minutes": 15,
            },
        },
    )
    assert blocked_send.status_code == 400

    # Invalid quiet hours and missing phone on opt-in return 400
    assert (
        client.put(
            "/api/v1/notifications/wa-user-1/preferences",
            json={"whatsapp_opt_in": True, "whatsapp_phone": ""},
        ).status_code
        == 400
    )
    assert (
        client.put(
            "/api/v1/notifications/wa-user-1/preferences",
            json={
                "whatsapp_opt_in": True,
                "whatsapp_phone": "+92 300 1234567",
                "quiet_hours_start": "25:00",
            },
        ).status_code
        == 400
    )

    # Opt in cleanly
    update_resp = client.put(
        "/api/v1/notifications/wa-user-1/preferences",
        json={
            "whatsapp_opt_in": True,
            "whatsapp_phone": "+92 300 1234567",
            "meal_reminders": True,
            "water_reminders": True,
            "workout_reminders": True,
            "quiet_hours_start": "22:30",
            "quiet_hours_end": "07:00",
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["whatsapp_opt_in"] is True
    assert update_resp.json()["whatsapp_phone"] == "923001234567"

    # Dry-run send
    dry_send = client.post(
        "/api/v1/notifications/wa-user-1/send",
        json={
            "template_name": "fitsoul_workout_nudge",
            "params": {
                "user_name": "Aymen",
                "routine_name": "PCOS Low-Impact",
                "duration_minutes": 15,
            },
            "dry_run": True,
        },
    )
    assert dry_send.status_code == 200
    dry_body = dry_send.json()
    assert dry_body["dry_run"] is True
    assert dry_body["log"]["status"] == "dry_run"
    assert "/workouts" in dry_body["log"]["deep_link"]

    # Live send via MockTransport
    live_send = client.post(
        "/api/v1/notifications/wa-user-1/send",
        json={
            "template_name": "fitsoul_meal_reminder",
            "params": {
                "user_name": "Aymen",
                "meal_slot": "Dinner",
                "suggested_meal": "2 chapati + grilled chicken",
                "target_kcal": 500,
            },
        },
    )
    assert live_send.status_code == 200
    live_body = live_send.json()
    assert live_body["dry_run"] is False
    assert live_body["log"]["status"] == "sent"
    assert live_body["log"]["provider_message_id"] == "wamid.TEST_1"

    # Graph API failure maps to 502 and persists failed log
    mock_state["fail"] = True
    failed_send = client.post(
        "/api/v1/notifications/wa-user-1/send",
        json={
            "template_name": "fitsoul_water_reminder",
            "params": {"user_name": "Aymen", "consumed_ml": 500, "target_ml": 2500},
        },
    )
    assert failed_send.status_code == 502

    logs_resp = client.get("/api/v1/notifications/wa-user-1/logs")
    assert logs_resp.status_code == 200
    logs = logs_resp.json()
    assert len(logs) == 3
    statuses = [entry["status"] for entry in logs]
    assert "failed" in statuses
    assert "sent" in statuses
    assert "dry_run" in statuses


def test_signed_webhook_statuses_stop_start_and_redirect(whatsapp_env: dict[str, Any]) -> None:
    client: TestClient = whatsapp_env["client"]
    settings: Settings = whatsapp_env["settings"]
    sent_requests: list[dict[str, Any]] = whatsapp_env["sent_requests"]

    _create_user_profile(client, "wa-user-2", phone="+92 300 5556677")
    assert (
        client.put(
            "/api/v1/notifications/wa-user-2/preferences",
            json={"whatsapp_opt_in": True, "whatsapp_phone": "03005556677"},
        ).status_code
        == 200
    )

    send_resp = client.post(
        "/api/v1/notifications/wa-user-2/send",
        json={
            "template_name": "fitsoul_night_summary",
            "params": {
                "user_name": "Aymen",
                "consumed_kcal": 1400,
                "target_kcal": 1500,
                "streak_days": 3,
            },
        },
    )
    assert send_resp.status_code == 200
    wamid = send_resp.json()["log"]["provider_message_id"]

    # Bad signature rejected
    bad_post = client.post(
        "/webhooks/whatsapp",
        content=b"{}",
        headers={"X-Hub-Signature-256": "sha256=deadbeef"},
    )
    assert bad_post.status_code == 403

    # Invalid JSON rejected when signed properly
    bad_json_raw = b"{not-json"
    bad_json_post = client.post(
        "/webhooks/whatsapp",
        content=bad_json_raw,
        headers={"X-Hub-Signature-256": _sign_body(bad_json_raw, settings.whatsapp_app_secret)},
    )
    assert bad_json_post.status_code == 400

    # Status progression: delivered -> read
    for status_value in ("delivered", "read"):
        status_payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "statuses": [
                                    {
                                        "id": wamid,
                                        "recipient_id": "923005556677",
                                        "status": status_value,
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        raw = json.dumps(status_payload).encode("utf-8")
        ack = client.post(
            "/webhooks/whatsapp",
            content=raw,
            headers={"X-Hub-Signature-256": _sign_body(raw, settings.whatsapp_app_secret)},
        )
        assert ack.status_code == 200
        assert ack.json()["statuses_processed"] == 1

    logs_after_status = client.get("/api/v1/notifications/wa-user-2/logs").json()
    assert any(
        item["provider_message_id"] == wamid and item["status"] == "read"
        for item in logs_after_status
    )

    # Inbound STOP disables opt-in and sends confirmation
    stop_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.IN_STOP",
                                    "from": "923005556677",
                                    "type": "text",
                                    "text": {"body": "STOP"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    stop_raw = json.dumps(stop_payload).encode("utf-8")
    stop_ack = client.post(
        "/webhooks/whatsapp",
        content=stop_raw,
        headers={"X-Hub-Signature-256": _sign_body(stop_raw, settings.whatsapp_app_secret)},
    )
    assert stop_ack.status_code == 200
    assert (
        client.get("/api/v1/notifications/wa-user-2/preferences").json()["whatsapp_opt_in"] is False
    )
    assert "START" in sent_requests[-1]["payload"]["text"]["body"]

    # Inbound START re-enables opt-in
    start_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.IN_START",
                                    "from": "923005556677",
                                    "type": "text",
                                    "text": {"body": "start"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    start_raw = json.dumps(start_payload).encode("utf-8")
    assert (
        client.post(
            "/webhooks/whatsapp",
            content=start_raw,
            headers={"X-Hub-Signature-256": _sign_body(start_raw, settings.whatsapp_app_secret)},
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/notifications/wa-user-2/preferences").json()["whatsapp_opt_in"] is True
    )

    # General incoming message redirects to PWA /chat link (ADR-001)
    chat_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.IN_CHAT",
                                    "from": "923005556677",
                                    "type": "text",
                                    "text": {"body": "Aaj kya khaun?"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    chat_raw = json.dumps(chat_payload).encode("utf-8")
    chat_ack = client.post(
        "/webhooks/whatsapp",
        content=chat_raw,
        headers={"X-Hub-Signature-256": _sign_body(chat_raw, settings.whatsapp_app_secret)},
    )
    assert chat_ack.status_code == 200
    assert chat_ack.json()["messages_processed"] == 1
    assert "https://app.fitsoul.pk/chat" in sent_requests[-1]["payload"]["text"]["body"]
