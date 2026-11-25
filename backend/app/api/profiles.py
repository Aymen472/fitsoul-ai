"""Profile CRUD and deterministic nutrition target endpoints."""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import ProfileRecord, ProfileRepository, get_db
from app.models import UserProfile

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])

DbSession = Annotated[Session, Depends(get_db)]


class ProfileUpsertRequest(BaseModel):
    """Request payload for creating a user profile and computing nutrition targets."""

    user_id: str | None = None
    email: str | None = None
    full_name: str | None = None
    phone: str | None = None
    profile: UserProfile


class ProfileUpdateRequest(BaseModel):
    """Request payload for updating an existing user profile."""

    email: str | None = None
    full_name: str | None = None
    phone: str | None = None
    profile: UserProfile


@router.post("", response_model=ProfileRecord, status_code=status.HTTP_201_CREATED)
def create_or_upsert_profile(payload: ProfileUpsertRequest, db: DbSession) -> ProfileRecord:
    """Create (or update) a user profile and return persisted deterministic nutrition targets."""
    user_id = (payload.user_id or "").strip() or str(uuid4())
    return ProfileRepository.upsert_profile(
        session=db,
        user_id=user_id,
        profile=payload.profile,
        email=payload.email,
        full_name=payload.full_name,
        phone=payload.phone,
    )


@router.get("/{user_id}", response_model=ProfileRecord)
def read_profile(user_id: str, db: DbSession) -> ProfileRecord:
    """Fetch a persisted user profile and its computed nutrition targets."""
    record = ProfileRepository.get_profile(session=db, user_id=user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return record


@router.put("/{user_id}", response_model=ProfileRecord)
def update_profile(user_id: str, payload: ProfileUpdateRequest, db: DbSession) -> ProfileRecord:
    """Update an existing user profile and recompute nutrition targets."""
    existing = ProfileRepository.get_profile(session=db, user_id=user_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return ProfileRepository.upsert_profile(
        session=db,
        user_id=user_id,
        profile=payload.profile,
        email=payload.email,
        full_name=payload.full_name,
        phone=payload.phone,
    )
