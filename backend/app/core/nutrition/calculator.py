"""Deterministic BMR, TDEE, safe weekly loss, and calorie target calculations."""

import math
from datetime import date, timedelta

from pydantic import BaseModel, Field

from app.models import ActivityLevel, Gender, Goal, UserProfile

FEMALE_CALORIE_FLOOR = 1200
MALE_CALORIE_FLOOR = 1500

BMR_MALE_OFFSET = 5.0
BMR_FEMALE_OFFSET = -161.0

DEFAULT_LOSS_DEFICIT_KCAL = 400
MIN_LOSS_DEFICIT_KCAL = 300
MAX_LOSS_DEFICIT_KCAL = 500
DEFAULT_GAIN_SURPLUS_KCAL = 300

KCAL_PER_KG = 7700.0
MIN_SAFE_WEEKLY_LOSS_PCT = 0.005
MAX_SAFE_WEEKLY_LOSS_PCT = 0.01
MAX_SAFE_WEEKLY_LOSS_KG = 1.0

ACTIVITY_MULTIPLIERS: dict[ActivityLevel, float] = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.ACTIVE: 1.725,
    ActivityLevel.VERY_ACTIVE: 1.9,
}


class WeeklyLossAssessment(BaseModel):
    """Safety evaluation for a weight-loss rate and target deadline."""

    requested_weekly_loss_kg: float | None
    safe_min_weekly_loss_kg: float
    safe_max_weekly_loss_kg: float
    recommended_weekly_loss_kg: float
    is_realistic: bool
    recommended_weeks: int | None
    safe_target_date: date | None
    warning: str | None = None


class CaloriePlan(BaseModel):
    """Complete deterministic daily calorie plan derived from a user profile."""

    bmr: int
    tdee: int
    target_calories: int
    calorie_floor: int
    floor_applied: bool
    daily_adjustment_kcal: int
    weekly_loss_assessment: WeeklyLossAssessment | None = None
    warnings: list[str] = Field(default_factory=list)


def get_calorie_floor(gender: Gender) -> int:
    """Return the minimum safe daily calorie floor for the given biological sex."""
    return MALE_CALORIE_FLOOR if gender == Gender.MALE else FEMALE_CALORIE_FLOOR


def calculate_bmr(weight_kg: float, height_cm: float, age: int, gender: Gender) -> float:
    """Compute Basal Metabolic Rate (kcal/day) using the Mifflin-St Jeor equation."""
    if weight_kg <= 0 or height_cm <= 0 or age <= 0:
        raise ValueError("weight_kg, height_cm, and age must be positive")
    offset = BMR_MALE_OFFSET if gender == Gender.MALE else BMR_FEMALE_OFFSET
    bmr = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age) + offset
    return round(bmr, 2)


def calculate_tdee(bmr: float, activity_level: ActivityLevel) -> float:
    """Compute Total Daily Energy Expenditure (kcal/day) from BMR and activity level."""
    if bmr <= 0:
        raise ValueError("bmr must be positive")
    return round(bmr * ACTIVITY_MULTIPLIERS[activity_level], 2)


