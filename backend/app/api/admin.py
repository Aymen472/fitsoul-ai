"""Admin console KPIs, safety flag review, food catalog CRUD, and user data deletion."""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.nutrition import FoodItem, GICategory, get_food_db
from app.db import (
    AdminOverviewMetrics,
    AdminRepository,
    AdminUserSummary,
    FlaggedMessageRecord,
    UserDeletionSummary,
    get_db,
)

router = APIRouter(tags=["admin", "legal"])


def get_admin_settings() -> Settings:
    """FastAPI dependency returning runtime settings for admin endpoints."""
    return get_settings()


def require_admin_access(
    request: Request,
    settings: Annotated[Settings, Depends(get_admin_settings)],
) -> None:
    """Enforce X-Admin-Key when configured and fail closed outside local development."""
    configured_key = settings.admin_api_key.strip()
    if configured_key:
        provided_key = (request.headers.get("X-Admin-Key") or "").strip()
        if not hmac.compare_digest(provided_key, configured_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or missing X-Admin-Key header",
            )
        return

    if settings.app_env.strip().lower() != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin endpoints require ADMIN_API_KEY outside development",
        )


DbSession = Annotated[Session, Depends(get_db)]
AdminAccessDep = Annotated[None, Depends(require_admin_access)]


class FoodUpsertRequest(BaseModel):
    """Payload to create or update a Pakistani food item in the catalog."""

    name: str = Field(..., min_length=1, max_length=255)
    urdu_name: str = Field(default="", max_length=255)
    aliases: list[str] = Field(default_factory=list)
    category: str = Field(..., min_length=1, max_length=64)
    serving_desc: str = Field(..., min_length=1, max_length=128)
    grams: float = Field(gt=0)
    kcal: float = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fat: float = Field(ge=0)
    fiber: float = Field(ge=0)
    sodium_mg: float = Field(ge=0)
    gi_category: GICategory = GICategory.MEDIUM
    tags: list[str] = Field(default_factory=list)


class FoodDeleteResponse(BaseModel):
    """Confirmation returned after deleting a food item from the catalog."""

    deleted: bool = True
    food_id: str


@router.get("/api/v1/admin/overview", response_model=AdminOverviewMetrics)
def read_admin_overview(
    _admin: AdminAccessDep,
    db: DbSession,
) -> AdminOverviewMetrics:
    """Return platform-wide user, subscription, revenue, safety, and AI cost KPIs."""
    return AdminRepository.get_overview_metrics(db)


@router.get("/api/v1/admin/users", response_model=list[AdminUserSummary])
def read_admin_users(
    _admin: AdminAccessDep,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AdminUserSummary]:
    """List users enriched with medical risk flag, billing plan, safety flags, and AI cost."""
    return AdminRepository.list_users_with_billing(db, limit=limit)


@router.get("/api/v1/admin/flagged-messages", response_model=list[FlaggedMessageRecord])
def read_flagged_messages(
    _admin: AdminAccessDep,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[FlaggedMessageRecord]:
    """List safety-flagged coach conversations for human review."""
    return AdminRepository.list_flagged_messages(db, limit=limit)


@router.get("/api/v1/admin/foods", response_model=list[FoodItem])
def read_admin_foods(
    _admin: AdminAccessDep,
    db: DbSession,
    q: Annotated[str, Query(max_length=100)] = "",
    category: Annotated[str, Query(max_length=64)] = "",
    limit: Annotated[int, Query(ge=1, le=250)] = 100,
) -> list[FoodItem]:
    """Search and filter the SQL foods catalog, auto-seeding from CSV on first access."""
    AdminRepository.ensure_foods_seeded(db, get_food_db().all_foods())
    return AdminRepository.list_foods(db, query=q, category=category, limit=limit)


@router.put("/api/v1/admin/foods/{food_id}", response_model=FoodItem)
def upsert_admin_food(
    food_id: str,
    payload: FoodUpsertRequest,
    _admin: AdminAccessDep,
    db: DbSession,
) -> FoodItem:
    """Create or update a food catalog entry by ID."""
    cleaned_id = food_id.strip()
    if not cleaned_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="food_id cannot be blank",
        )

    item = FoodItem(
        id=cleaned_id,
        name=payload.name.strip(),
        urdu_name=payload.urdu_name.strip(),
        aliases=[a.strip() for a in payload.aliases if a.strip()],
        category=payload.category.strip().lower(),
        serving_desc=payload.serving_desc.strip(),
        grams=payload.grams,
        kcal=payload.kcal,
        protein=payload.protein,
        carbs=payload.carbs,
        fat=payload.fat,
        fiber=payload.fiber,
        sodium_mg=payload.sodium_mg,
        gi_category=payload.gi_category,
        tags=[t.strip().lower() for t in payload.tags if t.strip()],
    )
    return AdminRepository.upsert_food(db, item)


@router.delete("/api/v1/admin/foods/{food_id}", response_model=FoodDeleteResponse)
def delete_admin_food(
    food_id: str,
    _admin: AdminAccessDep,
    db: DbSession,
) -> FoodDeleteResponse:
    """Delete a food catalog item by ID."""
    cleaned_id = food_id.strip()
    if not AdminRepository.delete_food(db, cleaned_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Food item not found")
    return FoodDeleteResponse(deleted=True, food_id=cleaned_id)


@router.delete("/api/v1/profiles/{user_id}/data", response_model=UserDeletionSummary)
def delete_user_account_and_data(user_id: str, db: DbSession) -> UserDeletionSummary:
    """Permanently delete a user's profile, tracking logs, chats, memories, and billing."""
    summary = AdminRepository.delete_user_account_data(db, user_id)
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return summary
