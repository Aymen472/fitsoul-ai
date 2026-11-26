"""Unit and integration tests for admin panel, safety review, food CRUD, and data wipe."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.admin import get_admin_settings
from app.config import Settings
from app.core.billing import PaymentProvider, PlanId
from app.db import (
    MealLogRow,
    MemoryRepository,
    MessageRepository,
    PaymentRepository,
    SubscriptionRepository,
    WaterLogRepository,
    create_db_engine,
    get_db,
    init_db,
)
from app.main import create_app


def _create_user(
    client: TestClient,
    user_id: str,
    *,
    full_name: str = "Aymen",
    high_risk: bool = False,
) -> None:
    resp = client.post(
        "/api/v1/profiles",
        json={
            "user_id": user_id,
            "email": f"{user_id}@example.com",
            "full_name": full_name,
            "profile": {
                "age": 28,
                "gender": "female",
                "height_cm": 165.0,
                "weight_kg": 74.0,
                "activity_level": "sedentary",
                "goal": "lose",
                "conditions": ["pcos"],
                "high_risk_conditions": ["kidney_disease"] if high_risk else [],
                "timezone": "Asia/Karachi",
            },
        },
    )
    assert resp.status_code == 201


@pytest.fixture
def admin_env() -> Iterator[dict[str, Any]]:
    """Provide an isolated SQLite session factory + TestClient with mutable settings."""
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    state: dict[str, Settings] = {
        "settings": Settings(app_env="development", admin_api_key="ops-secret")
    }

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    def override_get_admin_settings() -> Settings:
        return state["settings"]

    test_app = create_app(initialize_db=False)
    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_admin_settings] = override_get_admin_settings

    with TestClient(test_app) as client:
        yield {
            "client": client,
            "session_factory": session_factory,
            "state": state,
        }

    test_app.dependency_overrides.clear()
    engine.dispose()


def test_admin_auth_enforcement(admin_env: dict[str, Any]) -> None:
    client: TestClient = admin_env["client"]
    state: dict[str, Settings] = admin_env["state"]

    # Configured admin_api_key rejects missing/wrong key
    assert client.get("/api/v1/admin/overview").status_code == 403
    assert client.get("/api/v1/admin/overview", headers={"X-Admin-Key": "wrong"}).status_code == 403
    assert (
        client.get("/api/v1/admin/overview", headers={"X-Admin-Key": "ops-secret"}).status_code
        == 200
    )

    # Empty key outside development fails closed (403)
    state["settings"] = Settings(app_env="production", admin_api_key="")
    assert client.get("/api/v1/admin/overview").status_code == 403

    # Empty key in local development allows access (200)
    state["settings"] = Settings(app_env="development", admin_api_key="")
    assert client.get("/api/v1/admin/overview").status_code == 200


def test_admin_overview_users_and_flagged_safety_review(admin_env: dict[str, Any]) -> None:
    client: TestClient = admin_env["client"]
    session_factory = admin_env["session_factory"]
    headers = {"X-Admin-Key": "ops-secret"}

    _create_user(client, "admin-u1", full_name="Aymen", high_risk=False)
    _create_user(client, "admin-u2", full_name="Zainab", high_risk=True)

    with session_factory() as session:
        now = datetime.now(UTC)
        SubscriptionRepository.activate_paid_plan(
            session, "admin-u1", PlanId.PRO, PaymentProvider.JAZZCASH, now=now
        )
        SubscriptionRepository.start_trial_if_none(session, "admin-u2", now=now)

        tx_pkr = PaymentRepository.create_transaction(
            session,
            user_id="admin-u1",
            plan="pro",
            provider="jazzcash",
            amount=2999.0,
            currency="PKR",
            provider_order_id="fs_pkr_1",
            checkout_url="https://example.com/1",
        )
        PaymentRepository.mark_transaction_status(
            session, tx_pkr.provider_order_id, "paid", paid_at=now
        )

        tx_usd = PaymentRepository.create_transaction(
            session,
            user_id="admin-u2",
            plan="overseas",
            provider="lemonsqueezy",
            amount=9.99,
            currency="USD",
            provider_order_id="fs_usd_1",
            checkout_url="https://example.com/2",
        )
        PaymentRepository.mark_transaction_status(
            session, tx_usd.provider_order_id, "paid", paid_at=now
        )

        MessageRepository.save_message(session, "admin-u1", "user", "Assalam o alaikum")
        MessageRepository.save_message(session, "admin-u1", "assistant", "Walaikum assalam!")
        MessageRepository.save_message(
            session,
            "admin-u1",
            "user",
            "Mujhe sirf 500 kcal plan chahiye",
            flagged_safety=True,
        )
        MessageRepository.save_message(session, "admin-u1", "assistant", "Safe floor note.")

    ov = client.get("/api/v1/admin/overview", headers=headers)
    assert ov.status_code == 200
    metrics = ov.json()
    assert metrics["total_users"] == 2
    assert metrics["total_profiles"] == 2
    assert metrics["active_subscriptions"] == 2
    assert metrics["paid_subscriptions"] == 1
    assert metrics["trial_subscriptions"] == 1
    assert metrics["revenue_pkr"] == 2999.0
    assert metrics["revenue_usd"] == 9.99
    assert metrics["flagged_safety_count"] == 1
    assert metrics["total_messages"] == 4
    assert metrics["estimated_ai_cost_usd"] > 0

    users_resp = client.get("/api/v1/admin/users", headers=headers)
    assert users_resp.status_code == 200
    users = {u["user_id"]: u for u in users_resp.json()}
    assert users["admin-u1"]["subscription_plan"] == "pro"
    assert users["admin-u1"]["flagged_count"] == 1
    assert users["admin-u2"]["is_high_risk"] is True
    assert users["admin-u2"]["subscription_plan"] == "trial"

    flagged_resp = client.get("/api/v1/admin/flagged-messages", headers=headers)
    assert flagged_resp.status_code == 200
    flagged = flagged_resp.json()
    assert len(flagged) == 1
    assert flagged[0]["user_id"] == "admin-u1"
    assert "500 kcal" in flagged[0]["content"]


def test_admin_food_catalog_seed_search_upsert_and_delete(admin_env: dict[str, Any]) -> None:
    client: TestClient = admin_env["client"]
    headers = {"X-Admin-Key": "ops-secret"}

    all_foods = client.get("/api/v1/admin/foods?limit=250", headers=headers)
    assert all_foods.status_code == 200
    assert len(all_foods.json()) >= 165

    daal_foods = client.get("/api/v1/admin/foods?q=daal", headers=headers)
    assert daal_foods.status_code == 200
    assert any("daal" in item["name"].lower() for item in daal_foods.json())

    upsert_resp = client.put(
        "/api/v1/admin/foods/custom_methi_chicken",
        headers=headers,
        json={
            "name": "Custom Methi Chicken",
            "urdu_name": "میتھی چکن",
            "aliases": ["kasuri methi chicken"],
            "category": "curry",
            "serving_desc": "1 cup (180g)",
            "grams": 180.0,
            "kcal": 240.0,
            "protein": 24.0,
            "carbs": 5.0,
            "fat": 13.0,
            "fiber": 2.0,
            "sodium_mg": 410.0,
            "gi_category": "low",
            "tags": ["desi", "pcos_friendly"],
        },
    )
    assert upsert_resp.status_code == 200
    assert upsert_resp.json()["id"] == "custom_methi_chicken"

    del_ok = client.delete("/api/v1/admin/foods/custom_methi_chicken", headers=headers)
    assert del_ok.status_code == 200
    assert del_ok.json()["deleted"] is True

    del_again = client.delete("/api/v1/admin/foods/custom_methi_chicken", headers=headers)
    assert del_again.status_code == 404


def test_user_account_data_deletion_wipes_all_tables(admin_env: dict[str, Any]) -> None:
    client: TestClient = admin_env["client"]
    session_factory = admin_env["session_factory"]

    assert client.delete("/api/v1/profiles/unknown-user/data").status_code == 404

    _create_user(client, "wipe-user", full_name="Sara")

    with session_factory() as session:
        now = datetime.now(UTC)
        session.add(
            MealLogRow(
                id=str(uuid4()),
                user_id="wipe-user",
                meal_type="lunch",
                items=[{"food_name": "Daal", "kcal": 300.0}],
                total_kcal=300.0,
                protein_g=14.0,
                carbs_g=40.0,
                fat_g=8.0,
                logged_at=now - timedelta(hours=2),
            )
        )
        session.commit()
        WaterLogRepository.save_water_log(session, "wipe-user", 500)
        MessageRepository.save_message(session, "wipe-user", "user", "Hello")
        MemoryRepository.save_memory(session, "wipe-user", "preference", "Prefers brown rice")
        SubscriptionRepository.start_trial_if_none(session, "wipe-user", now=now)
        PaymentRepository.create_transaction(
            session,
            user_id="wipe-user",
            plan="pro",
            provider="safepay",
            amount=2999.0,
            currency="PKR",
            provider_order_id="fs_wipe_1",
            checkout_url="https://example.com/wipe",
        )

    del_resp = client.delete("/api/v1/profiles/wipe-user/data")
    assert del_resp.status_code == 200
    summary = del_resp.json()
    assert summary["deleted"] is True
    assert summary["records_removed"]["users"] == 1
    assert summary["records_removed"]["profiles"] == 1
    assert summary["records_removed"]["meal_logs"] == 1
    assert summary["records_removed"]["water_logs"] == 1
    assert summary["records_removed"]["messages"] == 1
    assert summary["records_removed"]["user_memories"] == 1
    assert summary["records_removed"]["subscriptions"] == 1
    assert summary["records_removed"]["payment_transactions"] == 1

    assert client.get("/api/v1/profiles/wipe-user").status_code == 404
    assert client.delete("/api/v1/profiles/wipe-user/data").status_code == 404
