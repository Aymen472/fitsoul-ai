"""Tests for health/readiness endpoints and application settings."""

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db import create_db_engine, get_db, init_db
from app.main import app, create_app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "FitSoul AI"
    assert settings.app_env == "development"
    assert "http://localhost:3000" in settings.cors_origins_list
    assert get_settings().app_name == "FitSoul AI"


def test_cors_allows_local_frontend_origin() -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_health_ready_reports_db_foods_and_safe_flags() -> None:
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    def override_get_settings() -> Settings:
        return Settings(
            _env_file=None,
            app_env="production",
            gemini_api_key="super-secret-gemini-value",
            admin_api_key="super-secret-admin-value",
            payment_webhook_secret="super-secret-pay-value",
        )

    test_app = create_app(initialize_db=False)
    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_settings] = override_get_settings

    try:
        with TestClient(test_app) as test_client:
            resp = test_client.get("/health/ready")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ready"
            assert data["app_env"] == "production"
            assert data["database_ok"] is True
            assert data["food_catalog_count"] >= 165
            assert data["integrations"] == {
                "gemini_configured": True,
                "whatsapp_configured": False,
                "supabase_configured": False,
                "admin_key_configured": True,
                "payment_webhook_configured": True,
                "scheduler_secret_configured": False,
            }
            assert "super-secret" not in resp.text
    finally:
        test_app.dependency_overrides.clear()
        engine.dispose()
