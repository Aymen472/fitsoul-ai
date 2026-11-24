"""Config-driven macro split and medical condition nutrition rules engine."""

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, Field, model_validator

from app.core.nutrition import calculate_calorie_plan
from app.models import MedicalCondition, UserProfile

KCAL_PER_GRAM_PROTEIN = 4
KCAL_PER_GRAM_CARBS = 4
KCAL_PER_GRAM_FAT = 9
MIN_FAT_G = 25

WATER_ML_PER_KG = 35
MIN_WATER_ML = 1500
MAX_WATER_ML = 4000
MACRO_PCT_SUM_TOLERANCE = 0.01

DEFAULT_RULES_PATH = Path(__file__).resolve().parent / "condition_rules.yaml"


class DefaultMacroRule(BaseModel):
    """Baseline macro percentages and daily nutrient bounds."""

    protein_pct: float = Field(gt=0, lt=1)
    carbs_pct: float = Field(gt=0, lt=1)
    fat_pct: float = Field(gt=0, lt=1)
    fiber_g_min: int = Field(ge=0)
    sodium_mg_max: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_macro_sum(self) -> Self:
        """Ensure default protein, carbs, and fat percentages sum to ~100%."""
        total = self.protein_pct + self.carbs_pct + self.fat_pct
        if not (1.0 - MACRO_PCT_SUM_TOLERANCE <= total <= 1.0 + MACRO_PCT_SUM_TOLERANCE):
            raise ValueError("Default macro percentages must sum to ~1.0")
        return self


class ConditionRule(BaseModel):
    """Overrides and tag constraints for a single medical condition."""

    carbs_max_pct: float | None = Field(default=None, gt=0, lt=1)
    protein_min_pct: float | None = Field(default=None, gt=0, lt=1)
    max_carbs_g: int | None = Field(default=None, gt=0)
    max_carbs_per_meal_g: int | None = Field(default=None, gt=0)
    fiber_g_min: int | None = Field(default=None, ge=0)
    sodium_mg_max: int | None = Field(default=None, gt=0)
    forbidden_tags: list[str] = Field(default_factory=list)
    required_tags: list[str] = Field(default_factory=list)


class RulesConfig(BaseModel):
    """Validated YAML rules configuration."""

    default: DefaultMacroRule
    conditions: dict[MedicalCondition, ConditionRule]


class NutritionTargets(BaseModel):
    """Deterministic daily nutrition targets and food tag constraints."""

    calories: int
    bmr: int
    tdee: int
    protein_g: int
    carbs_g: int
    fat_g: int
    fiber_g: int
    water_ml: int
    sodium_mg_max: int
    max_carbs_per_meal_g: int | None = None
    forbidden_tags: list[str] = Field(default_factory=list)
    required_tags: list[str] = Field(default_factory=list)
    applied_rules: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


@lru_cache
def load_rules(path: Path = DEFAULT_RULES_PATH) -> RulesConfig:
    """Load and validate condition nutrition rules from YAML."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return RulesConfig.model_validate(raw)


def calculate_water_target_ml(weight_kg: float) -> int:
    """Calculate daily hydration target (~35 ml/kg) clamped to safe bounds."""
    if weight_kg <= 0:
        raise ValueError("weight_kg must be positive")
    return max(MIN_WATER_ML, min(MAX_WATER_ML, round(weight_kg * WATER_ML_PER_KG)))


def _min_optional(current: int | None, candidate: int | None) -> int | None:
    """Return the stricter (lower) of two optional integer limits."""
    if candidate is None:
        return current
    if current is None:
        return candidate
    return min(current, candidate)


def get_nutrition_targets(
    profile: UserProfile,
    today: date | None = None,
    rules_config: RulesConfig | None = None,
) -> NutritionTargets:
    """Compute daily calorie, macro, water, and food-tag targets for a user profile."""
    config = rules_config if rules_config is not None else load_rules()
    calorie_plan = calculate_calorie_plan(profile, today=today)
    target_calories = calorie_plan.target_calories

    protein_pct = config.default.protein_pct
    carbs_pct = config.default.carbs_pct
    fiber_g = config.default.fiber_g_min
    sodium_mg_max = config.default.sodium_mg_max
    max_carbs_g: int | None = None
    max_carbs_per_meal_g: int | None = None
    forbidden_tags: set[str] = set()
    required_tags: set[str] = set()
    applied_rules: list[str] = []

    for condition in profile.conditions:
        rule = config.conditions.get(condition)
        if rule is None:
            continue

        applied_rules.append(condition.value)
        if rule.protein_min_pct is not None:
            protein_pct = max(protein_pct, rule.protein_min_pct)
        if rule.carbs_max_pct is not None:
            carbs_pct = min(carbs_pct, rule.carbs_max_pct)
        if rule.fiber_g_min is not None:
            fiber_g = max(fiber_g, rule.fiber_g_min)
        if rule.sodium_mg_max is not None:
            sodium_mg_max = min(sodium_mg_max, rule.sodium_mg_max)

        max_carbs_g = _min_optional(max_carbs_g, rule.max_carbs_g)
        max_carbs_per_meal_g = _min_optional(max_carbs_per_meal_g, rule.max_carbs_per_meal_g)
        forbidden_tags.update(rule.forbidden_tags)
        required_tags.update(rule.required_tags)

    if not applied_rules:
        applied_rules = ["default"]

    protein_g = round((target_calories * protein_pct) / KCAL_PER_GRAM_PROTEIN)
    carbs_g = round((target_calories * carbs_pct) / KCAL_PER_GRAM_CARBS)
    if max_carbs_g is not None and carbs_g > max_carbs_g:
        carbs_g = max_carbs_g

    remaining_kcal = (
        target_calories - (protein_g * KCAL_PER_GRAM_PROTEIN) - (carbs_g * KCAL_PER_GRAM_CARBS)
    )
    fat_g = max(MIN_FAT_G, round(remaining_kcal / KCAL_PER_GRAM_FAT))

    return NutritionTargets(
        calories=target_calories,
        bmr=calorie_plan.bmr,
        tdee=calorie_plan.tdee,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        fiber_g=fiber_g,
        water_ml=calculate_water_target_ml(profile.weight_kg),
        sodium_mg_max=sodium_mg_max,
        max_carbs_per_meal_g=max_carbs_per_meal_g,
        forbidden_tags=sorted(forbidden_tags),
        required_tags=sorted(required_tags),
        applied_rules=applied_rules,
        warnings=calorie_plan.warnings,
    )
