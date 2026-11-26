"""Food search, daily meal/water/weight/mood tracking, and dashboard summary endpoints."""

from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai import (
    GeminiClient,
    MealEditItem,
    MealPhotoScanner,
    PatternReport,
    detect_emotional_patterns,
)
from app.core.nutrition import FoodItem, get_food_db
from app.core.rules import NutritionTargets
from app.db import (
    MealLogRecord,
    MealLogRepository,
    MemoryRepository,
    MessageRepository,
    MoodLogRecord,
    MoodLogRepository,
    ProfileRepository,
    WaterLogRecord,
    WaterLogRepository,
    WeightLogRecord,
    WeightLogRepository,
    get_db,
)

DEFAULT_TIMEZONE = "Asia/Karachi"
STAPLE_FOOD_IDS = (
    "roti_whole_wheat",
    "daal_moong",
    "boiled_egg",
    "chicken_karahi",
    "plain_dahi",
    "doodh_patti_chai",
    "bhune_chanay",
    "chicken_biryani",
    "green_salad",
    "cucumber_raita",
    "oats_porridge",
    "apple",
)

router = APIRouter(prefix="/api/v1", tags=["tracking", "foods"])

DbSession = Annotated[Session, Depends(get_db)]


class FoodSearchItem(BaseModel):
    """Serializable Pakistani food catalog item for quick meal logging."""

    id: str
    name: str
    urdu_name: str
    category: str
    serving_desc: str
    grams: float
    kcal: float
    protein: float
    carbs: float
    fat: float
    fiber: float
    sodium_mg: float
    gi_category: str


class QuickMealLogRequest(BaseModel):
    """Confirmed food items and serving multipliers to log deterministically."""

    meal_type: Literal["breakfast", "lunch", "snack", "dinner"]
    items: list[MealEditItem] = Field(min_length=1, max_length=20)
    plate_notes: str = Field(default="", max_length=500)


class WaterLogRequest(BaseModel):
    """Hydration entry payload in milliliters."""

    amount_ml: int = Field(gt=0, le=5000)


class WeightLogRequest(BaseModel):
    """Body-weight check-in payload in kilograms."""

    weight_kg: float = Field(ge=30.0, le=250.0)


class MoodLogRequest(BaseModel):
    """Mood and optional context note payload."""

    mood: str = Field(min_length=1, max_length=32)
    note: str | None = Field(default=None, max_length=500)


class DashboardSummary(BaseModel):
    """Aggregated daily nutrition, hydration, weight, mood, streak, and pattern data."""

    user_id: str
    date: date
    targets: NutritionTargets
    consumed_kcal: float
    remaining_kcal: float
    consumed_protein_g: float
    consumed_carbs_g: float
    consumed_fat_g: float
    water_ml: int
    water_target_ml: int
    streak_days: int
    latest_weight_kg: float
    target_weight_kg: float | None = None
    weight_history: list[WeightLogRecord]
    today_meals: list[MealLogRecord]
    recent_meals: list[MealLogRecord]
    recent_moods: list[MoodLogRecord]
    patterns: PatternReport


def _ensure_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _resolve_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def _to_local_date(dt: datetime, tz: ZoneInfo) -> date:
    return _ensure_utc(dt).astimezone(tz).date()


def _to_food_search_item(food: FoodItem) -> FoodSearchItem:
    return FoodSearchItem(
        id=food.id,
        name=food.name,
        urdu_name=food.urdu_name,
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
    )


def compute_logging_streak_days(
    timestamps: Iterable[datetime],
    *,
    today_local: date,
    tz: ZoneInfo,
) -> int:
    """Count consecutive days of activity ending today or yesterday."""
    active_dates = {_to_local_date(ts, tz) for ts in timestamps}
    if today_local in active_dates:
        cursor = today_local
    elif (today_local - timedelta(days=1)) in active_dates:
        cursor = today_local - timedelta(days=1)
    else:
        return 0

    streak = 0
    while cursor in active_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


@router.get("/foods/search", response_model=list[FoodSearchItem])
def search_foods(
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=12, ge=1, le=30),
) -> list[FoodSearchItem]:
    """Search curated Pakistani foods or return common staples when query is empty."""
    food_db = get_food_db()
    cleaned = q.strip()
    if not cleaned:
        staples = [
            food for food_id in STAPLE_FOOD_IDS if (food := food_db.get_by_id(food_id)) is not None
        ]
        return [_to_food_search_item(food) for food in staples[:limit]]

    matches = food_db.search(cleaned, limit=limit)
    return [_to_food_search_item(food) for food in matches]


