"""Unit and integration tests for DB setup, Supabase migration, Profile API, and food seeder."""

from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.nutrition import get_food_db
from app.db import (
    Base,
    FoodRow,
    ProfileRepository,
    create_db_engine,
    get_db,
    init_db,
    normalize_database_url,
)
from app.main import create_app
from app.models import ActivityLevel, Gender, Goal, MedicalCondition, UserProfile

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "0001_initial_schema.sql"
)

ROADMAP_TABLES = {
    "users",
    "profiles",
    "nutrition_targets",
    "foods",
    "meal_logs",
    "water_logs",
    "weight_logs",
    "workouts",
    "mood_logs",
    "messages",
    "subscriptions",
}


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Provide a clean, isolated in-memory SQLite session per test."""
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    with session_factory() as session:
        yield session
    engine.dispose()


@pytest.fixture
def api_client() -> Iterator[TestClient]:
    """Provide a TestClient backed by an isolated in-memory SQLite database."""
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


@pytest.mark.parametrize(
    ("raw_url", "expected_url"),
    [
        ("postgres://user:pass@host:5432/db", "postgresql+psycopg://user:pass@host:5432/db"),
        ("postgresql://user:pass@host:5432/db", "postgresql+psycopg://user:pass@host:5432/db"),
        (
            "postgresql+psycopg://user:pass@host:5432/db",
            "postgresql+psycopg://user:pass@host:5432/db",
        ),
        ("sqlite:///./fitsoul_dev.db", "sqlite:///./fitsoul_dev.db"),
    ],
)
def test_normalize_database_url(raw_url: str, expected_url: str) -> None:
    assert normalize_database_url(raw_url) == expected_url


def test_orm_and_sql_migration_contain_all_roadmap_tables_with_rls() -> None:
    assert ROADMAP_TABLES.issubset(set(Base.metadata.tables.keys()))

    sql_text = MIGRATION_PATH.read_text(encoding="utf-8").lower()
    assert 'create extension if not exists "vector"' in sql_text
    for table in ROADMAP_TABLES:
        assert f"create table if not exists public.{table}" in sql_text
        assert f"alter table public.{table} enable row level security" in sql_text


def test_create_and_read_pcos_profile_via_api(api_client: TestClient) -> None:
    payload = {
        "user_id": "user-aymen-1",
        "email": "aymen@example.com",
        "full_name": "Aymen",
        "profile": {
            "age": 28,
            "gender": "female",
            "height_cm": 165.0,
            "weight_kg": 75.0,
            "activity_level": "sedentary",
            "goal": "lose",
            "conditions": ["pcos"],
        },
    }

    create_resp = api_client.post("/api/v1/profiles", json=payload)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["user_id"] == "user-aymen-1"
    assert created["email"] == "aymen@example.com"
    assert created["profile"]["bmi"] == 27.5
    assert created["targets"]["calories"] == 1376
    assert created["targets"]["protein_g"] == 103
    assert created["targets"]["carbs_g"] == 103
    assert created["targets"]["fat_g"] == 61
    assert created["targets"]["water_ml"] == 2625
    assert "refined_sugar" in created["targets"]["forbidden_tags"]

    get_resp = api_client.get("/api/v1/profiles/user-aymen-1")
    assert get_resp.status_code == 200
    assert get_resp.json() == created


def test_create_profile_auto_generates_user_id_when_omitted(api_client: TestClient) -> None:
    payload = {
        "profile": {
            "age": 30,
            "gender": "male",
            "height_cm": 178.0,
            "weight_kg": 80.0,
            "activity_level": "moderate",
            "goal": "maintain",
        }
    }

    resp = api_client.post("/api/v1/profiles", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["user_id"]) >= 32

    get_resp = api_client.get(f"/api/v1/profiles/{data['user_id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["targets"]["calories"] == data["targets"]["calories"]


def test_update_profile_recomputes_targets(api_client: TestClient) -> None:
    create_payload = {
        "user_id": "user-2",
        "profile": {
            "age": 28,
            "gender": "female",
            "height_cm": 165.0,
            "weight_kg": 75.0,
            "activity_level": "sedentary",
            "goal": "lose",
        },
    }
    assert api_client.post("/api/v1/profiles", json=create_payload).status_code == 201

    update_payload = {
        "profile": {
            "age": 28,
            "gender": "female",
            "height_cm": 165.0,
            "weight_kg": 70.0,
            "activity_level": "moderate",
            "goal": "lose",
            "conditions": ["hypertension"],
        }
    }
    put_resp = api_client.put("/api/v1/profiles/user-2", json=update_payload)
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert updated["profile"]["weight_kg"] == 70.0
    assert updated["targets"]["sodium_mg_max"] == 1500
    assert updated["targets"]["calories"] > 1376


def test_missing_profile_returns_404(api_client: TestClient) -> None:
    assert api_client.get("/api/v1/profiles/unknown-id").status_code == 404

    put_resp = api_client.put(
        "/api/v1/profiles/unknown-id",
        json={
            "profile": {
                "age": 28,
                "gender": "female",
                "height_cm": 165.0,
                "weight_kg": 75.0,
                "activity_level": "sedentary",
                "goal": "lose",
            }
        },
    )
    assert put_resp.status_code == 404


@pytest.mark.parametrize(
    "bad_profile",
    [
        {
            "age": 15,
            "gender": "female",
            "height_cm": 165.0,
            "weight_kg": 60.0,
            "activity_level": "sedentary",
            "goal": "lose",
        },
        {
            "age": 28,
            "gender": "male",
            "height_cm": 175.0,
            "weight_kg": 75.0,
            "activity_level": "sedentary",
            "goal": "lose",
            "conditions": ["pcos"],
        },
    ],
)
def test_invalid_profile_payload_returns_422(
    api_client: TestClient, bad_profile: dict[str, object]
) -> None:
    resp = api_client.post("/api/v1/profiles", json={"profile": bad_profile})
    assert resp.status_code == 422


def test_historical_profile_remains_readable_when_target_date_passes(
    db_session: Session,
) -> None:
    future_target = date.today() + timedelta(days=30)
    profile = UserProfile(
        age=28,
        gender=Gender.FEMALE,
        height_cm=165.0,
        weight_kg=75.0,
        target_weight_kg=68.0,
        target_date=future_target,
        activity_level=ActivityLevel.SEDENTARY,
        goal=Goal.LOSE,
        conditions=[MedicalCondition.PCOS],
    )
    ProfileRepository.upsert_profile(db_session, user_id="hist-user", profile=profile)

    # Simulate time passing so stored target_date is in the past
    from app.db import ProfileRow

    row = db_session.get(ProfileRow, "hist-user")
    assert row is not None
    row.target_date = date.today() - timedelta(days=5)
    db_session.commit()

    loaded = ProfileRepository.get_profile(db_session, "hist-user")
    assert loaded is not None
    assert loaded.profile.target_date == date.today() - timedelta(days=5)
    assert loaded.profile.bmi == 27.5


def test_seed_foods_is_idempotent(db_session: Session) -> None:
    food_db = get_food_db()
    foods = food_db.all_foods()

    first_count = ProfileRepository.seed_foods(db_session, foods)
    second_count = ProfileRepository.seed_foods(db_session, foods)

    rows = db_session.scalars(select(FoodRow)).all()
    assert first_count == food_db.count
    assert second_count == food_db.count
    assert len(rows) == food_db.count
