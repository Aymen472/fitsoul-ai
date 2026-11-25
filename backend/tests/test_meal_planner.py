"""Unit and integration tests for meal plan validator, AI retries, fallback, and grocery list."""

import json
from datetime import date, timedelta

import httpx
import pytest

from app.ai import AIMealPlanner, GeminiClient
from app.core.nutrition import get_calorie_floor, get_food_db
from app.core.rules import get_nutrition_targets
from app.core.safety import PlannedMealItem, RawDailyMealPlan, validate_meal_plan
from app.models import (
    ActivityLevel,
    DietType,
    Gender,
    Goal,
    HighRiskCondition,
    MedicalCondition,
    UserProfile,
)


def _make_profile(**overrides: object) -> UserProfile:
    """Build a valid baseline profile for meal planner tests."""
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


def _gemini_json_response(raw_plan: RawDailyMealPlan) -> httpx.Response:
    payload = {
        "candidates": [{"content": {"parts": [{"text": raw_plan.model_dump_json()}]}}],
        "usageMetadata": {
            "promptTokenCount": 500,
            "candidatesTokenCount": 200,
            "totalTokenCount": 700,
        },
    }
    return httpx.Response(200, text=json.dumps(payload))


def _valid_pcos_raw_plan() -> RawDailyMealPlan:
    """Valid ~1376 kcal, >=103g protein, <=108g carbs desi PCOS plan."""
    return RawDailyMealPlan(
        breakfast=[
            PlannedMealItem(food_id="boiled_egg", servings=2.0),
            PlannedMealItem(food_id="greek_yogurt", servings=1.0),
            PlannedMealItem(food_id="almonds", servings=1.0),
        ],
        lunch=[
            PlannedMealItem(food_id="grilled_chicken_breast", servings=1.0),
            PlannedMealItem(food_id="roti_whole_wheat", servings=1.0),
            PlannedMealItem(food_id="kachumber_salad", servings=1.0),
        ],
        snack=[
            PlannedMealItem(food_id="bhune_chanay", servings=1.0),
        ],
        dinner=[
            PlannedMealItem(food_id="grilled_rahu_fish", servings=1.0),
            PlannedMealItem(food_id="roti_whole_wheat", servings=1.0),
            PlannedMealItem(food_id="green_salad", servings=1.0),
        ],
        notes="Balanced desi PCOS plan",
    )


def test_validator_accepts_valid_pcos_plan() -> None:
    profile = _make_profile(conditions=[MedicalCondition.PCOS])
    targets = get_nutrition_targets(profile)
    db = get_food_db()
    allowed = db.filter_for_targets(targets, diet_type=profile.diet_type)

    result = validate_meal_plan(_valid_pcos_raw_plan(), profile, targets, allowed)

    assert result.is_valid is True
    assert result.errors == []
    assert result.validated_plan is not None
    assert abs(result.validated_plan.total_kcal - targets.calories) <= targets.calories * 0.05
    assert result.validated_plan.total_protein_g >= targets.protein_g


def test_validator_rejects_hallucinated_and_forbidden_foods() -> None:
    profile = _make_profile(conditions=[MedicalCondition.PCOS])
    targets = get_nutrition_targets(profile)
    db = get_food_db()
    allowed = db.filter_for_targets(targets, diet_type=profile.diet_type)

    bad_plan = _valid_pcos_raw_plan()
    bad_plan.snack.append(PlannedMealItem(food_id="unicorn_cake", servings=1.0))
    bad_plan.dinner.append(PlannedMealItem(food_id="gulab_jamun", servings=1.0))

    result = validate_meal_plan(bad_plan, profile, targets, allowed)

    assert result.is_valid is False
    assert any("unicorn_cake" in err for err in result.errors)
    assert any("gulab_jamun" in err for err in result.errors)