@router.post(
    "/tracking/{user_id}/meals",
    response_model=MealLogRecord,
    status_code=status.HTTP_201_CREATED,
)
def log_quick_meal(
    user_id: str,
    payload: QuickMealLogRequest,
    db: DbSession,
) -> MealLogRecord:
    """Compute exact Food DB nutrition for selected items and persist a meal log."""
    record = ProfileRepository.get_profile(db, user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    scanner = MealPhotoScanner(gemini_client=GeminiClient(api_key=""), food_db=get_food_db())
    try:
        summary = scanner.recalculate_from_edits(payload.items, plate_notes=payload.plate_notes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return MealLogRepository.save_meal_log(db, user_id, payload.meal_type, summary)


@router.post(
    "/tracking/{user_id}/water",
    response_model=WaterLogRecord,
    status_code=status.HTTP_201_CREATED,
)
def log_water_intake(
    user_id: str,
    payload: WaterLogRequest,
    db: DbSession,
) -> WaterLogRecord:
    """Log daily water intake in milliliters."""
    record = ProfileRepository.get_profile(db, user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    return WaterLogRepository.save_water_log(db, user_id, payload.amount_ml)


@router.post(
    "/tracking/{user_id}/weight",
    response_model=WeightLogRecord,
    status_code=status.HTTP_201_CREATED,
)
def log_body_weight(
    user_id: str,
    payload: WeightLogRequest,
    db: DbSession,
) -> WeightLogRecord:
    """Log a body-weight check-in in kilograms."""
    record = ProfileRepository.get_profile(db, user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    return WeightLogRepository.save_weight_log(db, user_id, payload.weight_kg)


@router.post(
    "/tracking/{user_id}/mood",
    response_model=MoodLogRecord,
    status_code=status.HTTP_201_CREATED,
)
def log_mood_checkin(
    user_id: str,
    payload: MoodLogRequest,
    db: DbSession,
) -> MoodLogRecord:
    """Log a mood and optional note for emotional pattern detection."""
    record = ProfileRepository.get_profile(db, user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    return MoodLogRepository.save_mood_log(db, user_id, payload.mood, note=payload.note)


@router.get("/tracking/{user_id}/dashboard", response_model=DashboardSummary)
def get_user_dashboard(user_id: str, db: DbSession) -> DashboardSummary:
    """Aggregate today's calories, macros, water, weight history, streaks, and patterns."""
    record = ProfileRepository.get_profile(db, user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    tz = _resolve_timezone(record.profile.timezone)
    now = datetime.now(UTC)
    local_today = now.astimezone(tz).date()

    meals_30d = MealLogRepository.get_recent_meal_logs(db, user_id, days=30, now=now)
    water_30d = WaterLogRepository.get_recent_water_logs(db, user_id, days=30, now=now)
    moods_30d = MoodLogRepository.get_recent_mood_logs(db, user_id, days=30, now=now)
    weights_90d = WeightLogRepository.get_recent_weight_logs(
        db, user_id, days=90, limit=60, now=now
    )
    messages_14d = MessageRepository.get_messages_since(db, user_id, days=14, now=now)
    memories = MemoryRepository.list_memories(db, user_id)

    today_meals = [m for m in meals_30d if _to_local_date(m.logged_at, tz) == local_today]
    today_water_ml = sum(
        w.amount_ml for w in water_30d if _to_local_date(w.logged_at, tz) == local_today
    )

    consumed_kcal = round(sum(m.total_kcal for m in today_meals), 1)
    consumed_protein_g = round(sum(m.protein_g for m in today_meals), 1)
    consumed_carbs_g = round(sum(m.carbs_g for m in today_meals), 1)
    consumed_fat_g = round(sum(m.fat_g for m in today_meals), 1)
    remaining_kcal = round(max(0.0, record.targets.calories - consumed_kcal), 1)

    streak_days = compute_logging_streak_days(
        [
            *(m.logged_at for m in meals_30d),
            *(w.logged_at for w in water_30d),
            *(mood.logged_at for mood in moods_30d),
            *(wt.logged_at for wt in weights_90d),
        ],
        today_local=local_today,
        tz=tz,
    )

    cutoff_14d = now - timedelta(days=14)
    patterns = detect_emotional_patterns(
        messages=messages_14d,
        meal_logs=[m for m in meals_30d if _ensure_utc(m.logged_at) >= cutoff_14d],
        mood_logs=[m for m in moods_30d if _ensure_utc(m.logged_at) >= cutoff_14d],
        daily_target_kcal=record.targets.calories,
        timezone_name=record.profile.timezone,
        memories=memories,
    )

    latest_weight_kg = weights_90d[-1].weight_kg if weights_90d else record.profile.weight_kg

    return DashboardSummary(
        user_id=user_id,
        date=local_today,
        targets=record.targets,
        consumed_kcal=consumed_kcal,
        remaining_kcal=remaining_kcal,
        consumed_protein_g=consumed_protein_g,
        consumed_carbs_g=consumed_carbs_g,
        consumed_fat_g=consumed_fat_g,
        water_ml=today_water_ml,
        water_target_ml=record.targets.water_ml,
        streak_days=streak_days,
        latest_weight_kg=latest_weight_kg,
        target_weight_kg=record.profile.target_weight_kg,
        weight_history=weights_90d,
        today_meals=today_meals,
        recent_meals=list(reversed(meals_30d))[:15],
        recent_moods=list(reversed(moods_30d))[:10],
        patterns=patterns,
    )
