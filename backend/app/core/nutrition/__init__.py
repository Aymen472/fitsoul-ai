"""Deterministic nutrition calculators (BMR, TDEE, macros)."""

from app.core.nutrition.calculator import (
    ACTIVITY_MULTIPLIERS,
    DEFAULT_GAIN_SURPLUS_KCAL,
    DEFAULT_LOSS_DEFICIT_KCAL,
    FEMALE_CALORIE_FLOOR,
    KCAL_PER_KG,
    MALE_CALORIE_FLOOR,
    CaloriePlan,
    WeeklyLossAssessment,
    calculate_bmr,
    calculate_calorie_plan,
    calculate_safe_weekly_loss,
    calculate_target_calories,
    calculate_tdee,
    get_calorie_floor,
)
from app.core.nutrition.food_db import (
    DEFAULT_FOODS_CSV,
    FoodDatabase,
    FoodItem,
    GICategory,
    ScaledNutrition,
    get_food_db,
)

__all__ = [
    "ACTIVITY_MULTIPLIERS",
    "CaloriePlan",
    "DEFAULT_FOODS_CSV",
    "DEFAULT_GAIN_SURPLUS_KCAL",
    "DEFAULT_LOSS_DEFICIT_KCAL",
    "FEMALE_CALORIE_FLOOR",
    "FoodDatabase",
    "FoodItem",
    "GICategory",
    "KCAL_PER_KG",
    "MALE_CALORIE_FLOOR",
    "ScaledNutrition",
    "WeeklyLossAssessment",
    "calculate_bmr",
    "calculate_calorie_plan",
    "calculate_safe_weekly_loss",
    "calculate_target_calories",
    "calculate_tdee",
    "get_calorie_floor",
    "get_food_db",
]
