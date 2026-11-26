"""AI personalized Pakistani meal planner with deterministic validator and fallback."""

from collections.abc import Callable
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from app.ai.client import GeminiClient, GeminiClientError
from app.core.nutrition import FoodDatabase, FoodItem, get_calorie_floor, get_food_db
from app.core.rules import NutritionTargets, get_nutrition_targets
from app.core.safety import (
    CALORIE_TOLERANCE_RATIO,
    MealType,
    PlannedMealItem,
    RawDailyMealPlan,
    ValidatedMeal,
    ValidatedMealPlan,
    validate_meal_plan,
)
from app.models import UserProfile

DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "meal_planner_system.txt"

SERVING_STEP = 0.25
MAX_FALLBACK_SERVINGS = 5.0
MAX_ITEMS_PER_MEAL = 8
LOW_SODIUM_CUTOFF_MG = 350.0


class GroceryItem(BaseModel):
    """Aggregated weekly grocery item derived from validated meal plans."""

    food_id: str
    name: str
    urdu_name: str
    category: str
    total_servings: float
    total_grams: float


class WeeklyMealPlan(BaseModel):
    """Multi-day validated meal plan paired with a consolidated grocery list."""

    days: list[ValidatedMealPlan]
    grocery_list: list[GroceryItem]


class MealSwapResult(BaseModel):
    """Validated replacement meal alongside updated daily totals and grocery items."""

    day_index: int
    meal_type: MealType
    meal: ValidatedMeal
    updated_day: ValidatedMealPlan
    day_grocery_items: list[GroceryItem]


def build_grocery_list(
    days: list[ValidatedMealPlan],
    food_db: FoodDatabase,
) -> list[GroceryItem]:
    """Aggregate servings and grams across validated daily plans."""
    totals: dict[str, tuple[float, float]] = {}
    for day in days:
        for meal in day.meals:
            for item in meal.items:
                prev_servings, prev_grams = totals.get(item.food_id, (0.0, 0.0))
                totals[item.food_id] = (
                    prev_servings + item.servings,
                    prev_grams + item.grams,
                )

    grocery: list[GroceryItem] = []
    for food_id, (total_servings, total_grams) in totals.items():
        food = food_db.get_by_id(food_id)
        grocery.append(
            GroceryItem(
                food_id=food_id,
                name=food.name if food is not None else food_id,
                urdu_name=food.urdu_name if food is not None else "",
                category=food.category if food is not None else "other",
                total_servings=round(total_servings, 2),
                total_grams=round(total_grams, 1),
            )
        )

    grocery.sort(key=lambda entry: (entry.category, entry.name))
    return grocery


