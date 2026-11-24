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
    assert get_settings().app_name == "FitSoul AI"
