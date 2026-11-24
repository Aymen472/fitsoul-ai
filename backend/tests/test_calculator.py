"""Unit tests for deterministic BMR, TDEE, weekly loss, and calorie floor calculations."""

from datetime import date, timedelta

import pytest

from app.core.nutrition import (
    FEMALE_CALORIE_FLOOR,
    MALE_CALORIE_FLOOR,
    calculate_bmr,
    calculate_calorie_plan,
    calculate_safe_weekly_loss,
    calculate_target_calories,
    calculate_tdee,
)
from app.models import ActivityLevel, Gender, Goal, UserProfile


def _make_profile(**overrides: object) -> UserProfile:
    """Create a valid UserProfile with sensible defaults for calculator tests."""
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


def test_roadmap_example_female_bmr_tdee_and_plan() -> None:
    """28y female, 165 cm, 75 kg, sedentary -> BMR ~1480, TDEE ~1776."""
    bmr = calculate_bmr(weight_kg=75.0, height_cm=165.0, age=28, gender=Gender.FEMALE)
    tdee = calculate_tdee(bmr, ActivityLevel.SEDENTARY)
    profile = _make_profile()
    plan = calculate_calorie_plan(profile)

    assert bmr == 1480.25
    assert tdee == 1776.3
    assert plan.bmr == 1480
    assert plan.tdee == 1776
    assert plan.target_calories == 1376
    assert plan.calorie_floor == FEMALE_CALORIE_FLOOR
    assert plan.floor_applied is False
    assert plan.daily_adjustment_kcal == -400
    assert plan.warnings == []


def test_male_bmr_calculation() -> None:
    # 10*80 + 6.25*178 - 5*30 + 5 = 800 + 1112.5 - 150 + 5 = 1767.5
    bmr = calculate_bmr(weight_kg=80.0, height_cm=178.0, age=30, gender=Gender.MALE)
    assert bmr == 1767.5


@pytest.mark.parametrize(
    ("activity_level", "expected_tdee"),
    [
        (ActivityLevel.SEDENTARY, 1800.0),
        (ActivityLevel.LIGHT, 2062.5),
        (ActivityLevel.MODERATE, 2325.0),
        (ActivityLevel.ACTIVE, 2587.5),
        (ActivityLevel.VERY_ACTIVE, 2850.0),
    ],
)
def test_tdee_all_activity_levels(activity_level: ActivityLevel, expected_tdee: float) -> None:
    assert calculate_tdee(1500.0, activity_level) == expected_tdee


def test_female_calorie_floor_enforced() -> None:
    # 45y female, 150 cm, 48 kg -> BMR = 480 + 937.5 - 225 - 161 = 1031.5; TDEE = 1237.8
    profile = _make_profile(age=45, height_cm=150.0, weight_kg=48.0, goal=Goal.LOSE)
    plan = calculate_calorie_plan(profile)

    assert plan.target_calories == FEMALE_CALORIE_FLOOR
    assert plan.calorie_floor == FEMALE_CALORIE_FLOOR
    assert plan.floor_applied is True
    assert any("1200" in w for w in plan.warnings)


def test_male_calorie_floor_enforced() -> None:
    # 50y male, 160 cm, 55 kg -> BMR = 550 + 1000 - 250 + 5 = 1305; TDEE = 1566
    profile = _make_profile(
        age=50,
        gender=Gender.MALE,
        height_cm=160.0,
        weight_kg=55.0,
        goal=Goal.LOSE,
    )
    plan = calculate_calorie_plan(profile)

    assert plan.target_calories == MALE_CALORIE_FLOOR
    assert plan.calorie_floor == MALE_CALORIE_FLOOR
    assert plan.floor_applied is True
    assert any("1500" in w for w in plan.warnings)


def test_extreme_deficit_never_breaches_floor() -> None:
    target, floor_applied = calculate_target_calories(
        tdee=1400.0,
        goal=Goal.LOSE,
        gender=Gender.FEMALE,
        daily_deficit_kcal=500,
    )
    assert target == FEMALE_CALORIE_FLOOR
    assert floor_applied is True


def test_high_risk_pregnant_user_gets_no_deficit() -> None:
    profile = _make_profile(is_pregnant=True, goal=Goal.LOSE)
    plan = calculate_calorie_plan(profile)

    assert plan.target_calories == plan.tdee
    assert plan.daily_adjustment_kcal == 0
    assert any("High-risk" in w and "deficit disabled" in w for w in plan.warnings)


