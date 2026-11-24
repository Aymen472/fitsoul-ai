"""Unit tests for the UserProfile Pydantic schema and validation rules."""

from datetime import date, time, timedelta

import pytest
from pydantic import ValidationError

from app.models import (
    ActivityLevel,
    DietType,
    Gender,
    Goal,
    HighRiskCondition,
    MedicalCondition,
    UserProfile,
)


def _base_profile_data(**overrides: object) -> dict[str, object]:
    """Build valid baseline profile data with optional overrides."""
    data: dict[str, object] = {
        "age": 28,
        "gender": Gender.FEMALE,
        "height_cm": 165.0,
        "weight_kg": 75.0,
        "activity_level": ActivityLevel.SEDENTARY,
        "goal": Goal.LOSE,
    }
    data.update(overrides)
    return data


def test_minimal_profile_defaults_and_computed_fields() -> None:
    profile = UserProfile(**_base_profile_data())

    assert profile.diet_type == DietType.NON_VEG
    assert profile.timezone == "Asia/Karachi"
    assert profile.conditions == []
    assert profile.high_risk_conditions == []
    assert profile.is_pregnant is False
    assert profile.on_regular_medication is False
    assert profile.bmi == 27.5
    assert profile.high_risk_reasons == []
    assert profile.is_high_risk is False
    assert profile.supplements_allowed is True


def test_rich_pcos_profile_and_list_normalization() -> None:
    future_date = date.today() + timedelta(days=90)
    profile = UserProfile(
        **_base_profile_data(
            target_weight_kg=62.0,
            target_date=future_date,
            conditions=[MedicalCondition.PCOS, MedicalCondition.PCOS],
            diet_type=DietType.EGGETARIAN,
            allergies=[" Peanuts ", "peanuts", "", "Shellfish"],
            dislikes=["Bitter Gourd", "  bitter gourd  ", ""],
            timezone="Europe/London",
            wake_time=time(7, 0),
            sleep_time=time(23, 0),
            workout_time=time(18, 30),
        )
    )

    assert profile.conditions == [MedicalCondition.PCOS]
    assert profile.allergies == ["peanuts", "shellfish"]
    assert profile.dislikes == ["bitter gourd"]
    assert profile.target_date == future_date
    assert profile.timezone == "Europe/London"
    assert profile.is_high_risk is False


@pytest.mark.parametrize("age", [18, 80])
def test_age_valid_boundaries(age: int) -> None:
    profile = UserProfile(**_base_profile_data(age=age))
    assert profile.age == age


@pytest.mark.parametrize("age", [17, 81])
def test_age_invalid_boundaries(age: int) -> None:
    with pytest.raises(ValidationError):
        UserProfile(**_base_profile_data(age=age))


@pytest.mark.parametrize("height_cm", [120.0, 220.0])
def test_height_valid_boundaries(height_cm: float) -> None:
    profile = UserProfile(**_base_profile_data(height_cm=height_cm))
    assert profile.height_cm == height_cm


@pytest.mark.parametrize("height_cm", [119.9, 220.1])
def test_height_invalid_boundaries(height_cm: float) -> None:
    with pytest.raises(ValidationError):
        UserProfile(**_base_profile_data(height_cm=height_cm))


@pytest.mark.parametrize("weight_kg", [30.0, 250.0])
def test_weight_valid_boundaries(weight_kg: float) -> None:
    profile = UserProfile(**_base_profile_data(weight_kg=weight_kg))
    assert profile.weight_kg == weight_kg


@pytest.mark.parametrize("weight_kg", [29.9, 250.1])
def test_weight_invalid_boundaries(weight_kg: float) -> None:
    with pytest.raises(ValidationError):
        UserProfile(**_base_profile_data(weight_kg=weight_kg))