class _FallbackBuilder:
    """Constructive deterministic meal builder that satisfies all safety constraints."""

    def __init__(
        self,
        profile: UserProfile,
        targets: NutritionTargets,
        allowed_foods: list[FoodItem],
    ) -> None:
        self.profile = profile
        self.targets = targets
        self.allowed_foods = allowed_foods
        self.floor = float(get_calorie_floor(profile.gender))
        self.max_kcal = targets.calories * (1.0 + CALORIE_TOLERANCE_RATIO * 0.9)
        self.min_kcal = max(self.floor, targets.calories * 0.97)
        self.carb_restricted = bool({"pcos", "diabetes_t2"} & set(targets.applied_rules))
        self.max_daily_carbs = targets.carbs_g * 1.03 if self.carb_restricted else float("inf")

        self.meals: dict[MealType, dict[str, float]] = {
            MealType.BREAKFAST: {},
            MealType.LUNCH: {},
            MealType.SNACK: {},
            MealType.DINNER: {},
        }
        self.by_id = {f.id: f for f in allowed_foods}

    def _totals(self) -> tuple[float, float, float, float]:
        kcal = 0.0
        protein = 0.0
        carbs = 0.0
        sodium = 0.0
        for slot in self.meals.values():
            for food_id, servings in slot.items():
                scaled = self.by_id[food_id].scale(servings)
                kcal += scaled.kcal
                protein += scaled.protein
                carbs += scaled.carbs
                sodium += scaled.sodium_mg
        return kcal, protein, carbs, sodium

    def _totals_with(
        self, meal_type: MealType, food: FoodItem, new_servings: float
    ) -> tuple[float, float, float, float, float]:
        """Compute exact post-update daily totals and target meal carbs without rounding drift."""
        kcal = 0.0
        protein = 0.0
        carbs = 0.0
        sodium = 0.0
        meal_carbs = 0.0
        for slot_type, slot in self.meals.items():
            seen_target = False
            for fid, srv in slot.items():
                effective = new_servings if (slot_type == meal_type and fid == food.id) else srv
                if slot_type == meal_type and fid == food.id:
                    seen_target = True
                scaled = self.by_id[fid].scale(effective)
                kcal += scaled.kcal
                protein += scaled.protein
                carbs += scaled.carbs
                sodium += scaled.sodium_mg
                if slot_type == meal_type:
                    meal_carbs += scaled.carbs
            if slot_type == meal_type and not seen_target:
                scaled = food.scale(new_servings)
                kcal += scaled.kcal
                protein += scaled.protein
                carbs += scaled.carbs
                sodium += scaled.sodium_mg
                meal_carbs += scaled.carbs
        return (
            round(kcal, 1),
            round(protein, 1),
            round(carbs, 1),
            round(sodium, 1),
            round(meal_carbs, 1),
        )

    def _can_add(self, meal_type: MealType, food: FoodItem, delta: float) -> bool:
        slot = self.meals[meal_type]
        current_servings = slot.get(food.id, 0.0)
        if current_servings == 0.0 and len(slot) >= MAX_ITEMS_PER_MEAL:
            return False
        new_servings = round(current_servings + delta, 2)
        if new_servings > MAX_FALLBACK_SERVINGS:
            return False

        kcal, _, carbs, sodium, meal_carbs = self._totals_with(meal_type, food, new_servings)
        if kcal > self.max_kcal:
            return False
        if sodium > self.targets.sodium_mg_max:
            return False
        if carbs > self.max_daily_carbs:
            return False
        return (
            self.targets.max_carbs_per_meal_g is None
            or meal_carbs <= self.targets.max_carbs_per_meal_g
        )

    def _try_add(self, meal_type: MealType, food: FoodItem, delta: float) -> bool:
        if not self._can_add(meal_type, food, delta):
            return False
        slot = self.meals[meal_type]
        slot[food.id] = round(slot.get(food.id, 0.0) + delta, 2)
        return True

    def _seed_slot(self, meal_type: MealType, candidates: list[FoodItem], day_index: int) -> None:
        if not candidates:
            return
        n = len(candidates)
        for offset in range(n):
            food = candidates[(day_index + offset) % n]
            for initial_servings in (1.0, 0.5, 0.25):
                if self._try_add(meal_type, food, initial_servings):
                    return

    def _boost_from_pool(
        self,
        pool: list[FoodItem],
        meal_order: list[MealType],
        should_continue: Callable[[], bool],
        *,
        prefer_existing: bool = True,
    ) -> None:
        pool_ids = {f.id for f in pool}
        while should_continue():
            progressed = False
            for meal_type in meal_order:
                if not should_continue():
                    return
                if prefer_existing:
                    existing = [self.by_id[fid] for fid in self.meals[meal_type]]
                    candidates = existing + [f for f in pool if f.id not in self.meals[meal_type]]
                else:
                    existing_in_pool = [
                        self.by_id[fid] for fid in self.meals[meal_type] if fid in pool_ids
                    ]
                    candidates = existing_in_pool + [
                        f for f in pool if f.id not in self.meals[meal_type]
                    ]
                for food in candidates:
                    if self._try_add(meal_type, food, SERVING_STEP):
                        progressed = True
                        break
            if not progressed:
                break

    def build(self, day_index: int = 0) -> RawDailyMealPlan:
        """Assemble and adjust a deterministic, rule-compliant 4-meal plan."""
        low_sodium_strict = self.targets.sodium_mg_max <= 1600
        ordered = sorted(
            self.allowed_foods,
            key=lambda f: (
                1 if (low_sodium_strict and f.sodium_mg > LOW_SODIUM_CUTOFF_MG) else 0,
                -(f.protein / max(f.kcal, 1.0)),
                f.id,
            ),
        )

        proteins = [f for f in ordered if f.protein >= 5.0]
        lean_proteins = sorted(
            [f for f in ordered if f.protein >= 3.5],
            key=lambda f: (
                1 if (low_sodium_strict and f.sodium_mg > LOW_SODIUM_CUTOFF_MG) else 0,
                -(f.protein / max(f.kcal, 1.0)),
                f.carbs,
                f.id,
            ),
        )
        breakfast_pool = [
            f
            for f in ordered
            if f.category in {"breakfast", "eggs_dairy"} and (f.protein >= 3.0 or f.fiber >= 2.0)
        ] or lean_proteins
        carb_staples = sorted(
            [
                f
                for f in ordered
                if f.category in {"bread", "rice", "daal", "breakfast", "snacks", "fruit"}
                and f.carbs >= 10.0
                and f.kcal > 0
            ],
            key=lambda f: (
                1 if (low_sodium_strict and f.sodium_mg > LOW_SODIUM_CUTOFF_MG) else 0,
                -f.fiber,
                f.id,
            ),
        )
        veggie_sides = [
            f for f in ordered if f.category in {"sabzi", "salad_condiment"} and f.kcal >= 15.0
        ]
        healthy_fats = sorted(
            [
                f
                for f in ordered
                if (f.fat >= 4.0 and f.carbs <= 8.0)
                or f.id in {"almonds", "walnuts", "pistachios", "olive_oil", "desi_ghee"}
            ],
            key=lambda f: (
                1 if (low_sodium_strict and f.sodium_mg > LOW_SODIUM_CUTOFF_MG) else 0,
                f.carbs,
                -f.kcal,
                f.id,
            ),
        )
        snack_pool = [
            f for f in ordered if f.category in {"snacks", "fruit", "eggs_dairy"}
        ] or ordered

        # Seed all four meals cleanly (1 core item per meal first)
        self._seed_slot(MealType.BREAKFAST, breakfast_pool, day_index)
        self._seed_slot(MealType.LUNCH, proteins or ordered, day_index)
        self._seed_slot(MealType.SNACK, snack_pool, day_index)
        self._seed_slot(MealType.DINNER, proteins or ordered, day_index + 1)

        meal_order = [MealType.LUNCH, MealType.DINNER, MealType.BREAKFAST, MealType.SNACK]

        # Step 1: Ensure protein target is met with leanest/lowest-carb proteins first
        high_density_proteins = [
            f for f in lean_proteins if (f.protein / max(f.kcal, 1.0)) >= 0.06
        ] or lean_proteins
        self._boost_from_pool(
            high_density_proteins or ordered,
            meal_order,
            lambda: self._totals()[1] < self.targets.protein_g,
            prefer_existing=False,
        )

        # Add staples/veggies if calorie & carb budget permits
        self._seed_slot(MealType.LUNCH, carb_staples, day_index)
        self._seed_slot(MealType.DINNER, veggie_sides or carb_staples, day_index + 1)

        # Step 2: Fill healthy carbs up toward 90% of target while leaving calorie room
        self._boost_from_pool(
            carb_staples + veggie_sides,
            [MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER, MealType.SNACK],
            lambda: (
                self._totals()[2] < self.targets.carbs_g * 0.9
                and self._totals()[0] < self.targets.calories * 0.94
            ),
        )

        # Step 3: Close remaining calorie gap using calorie-dense fats/proteins/staples
        calorie_pool = sorted(
            healthy_fats + lean_proteins + carb_staples + ordered,
            key=lambda f: (
                1 if (low_sodium_strict and f.sodium_mg > LOW_SODIUM_CUTOFF_MG) else 0,
                -f.kcal,
                f.id,
            ),
        )
        self._boost_from_pool(
            calorie_pool,
            [MealType.SNACK, MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER],
            lambda: self._totals()[0] < self.min_kcal,
            prefer_existing=False,
        )

        # Safety trim if slightly above upper bound while keeping protein target & non-empty meals
        while self._totals()[0] > self.max_kcal:
            trimmed = False
            for meal_type in meal_order:
                slot = self.meals[meal_type]
                for food_id in sorted(slot, key=lambda fid: -self.by_id[fid].kcal):
                    current = slot[food_id]
                    if current <= SERVING_STEP and len(slot) == 1:
                        continue
                    step_food = self.by_id[food_id].scale(SERVING_STEP)
                    if self._totals()[1] - step_food.protein < self.targets.protein_g:
                        continue
                    new_servings = round(current - SERVING_STEP, 2)
                    if new_servings <= 0:
                        del slot[food_id]
                    else:
                        slot[food_id] = new_servings
                    trimmed = True
                    break
                if trimmed:
                    break
            if not trimmed:
                break

        return RawDailyMealPlan(
            breakfast=[
                PlannedMealItem(food_id=fid, servings=servings)
                for fid, servings in self.meals[MealType.BREAKFAST].items()
            ],
            lunch=[
                PlannedMealItem(food_id=fid, servings=servings)
                for fid, servings in self.meals[MealType.LUNCH].items()
            ],
            snack=[
                PlannedMealItem(food_id=fid, servings=servings)
                for fid, servings in self.meals[MealType.SNACK].items()
            ],
            dinner=[
                PlannedMealItem(food_id=fid, servings=servings)
                for fid, servings in self.meals[MealType.DINNER].items()
            ],
            notes="Generated by deterministic fallback meal planner.",
        )