def test_validator_rejects_calorie_floor_and_deviation_breach() -> None:
    # Small female hitting 1200 floor
    profile = _make_profile(age=45, height_cm=150.0, weight_kg=48.0)
    targets = get_nutrition_targets(profile)
    db = get_food_db()
    allowed = db.filter_for_targets(targets, diet_type=profile.diet_type)

    starvation_plan = RawDailyMealPlan(
        breakfast=[PlannedMealItem(food_id="boiled_egg", servings=1.0)],
        lunch=[PlannedMealItem(food_id="grilled_chicken_breast", servings=1.0)],
        snack=[PlannedMealItem(food_id="apple", servings=1.0)],
        dinner=[PlannedMealItem(food_id="daal_moong", servings=1.0)],
    )

    result = validate_meal_plan(starvation_plan, profile, targets, allowed)

    assert result.is_valid is False
    assert any("below safe floor" in err for err in result.errors)
    assert any("±5%" in err for err in result.errors)


def test_validator_rejects_diabetes_per_meal_carb_cap_and_hypertension_sodium() -> None:
    profile = _make_profile(
        conditions=[MedicalCondition.DIABETES_T2, MedicalCondition.HYPERTENSION],
    )
    targets = get_nutrition_targets(profile)
    db = get_food_db()
    allowed = db.filter_for_targets(targets, diet_type=profile.diet_type)

    plan = RawDailyMealPlan(
        breakfast=[
            PlannedMealItem(food_id="roti_whole_wheat", servings=3.0),  # 70.5g carbs > 45g cap
        ],
        lunch=[PlannedMealItem(food_id="chicken_karahi", servings=3.0)],  # 1830 mg sodium > 1500
        snack=[PlannedMealItem(food_id="bhune_chanay", servings=1.0)],
        dinner=[PlannedMealItem(food_id="grilled_chicken_breast", servings=1.0)],
    )

    result = validate_meal_plan(plan, profile, targets, allowed)

    assert result.is_valid is False
    assert any("per-meal limit" in err for err in result.errors)
    assert any("sodium" in err.lower() for err in result.errors)


def test_ai_planner_retries_with_validation_feedback_then_succeeds() -> None:
    profile = _make_profile(conditions=[MedicalCondition.PCOS])
    prompts_seen: list[str] = []

    forbidden_plan = _valid_pcos_raw_plan()
    forbidden_plan.snack = [PlannedMealItem(food_id="gulab_jamun", servings=1.0)]

    low_cal_plan = RawDailyMealPlan(
        breakfast=[PlannedMealItem(food_id="boiled_egg", servings=1.0)],
        lunch=[PlannedMealItem(food_id="grilled_chicken_breast", servings=1.0)],
        snack=[PlannedMealItem(food_id="almonds", servings=1.0)],
        dinner=[PlannedMealItem(food_id="green_salad", servings=1.0)],
    )
    good_plan = _valid_pcos_raw_plan()

    responses = [forbidden_plan, low_cal_plan, good_plan]

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        prompts_seen.append(body["contents"][0]["parts"][0]["text"])
        return _gemini_json_response(responses[len(prompts_seen) - 1])

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        gemini = GeminiClient(api_key="test-key", client=http_client, trace_sink=lambda _: None)
        planner = AIMealPlanner(gemini_client=gemini, max_attempts=3)
        plan = planner.generate_daily_plan(profile)

    assert len(prompts_seen) == 3
    assert "gulab_jamun" in prompts_seen[1]
    assert "Previous attempt failed validation" in prompts_seen[1]
    assert "±5%" in prompts_seen[2]
    assert plan.used_fallback is False
    assert plan.attempts_used == 3