def test_high_risk_underweight_user_gets_limited_mode_warning() -> None:
    profile = _make_profile(height_cm=165.0, weight_kg=48.0, goal=Goal.GAIN)
    plan = calculate_calorie_plan(profile)

    assert plan.target_calories == plan.tdee + 300
    assert any("High-risk" in w for w in plan.warnings)


def test_maintain_and_gain_goals() -> None:
    maintain_plan = calculate_calorie_plan(_make_profile(goal=Goal.MAINTAIN))
    gain_plan = calculate_calorie_plan(_make_profile(goal=Goal.GAIN))

    assert maintain_plan.target_calories == maintain_plan.tdee
    assert maintain_plan.daily_adjustment_kcal == 0
    assert maintain_plan.weekly_loss_assessment is None

    assert gain_plan.target_calories == gain_plan.tdee + 300
    assert gain_plan.daily_adjustment_kcal == 300
    assert gain_plan.weekly_loss_assessment is None


def test_safe_weekly_loss_realistic_deadline() -> None:
    ref_today = date(2026, 11, 25)
    # Lose 5 kg in 10 weeks = 0.5 kg/week; safe max for 75 kg is 0.75 kg/week
    target_date = ref_today + timedelta(weeks=10)
    assessment = calculate_safe_weekly_loss(
        weight_kg=75.0,
        target_weight_kg=70.0,
        target_date=target_date,
        today=ref_today,
    )

    assert assessment.requested_weekly_loss_kg == 0.5
    assert assessment.safe_min_weekly_loss_kg == 0.38
    assert assessment.safe_max_weekly_loss_kg == 0.75
    assert assessment.is_realistic is True
    assert assessment.recommended_weeks == 10
    assert assessment.safe_target_date == target_date
    assert assessment.warning is None


def test_safe_weekly_loss_unrealistic_deadline() -> None:
    ref_today = date(2026, 11, 25)
    # 10 kg in 2 weeks = 5.0 kg/week (unrealistic); safe_max = 0.75 kg/week -> 14 weeks
    target_date = ref_today + timedelta(weeks=2)
    assessment = calculate_safe_weekly_loss(
        weight_kg=75.0,
        target_weight_kg=65.0,
        target_date=target_date,
        today=ref_today,
    )

    assert assessment.requested_weekly_loss_kg == 5.0
    assert assessment.is_realistic is False
    assert assessment.recommended_weekly_loss_kg == 0.75
    assert assessment.recommended_weeks == 14
    assert assessment.safe_target_date == ref_today + timedelta(weeks=14)
    assert assessment.warning is not None


def test_safe_weekly_loss_without_target_date() -> None:
    ref_today = date(2026, 11, 25)
    assessment = calculate_safe_weekly_loss(
        weight_kg=80.0,
        target_weight_kg=74.0,
        target_date=None,
        today=ref_today,
    )

    assert assessment.requested_weekly_loss_kg is None
    assert assessment.is_realistic is True
    assert assessment.recommended_weeks is not None and assessment.recommended_weeks > 0
    assert assessment.safe_target_date is not None
    assert assessment.warning is None


def test_safe_weekly_loss_past_target_date_raises() -> None:
    ref_today = date(2026, 11, 25)
    with pytest.raises(ValueError, match="target_date must be in the future"):
        calculate_safe_weekly_loss(
            weight_kg=75.0,
            target_weight_kg=70.0,
            target_date=ref_today,
            today=ref_today,
        )


def test_plan_includes_unrealistic_deadline_warning() -> None:
    # Use real future date (+14 days) so UserProfile validator accepts it
    unrealistic_date = date.today() + timedelta(days=14)
    profile = _make_profile(weight_kg=75.0, target_weight_kg=65.0, target_date=unrealistic_date)
    plan = calculate_calorie_plan(profile)

    assert plan.weekly_loss_assessment is not None
    assert plan.weekly_loss_assessment.is_realistic is False
    assert any("exceeds safe maximum" in w for w in plan.warnings)


def test_invalid_inputs_raise_value_error() -> None:
    with pytest.raises(ValueError):
        calculate_bmr(weight_kg=-5.0, height_cm=165.0, age=28, gender=Gender.FEMALE)
    with pytest.raises(ValueError):
        calculate_tdee(bmr=0.0, activity_level=ActivityLevel.SEDENTARY)
    with pytest.raises(ValueError):
        calculate_target_calories(tdee=-100.0, goal=Goal.LOSE, gender=Gender.FEMALE)