def build_fallback_meal_plan(
    profile: UserProfile,
    targets: NutritionTargets,
    allowed_foods: list[FoodItem],
    day_index: int = 0,
) -> RawDailyMealPlan:
    """Build a deterministic, rule-compliant Pakistani meal plan without calling an LLM."""
    return _FallbackBuilder(profile, targets, allowed_foods).build(day_index=day_index)


class AIMealPlanner:
    """Orchestrates Gemini structured meal planning with deterministic validation and fallback."""

    def __init__(
        self,
        gemini_client: GeminiClient | None = None,
        food_db: FoodDatabase | None = None,
        max_attempts: int = 3,
        system_prompt_path: Path = DEFAULT_PROMPT_PATH,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.gemini_client = gemini_client if gemini_client is not None else GeminiClient()
        self.food_db = food_db if food_db is not None else get_food_db()
        self.max_attempts = max_attempts
        self.system_prompt = system_prompt_path.read_text(encoding="utf-8")

    @staticmethod
    def _format_allowed_menu(allowed_foods: list[FoodItem]) -> str:
        lines = [
            f"{f.id} | {f.name} | {f.serving_desc} | {f.kcal:.0f} kcal | "
            f"P:{f.protein}g C:{f.carbs}g F:{f.fat}g Na:{f.sodium_mg:.0f}mg"
            for f in allowed_foods
        ]
        return "\n".join(lines)

    def _build_user_prompt(
        self,
        profile: UserProfile,
        targets: NutritionTargets,
        allowed_foods: list[FoodItem],
        day_index: int,
        previous_errors: list[str],
    ) -> str:
        meal_carb_note = (
            f"Max carbs per meal: {targets.max_carbs_per_meal_g}g\n"
            if targets.max_carbs_per_meal_g is not None
            else ""
        )
        error_block = ""
        if previous_errors:
            formatted_errors = "\n".join(f"- {err}" for err in previous_errors)
            error_block = (
                "\nPrevious attempt failed validation with these errors — fix all of them:\n"
                f"{formatted_errors}\n"
            )

        return (
            f"Generate Day {day_index + 1} meal plan for a {profile.age}y {profile.gender.value} "
            f"({profile.diet_type.value}, goal: {profile.goal.value}).\n"
            f"Daily Targets:\n"
            f"- Calories: {targets.calories} kcal (±5% tolerance, hard floor "
            f"{get_calorie_floor(profile.gender)} kcal)\n"
            f"- Minimum Protein: {targets.protein_g}g\n"
            f"- Target Carbs: {targets.carbs_g}g\n"
            f"- Target Fat: {targets.fat_g}g\n"
            f"- Max Sodium: {targets.sodium_mg_max} mg\n"
            f"{meal_carb_note}"
            f"- Applied Medical Rules: {', '.join(targets.applied_rules)}\n"
            f"{error_block}\n"
            f"Allowed Foods Catalog (use ONLY these food_id values):\n"
            f"{self._format_allowed_menu(allowed_foods)}"
        )

    def generate_daily_plan(
        self,
        profile: UserProfile,
        *,
        day_index: int = 0,
        today: date | None = None,
    ) -> ValidatedMealPlan:
        """Generate and deterministically verify a single daily meal plan."""
        targets = get_nutrition_targets(profile, today=today)
        allowed_foods = self.food_db.filter_for_targets(
            targets,
            diet_type=profile.diet_type,
            allergies=profile.allergies,
            dislikes=profile.dislikes,
        )

        previous_errors: list[str] = []
        attempts_made = 0

        for attempt in range(1, self.max_attempts + 1):
            attempts_made = attempt
            prompt = self._build_user_prompt(
                profile=profile,
                targets=targets,
                allowed_foods=allowed_foods,
                day_index=day_index,
                previous_errors=previous_errors,
            )
            try:
                raw_plan, _ = self.gemini_client.generate_structured(
                    prompt,
                    RawDailyMealPlan,
                    system_instruction=self.system_prompt,
                    trace_name="meal_plan_generation",
                    metadata={"day_index": day_index, "attempt": attempt},
                )
            except GeminiClientError:
                break

            validation = validate_meal_plan(
                raw_plan,
                profile,
                targets,
                allowed_foods,
                used_fallback=False,
                attempts_used=attempt,
            )
            if validation.is_valid and validation.validated_plan is not None:
                return validation.validated_plan
            previous_errors = validation.errors

        fallback_raw = build_fallback_meal_plan(
            profile, targets, allowed_foods, day_index=day_index
        )
        fallback_validation = validate_meal_plan(
            fallback_raw,
            profile,
            targets,
            allowed_foods,
            used_fallback=True,
            attempts_used=max(attempts_made, 1),
        )
        if not fallback_validation.is_valid or fallback_validation.validated_plan is None:
            raise RuntimeError(
                f"Fallback meal plan failed validation: {'; '.join(fallback_validation.errors)}"
            )
        return fallback_validation.validated_plan

    def generate_weekly_plan(
        self,
        profile: UserProfile,
        *,
        days: int = 7,
        today: date | None = None,
    ) -> WeeklyMealPlan:
        """Generate a validated multi-day meal plan and consolidated grocery list."""
        if days < 1:
            raise ValueError("days must be at least 1")

        daily_plans = [
            self.generate_daily_plan(profile, day_index=idx, today=today) for idx in range(days)
        ]
        grocery = build_grocery_list(daily_plans, self.food_db)
        return WeeklyMealPlan(days=daily_plans, grocery_list=grocery)

    @staticmethod
    def _validate_candidate_day(
        profile: UserProfile,
        targets: NutritionTargets,
        foods: list[FoodItem],
        day_index: int,
    ) -> ValidatedMealPlan | None:
        if not foods:
            return None
        try:
            raw = build_fallback_meal_plan(profile, targets, foods, day_index=day_index)
        except ValueError:
            return None
        validation = validate_meal_plan(
            raw,
            profile,
            targets,
            foods,
            used_fallback=True,
            attempts_used=1,
        )
        return validation.validated_plan if validation.is_valid else None

    def swap_meal_day(
        self,
        profile: UserProfile,
        *,
        meal_type: MealType,
        day_index: int = 0,
        exclude_food_ids: list[str] | None = None,
        attempt: int = 1,
        today: date | None = None,
    ) -> MealSwapResult:
        """Generate a valid alternative day plan aiming to replace `meal_type` foods."""
        targets = get_nutrition_targets(profile, today=today)
        allowed_foods = self.food_db.filter_for_targets(
            targets,
            diet_type=profile.diet_type,
            allergies=profile.allergies,
            dislikes=profile.dislikes,
        )
        excluded = {fid.strip() for fid in (exclude_food_ids or []) if fid.strip()}

        preferred_foods = [food for food in allowed_foods if food.id not in excluded]
        validated = self._validate_candidate_day(
            profile, targets, preferred_foods, day_index + attempt * 3 + 1
        )

        if validated is None:
            best_plan: ValidatedMealPlan | None = None
            best_overlap: int | None = None
            for offset in (
                day_index + attempt * 5 + 2,
                day_index + attempt * 7 + 3,
                day_index + attempt + 1,
            ):
                candidate = self._validate_candidate_day(profile, targets, allowed_foods, offset)
                if candidate is None:
                    continue
                meal_ids = {
                    item.food_id
                    for meal in candidate.meals
                    if meal.meal_type == meal_type
                    for item in meal.items
                }
                overlap = len(meal_ids & excluded)
                if best_plan is None or best_overlap is None or overlap < best_overlap:
                    best_plan = candidate
                    best_overlap = overlap
                if overlap == 0:
                    break
            validated = best_plan

        if validated is None:
            raise RuntimeError("Unable to find a valid alternative meal plan for this profile.")

        swapped_meal = next(m for m in validated.meals if m.meal_type == meal_type)
        day_grocery = build_grocery_list([validated], self.food_db)
        return MealSwapResult(
            day_index=day_index,
            meal_type=meal_type,
            meal=swapped_meal,
            updated_day=validated,
            day_grocery_items=day_grocery,
        )