def test_ai_planner_falls_back_after_invalid_retries_or_api_error() -> None:
    profile = _make_profile(conditions=[MedicalCondition.PCOS])
    bad_plan = RawDailyMealPlan(
        breakfast=[PlannedMealItem(food_id="nonexistent_food", servings=1.0)],
        lunch=[PlannedMealItem(food_id="grilled_chicken_breast", servings=1.0)],
        snack=[PlannedMealItem(food_id="almonds", servings=1.0)],
        dinner=[PlannedMealItem(food_id="green_salad", servings=1.0)],
    )

    transport = httpx.MockTransport(lambda _: _gemini_json_response(bad_plan))
    with httpx.Client(transport=transport) as http_client:
        gemini = GeminiClient(api_key="test-key", client=http_client, trace_sink=lambda _: None)
        planner = AIMealPlanner(gemini_client=gemini, max_attempts=3)
        plan = planner.generate_daily_plan(profile)

    assert plan.used_fallback is True
    assert plan.attempts_used == 3
    assert plan.total_kcal >= get_calorie_floor(profile.gender)

    # Also verify graceful fallback when Gemini API key is missing / failing
    offline_client = GeminiClient(api_key="", trace_sink=lambda _: None)
    offline_planner = AIMealPlanner(gemini_client=offline_client)
    offline_plan = offline_planner.generate_daily_plan(profile)
    assert offline_plan.used_fallback is True
    assert offline_plan.attempts_used == 1


TWENTY_TEST_PROFILES: list[tuple[str, UserProfile]] = [
    ("01_pcos_non_veg", _make_profile(conditions=[MedicalCondition.PCOS])),
    (
        "02_pcos_veg",
        _make_profile(conditions=[MedicalCondition.PCOS], diet_type=DietType.VEG),
    ),
    (
        "03_pcos_eggetarian",
        _make_profile(conditions=[MedicalCondition.PCOS], diet_type=DietType.EGGETARIAN),
    ),
    (
        "04_diabetes_male_lose",
        _make_profile(
            age=42,
            gender=Gender.MALE,
            height_cm=175.0,
            weight_kg=88.0,
            activity_level=ActivityLevel.LIGHT,
            conditions=[MedicalCondition.DIABETES_T2],
        ),
    ),
    (
        "05_diabetes_female_maintain",
        _make_profile(
            age=48,
            height_cm=160.0,
            weight_kg=68.0,
            goal=Goal.MAINTAIN,
            conditions=[MedicalCondition.DIABETES_T2],
        ),
    ),
    (
        "06_hypertension_male",
        _make_profile(
            age=50,
            gender=Gender.MALE,
            height_cm=172.0,
            weight_kg=85.0,
            activity_level=ActivityLevel.MODERATE,
            conditions=[MedicalCondition.HYPERTENSION],
        ),
    ),
    (
        "07_hypertension_female",
        _make_profile(
            age=44,
            height_cm=158.0,
            weight_kg=66.0,
            goal=Goal.MAINTAIN,
            conditions=[MedicalCondition.HYPERTENSION],
        ),
    ),
    (
        "08_hypothyroid_female",
        _make_profile(
            age=33,
            height_cm=163.0,
            weight_kg=74.0,
            conditions=[MedicalCondition.HYPOTHYROID],
        ),
    ),
    (
        "09_multi_pcos_diabetes_htn",
        _make_profile(
            age=31,
            height_cm=162.0,
            weight_kg=78.0,
            activity_level=ActivityLevel.MODERATE,
            conditions=[
                MedicalCondition.PCOS,
                MedicalCondition.DIABETES_T2,
                MedicalCondition.HYPERTENSION,
            ],
        ),
    ),
    (
        "10_multi_diabetes_htn_male",
        _make_profile(
            age=52,
            gender=Gender.MALE,
            height_cm=176.0,
            weight_kg=92.0,
            activity_level=ActivityLevel.MODERATE,
            conditions=[MedicalCondition.DIABETES_T2, MedicalCondition.HYPERTENSION],
        ),
    ),
    (
        "11_small_female_1200_floor",
        _make_profile(age=45, height_cm=150.0, weight_kg=48.0, goal=Goal.LOSE),
    ),
    (
        "12_small_male_1500_floor",
        _make_profile(age=50, gender=Gender.MALE, height_cm=160.0, weight_kg=55.0, goal=Goal.LOSE),
    ),
    (
        "13_tall_active_male_high_cal",
        _make_profile(
            age=26,
            gender=Gender.MALE,
            height_cm=188.0,
            weight_kg=92.0,
            activity_level=ActivityLevel.VERY_ACTIVE,
            goal=Goal.MAINTAIN,
        ),
    ),
    (
        "14_muscle_gain_male",
        _make_profile(
            age=24,
            gender=Gender.MALE,
            height_cm=178.0,
            weight_kg=64.0,
            target_weight_kg=70.0,
            activity_level=ActivityLevel.ACTIVE,
            goal=Goal.GAIN,
        ),
    ),
    (
        "15_muscle_gain_female_egg",
        _make_profile(
            age=25,
            height_cm=164.0,
            weight_kg=52.0,
            target_weight_kg=56.0,
            activity_level=ActivityLevel.MODERATE,
            goal=Goal.GAIN,
            diet_type=DietType.EGGETARIAN,
        ),
    ),
    (
        "16_pregnant_high_risk",
        _make_profile(
            age=29,
            height_cm=162.0,
            weight_kg=68.0,
            activity_level=ActivityLevel.LIGHT,
            goal=Goal.MAINTAIN,
            is_pregnant=True,
        ),
    ),
    (
        "17_underweight_high_risk",
        _make_profile(
            age=22,
            height_cm=165.0,
            weight_kg=47.0,
            target_weight_kg=53.0,
            goal=Goal.GAIN,
        ),
    ),
    (
        "18_dairy_allergy_male",
        _make_profile(
            age=34,
            gender=Gender.MALE,
            height_cm=177.0,
            weight_kg=82.0,
            activity_level=ActivityLevel.MODERATE,
            allergies=["dairy"],
        ),
    ),
    (
        "19_nut_allergy_karela_dislike_pcos",
        _make_profile(
            age=27,
            height_cm=161.0,
            weight_kg=71.0,
            conditions=[MedicalCondition.PCOS],
            allergies=["nuts", "peanuts"],
            dislikes=["karela"],
        ),
    ),
    (
        "20_bride_transformation_t1_flag",
        _make_profile(
            age=26,
            height_cm=164.0,
            weight_kg=70.0,
            target_weight_kg=62.0,
            target_date=date.today() + timedelta(days=90),
            activity_level=ActivityLevel.MODERATE,
            high_risk_conditions=[HighRiskCondition.EATING_DISORDER_HISTORY],
        ),
    ),
]


