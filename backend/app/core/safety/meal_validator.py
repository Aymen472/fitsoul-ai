"""Deterministic Python validator for AI-generated and fallback meal plans."""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.core.nutrition import FoodItem, ScaledNutrition, get_calorie_floor
from app.core.rules import NutritionTargets
from app.models import UserProfile

CALORIE_TOLERANCE_RATIO = 0.05
CARB_CAP_TOLERANCE_RATIO = 1.05
MIN_SERVINGS = 0.25
MAX_SERVINGS = 5.0
CARB_RESTRICTED_RULES = frozenset({"pcos", "diabetes_t2"})


class MealType(StrEnum):
    """Standard four-meal daily structure."""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    SNACK = "snack"
    DINNER = "dinner"


class PlannedMealItem(BaseModel):
    """Single food choice and serving multiplier proposed by the meal planner."""

    food_id: str
    servings: float = Field(ge=MIN_SERVINGS, le=MAX_SERVINGS)


class RawDailyMealPlan(BaseModel):
    """Structured JSON schema returned by Gemini or the fallback meal builder."""

    breakfast: list[PlannedMealItem]
    lunch: list[PlannedMealItem]
    snack: list[PlannedMealItem]
    dinner: list[PlannedMealItem]
    notes: str = ""


class ValidatedMeal(BaseModel):
    """Single meal with deterministic DB-computed calories and macros."""

    meal_type: MealType
    items: list[ScaledNutrition]
    kcal: float
    protein: float
    carbs: float
    fat: float
    fiber: float
    sodium_mg: float


class ValidatedMealPlan(BaseModel):
    """Complete verified daily meal plan with deterministic daily totals."""

    meals: list[ValidatedMeal]
    total_kcal: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    total_fiber_g: float
    total_sodium_mg: float
    notes: str = ""
    used_fallback: bool = False
    attempts_used: int = 1


class MealValidationResult(BaseModel):
    """Outcome of deterministic meal plan validation."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    validated_plan: ValidatedMealPlan | None = None


def validate_meal_plan(
    raw_plan: RawDailyMealPlan,
    profile: UserProfile,
    targets: NutritionTargets,
    allowed_foods: list[FoodItem],
    *,
    used_fallback: bool = False,
    attempts_used: int = 1,
) -> MealValidationResult:
    """Verify every food, calorie floor, ±5% calorie band, protein, carbs, and sodium."""
    allowed_by_id = {food.id: food for food in allowed_foods}
    errors: list[str] = []
    validated_meals: list[ValidatedMeal] = []

    meal_slots: list[tuple[MealType, list[PlannedMealItem]]] = [
        (MealType.BREAKFAST, raw_plan.breakfast),
        (MealType.LUNCH, raw_plan.lunch),
        (MealType.SNACK, raw_plan.snack),
        (MealType.DINNER, raw_plan.dinner),
    ]

    for meal_type, slot_items in meal_slots:
        if not slot_items:
            errors.append(f"Meal '{meal_type.value}' must contain at least one item.")
            continue

        scaled_items: list[ScaledNutrition] = []
        for planned in slot_items:
            food = allowed_by_id.get(planned.food_id)
            if food is None:
                errors.append(
                    f"Food '{planned.food_id}' in '{meal_type.value}' is unknown or not allowed "
                    "for this profile."
                )
                continue
            scaled_items.append(food.scale(planned.servings))

        if not scaled_items:
            continue

        meal_kcal = round(sum(item.kcal for item in scaled_items), 1)
        meal_protein = round(sum(item.protein for item in scaled_items), 1)
        meal_carbs = round(sum(item.carbs for item in scaled_items), 1)
        meal_fat = round(sum(item.fat for item in scaled_items), 1)
        meal_fiber = round(sum(item.fiber for item in scaled_items), 1)
        meal_sodium = round(sum(item.sodium_mg for item in scaled_items), 1)

        if targets.max_carbs_per_meal_g is not None and meal_carbs > targets.max_carbs_per_meal_g:
            errors.append(
                f"Meal '{meal_type.value}' carbs ({meal_carbs}g) exceed per-meal limit "
                f"({targets.max_carbs_per_meal_g}g)."
            )

        validated_meals.append(
            ValidatedMeal(
                meal_type=meal_type,
                items=scaled_items,
                kcal=meal_kcal,
                protein=meal_protein,
                carbs=meal_carbs,
                fat=meal_fat,
                fiber=meal_fiber,
                sodium_mg=meal_sodium,
            )
        )

    total_kcal = round(sum(m.kcal for m in validated_meals), 1)
    total_protein = round(sum(m.protein for m in validated_meals), 1)
    total_carbs = round(sum(m.carbs for m in validated_meals), 1)
    total_fat = round(sum(m.fat for m in validated_meals), 1)
    total_fiber = round(sum(m.fiber for m in validated_meals), 1)
    total_sodium = round(sum(m.sodium_mg for m in validated_meals), 1)

    calorie_floor = get_calorie_floor(profile.gender)
    if total_kcal < calorie_floor:
        errors.append(
            f"Total calories ({total_kcal} kcal) are below safe floor ({calorie_floor} kcal)."
        )

    max_deviation = targets.calories * CALORIE_TOLERANCE_RATIO
    if abs(total_kcal - targets.calories) > max_deviation:
        min_band = round(targets.calories - max_deviation, 1)
        max_band = round(targets.calories + max_deviation, 1)
        errors.append(
            f"Total calories ({total_kcal} kcal) must be within ±5% of target "
            f"({min_band}–{max_band} kcal)."
        )

    if total_protein < targets.protein_g:
        errors.append(
            f"Total protein ({total_protein}g) is below daily target ({targets.protein_g}g)."
        )

    if set(targets.applied_rules) & CARB_RESTRICTED_RULES:
        carb_ceiling = round(targets.carbs_g * CARB_CAP_TOLERANCE_RATIO, 1)
        if total_carbs > carb_ceiling:
            errors.append(
                f"Total carbs ({total_carbs}g) exceed condition ceiling ({carb_ceiling}g)."
            )

    if total_sodium > targets.sodium_mg_max:
        errors.append(
            f"Total sodium ({total_sodium} mg) exceeds daily limit ({targets.sodium_mg_max} mg)."
        )

    if errors:
        return MealValidationResult(is_valid=False, errors=errors, validated_plan=None)

    plan = ValidatedMealPlan(
        meals=validated_meals,
        total_kcal=total_kcal,
        total_protein_g=total_protein,
        total_carbs_g=total_carbs,
        total_fat_g=total_fat,
        total_fiber_g=total_fiber,
        total_sodium_mg=total_sodium,
        notes=raw_plan.notes,
        used_fallback=used_fallback,
        attempts_used=attempts_used,
    )
    return MealValidationResult(is_valid=True, errors=[], validated_plan=plan)
