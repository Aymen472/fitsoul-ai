"""Repository layer for user profiles, deterministic nutrition targets, and food seeding."""

from datetime import date

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.nutrition import FoodItem
from app.core.rules import NutritionTargets, get_nutrition_targets
from app.db.tables import FoodRow, NutritionTargetRow, ProfileRow, UserRow
from app.models import (
    ActivityLevel,
    DietType,
    Gender,
    Goal,
    HighRiskCondition,
    MedicalCondition,
    UserProfile,
)


class ProfileRecord(BaseModel):
    """Persisted user profile combined with computed nutrition targets."""

    user_id: str
    email: str | None = None
    full_name: str | None = None
    phone: str | None = None
    profile: UserProfile
    targets: NutritionTargets


class ProfileRepository:
    """Data-access operations for user profiles, targets, and food catalog seeding."""

    @staticmethod
    def upsert_profile(
        session: Session,
        user_id: str,
        profile: UserProfile,
        email: str | None = None,
        full_name: str | None = None,
        phone: str | None = None,
        today: date | None = None,
    ) -> ProfileRecord:
        """Create or update a user, their health profile, and computed nutrition targets."""
        user_row = session.get(UserRow, user_id)
        if user_row is None:
            user_row = UserRow(
                id=user_id,
                email=email,
                full_name=full_name,
                phone=phone,
            )
            session.add(user_row)
            session.flush()
        else:
            if email is not None:
                user_row.email = email
            if full_name is not None:
                user_row.full_name = full_name
            if phone is not None:
                user_row.phone = phone

        targets = get_nutrition_targets(profile, today=today)

        profile_row = ProfileRow(
            user_id=user_id,
            age=profile.age,
            gender=profile.gender.value,
            height_cm=profile.height_cm,
            weight_kg=profile.weight_kg,
            target_weight_kg=profile.target_weight_kg,
            target_date=profile.target_date,
            activity_level=profile.activity_level.value,
            goal=profile.goal.value,
            conditions=[c.value for c in profile.conditions],
            high_risk_conditions=[c.value for c in profile.high_risk_conditions],
            is_pregnant=profile.is_pregnant,
            on_regular_medication=profile.on_regular_medication,
            diet_type=profile.diet_type.value,
            allergies=list(profile.allergies),
            dislikes=list(profile.dislikes),
            timezone=profile.timezone,
            wake_time=profile.wake_time,
            sleep_time=profile.sleep_time,
            workout_time=profile.workout_time,
            bmi=profile.bmi,
            is_high_risk=profile.is_high_risk,
            high_risk_reasons=list(profile.high_risk_reasons),
            supplements_allowed=profile.supplements_allowed,
        )
        session.merge(profile_row)

        target_row = NutritionTargetRow(
            user_id=user_id,
            calories=targets.calories,
            bmr=targets.bmr,
            tdee=targets.tdee,
            protein_g=targets.protein_g,
            carbs_g=targets.carbs_g,
            fat_g=targets.fat_g,
            fiber_g=targets.fiber_g,
            water_ml=targets.water_ml,
            sodium_mg_max=targets.sodium_mg_max,
            max_carbs_per_meal_g=targets.max_carbs_per_meal_g,
            forbidden_tags=list(targets.forbidden_tags),
            required_tags=list(targets.required_tags),
            applied_rules=list(targets.applied_rules),
            warnings=list(targets.warnings),
        )
        session.merge(target_row)
        session.commit()

        return ProfileRecord(
            user_id=user_id,
            email=user_row.email,
            full_name=user_row.full_name,
            phone=user_row.phone,
            profile=profile,
            targets=targets,
        )

    @staticmethod
    def get_profile(session: Session, user_id: str) -> ProfileRecord | None:
        """Fetch a saved user profile and its computed nutrition targets."""
        user_row = session.get(UserRow, user_id)
        profile_row = session.get(ProfileRow, user_id)
        target_row = session.get(NutritionTargetRow, user_id)
        if user_row is None or profile_row is None or target_row is None:
            return None

        # Use model_construct so historical profiles whose target_date has passed remain readable.
        profile = UserProfile.model_construct(
            age=profile_row.age,
            gender=Gender(profile_row.gender),
            height_cm=profile_row.height_cm,
            weight_kg=profile_row.weight_kg,
            target_weight_kg=profile_row.target_weight_kg,
            target_date=profile_row.target_date,
            activity_level=ActivityLevel(profile_row.activity_level),
            goal=Goal(profile_row.goal),
            conditions=[MedicalCondition(c) for c in profile_row.conditions],
            high_risk_conditions=[HighRiskCondition(c) for c in profile_row.high_risk_conditions],
            is_pregnant=profile_row.is_pregnant,
            on_regular_medication=profile_row.on_regular_medication,
            diet_type=DietType(profile_row.diet_type),
            allergies=list(profile_row.allergies),
            dislikes=list(profile_row.dislikes),
            timezone=profile_row.timezone,
            wake_time=profile_row.wake_time,
            sleep_time=profile_row.sleep_time,
            workout_time=profile_row.workout_time,
        )
        targets = NutritionTargets.model_validate(target_row, from_attributes=True)

        return ProfileRecord(
            user_id=user_id,
            email=user_row.email,
            full_name=user_row.full_name,
            phone=user_row.phone,
            profile=profile,
            targets=targets,
        )

    @staticmethod
    def seed_foods(session: Session, foods: list[FoodItem]) -> int:
        """Idempotently upsert food catalog items into the foods table."""
        for food in foods:
            session.merge(
                FoodRow(
                    id=food.id,
                    name=food.name,
                    urdu_name=food.urdu_name,
                    aliases=list(food.aliases),
                    category=food.category,
                    serving_desc=food.serving_desc,
                    grams=food.grams,
                    kcal=food.kcal,
                    protein=food.protein,
                    carbs=food.carbs,
                    fat=food.fat,
                    fiber=food.fiber,
                    sodium_mg=food.sodium_mg,
                    gi_category=food.gi_category.value,
                    tags=list(food.tags),
                )
            )
        session.commit()
        return len(foods)