@pytest.mark.parametrize(("label", "profile"), TWENTY_TEST_PROFILES)
def test_twenty_diverse_profiles_produce_100_percent_valid_plans(
    label: str, profile: UserProfile
) -> None:
    targets = get_nutrition_targets(profile)
    planner = AIMealPlanner(gemini_client=GeminiClient(api_key="", trace_sink=lambda _: None))

    plan = planner.generate_daily_plan(profile)

    assert len(plan.meals) == 4, f"{label}: expected 4 meals"
    assert plan.total_kcal >= get_calorie_floor(profile.gender), f"{label}: below floor"
    assert abs(plan.total_kcal - targets.calories) <= targets.calories * 0.05, (
        f"{label}: {plan.total_kcal} outside ±5% of {targets.calories}"
    )
    assert plan.total_protein_g >= targets.protein_g, f"{label}: low protein"
    assert plan.total_sodium_mg <= targets.sodium_mg_max, f"{label}: sodium too high"
    if targets.max_carbs_per_meal_g is not None:
        for meal in plan.meals:
            assert meal.carbs <= targets.max_carbs_per_meal_g, (
                f"{label}: {meal.meal_type} carbs {meal.carbs} > {targets.max_carbs_per_meal_g}"
            )


def test_weekly_plan_and_grocery_list_aggregation() -> None:
    profile = _make_profile(conditions=[MedicalCondition.PCOS])
    planner = AIMealPlanner(gemini_client=GeminiClient(api_key="", trace_sink=lambda _: None))

    weekly = planner.generate_weekly_plan(profile, days=7)

    assert len(weekly.days) == 7
    assert weekly.grocery_list
    first_item = weekly.grocery_list[0]
    expected_grams = round(
        sum(
            item.grams
            for day in weekly.days
            for meal in day.meals
            for item in meal.items
            if item.food_id == first_item.food_id
        ),
        1,
    )
    assert first_item.total_grams == expected_grams
