"""Unit tests for the config-driven macro and medical condition rules engine."""

from datetime import date, timedelta

import pytest

from app.core.rules import (
    calculate_water_target_ml,
    get_nutrition_targets,
    load_rules,
)
from app.models import ActivityLevel, Gender, Goal, MedicalCondition, UserProfile


def _make_profile(**overrides: object) -> UserProfile:
    """Build a valid baseline profile for rules engine tests."""
    data: dict[str, object] = {
        "age": 28,
        "gender": Gender.FEMALE,
        "height_cm": 165.0,
        "weight_kg": 75.0,
        "activity_level": ActivityLevel.SEDENTARY,
        "goal": Goal.LOSE,
    }
    data.update(overrides)
    return UserProfile(**data)


def _macro_calories(protein_g: int, carbs_g: int, fat_g: int) -> int:
    """Compute total calories from macro grams."""
    return (protein_g * 4) + (carbs_g * 4) + (fat_g * 9)


def test_yaml_rules_config_loads_all_conditions() -> None:
    config = load_rules()

    assert set(config.conditions.keys()) == set(MedicalCondition)
    assert config.default.protein_pct == 0.25
    assert config.default.carbs_pct == 0.45
    assert config.default.fat_pct == 0.30


def test_default_profile_targets_and_macro_math() -> None:
    profile = _make_profile()
    targets = get_nutrition_targets(profile)

    assert targets.calories == 1376
    assert targets.bmr == 1480
    assert targets.tdee == 1776
    assert targets.protein_g == 86
    assert targets.carbs_g == 155
    assert targets.fat_g == 46
    assert abs(_macro_calories(targets.protein_g, targets.carbs_g, targets.fat_g) - 1376) <= 10
    assert targets.fiber_g == 25
    assert targets.sodium_mg_max == 2300
    assert targets.max_carbs_per_meal_g is None
    assert targets.forbidden_tags == []
    assert targets.required_tags == []
    assert targets.applied_rules == ["default"]


def test_pcos_profile_applies_low_gi_high_protein_rules() -> None:
    profile = _make_profile(conditions=[MedicalCondition.PCOS])
    targets = get_nutrition_targets(profile)

    assert targets.applied_rules == ["pcos"]
    assert (targets.protein_g * 4) / targets.calories >= 0.295
    assert (targets.carbs_g * 4) / targets.calories <= 0.305
    assert targets.fiber_g == 30
    assert "low_gi" in targets.required_tags
    assert "high_fiber" in targets.required_tags
    assert "refined_sugar" in targets.forbidden_tags
    assert "high_gi" in targets.forbidden_tags


def test_diabetes_t2_enforces_daily_carb_cap_and_per_meal_limit() -> None:
    # Active tall male -> high target calories (> 2500 kcal) so 130g daily carb cap binds
    profile = _make_profile(
        age=32,
        gender=Gender.MALE,
        height_cm=180.0,
        weight_kg=90.0,
        activity_level=ActivityLevel.ACTIVE,
        goal=Goal.MAINTAIN,
        conditions=[MedicalCondition.DIABETES_T2],
    )
    targets = get_nutrition_targets(profile)

    assert targets.calories > 2500
    assert targets.carbs_g == 130
    assert targets.max_carbs_per_meal_g == 45
    assert "sugary_drink" in targets.forbidden_tags
    assert "low_gi" in targets.required_tags
    total_kcal = _macro_calories(targets.protein_g, targets.carbs_g, targets.fat_g)
    assert abs(total_kcal - targets.calories) <= 10


def test_hypertension_enforces_sodium_limit() -> None:
    profile = _make_profile(conditions=[MedicalCondition.HYPERTENSION])
    targets = get_nutrition_targets(profile)

    assert targets.sodium_mg_max == 1500
    assert targets.fiber_g == 28
    assert "high_sodium" in targets.forbidden_tags
    assert "processed_salty" in targets.forbidden_tags
    assert "potassium_rich" in targets.required_tags


def test_hypothyroid_applies_protein_and_whole_food_rules() -> None:
    profile = _make_profile(conditions=[MedicalCondition.HYPOTHYROID])
    targets = get_nutrition_targets(profile)

    assert (targets.protein_g * 4) / targets.calories >= 0.275
    assert targets.fiber_g == 28
    assert "ultra_processed" in targets.forbidden_tags
    assert "whole_foods" in targets.required_tags


def test_multiple_conditions_merge_strictest_bounds() -> None:
    profile = _make_profile(
        activity_level=ActivityLevel.VERY_ACTIVE,
        goal=Goal.MAINTAIN,
        conditions=[
            MedicalCondition.PCOS,
            MedicalCondition.DIABETES_T2,
            MedicalCondition.HYPERTENSION,
        ],
    )
    targets = get_nutrition_targets(profile)

    assert targets.applied_rules == ["pcos", "diabetes_t2", "hypertension"]
    assert targets.sodium_mg_max == 1500
    assert targets.max_carbs_per_meal_g == 45
    assert targets.fiber_g == 30
    assert (targets.protein_g * 4) / targets.calories >= 0.295
    assert targets.carbs_g <= 130
    assert (targets.carbs_g * 4) / targets.calories <= 0.305
    assert set(targets.forbidden_tags) == {
        "high_gi",
        "high_sodium",
        "processed_salty",
        "refined_sugar",
        "sugary_drink",
    }
    assert set(targets.required_tags) == {"high_fiber", "low_gi", "potassium_rich"}


@pytest.mark.parametrize(
    ("weight_kg", "expected_ml"),
    [
        (75.0, 2625),
        (35.0, 1500),
        (150.0, 4000),
    ],
)
def test_water_target_bounds(weight_kg: float, expected_ml: int) -> None:
    assert calculate_water_target_ml(weight_kg) == expected_ml


def test_water_target_invalid_weight_raises() -> None:
    with pytest.raises(ValueError):
        calculate_water_target_ml(0.0)


def test_calorie_plan_warnings_propagate_to_nutrition_targets() -> None:
    unrealistic_date = date.today() + timedelta(days=14)
    profile = _make_profile(weight_kg=75.0, target_weight_kg=65.0, target_date=unrealistic_date)
    targets = get_nutrition_targets(profile)

    assert any("exceeds safe maximum" in w for w in targets.warnings)
