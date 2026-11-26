"""SQLAlchemy 2.0 ORM tables matching the Supabase Postgres schema."""

from datetime import UTC, date, datetime, time
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(UTC)


def _new_uuid() -> str:
    """Generate a string UUID primary key."""
    return str(uuid4())


class UserRow(Base):
    """Registered FitSoul AI user account."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_uuid)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now
    )


class ProfileRow(Base):
    """Health, diet, and scheduling profile for a user."""

    __tablename__ = "profiles"

    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(16))
    height_cm: Mapped[float] = mapped_column(Float)
    weight_kg: Mapped[float] = mapped_column(Float)
    target_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    activity_level: Mapped[str] = mapped_column(String(32))
    goal: Mapped[str] = mapped_column(String(16))
    conditions: Mapped[list[str]] = mapped_column(JSON, default=list)
    high_risk_conditions: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_pregnant: Mapped[bool] = mapped_column(Boolean, default=False)
    on_regular_medication: Mapped[bool] = mapped_column(Boolean, default=False)
    diet_type: Mapped[str] = mapped_column(String(24), default="non_veg")
    allergies: Mapped[list[str]] = mapped_column(JSON, default=list)
    dislikes: Mapped[list[str]] = mapped_column(JSON, default=list)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Karachi")
    wake_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    sleep_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    workout_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    bmi: Mapped[float] = mapped_column(Float)
    is_high_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    high_risk_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    supplements_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now
    )


class NutritionTargetRow(Base):
    """Persisted deterministic daily nutrition targets for a user."""

    __tablename__ = "nutrition_targets"

    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    calories: Mapped[int] = mapped_column(Integer)
    bmr: Mapped[int] = mapped_column(Integer)
    tdee: Mapped[int] = mapped_column(Integer)
    protein_g: Mapped[int] = mapped_column(Integer)
    carbs_g: Mapped[int] = mapped_column(Integer)
    fat_g: Mapped[int] = mapped_column(Integer)
    fiber_g: Mapped[int] = mapped_column(Integer)
    water_ml: Mapped[int] = mapped_column(Integer)
    sodium_mg_max: Mapped[int] = mapped_column(Integer)
    max_carbs_per_meal_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    forbidden_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    required_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    applied_rules: Mapped[list[str]] = mapped_column(JSON, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now
    )


class FoodRow(Base):
    """Verified Pakistani and South Asian food catalog entry."""

    __tablename__ = "foods"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    urdu_name: Mapped[str] = mapped_column(String(255), default="")
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    category: Mapped[str] = mapped_column(String(64), index=True)
    serving_desc: Mapped[str] = mapped_column(String(128))
    grams: Mapped[float] = mapped_column(Float)
    kcal: Mapped[float] = mapped_column(Float)
    protein: Mapped[float] = mapped_column(Float)
    carbs: Mapped[float] = mapped_column(Float)
    fat: Mapped[float] = mapped_column(Float)
    fiber: Mapped[float] = mapped_column(Float)
    sodium_mg: Mapped[float] = mapped_column(Float)
    gi_category: Mapped[str] = mapped_column(String(16), default="medium")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)


class MealLogRow(Base):
    """Logged meal entry with food items and optional photo reference."""

    __tablename__ = "meal_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    meal_type: Mapped[str] = mapped_column(String(32))
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    total_kcal: Mapped[float] = mapped_column(Float)
    protein_g: Mapped[float] = mapped_column(Float)
    carbs_g: Mapped[float] = mapped_column(Float)
    fat_g: Mapped[float] = mapped_column(Float)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class WaterLogRow(Base):
    """Hydration log entry in milliliters."""

    __tablename__ = "water_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    amount_ml: Mapped[int] = mapped_column(Integer)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class WeightLogRow(Base):
    """Body weight check-in record."""

    __tablename__ = "weight_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    weight_kg: Mapped[float] = mapped_column(Float)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class WorkoutRow(Base):
    """Completed workout or face yoga session."""

    __tablename__ = "workouts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    routine_name: Mapped[str] = mapped_column(String(255))
    workout_type: Mapped[str] = mapped_column(String(32), default="fitness")
    duration_minutes: Mapped[int] = mapped_column(Integer)
    calories_burned: Mapped[float] = mapped_column(Float, default=0.0)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class MoodLogRow(Base):
    """Daily mood and emotional trigger log."""

    __tablename__ = "mood_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mood: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class MessageRow(Base):
    """Persistent AI coach conversation message with safety flag and embedding."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(24), default="web")
    flagged_safety: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class UserMemoryRow(Base):
    """Long-term semantic memory fact (preference, trigger, win, or lifestyle fact)."""

    __tablename__ = "user_memories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class SubscriptionRow(Base):
    """User subscription and billing status."""

    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    plan: Mapped[str] = mapped_column(String(32), default="trial")
    status: Mapped[str] = mapped_column(String(32), default="active")
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)


class NotificationPreferenceRow(Base):
    """Per-user WhatsApp opt-in, phone number, reminder toggles, and quiet hours."""

    __tablename__ = "notification_preferences"

    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    whatsapp_phone: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    meal_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    water_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    workout_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    night_summary: Mapped[bool] = mapped_column(Boolean, default=True)
    weekly_report: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_hours_start: Mapped[str] = mapped_column(String(8), default="22:30")
    quiet_hours_end: Mapped[str] = mapped_column(String(8), default="07:00")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now
    )


class NotificationLogRow(Base):
    """Outbound template notifications, webhook status updates, and inbound replies."""

    __tablename__ = "notification_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    channel: Mapped[str] = mapped_column(String(24), default="whatsapp")
    direction: Mapped[str] = mapped_column(String(16), default="outbound")
    template_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recipient_phone: Mapped[str] = mapped_column(String(32))
    provider_message_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    deep_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now
    )


class PaymentTransactionRow(Base):
    """Checkout order and webhook payment status history."""

    __tablename__ = "payment_transactions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_uuid)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    plan: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(32))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="PKR")
    status: Mapped[str] = mapped_column(String(24), default="pending")
    provider_order_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
