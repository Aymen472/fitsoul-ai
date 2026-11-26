"""Unit and API tests for timezone/quiet-hours-aware proactive WhatsApp scheduler."""

from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.whatsapp import get_whatsapp_client, get_whatsapp_settings
from app.config import Settings
from app.db import (
    MealLogRow,
    NotificationRepository,
    ProfileRepository,
    SubscriptionRow,
    WaterLogRepository,
    WeightLogRepository,
    WorkoutRepository,
    create_db_engine,
    get_db,
    init_db,
)
from app.main import create_app
from app.models import (
    ActivityLevel,
    DietType,
    Gender,
    Goal,
    MedicalCondition,
    UserProfile,
)
from app.services import (
    WhatsAppCloudClient,
    WhatsAppTemplateName,
    evaluate_due_notifications_for_user,
    is_within_quiet_hours,
    run_proactive_scheduler,
)


@pytest.fixture
def scheduler_env() -> Iterator[dict[str, Any]]:
    """Provide an isolated in-memory SQLite session factory + TestClient."""
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    test_settings = Settings(
        whatsapp_verify_token="verify-tok",
        whatsapp_access_token="",
        whatsapp_phone_number_id="",
        pwa_base_url="https://app.fitsoul.pk",
        scheduler_secret="cron-top-secret",
    )

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    def override_get_settings() -> Settings:
        return test_settings

    def override_get_client() -> WhatsAppCloudClient:
        return WhatsAppCloudClient(
            access_token="",
            phone_number_id="",
            pwa_base_url=test_settings.pwa_base_url,
        )

    test_app = create_app(initialize_db=False)
    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_whatsapp_settings] = override_get_settings
    test_app.dependency_overrides[get_whatsapp_client] = override_get_client

    with TestClient(test_app) as client:
        yield {
            "client": client,
            "session_factory": session_factory,
            "settings": test_settings,
            "wa_client": override_get_client(),
        }

    test_app.dependency_overrides.clear()
    engine.dispose()


def _seed_opted_in_user(
    session: Session,
    user_id: str = "sched-user",
    *,
    diet_type: DietType = DietType.NON_VEG,
    workout_time: time | None = None,
    phone: str = "+92 300 1112233",
    quiet_start: str = "22:30",
    quiet_end: str = "07:00",
    conditions: list[MedicalCondition] | None = None,
) -> None:
    ProfileRepository.upsert_profile(
        session,
        user_id=user_id,
        email=f"{user_id}@example.com",
        full_name="Aymen",
        phone=phone,
        profile=UserProfile(
            age=28,
            gender=Gender.FEMALE,
            height_cm=165.0,
            weight_kg=74.0,
            activity_level=ActivityLevel.SEDENTARY,
            goal=Goal.LOSE,
            diet_type=diet_type,
            conditions=conditions if conditions is not None else [MedicalCondition.PCOS],
            timezone="Asia/Karachi",
            workout_time=workout_time,
        ),
    )
    NotificationRepository.upsert_preferences(
        session,
        user_id,
        whatsapp_opt_in=True,
        whatsapp_phone=phone,
        quiet_hours_start=quiet_start,
        quiet_hours_end=quiet_end,
    )


def _add_meal_row(
    session: Session,
    user_id: str,
    meal_type: str,
    total_kcal: float,
    logged_at: datetime,
) -> None:
    session.add(
        MealLogRow(
            id=str(uuid4()),
            user_id=user_id,
            meal_type=meal_type,
            items=[{"food_name": "Chapati & Daal", "kcal": total_kcal}],
            total_kcal=total_kcal,
            protein_g=20.0,
            carbs_g=45.0,
            fat_g=10.0,
            logged_at=logged_at,
        )
    )
    session.commit()


def test_is_within_quiet_hours_windows() -> None:
    # Overnight sleep window 22:30 -> 07:00
    assert is_within_quiet_hours(time(22, 30), "22:30", "07:00") is True
    assert is_within_quiet_hours(time(23, 55), "22:30", "07:00") is True
    assert is_within_quiet_hours(time(2, 15), "22:30", "07:00") is True
    assert is_within_quiet_hours(time(6, 59), "22:30", "07:00") is True
    assert is_within_quiet_hours(time(7, 0), "22:30", "07:00") is False
    assert is_within_quiet_hours(time(13, 0), "22:30", "07:00") is False

    # Same-day window 14:00 -> 16:00
    assert is_within_quiet_hours(time(14, 0), "14:00", "16:00") is True
    assert is_within_quiet_hours(time(15, 59), "14:00", "16:00") is True
    assert is_within_quiet_hours(time(16, 0), "14:00", "16:00") is False
    assert is_within_quiet_hours(time(13, 59), "14:00", "16:00") is False

    # Equal start/end disables quiet hours
    assert is_within_quiet_hours(time(23, 0), "00:00", "00:00") is False