@pytest.mark.parametrize("tz", ["Invalid/Zone", "", "Mars/Olympus"])
def test_invalid_timezone_raises(tz: str) -> None:
    with pytest.raises(ValidationError, match="Invalid IANA timezone"):
        UserProfile(**_base_profile_data(timezone=tz))


@pytest.mark.parametrize("days_offset", [0, -1, -30])
def test_target_date_today_or_past_raises(days_offset: int) -> None:
    bad_date = date.today() + timedelta(days=days_offset)
    with pytest.raises(ValidationError, match="target_date must be in the future"):
        UserProfile(**_base_profile_data(target_date=bad_date))


@pytest.mark.parametrize("target_weight", [75.0, 80.0])
def test_lose_goal_requires_lower_target_weight(target_weight: float) -> None:
    with pytest.raises(ValidationError, match="target_weight_kg must be less than"):
        UserProfile(**_base_profile_data(goal=Goal.LOSE, target_weight_kg=target_weight))


@pytest.mark.parametrize("target_weight", [75.0, 70.0])
def test_gain_goal_requires_higher_target_weight(target_weight: float) -> None:
    with pytest.raises(ValidationError, match="target_weight_kg must be greater than"):
        UserProfile(**_base_profile_data(goal=Goal.GAIN, target_weight_kg=target_weight))


def test_gain_goal_valid_higher_target_weight() -> None:
    profile = UserProfile(
        **_base_profile_data(goal=Goal.GAIN, weight_kg=55.0, target_weight_kg=62.0)
    )
    assert profile.target_weight_kg == 62.0


def test_pcos_on_male_raises() -> None:
    with pytest.raises(ValidationError, match="PCOS condition is only applicable to female"):
        UserProfile(**_base_profile_data(gender=Gender.MALE, conditions=[MedicalCondition.PCOS]))


def test_pregnant_on_male_raises() -> None:
    with pytest.raises(ValidationError, match="is_pregnant is only applicable to female"):
        UserProfile(**_base_profile_data(gender=Gender.MALE, is_pregnant=True))


def test_underweight_bmi_triggers_high_risk() -> None:
    profile = UserProfile(**_base_profile_data(height_cm=165.0, weight_kg=48.0, goal=Goal.GAIN))

    assert profile.bmi == 17.6
    assert profile.is_high_risk is True
    assert profile.high_risk_reasons == ["underweight_bmi"]
    assert profile.supplements_allowed is False


def test_pregnancy_triggers_high_risk() -> None:
    profile = UserProfile(**_base_profile_data(is_pregnant=True, goal=Goal.MAINTAIN))

    assert profile.is_high_risk is True
    assert profile.high_risk_reasons == ["pregnancy"]
    assert profile.supplements_allowed is False


@pytest.mark.parametrize(
    "condition",
    [
        HighRiskCondition.DIABETES_T1,
        HighRiskCondition.KIDNEY_DISEASE,
        HighRiskCondition.LIVER_DISEASE,
        HighRiskCondition.EATING_DISORDER_HISTORY,
    ],
)
def test_high_risk_conditions_disable_supplements(condition: HighRiskCondition) -> None:
    profile = UserProfile(**_base_profile_data(high_risk_conditions=[condition, condition]))

    assert profile.high_risk_conditions == [condition]
    assert profile.is_high_risk is True
    assert profile.high_risk_reasons == [condition.value]
    assert profile.supplements_allowed is False


def test_regular_medication_disables_supplements_without_high_risk() -> None:
    profile = UserProfile(**_base_profile_data(on_regular_medication=True))

    assert profile.is_high_risk is False
    assert profile.high_risk_reasons == []
    assert profile.supplements_allowed is False


def test_model_dump_includes_computed_fields() -> None:
    profile = UserProfile(**_base_profile_data())
    dumped = profile.model_dump()

    assert dumped["bmi"] == 27.5
    assert dumped["is_high_risk"] is False
    assert dumped["high_risk_reasons"] == []
    assert dumped["supplements_allowed"] is True
