"""Health and production readiness check endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.nutrition import get_food_db
from app.db import get_db

router = APIRouter(tags=["health"])


class ReadinessIntegrations(BaseModel):
    """Boolean-only integration configuration indicators (never exposes secrets)."""

    gemini_configured: bool
    whatsapp_configured: bool
    supabase_configured: bool
    admin_key_configured: bool
    payment_webhook_configured: bool
    scheduler_secret_configured: bool


class ReadinessResponse(BaseModel):
    """Deep readiness diagnostic checking database connectivity and food catalog load."""

    status: str
    app_env: str
    database_ok: bool
    food_catalog_count: int
    integrations: ReadinessIntegrations


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return service liveness status."""
    return {"status": "ok"}


@router.get("/health/ready", response_model=ReadinessResponse)
def readiness_check(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReadinessResponse:
    """Verify DB connectivity, Pakistani food catalog availability, and integration flags."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database readiness check failed",
        ) from exc

    food_count = get_food_db().count
    return ReadinessResponse(
        status="ready",
        app_env=settings.app_env,
        database_ok=True,
        food_catalog_count=food_count,
        integrations=ReadinessIntegrations(
            gemini_configured=bool(settings.gemini_api_key.strip()),
            whatsapp_configured=bool(
                settings.whatsapp_access_token.strip() and settings.whatsapp_phone_number_id.strip()
            ),
            supabase_configured=bool(
                settings.supabase_url.strip() and settings.supabase_anon_key.strip()
            ),
            admin_key_configured=bool(settings.admin_api_key.strip()),
            payment_webhook_configured=bool(settings.payment_webhook_secret.strip()),
            scheduler_secret_configured=bool(settings.scheduler_secret.strip()),
        ),
    )
