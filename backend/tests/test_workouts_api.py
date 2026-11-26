"""Unit and integration tests for workout/face-yoga library, MET math, and workout APIs."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.workouts import calculate_calories_burned_met
from app.db import create_db_engine, get_db, init_db
from app.main import create_app


@pytest.fixture
def workout_client() -> Iterator[TestClient]:
    """Provide an isolated in-memory SQLite TestClient for workout endpoints."""
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


def _create_user_profile(client: TestClient, user_id: str = "workout-aymen") -> None:
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
                "activity_level": "sedentary",
                "goal": "lose",
                "conditions": ["pcos"],
                "timezone": "Asia/Karachi",
            },
        },
    )
    assert resp.status_code == 201


def test_calculate_calories_burned_met_formula_and_validation() -> None:
    assert calculate_calories_burned_met(4.0, 75.0, 15) == 75.0
    assert calculate_calories_burned_met(1.8, 70.0, 8) == 16.8

    with pytest.raises(ValueError):
        calculate_calories_burned_met(0.0, 75.0, 15)
    with pytest.raises(ValueError):
        calculate_calories_burned_met(4.0, -75.0, 15)
    with pytest.raises(ValueError):
        calculate_calories_burned_met(4.0, 75.0, 0)


def test_list_routines_filters_by_category_and_contraindications(
    workout_client: TestClient,
) -> None:
    all_resp = workout_client.get("/api/v1/workouts/routines")
    assert all_resp.status_code == 200
    all_routines = all_resp.json()
    assert len(all_routines) == 6

    face_resp = workout_client.get("/api/v1/workouts/routines?workout_type=face_yoga")
    assert face_resp.status_code == 200
    face_routines = face_resp.json()
    assert len(face_routines) == 3
    assert all(r["workout_type"] == "face_yoga" for r in face_routines)

    knee_safe = workout_client.get("/api/v1/workouts/routines?avoid=knee").json()
    assert all("knee" not in r["contraindications"] for r in knee_safe)
    assert all(r["id"] != "fat_burn_home_circuit" for r in knee_safe)

    neck_safe = workout_client.get(
        "/api/v1/workouts/routines?workout_type=face_yoga&avoid=neck"
    ).json()
    assert [r["id"] for r in neck_safe] == ["face_yoga_cheek_depuff"]


def test_log_completed_workout_uses_met_and_updates_dashboard_streak(
    workout_client: TestClient,
) -> None:
    _create_user_profile(workout_client, "fit-user")

    log_resp = workout_client.post(
        "/api/v1/tracking/fit-user/workouts",
        json={"routine_id": "pcos_low_impact_cardio", "duration_minutes": 15},
    )
    assert log_resp.status_code == 201
    logged = log_resp.json()
    assert logged["routine_name"] == "PCOS Hormone-Balance Walk & Tone"
    assert logged["workout_type"] == "fitness"
    assert logged["duration_minutes"] == 15
    assert logged["calories_burned"] == 75.0

    # Custom face yoga log updates using latest weight (75 kg * 1.6 MET * 10/60 = 20.0 kcal)
    custom_resp = workout_client.post(
        "/api/v1/tracking/fit-user/workouts",
        json={
            "routine_name": "Evening De-Stress Face Flow",
            "workout_type": "face_yoga",
            "duration_minutes": 10,
        },
    )
    assert custom_resp.status_code == 201
    assert custom_resp.json()["calories_burned"] == 20.0

    history_resp = workout_client.get("/api/v1/tracking/fit-user/workouts")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) == 2

    dash_resp = workout_client.get("/api/v1/tracking/fit-user/dashboard")
    assert dash_resp.status_code == 200
    assert dash_resp.json()["streak_days"] >= 1


def test_workout_endpoints_handle_errors_cleanly(workout_client: TestClient) -> None:
    _create_user_profile(workout_client, "err-user")

    assert workout_client.get("/api/v1/tracking/missing/workouts").status_code == 404
    assert (
        workout_client.post(
            "/api/v1/tracking/missing/workouts",
            json={"routine_id": "pcos_low_impact_cardio", "duration_minutes": 15},
        ).status_code
        == 404
    )
    assert (
        workout_client.post(
            "/api/v1/tracking/err-user/workouts",
            json={"routine_id": "unknown_routine", "duration_minutes": 15},
        ).status_code
        == 404
    )
    assert (
        workout_client.post(
            "/api/v1/tracking/err-user/workouts",
            json={"duration_minutes": 15},
        ).status_code
        == 400
    )
