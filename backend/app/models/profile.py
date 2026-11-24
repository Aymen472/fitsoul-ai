"""User profile Pydantic schema, medical/high-risk flags, and validators."""

from collections.abc import Iterable
from datetime import date, time
from enum import StrEnum
from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

MIN_AGE = 18
MAX_AGE = 80
MIN_HEIGHT_CM = 120.0
MAX_HEIGHT_CM = 220.0
MIN_WEIGHT_KG = 30.0
MAX_WEIGHT_KG = 250.0
UNDERWEIGHT_BMI_THRESHOLD = 18.5
DEFAULT_TIMEZONE = "Asia/Karachi"


def _dedupe_preserve_order[T](items: Iterable[T]) -> list[T]:
    """Return unique items while preserving their original order."""
    return list(dict.fromkeys(items))


class Gender(StrEnum):
    """Biological sex used by clinical BMR equations and calorie floors."""

    FEMALE = "female"
    MALE = "male"


class ActivityLevel(StrEnum):
    """Daily activity multiplier categories for TDEE estimation."""

    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


class Goal(StrEnum):
    """Primary body-weight objective."""

    LOSE = "lose"
    MAINTAIN = "maintain"
    GAIN = "gain"


class MedicalCondition(StrEnum):
    """Supported nutrition rule conditions."""

    PCOS = "pcos"
    DIABETES_T2 = "diabetes_t2"
    HYPOTHYROID = "hypothyroid"
    HYPERTENSION = "hypertension"


class HighRiskCondition(StrEnum):
    """Conditions that place a user in limited/doctor-supervision safety mode."""

    DIABETES_T1 = "diabetes_t1"
    KIDNEY_DISEASE = "kidney_disease"
    LIVER_DISEASE = "liver_disease"
    EATING_DISORDER_HISTORY = "eating_disorder_history"


class DietType(StrEnum):
    """Dietary preference."""

    NON_VEG = "non_veg"
    VEG = "veg"
    EGGETARIAN = "eggetarian"


class UserProfile(BaseModel):
    """Validated user health, lifestyle, and scheduling profile."""

    age: int = Field(ge=MIN_AGE, le=MAX_AGE)
    gender: Gender
    height_cm: float = Field(ge=MIN_HEIGHT_CM, le=MAX_HEIGHT_CM)
    weight_kg: float = Field(ge=MIN_WEIGHT_KG, le=MAX_WEIGHT_KG)
    target_weight_kg: float | None = Field(default=None, ge=MIN_WEIGHT_KG, le=MAX_WEIGHT_KG)
    target_date: date | None = None

    activity_level: ActivityLevel
    goal: Goal
    conditions: list[MedicalCondition] = Field(default_factory=list)
    high_risk_conditions: list[HighRiskCondition] = Field(default_factory=list)
    is_pregnant: bool = False
    on_regular_medication: bool = False

    diet_type: DietType = DietType.NON_VEG
    allergies: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)

    timezone: str = DEFAULT_TIMEZONE
    wake_time: time | None = None
    sleep_time: time | None = None
    workout_time: time | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        """Ensure timezone is a valid IANA timezone identifier."""
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Invalid IANA timezone: '{value}'") from exc
        return value

    @field_validator("target_date")
    @classmethod
    def validate_target_date(cls, value: date | None) -> date | None:
        """Ensure target_date, when provided, is strictly in the future."""
        if value is not None and value <= date.today():
            raise ValueError("target_date must be in the future")
        return value

    @field_validator("allergies", "dislikes")
    @classmethod
    def normalize_text_lists(cls, value: list[str]) -> list[str]:
        """Strip, lowercase, drop blanks, and deduplicate free-text food lists."""
        cleaned = (item.strip().lower() for item in value)
        return _dedupe_preserve_order(item for item in cleaned if item)

    @field_validator("conditions", "high_risk_conditions")
    @classmethod
    def dedupe_condition_lists(
        cls,
        value: list[MedicalCondition | HighRiskCondition],
    ) -> list[MedicalCondition | HighRiskCondition]:
        """Deduplicate condition lists while preserving order."""
        return _dedupe_preserve_order(value)

    @model_validator(mode="after")
    def validate_profile_consistency(self) -> Self:
        """Validate cross-field biological and goal constraints."""
        if MedicalCondition.PCOS in self.conditions and self.gender == Gender.MALE:
            raise ValueError("PCOS condition is only applicable to female profiles")
        if self.is_pregnant and self.gender == Gender.MALE:
            raise ValueError("is_pregnant is only applicable to female profiles")

        if self.target_weight_kg is not None:
            if self.goal == Goal.LOSE and self.target_weight_kg >= self.weight_kg:
                raise ValueError(
                    "For weight loss goal, target_weight_kg must be less than current weight_kg"
                )
            if self.goal == Goal.GAIN and self.target_weight_kg <= self.weight_kg:
                raise ValueError(
                    "For weight gain goal, target_weight_kg must be greater than current weight_kg"
                )

        return self

    @computed_field
    @property
    def bmi(self) -> float:
        """Body Mass Index (kg/m^2), rounded to one decimal place."""
        height_m = self.height_cm / 100
        return round(self.weight_kg / (height_m**2), 1)

    @computed_field
    @property
    def high_risk_reasons(self) -> list[str]:
        """Reasons why the profile requires limited mode and doctor supervision."""
        reasons: list[str] = []
        if self.bmi < UNDERWEIGHT_BMI_THRESHOLD:
            reasons.append("underweight_bmi")
        if self.is_pregnant:
            reasons.append("pregnancy")
        reasons.extend(condition.value for condition in self.high_risk_conditions)
        return reasons

    @computed_field
    @property
    def is_high_risk(self) -> bool:
        """True if any high-risk health flag or condition is present."""
        return bool(self.high_risk_reasons)

    @computed_field
    @property
    def supplements_allowed(self) -> bool:
        """Disable supplement guidance for high-risk users or regular medication."""
        return not self.is_high_risk and not self.on_regular_medication
