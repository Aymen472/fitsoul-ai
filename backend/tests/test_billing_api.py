"""Unit and integration tests for subscriptions, 7-day trial, payments, and webhooks."""

import hashlib
import hmac
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.billing import get_billing_settings
from app.config import Settings
from app.core.billing import (
    PaymentProvider,
    PlanId,
    SubscriptionStatus,
    compute_entitlements,
    get_plan,
    list_plans,
)
from app.db import (
    NotificationRepository,
    SubscriptionRepository,
    create_db_engine,
    get_db,
    init_db,
)
from app.main import create_app
from app.services import (
    WhatsAppTemplateName,
    evaluate_due_notifications_for_user,
    verify_payment_webhook_signature,
)


def _sign_payment_body(raw_body: bytes, secret: str, *, prefix: bool = True) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}" if prefix else digest


def _create_user_profile(client: TestClient, user_id: str = "bill-aymen") -> None:
    resp = client.post(
        "/api/v1/profiles",
        json={
            "user_id": user_id,
            "email": f"{user_id}@example.com",
            "full_name": "Aymen",
            "phone": "+92 300 4445566",
            "profile": {
                "age": 28,
                "gender": "female",
                "height_cm": 165.0,
                "weight_kg": 74.0,
                "activity_level": "sedentary",
                "goal": "lose",
                "conditions": ["pcos"],
                "timezone": "Asia/Karachi",
            },
        },
    )
    assert resp.status_code == 201


@pytest.fixture
def billing_env() -> Iterator[dict[str, Any]]:
    """Provide an isolated in-memory SQLite session factory + TestClient for billing."""
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    test_settings = Settings(
        pwa_base_url="https://app.fitsoul.pk",
        payment_webhook_secret="pay-webhook-secret",
    )

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    def override_get_billing_settings() -> Settings:
        return test_settings

    test_app = create_app(initialize_db=False)
    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_billing_settings] = override_get_billing_settings

    with TestClient(test_app) as client:
        yield {
            "client": client,
            "session_factory": session_factory,
            "settings": test_settings,
        }

    test_app.dependency_overrides.clear()
    engine.dispose()


def test_plan_catalog_and_compute_entitlements() -> None:
    plans = list_plans()
    assert len(plans) == 5
    assert get_plan(PlanId.TRIAL).duration_days == 7
    assert get_plan(PlanId.BASIC).price_amount == 1499.0
    assert get_plan(PlanId.PRO).price_amount == 2999.0
    assert get_plan(PlanId.TRANSFORMATION).price_amount == 6999.0
    assert get_plan(PlanId.TRANSFORMATION).duration_days == 90
    assert get_plan(PlanId.OVERSEAS).currency == "USD"
    assert get_plan(PlanId.OVERSEAS).price_amount == 9.99

    with pytest.raises(ValueError, match="Unknown subscription plan"):
        get_plan("enterprise")

    now = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)

    # Active Basic plan -> basic access mode, 5 chats/day, no photo/workouts
    status_basic, ent_basic = compute_entitlements(
        "basic",
        "active",
        now + timedelta(days=10),
        now=now,
    )
    assert status_basic == SubscriptionStatus.ACTIVE
    assert ent_basic.access_mode == "basic"
    assert ent_basic.daily_chat_limit == 5
    assert ent_basic.can_use_weekly_meal_plan is True
    assert ent_basic.can_use_photo_scanner is False
    assert ent_basic.can_use_workouts_face_yoga is False
    assert ent_basic.renewal_due_soon is False

    # Active Pro plan expiring in 2 days -> renewal_due_soon=True, full access
    status_pro, ent_pro = compute_entitlements(
        "pro",
        "active",
        now + timedelta(days=2),
        now=now,
    )
    assert status_pro == SubscriptionStatus.ACTIVE
    assert ent_pro.access_mode == "full"
    assert ent_pro.days_remaining == 2
    assert ent_pro.renewal_due_soon is True
    assert ent_pro.daily_chat_limit is None
    assert ent_pro.can_use_photo_scanner is True
    assert ent_pro.can_use_workouts_face_yoga is True

    # Expired subscription -> EXPIRED + limited mode
    status_exp, ent_exp = compute_entitlements(
        "trial",
        "active",
        now - timedelta(hours=1),
        now=now,
    )
    assert status_exp == SubscriptionStatus.EXPIRED
    assert ent_exp.access_mode == "limited"
    assert ent_exp.is_active is False
    assert ent_exp.daily_chat_limit == 2


