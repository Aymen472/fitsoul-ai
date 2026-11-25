"""Tests for the health endpoint and application settings."""

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app

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
