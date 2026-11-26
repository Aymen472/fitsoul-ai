"""Unit and integration tests for food search, daily tracking, and dashboard endpoints."""

from collections.abc import Iterator
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.tracking import compute_logging_streak_days
from app.db import create_db_engine, get_db, init_db
from app.main import create_app


@pytest.fixture
def tracking_client() -> Iterator[TestClient]:
    """Provide an isolated in-memory SQLite TestClient for tracking endpoints."""
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    test_app = create_app(initialize_db=False)
    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app) as client:
        yield client

    test_app.dependency_overrides.clear()
    engine.dispose()


def _seed_profile(client: TestClient, user_id: str = "track-aymen") -> dict:
    resp = client.post(
        "/api/v1/profiles",
        json={
            "user_id": user_id,
            "email": f"{user_id}@example.com",
            "full_name": "Aymen",
            "profile": {
                "age": 28,
                "gender": "female",
                "height_cm": 165.0,
                "weight_kg": 75.0,
                "target_weight_kg": 66.0,
                "activity_level": "sedentary",
                "goal": "lose",
                "conditions": ["pcos"],
                "timezone": "Asia/Karachi",
            },
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_food_search_returns_staples_and_matches_pakistani_dishes(
    tracking_client: TestClient,
) -> None:
    staples_resp = tracking_client.get("/api/v1/foods/search?limit=8")
    assert staples_resp.status_code == 200
    staples = staples_resp.json()
    assert len(staples) == 8
    assert staples[0]["id"] == "roti_whole_wheat"

    search_resp = tracking_client.get("/api/v1/foods/search?q=daal%20moong&limit=5")
    assert search_resp.status_code == 200
    matches = search_resp.json()
    assert len(matches) >= 1
    assert matches[0]["id"] == "daal_moong"


def test_quick_meal_log_uses_deterministic_food_db_math_and_rejects_unknown_food(
    tracking_client: TestClient,
) -> None:
    _seed_profile(tracking_client, "meal-log-user")

    log_resp = tracking_client.post(
        "/api/v1/tracking/meal-log-user/meals",
        json={
            "meal_type": "lunch",
            "items": [
                {"food_id": "roti_whole_wheat", "servings": 2.0},
                {"food_id": "daal_moong", "servings": 1.0},
            ],
            "plate_notes": "Ghar ki daal roti",
        },
    )
    assert log_resp.status_code == 201
    logged = log_resp.json()
    assert logged["meal_type"] == "lunch"
    assert logged["total_kcal"] == 435.0
    assert len(logged["items"]) == 2

    bad_resp = tracking_client.post(
        "/api/v1/tracking/meal-log-user/meals",
        json={
            "meal_type": "dinner",
            "items": [{"food_id": "nonexistent_dish_xyz", "servings": 1.0}],
        },
    )
    assert bad_resp.status_code == 400


def test_water_weight_mood_logging_and_dashboard_aggregation(
    tracking_client: TestClient,
) -> None:
    profile = _seed_profile(tracking_client, "dash-user")
    target_kcal = profile["targets"]["calories"]

    assert (
        tracking_client.post(
            "/api/v1/tracking/dash-user/meals",
            json={
                "meal_type": "breakfast",
                "items": [{"food_id": "boiled_egg", "servings": 2.0}],
            },
        ).status_code
        == 201
    )
    assert (
        tracking_client.post(
            "/api/v1/tracking/dash-user/water",
            json={"amount_ml": 250},
        ).status_code
        == 201
    )
    assert (
        tracking_client.post(
            "/api/v1/tracking/dash-user/water",
            json={"amount_ml": 500},
        ).status_code
        == 201
    )
    assert (
        tracking_client.post(
            "/api/v1/tracking/dash-user/weight",
            json={"weight_kg": 74.2},
        ).status_code
        == 201
    )
    assert (
        tracking_client.post(
            "/api/v1/tracking/dash-user/mood",
            json={"mood": "happy", "note": "Completed morning walk"},
        ).status_code
        == 201
    )

    dash_resp = tracking_client.get("/api/v1/tracking/dash-user/dashboard")
    assert dash_resp.status_code == 200
    dash = dash_resp.json()

    assert dash["user_id"] == "dash-user"
    assert dash["consumed_kcal"] == 156.0
    assert dash["remaining_kcal"] == round(target_kcal - 156.0, 1)
    assert dash["consumed_protein_g"] == 12.6
    assert dash["water_ml"] == 750
    assert dash["water_target_ml"] == profile["targets"]["water_ml"]
    assert dash["latest_weight_kg"] == 74.2
    assert dash["target_weight_kg"] == 66.0
    assert len(dash["weight_history"]) == 1
    assert len(dash["today_meals"]) == 1
    assert len(dash["recent_moods"]) == 1
    assert dash["streak_days"] >= 1
    assert any(p["pattern_type"] == "micro_win" for p in dash["patterns"]["patterns"])


def test_compute_logging_streak_days_handles_consecutive_and_yesterday_grace() -> None:
    tz = ZoneInfo("Asia/Karachi")
    today = date(2026, 11, 25)

    three_day_timestamps = [
        datetime(2026, 11, 23, 8, 0, tzinfo=UTC),
        datetime(2026, 11, 24, 9, 0, tzinfo=UTC),
        datetime(2026, 11, 25, 10, 0, tzinfo=UTC),
    ]
    assert compute_logging_streak_days(three_day_timestamps, today_local=today, tz=tz) == 3

    yesterday_grace = [
        datetime(2026, 11, 23, 8, 0, tzinfo=UTC),
        datetime(2026, 11, 24, 9, 0, tzinfo=UTC),
    ]
    assert compute_logging_streak_days(yesterday_grace, today_local=today, tz=tz) == 2

    broken_streak = [datetime(2026, 11, 22, 9, 0, tzinfo=UTC)]
    assert compute_logging_streak_days(broken_streak, today_local=today, tz=tz) == 0


def test_tracking_endpoints_return_404_for_unknown_user(tracking_client: TestClient) -> None:
    assert tracking_client.get("/api/v1/tracking/missing/dashboard").status_code == 404
    assert (
        tracking_client.post(
            "/api/v1/tracking/missing/meals",
            json={"meal_type": "lunch", "items": [{"food_id": "boiled_egg", "servings": 1}]},
        ).status_code
        == 404
    )
    assert (
        tracking_client.post("/api/v1/tracking/missing/water", json={"amount_ml": 250}).status_code
        == 404
    )
    assert (
        tracking_client.post(
            "/api/v1/tracking/missing/weight", json={"weight_kg": 70.0}
        ).status_code
        == 404
    )
    assert (
        tracking_client.post("/api/v1/tracking/missing/mood", json={"mood": "happy"}).status_code
        == 404
    )