def test_meal_and_water_reminders_respect_logged_state(
    scheduler_env: dict[str, Any],
) -> None:
    session_factory = scheduler_env["session_factory"]

    with session_factory() as session:
        _seed_opted_in_user(session, "veg-user", diet_type=DietType.VEG)

        # 08:15 Asia/Karachi = 03:15 UTC -> Breakfast reminder due
        breakfast_utc = datetime(2026, 11, 26, 3, 15, tzinfo=UTC)
        jobs, _, _, _ = evaluate_due_notifications_for_user(session, "veg-user", now=breakfast_utc)
        assert [j.template_name for j in jobs] == [WhatsAppTemplateName.MEAL_REMINDER]
        assert jobs[0].params["meal_slot"] == "Breakfast"
        assert "Oats" in jobs[0].params["suggested_meal"]

        # Log breakfast -> no longer due
        _add_meal_row(session, "veg-user", "breakfast", 350.0, breakfast_utc)
        jobs_after, _, _, _ = evaluate_due_notifications_for_user(
            session, "veg-user", now=breakfast_utc
        )
        assert jobs_after == []

        # 11:20 Asia/Karachi = 06:20 UTC -> Midday water due until target met
        water_utc = datetime(2026, 11, 26, 6, 20, tzinfo=UTC)
        water_jobs, _, _, _ = evaluate_due_notifications_for_user(
            session, "veg-user", now=water_utc
        )
        assert [j.template_name for j in water_jobs] == [WhatsAppTemplateName.WATER_REMINDER]

        WaterLogRepository.save_water_log(session, "veg-user", 3000, logged_at=water_utc)
        water_jobs_after, _, _, _ = evaluate_due_notifications_for_user(
            session, "veg-user", now=water_utc
        )
        assert water_jobs_after == []


def test_workout_nudge_night_summary_and_weekly_report(
    scheduler_env: dict[str, Any],
) -> None:
    session_factory = scheduler_env["session_factory"]

    with session_factory() as session:
        _seed_opted_in_user(session, "combo-user", workout_time=time(17, 30))

        # 17:45 Asia/Karachi = 12:45 UTC -> Custom workout nudge due
        wk_utc = datetime(2026, 11, 26, 12, 45, tzinfo=UTC)
        wk_jobs, _, _, _ = evaluate_due_notifications_for_user(session, "combo-user", now=wk_utc)
        assert any(j.template_name == WhatsAppTemplateName.WORKOUT_NUDGE for j in wk_jobs)

        # Log workout -> skipped
        WorkoutRepository.save_workout(
            session,
            "combo-user",
            "PCOS Low-Impact Walk & Tone",
            "fitness",
            15,
            75.0,
            completed_at=wk_utc,
        )
        wk_jobs_after, _, _, _ = evaluate_due_notifications_for_user(
            session, "combo-user", now=wk_utc
        )
        assert all(j.template_name != WhatsAppTemplateName.WORKOUT_NUDGE for j in wk_jobs_after)

        # 21:15 Asia/Karachi = 16:15 UTC -> Night summary with today's calories + streak
        _add_meal_row(
            session, "combo-user", "lunch", 520.0, datetime(2026, 11, 26, 8, 0, tzinfo=UTC)
        )
        night_utc = datetime(2026, 11, 26, 16, 15, tzinfo=UTC)
        night_jobs, _, _, _ = evaluate_due_notifications_for_user(
            session, "combo-user", now=night_utc
        )
        assert [j.template_name for j in night_jobs] == [WhatsAppTemplateName.NIGHT_SUMMARY]
        assert night_jobs[0].params["consumed_kcal"] == "520"
        assert night_jobs[0].params["streak_days"] == "1"

        # Seed weight drop + Sunday 10:15 Asia/Karachi (2026-11-29 05:15 UTC) -> Weekly report
        WeightLogRepository.save_weight_log(
            session, "combo-user", 74.5, logged_at=datetime(2026, 11, 24, 9, 0, tzinfo=UTC)
        )
        WeightLogRepository.save_weight_log(
            session, "combo-user", 73.9, logged_at=datetime(2026, 11, 28, 9, 0, tzinfo=UTC)
        )
        sunday_utc = datetime(2026, 11, 29, 5, 15, tzinfo=UTC)
        sunday_jobs, _, _, _ = evaluate_due_notifications_for_user(
            session, "combo-user", now=sunday_utc
        )
        weekly = [j for j in sunday_jobs if j.template_name == WhatsAppTemplateName.WEEKLY_REPORT]
        assert len(weekly) == 1
        assert weekly[0].params["workouts_completed"] == "1"
        assert weekly[0].params["weight_delta"] == "-0.6 kg"


