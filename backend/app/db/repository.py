"""Repository layer for profiles, meal logs, messages, memories, mood logs, and foods."""

import re
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.billing import PaymentProvider, PlanId, get_plan
from app.core.nutrition import FoodItem
from app.core.rules import NutritionTargets, get_nutrition_targets
from app.db.tables import (
    FoodRow,
    MealLogRow,
    MessageRow,
    MoodLogRow,
    NotificationLogRow,
    NotificationPreferenceRow,
    NutritionTargetRow,
    PaymentTransactionRow,
    ProfileRow,
    SubscriptionRow,
    UserMemoryRow,
    UserRow,
    WaterLogRow,
    WeightLogRow,
    WorkoutRow,
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


_HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def normalize_phone_digits(phone: str) -> str:
    """Normalize an international or Pakistani phone number into digits without '+'."""
    cleaned = re.sub(r"[\s\-()]+", "", phone.strip())
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    if not cleaned or not cleaned.isdigit():
        raise ValueError("Phone number must contain digits only")
    if len(cleaned) == 11 and cleaned.startswith("03"):
        cleaned = f"92{cleaned[1:]}"
    if not (10 <= len(cleaned) <= 15):
        raise ValueError("Phone number must be between 10 and 15 digits")
    return cleaned


def _validate_hhmm(value: str) -> str:
    """Validate a 24-hour HH:MM string such as '22:30' or '07:00'."""
    cleaned = value.strip()
    if not _HHMM_RE.match(cleaned):
        raise ValueError("Time must be in 24-hour HH:MM format (e.g., '22:30')")
    return cleaned


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

    @staticmethod
    def get_profile_by_phone(session: Session, phone: str) -> ProfileRecord | None:
        """Resolve a user profile from WhatsApp preferences or account phone number."""
        try:
            normalized = normalize_phone_digits(phone)
        except ValueError:
            return None

        pref_row = session.scalar(
            select(NotificationPreferenceRow).where(
                NotificationPreferenceRow.whatsapp_phone == normalized
            )
        )
        if pref_row is not None:
            return ProfileRepository.get_profile(session, pref_row.user_id)

        users = session.scalars(select(UserRow).where(UserRow.phone.is_not(None))).all()
        for user in users:
            if not user.phone:
                continue
            try:
                if normalize_phone_digits(user.phone) == normalized:
                    return ProfileRepository.get_profile(session, user.id)
            except ValueError:
                continue
        return None


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


class WaterLogRecord(BaseModel):
    """Persisted hydration intake record in milliliters."""

    id: str
    user_id: str
    amount_ml: int
    logged_at: datetime


class DailyWaterSummary(BaseModel):
    """Aggregated hydration logs and total milliliters for a single date."""

    date: date
    logs: list[WaterLogRecord]
    total_ml: int


def _to_water_log_record(row: WaterLogRow) -> WaterLogRecord:
    return WaterLogRecord(
        id=row.id,
        user_id=row.user_id,
        amount_ml=row.amount_ml,
        logged_at=_ensure_utc(row.logged_at),
    )


class WaterLogRepository:
    """Data-access operations for user hydration logs."""

    @staticmethod
    def save_water_log(
        session: Session,
        user_id: str,
        amount_ml: int,
        *,
        logged_at: datetime | None = None,
    ) -> WaterLogRecord:
        """Persist a hydration intake entry to the water_logs table."""
        if amount_ml <= 0:
            raise ValueError("amount_ml must be positive")

        timestamp = _ensure_utc(logged_at) if logged_at is not None else datetime.now(UTC)
        row = WaterLogRow(
            id=str(uuid4()),
            user_id=user_id,
            amount_ml=amount_ml,
            logged_at=timestamp,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_water_log_record(row)

    @staticmethod
    def get_recent_water_logs(
        session: Session,
        user_id: str,
        *,
        days: int = 30,
        now: datetime | None = None,
    ) -> list[WaterLogRecord]:
        """Fetch water logs within the last N days ordered chronologically."""
        reference = _ensure_utc(now) if now is not None else datetime.now(UTC)
        cutoff = reference - timedelta(days=days)

        stmt = (
            select(WaterLogRow)
            .where(WaterLogRow.user_id == user_id)
            .order_by(WaterLogRow.logged_at.asc(), WaterLogRow.id.asc())
        )
        rows = session.scalars(stmt).all()
        return [_to_water_log_record(row) for row in rows if _ensure_utc(row.logged_at) >= cutoff]


class WeightLogRecord(BaseModel):
    """Persisted body-weight check-in record in kilograms."""

    id: str
    user_id: str
    weight_kg: float
    logged_at: datetime


def _to_weight_log_record(row: WeightLogRow) -> WeightLogRecord:
    return WeightLogRecord(
        id=row.id,
        user_id=row.user_id,
        weight_kg=row.weight_kg,
        logged_at=_ensure_utc(row.logged_at),
    )


class WeightLogRepository:
    """Data-access operations for body-weight check-ins."""

    @staticmethod
    def save_weight_log(
        session: Session,
        user_id: str,
        weight_kg: float,
        *,
        logged_at: datetime | None = None,
    ) -> WeightLogRecord:
        """Persist a body-weight check-in to the weight_logs table."""
        if not (30.0 <= weight_kg <= 250.0):
            raise ValueError("weight_kg must be between 30.0 and 250.0")

        timestamp = _ensure_utc(logged_at) if logged_at is not None else datetime.now(UTC)
        row = WeightLogRow(
            id=str(uuid4()),
            user_id=user_id,
            weight_kg=round(float(weight_kg), 1),
            logged_at=timestamp,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_weight_log_record(row)

    @staticmethod
    def get_recent_weight_logs(
        session: Session,
        user_id: str,
        *,
        days: int = 90,
        limit: int = 60,
        now: datetime | None = None,
    ) -> list[WeightLogRecord]:
        """Fetch recent weight check-ins ordered chronologically (up to `limit` latest)."""
        reference = _ensure_utc(now) if now is not None else datetime.now(UTC)
        cutoff = reference - timedelta(days=days)

        stmt = (
            select(WeightLogRow)
            .where(WeightLogRow.user_id == user_id)
            .order_by(WeightLogRow.logged_at.asc(), WeightLogRow.id.asc())
        )
        rows = session.scalars(stmt).all()
        filtered = [
            _to_weight_log_record(row) for row in rows if _ensure_utc(row.logged_at) >= cutoff
        ]
        if limit > 0 and len(filtered) > limit:
            return filtered[-limit:]
        return filtered


class WorkoutLogRecord(BaseModel):
    """Persisted completed workout or face yoga session."""

    id: str
    user_id: str
    routine_name: str
    workout_type: str
    duration_minutes: int
    calories_burned: float
    completed_at: datetime


def _to_workout_log_record(row: WorkoutRow) -> WorkoutLogRecord:
    return WorkoutLogRecord(
        id=row.id,
        user_id=row.user_id,
        routine_name=row.routine_name,
        workout_type=row.workout_type,
        duration_minutes=row.duration_minutes,
        calories_burned=row.calories_burned,
        completed_at=_ensure_utc(row.completed_at),
    )


class WorkoutRepository:
    """Data-access operations for completed fitness and face yoga sessions."""

    @staticmethod
    def save_workout(
        session: Session,
        user_id: str,
        routine_name: str,
        workout_type: str,
        duration_minutes: int,
        calories_burned: float,
        *,
        completed_at: datetime | None = None,
    ) -> WorkoutLogRecord:
        """Persist a completed workout or face yoga session."""
        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")
        if calories_burned < 0:
            raise ValueError("calories_burned cannot be negative")

        timestamp = _ensure_utc(completed_at) if completed_at is not None else datetime.now(UTC)
        row = WorkoutRow(
            id=str(uuid4()),
            user_id=user_id,
            routine_name=routine_name.strip(),
            workout_type=workout_type.strip(),
            duration_minutes=duration_minutes,
            calories_burned=round(float(calories_burned), 1),
            completed_at=timestamp,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_workout_log_record(row)

    @staticmethod
    def get_recent_workouts(
        session: Session,
        user_id: str,
        *,
        days: int = 30,
        limit: int = 30,
        now: datetime | None = None,
    ) -> list[WorkoutLogRecord]:
        """Fetch recent completed workouts ordered chronologically."""
        reference = _ensure_utc(now) if now is not None else datetime.now(UTC)
        cutoff = reference - timedelta(days=days)

        stmt = (
            select(WorkoutRow)
            .where(WorkoutRow.user_id == user_id)
            .order_by(WorkoutRow.completed_at.asc(), WorkoutRow.id.asc())
        )
        rows = session.scalars(stmt).all()
        filtered = [
            _to_workout_log_record(row) for row in rows if _ensure_utc(row.completed_at) >= cutoff
        ]
        if limit > 0 and len(filtered) > limit:
            return filtered[-limit:]
        return filtered


class NotificationPreferenceRecord(BaseModel):
    """Persisted WhatsApp notification preferences for a user."""

    user_id: str
    whatsapp_opt_in: bool
    whatsapp_phone: str | None = None
    meal_reminders: bool = True
    water_reminders: bool = True
    workout_reminders: bool = True
    night_summary: bool = True
    weekly_report: bool = True
    quiet_hours_start: str = "22:30"
    quiet_hours_end: str = "07:00"
    updated_at: datetime | None = None


class NotificationLogRecord(BaseModel):
    """Persisted outbound template notification or inbound webhook event."""

    id: str
    user_id: str | None = None
    channel: str
    direction: str
    template_name: str | None = None
    recipient_phone: str
    provider_message_id: str | None = None
    status: str
    deep_link: str | None = None
    payload: dict[str, Any]
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


def _to_notification_preference_record(
    row: NotificationPreferenceRow,
) -> NotificationPreferenceRecord:
    return NotificationPreferenceRecord(
        user_id=row.user_id,
        whatsapp_opt_in=row.whatsapp_opt_in,
        whatsapp_phone=row.whatsapp_phone,
        meal_reminders=row.meal_reminders,
        water_reminders=row.water_reminders,
        workout_reminders=row.workout_reminders,
        night_summary=row.night_summary,
        weekly_report=row.weekly_report,
        quiet_hours_start=row.quiet_hours_start,
        quiet_hours_end=row.quiet_hours_end,
        updated_at=_ensure_utc(row.updated_at),
    )


def _to_notification_log_record(row: NotificationLogRow) -> NotificationLogRecord:
    return NotificationLogRecord(
        id=row.id,
        user_id=row.user_id,
        channel=row.channel,
        direction=row.direction,
        template_name=row.template_name,
        recipient_phone=row.recipient_phone,
        provider_message_id=row.provider_message_id,
        status=row.status,
        deep_link=row.deep_link,
        payload=dict(row.payload or {}),
        error_message=row.error_message,
        created_at=_ensure_utc(row.created_at),
        updated_at=_ensure_utc(row.updated_at),
    )


class NotificationRepository:
    """Data-access operations for WhatsApp preferences, opt-in state, and delivery logs."""

    @staticmethod
    def get_preferences(session: Session, user_id: str) -> NotificationPreferenceRecord | None:
        """Fetch saved notification preferences for a user, if any exist."""
        row = session.get(NotificationPreferenceRow, user_id)
        if row is None:
            return None
        return _to_notification_preference_record(row)

    @staticmethod
    def upsert_preferences(
        session: Session,
        user_id: str,
        *,
        whatsapp_opt_in: bool,
        whatsapp_phone: str | None = None,
        meal_reminders: bool = True,
        water_reminders: bool = True,
        workout_reminders: bool = True,
        night_summary: bool = True,
        weekly_report: bool = True,
        quiet_hours_start: str = "22:30",
        quiet_hours_end: str = "07:00",
    ) -> NotificationPreferenceRecord:
        """Create or update WhatsApp opt-in settings, phone number, and quiet hours."""
        quiet_start = _validate_hhmm(quiet_hours_start)
        quiet_end = _validate_hhmm(quiet_hours_end)

        normalized_phone: str | None = None
        if whatsapp_phone is not None and whatsapp_phone.strip():
            normalized_phone = normalize_phone_digits(whatsapp_phone)

        if whatsapp_opt_in and normalized_phone is None:
            raise ValueError("whatsapp_phone is required when whatsapp_opt_in is enabled")

        user_row = session.get(UserRow, user_id)
        if user_row is not None and user_row.phone is None and normalized_phone is not None:
            conflict = session.scalar(
                select(UserRow).where(UserRow.phone == normalized_phone, UserRow.id != user_id)
            )
            if conflict is None:
                user_row.phone = normalized_phone

        now = datetime.now(UTC)
        row = session.get(NotificationPreferenceRow, user_id)
        if row is None:
            row = NotificationPreferenceRow(user_id=user_id)
        row.whatsapp_opt_in = whatsapp_opt_in
        row.whatsapp_phone = normalized_phone
        row.meal_reminders = meal_reminders
        row.water_reminders = water_reminders
        row.workout_reminders = workout_reminders
        row.night_summary = night_summary
        row.weekly_report = weekly_report
        row.quiet_hours_start = quiet_start
        row.quiet_hours_end = quiet_end
        row.updated_at = now
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_notification_preference_record(row)

    @staticmethod
    def set_opt_in_by_phone(
        session: Session,
        phone: str,
        opt_in: bool,
    ) -> NotificationPreferenceRecord | None:
        """Toggle WhatsApp opt-in state by phone number (used for STOP/START keywords)."""
        try:
            normalized = normalize_phone_digits(phone)
        except ValueError:
            return None

        now = datetime.now(UTC)
        pref_row = session.scalar(
            select(NotificationPreferenceRow).where(
                NotificationPreferenceRow.whatsapp_phone == normalized
            )
        )
        if pref_row is not None:
            pref_row.whatsapp_opt_in = opt_in
            pref_row.updated_at = now
            session.commit()
            session.refresh(pref_row)
            return _to_notification_preference_record(pref_row)

        profile = ProfileRepository.get_profile_by_phone(session, normalized)
        if profile is None:
            return None

        pref_row = session.get(NotificationPreferenceRow, profile.user_id)
        if pref_row is None:
            pref_row = NotificationPreferenceRow(
                user_id=profile.user_id,
                whatsapp_opt_in=opt_in,
                whatsapp_phone=normalized,
                updated_at=now,
            )
            session.add(pref_row)
        else:
            pref_row.whatsapp_opt_in = opt_in
            pref_row.whatsapp_phone = normalized
            pref_row.updated_at = now
        session.commit()
        session.refresh(pref_row)
        return _to_notification_preference_record(pref_row)

    @staticmethod
    def log_notification(
        session: Session,
        *,
        recipient_phone: str,
        direction: str,
        status: str,
        user_id: str | None = None,
        channel: str = "whatsapp",
        template_name: str | None = None,
        provider_message_id: str | None = None,
        deep_link: str | None = None,
        payload: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> NotificationLogRecord:
        """Persist an outbound notification attempt or inbound WhatsApp message event."""
        if direction not in {"outbound", "inbound"}:
            raise ValueError("direction must be 'outbound' or 'inbound'")

        now = datetime.now(UTC)
        row = NotificationLogRow(
            id=str(uuid4()),
            user_id=user_id,
            channel=channel.strip() or "whatsapp",
            direction=direction,
            template_name=template_name,
            recipient_phone=recipient_phone.strip(),
            provider_message_id=provider_message_id,
            status=status.strip() or "queued",
            deep_link=deep_link,
            payload=dict(payload or {}),
            error_message=error_message,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_notification_log_record(row)

    @staticmethod
    def update_delivery_status(
        session: Session,
        provider_message_id: str,
        status: str,
        *,
        error_message: str | None = None,
    ) -> NotificationLogRecord | None:
        """Update delivery status (sent/delivered/read/failed) from Meta webhook callbacks."""
        msg_id = provider_message_id.strip()
        if not msg_id:
            return None

        stmt = (
            select(NotificationLogRow)
            .where(NotificationLogRow.provider_message_id == msg_id)
            .order_by(NotificationLogRow.created_at.desc())
        )
        row = session.scalars(stmt).first()
        if row is None:
            return None

        row.status = status.strip() or row.status
        row.updated_at = datetime.now(UTC)
        if error_message is not None:
            row.error_message = error_message
        session.commit()
        session.refresh(row)
        return _to_notification_log_record(row)

    @staticmethod
    def list_user_notifications(
        session: Session,
        user_id: str,
        *,
        limit: int = 30,
    ) -> list[NotificationLogRecord]:
        """List recent notifications for a user ordered newest first."""
        stmt = (
            select(NotificationLogRow)
            .where(NotificationLogRow.user_id == user_id)
            .order_by(NotificationLogRow.created_at.desc(), NotificationLogRow.id.desc())
        )
        if limit > 0:
            stmt = stmt.limit(limit)
        rows = session.scalars(stmt).all()
        return [_to_notification_log_record(row) for row in rows]

    @staticmethod
    def list_opted_in_preferences(session: Session) -> list[NotificationPreferenceRecord]:
        """List preferences for all users who opted in to WhatsApp notifications."""
        stmt = (
            select(NotificationPreferenceRow)
            .where(
                NotificationPreferenceRow.whatsapp_opt_in.is_(True),
                NotificationPreferenceRow.whatsapp_phone.is_not(None),
            )
            .order_by(NotificationPreferenceRow.user_id.asc())
        )
        rows = session.scalars(stmt).all()
        return [_to_notification_preference_record(row) for row in rows if row.whatsapp_phone]

    @staticmethod
    def has_sent_slot(
        session: Session,
        user_id: str,
        slot_key: str,
        *,
        lookback_days: int = 8,
        now: datetime | None = None,
    ) -> bool:
        """Check whether an outbound notification for `slot_key` was already dispatched."""
        reference = _ensure_utc(now) if now is not None else datetime.now(UTC)
        cutoff = reference - timedelta(days=lookback_days)

        stmt = select(NotificationLogRow).where(
            NotificationLogRow.user_id == user_id,
            NotificationLogRow.direction == "outbound",
            NotificationLogRow.status.in_(("sent", "delivered", "read", "dry_run")),
        )
        rows = session.scalars(stmt).all()
        return any(
            _ensure_utc(row.created_at) >= cutoff
            and (row.payload or {}).get("slot_key") == slot_key
            for row in rows
        )


class SubscriptionRecord(BaseModel):
    """Persisted subscription state for a user."""

    id: str
    user_id: str
    plan: str
    status: str
    provider: str | None = None
    starts_at: datetime
    expires_at: datetime | None = None
    created_at: datetime


class PaymentTransactionRecord(BaseModel):
    """Persisted checkout order and webhook payment outcome."""

    id: str
    user_id: str
    plan: str
    provider: str
    amount: float
    currency: str
    status: str
    provider_order_id: str
    checkout_url: str | None = None
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    paid_at: datetime | None = None


def _to_subscription_record(row: SubscriptionRow) -> SubscriptionRecord:
    return SubscriptionRecord(
        id=row.id,
        user_id=row.user_id,
        plan=row.plan,
        status=row.status,
        provider=row.provider,
        starts_at=_ensure_utc(row.starts_at),
        expires_at=_ensure_utc(row.expires_at) if row.expires_at is not None else None,
        created_at=_ensure_utc(row.created_at),
    )


def _to_payment_tx_record(row: PaymentTransactionRow) -> PaymentTransactionRecord:
    return PaymentTransactionRecord(
        id=row.id,
        user_id=row.user_id,
        plan=row.plan,
        provider=row.provider,
        amount=row.amount,
        currency=row.currency,
        status=row.status,
        provider_order_id=row.provider_order_id,
        checkout_url=row.checkout_url,
        metadata_json=dict(row.metadata_json or {}),
        created_at=_ensure_utc(row.created_at),
        updated_at=_ensure_utc(row.updated_at),
        paid_at=_ensure_utc(row.paid_at) if row.paid_at is not None else None,
    )


class SubscriptionRepository:
    """Data-access operations for user trials, paid subscriptions, and cancellation."""

    @staticmethod
    def get_subscription(
        session: Session,
        user_id: str,
        *,
        now: datetime | None = None,
    ) -> SubscriptionRecord | None:
        """Fetch the subscription row for `user_id` if present."""
        _ = now  # reserved for callers inspecting active window
        row = session.scalar(select(SubscriptionRow).where(SubscriptionRow.user_id == user_id))
        if row is None:
            return None
        return _to_subscription_record(row)

    @staticmethod
    def start_trial_if_none(
        session: Session,
        user_id: str,
        *,
        now: datetime | None = None,
    ) -> tuple[SubscriptionRecord, bool]:
        """Start a 7-day free trial only if the user has never held a subscription."""
        existing = session.scalar(select(SubscriptionRow).where(SubscriptionRow.user_id == user_id))
        if existing is not None:
            return _to_subscription_record(existing), False

        reference = _ensure_utc(now) if now is not None else datetime.now(UTC)
        row = SubscriptionRow(
            id=str(uuid4()),
            user_id=user_id,
            plan=PlanId.TRIAL.value,
            status="active",
            provider=None,
            starts_at=reference,
            expires_at=reference + timedelta(days=7),
            created_at=reference,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_subscription_record(row), True

    @staticmethod
    def activate_paid_plan(
        session: Session,
        user_id: str,
        plan_id: PlanId,
        provider: PaymentProvider,
        *,
        now: datetime | None = None,
    ) -> SubscriptionRecord:
        """Activate a paid subscription or extend an active non-trial paid subscription."""
        if plan_id == PlanId.TRIAL:
            raise ValueError("Cannot activate trial as a paid plan")

        plan_def = get_plan(plan_id)
        reference = _ensure_utc(now) if now is not None else datetime.now(UTC)

        row = session.scalar(select(SubscriptionRow).where(SubscriptionRow.user_id == user_id))
        if row is None:
            row = SubscriptionRow(
                id=str(uuid4()),
                user_id=user_id,
                plan=plan_def.id.value,
                status="active",
                provider=provider.value,
                starts_at=reference,
                expires_at=reference + timedelta(days=plan_def.duration_days),
                created_at=reference,
            )
            session.add(row)
        else:
            existing_exp = _ensure_utc(row.expires_at) if row.expires_at is not None else None
            is_active_paid = (
                row.status == "active"
                and row.plan != PlanId.TRIAL.value
                and existing_exp is not None
                and existing_exp > reference
            )
            base_start = existing_exp if is_active_paid and existing_exp is not None else reference
            if not is_active_paid:
                row.starts_at = reference
            row.plan = plan_def.id.value
            row.status = "active"
            row.provider = provider.value
            row.expires_at = base_start + timedelta(days=plan_def.duration_days)
            session.add(row)

        session.commit()
        session.refresh(row)
        return _to_subscription_record(row)

    @staticmethod
    def cancel_subscription(
        session: Session,
        user_id: str,
        *,
        now: datetime | None = None,
    ) -> SubscriptionRecord | None:
        """Mark a user's subscription as cancelled."""
        _ = now
        row = session.scalar(select(SubscriptionRow).where(SubscriptionRow.user_id == user_id))
        if row is None:
            return None
        row.status = "cancelled"
        session.commit()
        session.refresh(row)
        return _to_subscription_record(row)


class PaymentRepository:
    """Data-access operations for checkout orders and webhook payment transactions."""

    @staticmethod
    def create_transaction(
        session: Session,
        *,
        user_id: str,
        plan: str,
        provider: str,
        amount: float,
        currency: str,
        provider_order_id: str,
        checkout_url: str | None,
        metadata_json: dict[str, Any] | None = None,
    ) -> PaymentTransactionRecord:
        """Create a new pending payment transaction record."""
        now = datetime.now(UTC)
        row = PaymentTransactionRow(
            id=str(uuid4()),
            user_id=user_id,
            plan=plan,
            provider=provider,
            amount=float(amount),
            currency=currency,
            status="pending",
            provider_order_id=provider_order_id,
            checkout_url=checkout_url,
            metadata_json=dict(metadata_json or {}),
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_payment_tx_record(row)

    @staticmethod
    def get_by_order_id(
        session: Session,
        provider_order_id: str,
    ) -> PaymentTransactionRecord | None:
        """Look up a payment transaction by its unique provider order ID."""
        row = session.scalar(
            select(PaymentTransactionRow).where(
                PaymentTransactionRow.provider_order_id == provider_order_id
            )
        )
        if row is None:
            return None
        return _to_payment_tx_record(row)

    @staticmethod
    def mark_transaction_status(
        session: Session,
        provider_order_id: str,
        status: str,
        *,
        metadata_update: dict[str, Any] | None = None,
        paid_at: datetime | None = None,
    ) -> PaymentTransactionRecord | None:
        """Update transaction status and optional payment metadata."""
        row = session.scalar(
            select(PaymentTransactionRow).where(
                PaymentTransactionRow.provider_order_id == provider_order_id
            )
        )
        if row is None:
            return None

        row.status = status.strip()
        row.updated_at = datetime.now(UTC)
        if paid_at is not None:
            row.paid_at = _ensure_utc(paid_at)
        if metadata_update:
            row.metadata_json = {**dict(row.metadata_json or {}), **metadata_update}
        session.commit()
        session.refresh(row)
        return _to_payment_tx_record(row)

    @staticmethod
    def list_user_transactions(
        session: Session,
        user_id: str,
        *,
        limit: int = 20,
    ) -> list[PaymentTransactionRecord]:
        """List payment transactions for a user ordered newest first."""
        stmt = (
            select(PaymentTransactionRow)
            .where(PaymentTransactionRow.user_id == user_id)
            .order_by(PaymentTransactionRow.created_at.desc(), PaymentTransactionRow.id.desc())
        )
        if limit > 0:
            stmt = stmt.limit(limit)
        rows = session.scalars(stmt).all()
        return [_to_payment_tx_record(row) for row in rows]