def calculate_safe_weekly_loss(
    weight_kg: float,
    target_weight_kg: float | None,
    target_date: date | None,
    today: date | None = None,
) -> WeeklyLossAssessment:
    """Assess whether a weight-loss goal and deadline fall within safe 0.5-1% weekly bounds."""
    if weight_kg <= 0:
        raise ValueError("weight_kg must be positive")

    ref_today = today if today is not None else date.today()
    if target_date is not None and target_date <= ref_today:
        raise ValueError("target_date must be in the future")

    safe_max = round(min(weight_kg * MAX_SAFE_WEEKLY_LOSS_PCT, MAX_SAFE_WEEKLY_LOSS_KG), 2)
    safe_min = round(min(weight_kg * MIN_SAFE_WEEKLY_LOSS_PCT, safe_max), 2)
    sustainable_rate = round((safe_min + safe_max) / 2, 2)

    if target_weight_kg is None or target_weight_kg >= weight_kg:
        return WeeklyLossAssessment(
            requested_weekly_loss_kg=None,
            safe_min_weekly_loss_kg=safe_min,
            safe_max_weekly_loss_kg=safe_max,
            recommended_weekly_loss_kg=sustainable_rate,
            is_realistic=True,
            recommended_weeks=None,
            safe_target_date=None,
            warning=None,
        )

    kg_to_lose = weight_kg - target_weight_kg
    if target_date is None:
        weeks_needed = math.ceil(kg_to_lose / sustainable_rate)
        return WeeklyLossAssessment(
            requested_weekly_loss_kg=None,
            safe_min_weekly_loss_kg=safe_min,
            safe_max_weekly_loss_kg=safe_max,
            recommended_weekly_loss_kg=sustainable_rate,
            is_realistic=True,
            recommended_weeks=weeks_needed,
            safe_target_date=ref_today + timedelta(weeks=weeks_needed),
            warning=None,
        )

    weeks_available = (target_date - ref_today).days / 7.0
    requested_rate = round(kg_to_lose / weeks_available, 2)

    if requested_rate > safe_max:
        recommended_weeks = math.ceil(kg_to_lose / safe_max)
        safe_date = ref_today + timedelta(weeks=recommended_weeks)
        warning = (
            f"Requested weekly loss ({requested_rate:.2f} kg/week) exceeds safe maximum "
            f"({safe_max:.2f} kg/week). Recommended timeline: {recommended_weeks} weeks "
            f"(by {safe_date.isoformat()})."
        )
        return WeeklyLossAssessment(
            requested_weekly_loss_kg=requested_rate,
            safe_min_weekly_loss_kg=safe_min,
            safe_max_weekly_loss_kg=safe_max,
            recommended_weekly_loss_kg=safe_max,
            is_realistic=False,
            recommended_weeks=recommended_weeks,
            safe_target_date=safe_date,
            warning=warning,
        )

    return WeeklyLossAssessment(
        requested_weekly_loss_kg=requested_rate,
        safe_min_weekly_loss_kg=safe_min,
        safe_max_weekly_loss_kg=safe_max,
        recommended_weekly_loss_kg=requested_rate,
        is_realistic=True,
        recommended_weeks=math.ceil(weeks_available),
        safe_target_date=target_date,
        warning=None,
    )


def calculate_target_calories(
    tdee: float,
    goal: Goal,
    gender: Gender,
    is_high_risk: bool = False,
    daily_deficit_kcal: int = DEFAULT_LOSS_DEFICIT_KCAL,
) -> tuple[int, bool]:
    """Compute safe daily target calories and indicate whether the calorie floor was applied."""
    if tdee <= 0:
        raise ValueError("tdee must be positive")

    if goal == Goal.LOSE:
        if is_high_risk:
            raw_target = round(tdee)
        else:
            clamped_deficit = max(
                MIN_LOSS_DEFICIT_KCAL,
                min(MAX_LOSS_DEFICIT_KCAL, daily_deficit_kcal),
            )
            raw_target = round(tdee - clamped_deficit)
    elif goal == Goal.GAIN:
        raw_target = round(tdee + DEFAULT_GAIN_SURPLUS_KCAL)
    else:
        raw_target = round(tdee)

    floor = get_calorie_floor(gender)
    if raw_target < floor:
        return floor, True
    return raw_target, False


def calculate_calorie_plan(profile: UserProfile, today: date | None = None) -> CaloriePlan:
    """Build a complete, deterministic calorie plan for a validated UserProfile."""
    bmr_exact = calculate_bmr(
        weight_kg=profile.weight_kg,
        height_cm=profile.height_cm,
        age=profile.age,
        gender=profile.gender,
    )
    tdee_exact = calculate_tdee(bmr_exact, profile.activity_level)
    tdee_rounded = round(tdee_exact)

    target_calories, floor_applied = calculate_target_calories(
        tdee=tdee_exact,
        goal=profile.goal,
        gender=profile.gender,
        is_high_risk=profile.is_high_risk,
    )
    calorie_floor = get_calorie_floor(profile.gender)

    warnings: list[str] = []
    if profile.is_high_risk:
        if profile.goal == Goal.LOSE:
            warnings.append(
                "High-risk profile detected: calorie deficit disabled; calories set to "
                "maintenance. Please consult a doctor."
            )
        else:
            warnings.append(
                "High-risk profile detected: limited guidance mode active. Please consult a doctor."
            )

    if floor_applied:
        warnings.append(
            f"Target calories raised to safe minimum floor of {calorie_floor} kcal/day."
        )

    weekly_assessment: WeeklyLossAssessment | None = None
    if profile.goal == Goal.LOSE:
        weekly_assessment = calculate_safe_weekly_loss(
            weight_kg=profile.weight_kg,
            target_weight_kg=profile.target_weight_kg,
            target_date=profile.target_date,
            today=today,
        )
        if weekly_assessment.warning is not None:
            warnings.append(weekly_assessment.warning)

    return CaloriePlan(
        bmr=round(bmr_exact),
        tdee=tdee_rounded,
        target_calories=target_calories,
        calorie_floor=calorie_floor,
        floor_applied=floor_applied,
        daily_adjustment_kcal=target_calories - tdee_rounded,
        weekly_loss_assessment=weekly_assessment,
        warnings=warnings,
    )