def test_proactive_pattern_and_subscription_renewal_nudges(
    scheduler_env: dict[str, Any],
) -> None:
    session_factory = scheduler_env["session_factory"]

    with session_factory() as session:
        _seed_opted_in_user(session, "support-user", workout_time=time(8, 30))

        # Two late-night meals (22:30 local = 17:30 UTC) trigger LATE_NIGHT_CRAVING pattern
        _add_meal_row(
            session, "support-user", "snack", 310.0, datetime(2026, 11, 24, 17, 30, tzinfo=UTC)
        )
        _add_meal_row(
            session, "support-user", "snack", 280.0, datetime(2026, 11, 25, 17, 30, tzinfo=UTC)
        )

        now_utc = datetime(2026, 11, 26, 13, 0, tzinfo=UTC)  # 18:00 Asia/Karachi
        session.add(
            SubscriptionRow(
                id="sub-1",
                user_id="support-user",
                plan="Pro Monthly",
                status="active",
                expires_at=now_utc + timedelta(days=2),
            )
        )
        session.commit()

        jobs, _, _, _ = evaluate_due_notifications_for_user(session, "support-user", now=now_utc)
        templates = {j.template_name for j in jobs}
        assert WhatsAppTemplateName.PROACTIVE_SUPPORT in templates
        assert WhatsAppTemplateName.SUBSCRIPTION_RENEWAL in templates
        renewal_job = next(
            j for j in jobs if j.template_name == WhatsAppTemplateName.SUBSCRIPTION_RENEWAL
        )
        assert renewal_job.params["days_remaining"] == "2"


def test_quiet_hours_suppression_and_slot_deduplication(
    scheduler_env: dict[str, Any],
) -> None:
    session_factory = scheduler_env["session_factory"]
    wa_client: WhatsAppCloudClient = scheduler_env["wa_client"]

    with session_factory() as session:
        _seed_opted_in_user(session, "dedup-user")

        # 23:15 Asia/Karachi = 18:15 UTC -> suppressed by quiet hours (22:30 - 07:00)
        quiet_utc = datetime(2026, 11, 26, 18, 15, tzinfo=UTC)
        quiet_run = run_proactive_scheduler(session, wa_client, now=quiet_utc)
        assert quiet_run.evaluated_users == 1
        assert quiet_run.skipped_quiet_hours == 1
        assert quiet_run.sent_count == 0

        # 13:15 Asia/Karachi = 08:15 UTC -> Lunch reminder sent once, deduplicated on second run
        lunch_utc = datetime(2026, 11, 26, 8, 15, tzinfo=UTC)
        first_run = run_proactive_scheduler(session, wa_client, now=lunch_utc)
        assert first_run.due_count == 1
        assert first_run.sent_count == 1
        assert first_run.dispatched[0].template_name == WhatsAppTemplateName.MEAL_REMINDER

        second_run = run_proactive_scheduler(session, wa_client, now=lunch_utc)
        assert second_run.due_count == 0
        assert second_run.sent_count == 0
        assert second_run.skipped_duplicate == 1


def test_scheduler_api_routes_and_secret_guard(scheduler_env: dict[str, Any]) -> None:
    client: TestClient = scheduler_env["client"]
    session_factory = scheduler_env["session_factory"]

    assert client.get("/api/v1/notifications/missing-user/schedule-preview").status_code == 404

    with session_factory() as session:
        _seed_opted_in_user(session, "api-sched-user")

    # Preview at 13:10 Asia/Karachi (08:10 UTC)
    preview_resp = client.get(
        "/api/v1/notifications/api-sched-user/schedule-preview",
        params={"at_utc": "2026-11-26T08:10:00Z"},
    )
    assert preview_resp.status_code == 200
    preview = preview_resp.json()
    assert preview["timezone"] == "Asia/Karachi"
    assert preview["in_quiet_hours"] is False
    assert preview["whatsapp_opt_in"] is True
    assert len(preview["upcoming_slots"]) == 8
    assert preview["due_jobs"][0]["template_name"] == "fitsoul_meal_reminder"

    # Missing or wrong X-Scheduler-Secret returns 403
    bad_run = client.post(
        "/api/v1/notifications/scheduler/run",
        json={"user_id": "api-sched-user", "dry_run": True, "at_utc": "2026-11-26T08:10:00Z"},
        headers={"X-Scheduler-Secret": "wrong"},
    )
    assert bad_run.status_code == 403

    ok_run = client.post(
        "/api/v1/notifications/scheduler/run",
        json={"user_id": "api-sched-user", "dry_run": True, "at_utc": "2026-11-26T08:10:00Z"},
        headers={"X-Scheduler-Secret": "cron-top-secret"},
    )
    assert ok_run.status_code == 200
    summary = ok_run.json()
    assert summary["sent_count"] == 1
    assert summary["dry_run"] is True