def test_verify_payment_webhook_signature() -> None:
    raw = b'{"order_id":"fs_123","event":"payment.succeeded"}'
    secret = "pay-secret"

    assert (
        verify_payment_webhook_signature(raw, _sign_payment_body(raw, secret, prefix=True), secret)
        is True
    )
    assert (
        verify_payment_webhook_signature(raw, _sign_payment_body(raw, secret, prefix=False), secret)
        is True
    )
    assert (
        verify_payment_webhook_signature(raw + b" ", _sign_payment_body(raw, secret), secret)
        is False
    )
    assert verify_payment_webhook_signature(raw, "sha256=bad", secret) is False
    assert verify_payment_webhook_signature(raw, None, secret) is False
    assert verify_payment_webhook_signature(raw, _sign_payment_body(raw, secret), "") is False


def test_billing_trial_and_checkout_validation(billing_env: dict[str, Any]) -> None:
    client: TestClient = billing_env["client"]

    plans_resp = client.get("/api/v1/billing/plans")
    assert plans_resp.status_code == 200
    assert len(plans_resp.json()) == 5

    assert client.get("/api/v1/billing/missing-user/subscription").status_code == 404
    assert client.post("/api/v1/billing/missing-user/trial").status_code == 404

    _create_user_profile(client, "trial-user")

    # Initial status -> Limited mode & eligible for 7-day trial
    initial = client.get("/api/v1/billing/trial-user/subscription")
    assert initial.status_code == 200
    body = initial.json()
    assert body["subscription"] is None
    assert body["trial_eligible"] is True
    assert body["entitlements"]["access_mode"] == "limited"

    # First trial activation succeeds; second trial returns 409 Conflict
    trial_ok = client.post("/api/v1/billing/trial-user/trial")
    assert trial_ok.status_code == 201
    assert trial_ok.json()["plan"] == "trial"

    trial_dup = client.post("/api/v1/billing/trial-user/trial")
    assert trial_dup.status_code == 409

    # Checkout validation: rejects trial plan or incompatible provider
    assert (
        client.post(
            "/api/v1/billing/trial-user/checkout",
            json={"plan_id": "trial", "provider": "safepay"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/billing/trial-user/checkout",
            json={"plan_id": "overseas", "provider": "jazzcash"},
        ).status_code
        == 400
    )

    # Local JazzCash Pro checkout & Overseas LemonSqueezy checkout succeed
    pro_checkout = client.post(
        "/api/v1/billing/trial-user/checkout",
        json={"plan_id": "pro", "provider": "jazzcash"},
    )
    assert pro_checkout.status_code == 201
    assert pro_checkout.json()["sandbox_mode"] is True
    assert pro_checkout.json()["transaction"]["amount"] == 2999.0
    assert pro_checkout.json()["transaction"]["currency"] == "PKR"

    overseas_checkout = client.post(
        "/api/v1/billing/trial-user/checkout",
        json={"plan_id": "overseas", "provider": "lemonsqueezy"},
    )
    assert overseas_checkout.status_code == 201
    assert overseas_checkout.json()["transaction"]["currency"] == "USD"
    assert overseas_checkout.json()["transaction"]["amount"] == 9.99


def test_signed_payment_webhooks_idempotency_renewal_and_refund(
    billing_env: dict[str, Any],
) -> None:
    client: TestClient = billing_env["client"]
    settings: Settings = billing_env["settings"]

    _create_user_profile(client, "pay-user")

    checkout_resp = client.post(
        "/api/v1/billing/pay-user/checkout",
        json={"plan_id": "pro", "provider": "easypaisa"},
    )
    assert checkout_resp.status_code == 201
    order_id = checkout_resp.json()["transaction"]["provider_order_id"]

    # Bad provider or invalid signature rejected
    assert client.post("/webhooks/payments/unknown", content=b"{}").status_code == 400
    assert (
        client.post(
            "/webhooks/payments/easypaisa",
            content=b"{}",
            headers={"X-Payment-Signature": "sha256=bad"},
        ).status_code
        == 403
    )

    # Valid signed payment.succeeded activates Pro for 30 days
    ok_payload = json.dumps(
        {
            "order_id": order_id,
            "event": "payment.succeeded",
            "provider_reference": "EP-TXN-001",
        }
    ).encode("utf-8")
    ack_1 = client.post(
        "/webhooks/payments/easypaisa",
        content=ok_payload,
        headers={
            "X-Payment-Signature": _sign_payment_body(ok_payload, settings.payment_webhook_secret)
        },
    )
    assert ack_1.status_code == 200
    ack_1_body = ack_1.json()
    assert ack_1_body["already_processed"] is False
    assert ack_1_body["transaction"]["status"] == "paid"
    assert ack_1_body["subscription"]["plan"] == "pro"
    assert ack_1_body["subscription"]["status"] == "active"
    first_expiry = ack_1_body["subscription"]["expires_at"]

    # Duplicate webhook is idempotent and does NOT double-extend expiry
    ack_2 = client.post(
        "/webhooks/payments/easypaisa",
        content=ok_payload,
        headers={
            "X-Payment-Signature": _sign_payment_body(ok_payload, settings.payment_webhook_secret)
        },
    )
    assert ack_2.status_code == 200
    assert ack_2.json()["already_processed"] is True
    assert ack_2.json()["subscription"]["expires_at"] == first_expiry

    # Early renewal via Safepay extends existing expiry by another 30 days (~60 days total)
    renew_checkout = client.post(
        "/api/v1/billing/pay-user/checkout",
        json={"plan_id": "pro", "provider": "safepay"},
    )
    assert renew_checkout.status_code == 201
    renew_order_id = renew_checkout.json()["transaction"]["provider_order_id"]
    renew_raw = json.dumps({"order_id": renew_order_id, "event": "payment.succeeded"}).encode(
        "utf-8"
    )
    renew_ack = client.post(
        "/webhooks/payments/safepay",
        content=renew_raw,
        headers={
            "X-Payment-Signature": _sign_payment_body(renew_raw, settings.payment_webhook_secret)
        },
    )
    assert renew_ack.status_code == 200
    status_after_renew = client.get("/api/v1/billing/pay-user/subscription").json()
    assert status_after_renew["entitlements"]["days_remaining"] >= 59

    # Refund cancels subscription and returns user to limited mode
    refund_raw = json.dumps({"order_id": renew_order_id, "event": "payment.refunded"}).encode(
        "utf-8"
    )
    refund_ack = client.post(
        "/webhooks/payments/safepay",
        content=refund_raw,
        headers={
            "X-Payment-Signature": _sign_payment_body(refund_raw, settings.payment_webhook_secret)
        },
    )
    assert refund_ack.status_code == 200
    assert refund_ack.json()["transaction"]["status"] == "refunded"
    assert refund_ack.json()["subscription"]["status"] == "cancelled"

    final_status = client.get("/api/v1/billing/pay-user/subscription").json()
    assert final_status["entitlements"]["access_mode"] == "limited"

    # Separate failed transaction preserves failed status
    fail_checkout = client.post(
        "/api/v1/billing/pay-user/checkout",
        json={"plan_id": "basic", "provider": "payfast"},
    )
    fail_order_id = fail_checkout.json()["transaction"]["provider_order_id"]
    fail_raw = json.dumps({"order_id": fail_order_id, "event": "payment.failed"}).encode("utf-8")
    fail_ack = client.post(
        "/webhooks/payments/payfast",
        content=fail_raw,
        headers={
            "X-Payment-Signature": _sign_payment_body(fail_raw, settings.payment_webhook_secret)
        },
    )
    assert fail_ack.status_code == 200
    assert fail_ack.json()["transaction"]["status"] == "failed"


def test_activated_subscription_triggers_whatsapp_renewal_reminder(
    billing_env: dict[str, Any],
) -> None:
    client: TestClient = billing_env["client"]
    session_factory = billing_env["session_factory"]

    _create_user_profile(client, "renewal-link-user")

    with session_factory() as session:
        NotificationRepository.upsert_preferences(
            session,
            "renewal-link-user",
            whatsapp_opt_in=True,
            whatsapp_phone="+92 300 4445566",
            meal_reminders=False,
            water_reminders=False,
            workout_reminders=False,
            night_summary=False,
            weekly_report=False,
        )
        start_time = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
        sub = SubscriptionRepository.activate_paid_plan(
            session,
            "renewal-link-user",
            PlanId.PRO,
            PaymentProvider.JAZZCASH,
            now=start_time,
        )
        assert sub.expires_at is not None

        # Evaluate 2 days before expiry (14:00 Asia/Karachi = 09:00 UTC on Nov 29)
        eval_time = sub.expires_at - timedelta(days=2)
        jobs, _, _, _ = evaluate_due_notifications_for_user(
            session,
            "renewal-link-user",
            now=eval_time,
        )
        assert any(j.template_name == WhatsAppTemplateName.SUBSCRIPTION_RENEWAL for j in jobs)
