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

__all__ = [
    "ACTIVITY_MULTIPLIERS",
    "CaloriePlan",
    "DEFAULT_GAIN_SURPLUS_KCAL",
    "DEFAULT_LOSS_DEFICIT_KCAL",
    "FEMALE_CALORIE_FLOOR",
    "KCAL_PER_KG",
    "MALE_CALORIE_FLOOR",
    "WeeklyLossAssessment",
    "calculate_bmr",
    "calculate_calorie_plan",
    "calculate_safe_weekly_loss",
    "calculate_target_calories",
    "calculate_tdee",
    "get_calorie_floor",
]
