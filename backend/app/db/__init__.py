"""Database models, engine helpers, and repository layer."""

from app.db.database import (
    DEFAULT_SQLITE_URL,
    Base,
    create_db_engine,
    get_db,
    get_engine,
    get_session_factory,
    init_db,
    normalize_database_url,
)
from app.db.repository import ProfileRecord, ProfileRepository
from app.db.tables import (
    FoodRow,
    MealLogRow,
    MessageRow,
    MoodLogRow,
    NutritionTargetRow,
    ProfileRow,
    SubscriptionRow,
    UserRow,
    WaterLogRow,
    WeightLogRow,
    WorkoutRow,
)

__all__ = [
    "Base",
    "DEFAULT_SQLITE_URL",
    "FoodRow",
    "MealLogRow",
    "MessageRow",
    "MoodLogRow",
    "NutritionTargetRow",
    "ProfileRecord",
    "ProfileRepository",
    "ProfileRow",
    "SubscriptionRow",
    "UserRow",
    "WaterLogRow",
    "WeightLogRow",
    "WorkoutRow",
    "create_db_engine",
    "get_db",
    "get_engine",
    "get_session_factory",
    "init_db",
    "normalize_database_url",
]
