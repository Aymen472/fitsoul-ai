"""Repository layer for profiles, meal logs, messages, memories, mood logs, and foods."""

from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.nutrition import FoodItem
from app.core.rules import NutritionTargets, get_nutrition_targets
from app.db.tables import (
    FoodRow,
    MealLogRow,
    MessageRow,
    MoodLogRow,
    NutritionTargetRow,
    ProfileRow,
    UserMemoryRow,
    UserRow,
)
from app.models import (
    ActivityLevel,
    DietType,
    Gender,
    Goal,
    HighRiskCondition,
    MedicalCondition,
    UserProfile,
)

if TYPE_CHECKING:
    from app.ai.photo_scanner import PhotoScanSummary


def _ensure_utc(dt: datetime) -> datetime:
    """Normalize naive or tz-aware datetimes to UTC."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


class ProfileRecord(BaseModel):
    """Persisted user profile combined with computed nutrition targets."""

    user_id: str
    email: str | None = None
    full_name: str | None = None
    phone: str | None = None
    profile: UserProfile
    targets: NutritionTargets


class ProfileRepository:
    """Data-access operations for user profiles, targets, and food catalog seeding."""

    @staticmethod
    def upsert_profile(
        session: Session,
        user_id: str,
        profile: UserProfile,
        email: str | None = None,
        full_name: str | None = None,
        phone: str | None = None,
        today: date | None = None,
    ) -> ProfileRecord:
        """Create or update a user, their health profile, and computed nutrition targets."""
        user_row = session.get(UserRow, user_id)
        if user_row is None:
            user_row = UserRow(
                id=user_id,
                email=email,
                full_name=full_name,
                phone=phone,
            )
            session.add(user_row)
            session.flush()
        else:
            if email is not None:
                user_row.email = email
            if full_name is not None:
                user_row.full_name = full_name
            if phone is not None:
                user_row.phone = phone

        targets = get_nutrition_targets(profile, today=today)

        profile_row = ProfileRow(
            user_id=user_id,
            age=profile.age,
            gender=profile.gender.value,
            height_cm=profile.height_cm,
            weight_kg=profile.weight_kg,
            target_weight_kg=profile.target_weight_kg,
            target_date=profile.target_date,
            activity_level=profile.activity_level.value,
            goal=profile.goal.value,
            conditions=[c.value for c in profile.conditions],
            high_risk_conditions=[c.value for c in profile.high_risk_conditions],
            is_pregnant=profile.is_pregnant,
            on_regular_medication=profile.on_regular_medication,
            diet_type=profile.diet_type.value,
            allergies=list(profile.allergies),
            dislikes=list(profile.dislikes),
            timezone=profile.timezone,
            wake_time=profile.wake_time,
            sleep_time=profile.sleep_time,
            workout_time=profile.workout_time,
            bmi=profile.bmi,
            is_high_risk=profile.is_high_risk,
            high_risk_reasons=list(profile.high_risk_reasons),
            supplements_allowed=profile.supplements_allowed,
        )
        session.merge(profile_row)

        target_row = NutritionTargetRow(
            user_id=user_id,
            calories=targets.calories,
            bmr=targets.bmr,
            tdee=targets.tdee,
            protein_g=targets.protein_g,
            carbs_g=targets.carbs_g,
            fat_g=targets.fat_g,
            fiber_g=targets.fiber_g,
            water_ml=targets.water_ml,
            sodium_mg_max=targets.sodium_mg_max,
            max_carbs_per_meal_g=targets.max_carbs_per_meal_g,
            forbidden_tags=list(targets.forbidden_tags),
            required_tags=list(targets.required_tags),
            applied_rules=list(targets.applied_rules),
            warnings=list(targets.warnings),
        )
        session.merge(target_row)
        session.commit()

        return ProfileRecord(
            user_id=user_id,
            email=user_row.email,
            full_name=user_row.full_name,
            phone=user_row.phone,
            profile=profile,
            targets=targets,
        )

    @staticmethod
    def get_profile(session: Session, user_id: str) -> ProfileRecord | None:
        """Fetch a saved user profile and its computed nutrition targets."""
        user_row = session.get(UserRow, user_id)
        profile_row = session.get(ProfileRow, user_id)
        target_row = session.get(NutritionTargetRow, user_id)
        if user_row is None or profile_row is None or target_row is None:
            return None

        # Use model_construct so historical profiles whose target_date has passed remain readable.
        profile = UserProfile.model_construct(
            age=profile_row.age,
            gender=Gender(profile_row.gender),
            height_cm=profile_row.height_cm,
            weight_kg=profile_row.weight_kg,
            target_weight_kg=profile_row.target_weight_kg,
            target_date=profile_row.target_date,
            activity_level=ActivityLevel(profile_row.activity_level),
            goal=Goal(profile_row.goal),
            conditions=[MedicalCondition(c) for c in profile_row.conditions],
            high_risk_conditions=[HighRiskCondition(c) for c in profile_row.high_risk_conditions],
            is_pregnant=profile_row.is_pregnant,
            on_regular_medication=profile_row.on_regular_medication,
            diet_type=DietType(profile_row.diet_type),
            allergies=list(profile_row.allergies),
            dislikes=list(profile_row.dislikes),
            timezone=profile_row.timezone,
            wake_time=profile_row.wake_time,
            sleep_time=profile_row.sleep_time,
            workout_time=profile_row.workout_time,
        )
        targets = NutritionTargets.model_validate(target_row, from_attributes=True)

        return ProfileRecord(
            user_id=user_id,
            email=user_row.email,
            full_name=user_row.full_name,
            phone=user_row.phone,
            profile=profile,
            targets=targets,
        )

    @staticmethod
    def seed_foods(session: Session, foods: list[FoodItem]) -> int:
        """Idempotently upsert food catalog items into the foods table."""
        for food in foods:
            session.merge(
                FoodRow(
                    id=food.id,
                    name=food.name,
                    urdu_name=food.urdu_name,
                    aliases=list(food.aliases),
                    category=food.category,
                    serving_desc=food.serving_desc,
                    grams=food.grams,
                    kcal=food.kcal,
                    protein=food.protein,
                    carbs=food.carbs,
                    fat=food.fat,
                    fiber=food.fiber,
                    sodium_mg=food.sodium_mg,
                    gi_category=food.gi_category.value,
                    tags=list(food.tags),
                )
            )
        session.commit()
        return len(foods)


class MealLogRecord(BaseModel):
    """Persisted meal log entry with serialized food items and totals."""

    id: str
    user_id: str
    meal_type: str
    items: list[dict[str, Any]]
    total_kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    photo_url: str | None = None
    logged_at: datetime


class DailyMealSummary(BaseModel):
    """Aggregated meal logs and nutrition totals for a single UTC date."""

    date: date
    logs: list[MealLogRecord]
    total_kcal: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float


def _to_meal_log_record(row: MealLogRow) -> MealLogRecord:
    return MealLogRecord(
        id=row.id,
        user_id=row.user_id,
        meal_type=row.meal_type,
        items=row.items,
        total_kcal=row.total_kcal,
        protein_g=row.protein_g,
        carbs_g=row.carbs_g,
        fat_g=row.fat_g,
        photo_url=row.photo_url,
        logged_at=_ensure_utc(row.logged_at),
    )


class MealLogRepository:
    """Data-access operations for logging scanned/confirmed meals and daily summaries."""

    @staticmethod
    def save_meal_log(
        session: Session,
        user_id: str,
        meal_type: str,
        summary: "PhotoScanSummary",
        *,
        photo_url: str | None = None,
        logged_at: datetime | None = None,
    ) -> MealLogRecord:
        """Persist a confirmed or scanned meal summary to the meal_logs table."""
        timestamp = _ensure_utc(logged_at) if logged_at is not None else datetime.now(UTC)
        serialized_items = [item.model_dump(mode="json") for item in summary.items]
        row = MealLogRow(
            id=str(uuid4()),
            user_id=user_id,
            meal_type=meal_type,
            items=serialized_items,
            total_kcal=summary.total_kcal,
            protein_g=summary.total_protein_g,
            carbs_g=summary.total_carbs_g,
            fat_g=summary.total_fat_g,
            photo_url=photo_url,
            logged_at=timestamp,
        )
        session.add(row)
        session.commit()
        session.refresh(row)

        return _to_meal_log_record(row)

    @staticmethod
    def get_daily_meal_logs(
        session: Session,
        user_id: str,
        target_date: date,
    ) -> DailyMealSummary:
        """Fetch all meal logs for a user on a given UTC date and compute daily totals."""
        day_start = datetime.combine(target_date, time.min, tzinfo=UTC)
        day_end = day_start + timedelta(days=1)

        stmt = (
            select(MealLogRow)
            .where(
                MealLogRow.user_id == user_id,
                MealLogRow.logged_at >= day_start,
                MealLogRow.logged_at < day_end,
            )
            .order_by(MealLogRow.logged_at.asc())
        )
        rows = session.scalars(stmt).all()
        logs = [_to_meal_log_record(row) for row in rows]

        return DailyMealSummary(
            date=target_date,
            logs=logs,
            total_kcal=round(sum(log.total_kcal for log in logs), 1),
            total_protein_g=round(sum(log.protein_g for log in logs), 1),
            total_carbs_g=round(sum(log.carbs_g for log in logs), 1),
            total_fat_g=round(sum(log.fat_g for log in logs), 1),
        )

    @staticmethod
    def get_recent_meal_logs(
        session: Session,
        user_id: str,
        *,
        days: int = 14,
        now: datetime | None = None,
    ) -> list[MealLogRecord]:
        """Fetch meal logs from the last N days ordered chronologically."""
        reference = _ensure_utc(now) if now is not None else datetime.now(UTC)
        cutoff = reference - timedelta(days=days)

        stmt = (
            select(MealLogRow)
            .where(MealLogRow.user_id == user_id)
            .order_by(MealLogRow.logged_at.asc(), MealLogRow.id.asc())
        )
        rows = session.scalars(stmt).all()
        return [_to_meal_log_record(row) for row in rows if _ensure_utc(row.logged_at) >= cutoff]


class MessageRecord(BaseModel):
    """Persisted AI coach conversation message."""

    id: str
    user_id: str
    role: str
    content: str
    channel: str = "web"
    flagged_safety: bool = False
    embedding: list[float] | None = None
    created_at: datetime


def _to_message_record(row: MessageRow) -> MessageRecord:
    return MessageRecord(
        id=row.id,
        user_id=row.user_id,
        role=row.role,
        content=row.content,
        channel=row.channel,
        flagged_safety=row.flagged_safety,
        embedding=list(row.embedding) if row.embedding is not None else None,
        created_at=_ensure_utc(row.created_at),
    )


class MessageRepository:
    """Data-access operations for persistent conversation history."""

    @staticmethod
    def save_message(
        session: Session,
        user_id: str,
        role: str,
        content: str,
        *,
        channel: str = "web",
        flagged_safety: bool = False,
        embedding: list[float] | None = None,
        created_at: datetime | None = None,
    ) -> MessageRecord:
        """Persist a single chat turn to the messages table."""
        timestamp = _ensure_utc(created_at) if created_at is not None else datetime.now(UTC)
        row = MessageRow(
            id=str(uuid4()),
            user_id=user_id,
            role=role,
            content=content,
            channel=channel,
            flagged_safety=flagged_safety,
            embedding=list(embedding) if embedding is not None else None,
            created_at=timestamp,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_message_record(row)

    @staticmethod
    def get_recent_messages(
        session: Session,
        user_id: str,
        *,
        limit: int = 20,
    ) -> list[MessageRecord]:
        """Fetch up to `limit` latest messages returned in chronological order."""
        stmt = (
            select(MessageRow)
            .where(MessageRow.user_id == user_id)
            .order_by(MessageRow.created_at.desc(), MessageRow.id.desc())
            .limit(limit)
        )
        rows = list(session.scalars(stmt).all())
        rows.reverse()
        return [_to_message_record(row) for row in rows]

    @staticmethod
    def get_messages_since(
        session: Session,
        user_id: str,
        *,
        days: int = 14,
        now: datetime | None = None,
    ) -> list[MessageRecord]:
        """Fetch messages within the last N days ordered chronologically."""
        reference = _ensure_utc(now) if now is not None else datetime.now(UTC)
        cutoff = reference - timedelta(days=days)

        stmt = (
            select(MessageRow)
            .where(MessageRow.user_id == user_id)
            .order_by(MessageRow.created_at.asc(), MessageRow.id.asc())
        )
        rows = session.scalars(stmt).all()
        return [_to_message_record(row) for row in rows if _ensure_utc(row.created_at) >= cutoff]


class UserMemoryRecord(BaseModel):
    """Persisted long-term semantic memory fact for a user."""

    id: str
    user_id: str
    category: str
    content: str
    embedding: list[float] | None = None
    created_at: datetime


def _to_memory_record(row: UserMemoryRow) -> UserMemoryRecord:
    return UserMemoryRecord(
        id=row.id,
        user_id=row.user_id,
        category=row.category,
        content=row.content,
        embedding=list(row.embedding) if row.embedding is not None else None,
        created_at=_ensure_utc(row.created_at),
    )


class MemoryRepository:
    """Data-access operations for extracted long-term user memories."""

    @staticmethod
    def save_memory(
        session: Session,
        user_id: str,
        category: str,
        content: str,
        *,
        embedding: list[float] | None = None,
        created_at: datetime | None = None,
    ) -> UserMemoryRecord:
        """Persist a memory fact, deduplicating case-insensitively within user + category."""
        cleaned = content.strip()
        if not cleaned:
            raise ValueError("Memory content cannot be empty")

        existing_stmt = select(UserMemoryRow).where(UserMemoryRow.user_id == user_id)
        for existing in session.scalars(existing_stmt).all():
            if (
                existing.category == category
                and existing.content.strip().lower() == cleaned.lower()
            ):
                return _to_memory_record(existing)

        timestamp = _ensure_utc(created_at) if created_at is not None else datetime.now(UTC)
        row = UserMemoryRow(
            id=str(uuid4()),
            user_id=user_id,
            category=category,
            content=cleaned,
            embedding=list(embedding) if embedding is not None else None,
            created_at=timestamp,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_memory_record(row)

    @staticmethod
    def list_memories(session: Session, user_id: str) -> list[UserMemoryRecord]:
        """List all persisted long-term memories for a user (newest first)."""
        stmt = (
            select(UserMemoryRow)
            .where(UserMemoryRow.user_id == user_id)
            .order_by(UserMemoryRow.created_at.desc(), UserMemoryRow.id.desc())
        )
        return [_to_memory_record(row) for row in session.scalars(stmt).all()]


class MoodLogRecord(BaseModel):
    """Persisted daily mood and emotional trigger log entry."""

    id: str
    user_id: str
    mood: str
    note: str | None = None
    logged_at: datetime


def _to_mood_log_record(row: MoodLogRow) -> MoodLogRecord:
    return MoodLogRecord(
        id=row.id,
        user_id=row.user_id,
        mood=row.mood,
        note=row.note,
        logged_at=_ensure_utc(row.logged_at),
    )


class MoodLogRepository:
    """Data-access operations for mood check-ins and emotional trigger logs."""

    @staticmethod
    def save_mood_log(
        session: Session,
        user_id: str,
        mood: str,
        *,
        note: str | None = None,
        logged_at: datetime | None = None,
    ) -> MoodLogRecord:
        """Persist a mood log entry to the mood_logs table."""
        timestamp = _ensure_utc(logged_at) if logged_at is not None else datetime.now(UTC)
        row = MoodLogRow(
            id=str(uuid4()),
            user_id=user_id,
            mood=mood.strip(),
            note=note.strip() if note else None,
            logged_at=timestamp,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_mood_log_record(row)

    @staticmethod
    def get_recent_mood_logs(
        session: Session,
        user_id: str,
        *,
        days: int = 14,
        now: datetime | None = None,
    ) -> list[MoodLogRecord]:
        """Fetch mood logs within the last N days ordered chronologically."""
        reference = _ensure_utc(now) if now is not None else datetime.now(UTC)
        cutoff = reference - timedelta(days=days)

        stmt = (
            select(MoodLogRow)
            .where(MoodLogRow.user_id == user_id)
            .order_by(MoodLogRow.logged_at.asc(), MoodLogRow.id.asc())
        )
        rows = session.scalars(stmt).all()
        return [_to_mood_log_record(row) for row in rows if _ensure_utc(row.logged_at) >= cutoff]
