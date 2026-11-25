"""Safety-wrapped FitSoul AI coach agent grounded in deterministic nutrition data."""

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.ai.client import GeminiClient, GeminiClientError
from app.ai.intent_router import CoachIntent, classify_intent, parse_text_meal_items
from app.ai.tracing import AIUsage
from app.core.nutrition import FoodDatabase, FoodItem, get_food_db
from app.core.rules import NutritionTargets, get_nutrition_targets
from app.core.safety import (
    MANDATORY_DOCTOR_NOTE,
    SAFE_OUTPUT_FALLBACK,
    SafetyCategory,
    check_input_safety,
    check_output_safety,
    get_safe_supplement_info,
)
from app.models import UserProfile

DEFAULT_COACH_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "coach_system.txt"
MAX_HISTORY_TURNS = 6
PREFERRED_SNACK_IDS = (
    "bhune_chanay",
    "roasted_makhana",
    "boiled_egg",
    "almonds",
    "guava",
    "plain_dahi",
    "cucumber_raita",
    "apple",
)
_EATING_OUT_STOPWORDS = frozenset(
    {
        "dawat",
        "daawat",
        "shaadi",
        "wedding",
        "restaurant",
        "menu",
        "mein",
        "me",
        "hai",
        "hain",
        "kya",
        "karun",
        "karoon",
        "khana",
        "bahar",
        "aaj",
        "party",
        "in",
        "at",
        "on",
        "the",
        "is",
        "what",
        "should",
        "i",
        "eat",
        "for",
        "today",
    }
)


class ChatTurn(BaseModel):
    """Single historical conversation turn passed to the coach."""

    role: Literal["user", "assistant"]
    content: str


class CoachReply(BaseModel):
    """Structured response produced by CoachAgent."""

    reply: str
    intent: CoachIntent
    flagged_safety: bool = False
    safety_category: SafetyCategory = SafetyCategory.SAFE
    stop_diet_advice: bool = False
    grounded_data: dict[str, Any] = Field(default_factory=dict)
    used_fallback: bool = False
    usage: AIUsage | None = None


def _select_craving_snacks(
    profile: UserProfile,
    targets: NutritionTargets,
    food_db: FoodDatabase,
) -> list[FoodItem]:
    allowed = food_db.filter_for_targets(
        targets,
        diet_type=profile.diet_type,
        allergies=profile.allergies,
        dislikes=profile.dislikes,
    )
    snack_pool = [
        item
        for item in allowed
        if item.category in {"snacks", "fruit", "eggs_dairy"} and item.kcal > 0
    ]
    by_id = {item.id: item for item in snack_pool}

    chosen: list[FoodItem] = []
    for preferred_id in PREFERRED_SNACK_IDS:
        if preferred_id in by_id:
            chosen.append(by_id[preferred_id])
        if len(chosen) == 4:
            return chosen

    for item in snack_pool:
        if item not in chosen:
            chosen.append(item)
        if len(chosen) == 4:
            break
    return chosen


def _extract_eating_out_matches(message: str, food_db: FoodDatabase) -> list[FoodItem]:
    tokens = [
        tok
        for tok in re.findall(r"[a-zA-Z]+", message.lower())
        if tok not in _EATING_OUT_STOPWORDS and len(tok) >= 3
    ]
    cleaned = " ".join(tokens)
    if not cleaned:
        return []
    return food_db.search(cleaned, limit=3, min_score=0.65)


class CoachAgent:
    """Routes user messages through safety guardrails, deterministic tools, and Gemini."""

    def __init__(
        self,
        gemini_client: GeminiClient | None = None,
        food_db: FoodDatabase | None = None,
        system_prompt_path: Path = DEFAULT_COACH_PROMPT_PATH,
    ) -> None:
        self.gemini_client = gemini_client if gemini_client is not None else GeminiClient()
        self.food_db = food_db if food_db is not None else get_food_db()
        self.system_prompt = system_prompt_path.read_text(encoding="utf-8")

    def _prepare_intent_context(
        self,
        *,
        intent: CoachIntent,
        message: str,
        profile: UserProfile,
        targets: NutritionTargets,
        daily_logged_kcal: float,
    ) -> tuple[dict[str, Any], str, bool]:
        """Return (grounded_data, deterministic_fallback_reply, short_circuit)."""
        if intent == CoachIntent.SUPPLEMENT_QUERY:
            supp = get_safe_supplement_info(profile)
            data = supp.model_dump()
            if not supp.allowed:
                return (
                    data,
                    supp.disabled_reason or supp.disclaimer,
                    True,
                )
            top_names = ", ".join(item.name for item in supp.supplements[:3])
            fallback = (
                f"Aap ki profile ke liye general OTC options yeh discuss kiye ja sakte hain: "
                f"{top_names}. {MANDATORY_DOCTOR_NOTE}"
            )
            return data, fallback, False

        if intent == CoachIntent.MEAL_LOG:
            items = parse_text_meal_items(message, self.food_db)
            logged_kcal = round(sum(i.kcal for i in items), 1)
            new_daily = round(daily_logged_kcal + logged_kcal, 1)
            remaining = round(max(0.0, targets.calories - new_daily), 1)
            data = {
                "logged_items": [item.model_dump() for item in items],
                "logged_kcal": logged_kcal,
                "new_daily_kcal": new_daily,
                "remaining_kcal": remaining,
                "daily_target_kcal": targets.calories,
            }
            if items:
                summary = ", ".join(f"{i.servings:g}x {i.name} ({i.kcal} kcal)" for i in items)
                fallback = (
                    f"Meal note ho gaya: {summary} — total {logged_kcal} kcal. "
                    f"Aaj ke target ({targets.calories} kcal) mein se {remaining} kcal baki hain."
                )
            else:
                fallback = (
                    "Main ne meal detect kiya, lekin exact item database mein match nahi hua — "
                    "dish ka naam aur quantity (jaise '2 roti aur 1 bowl daal moong') likh dein."
                )
            return data, fallback, False

        if intent == CoachIntent.CRAVING:
            snacks = _select_craving_snacks(profile, targets, self.food_db)
            snack_dicts = [
                {
                    "food_id": s.id,
                    "name": s.name,
                    "serving_desc": s.serving_desc,
                    "kcal": s.kcal,
                    "protein_g": s.protein,
                }
                for s in snacks
            ]
            data = {"snack_options": snack_dicts, "applied_rules": targets.applied_rules}
            ideas = "; ".join(f"{s.name} ({s.serving_desc}, {s.kcal:.0f} kcal)" for s in snacks)
            fallback = f"Craving ke waqt bina guilt ke yeh desi healthy swaps try karein: {ideas}."
            return data, fallback, False

        if intent == CoachIntent.EATING_OUT:
            dishes = _extract_eating_out_matches(message, self.food_db)
            dish_data = [
                {
                    "food_id": d.id,
                    "name": d.name,
                    "serving_desc": d.serving_desc,
                    "full_serving_kcal": d.kcal,
                    "half_serving_kcal": round(d.kcal * 0.5, 1),
                }
                for d in dishes
            ]
            remaining = round(max(0.0, targets.calories - daily_logged_kcal), 1)
            data = {"matched_dishes": dish_data, "remaining_kcal": remaining}
            if dishes:
                top = dishes[0]
                fallback = (
                    f"Dawat mein {top.name} bilkul enjoy karein! 1 full {top.serving_desc} "
                    f"~{top.kcal:.0f} kcal ka hota hai — half portion (~{top.kcal * 0.5:.0f} kcal) "
                    "plus green salad/raita lein, bina guilt ke balance rahega."
                )
            else:
                fallback = (
                    "Bahar khate waqt half plate main dish + salad ya raita lein aur meetha/"
                    "sugary drinks skip karein — dawat enjoy karna bilkul theek hai!"
                )
            return data, fallback, False

        if intent == CoachIntent.PROGRESS_QUERY:
            remaining = round(max(0.0, targets.calories - daily_logged_kcal), 1)
            data = {
                "daily_target_kcal": targets.calories,
                "daily_logged_kcal": round(daily_logged_kcal, 1),
                "remaining_kcal": remaining,
                "protein_g": targets.protein_g,
                "carbs_g": targets.carbs_g,
                "fat_g": targets.fat_g,
                "water_ml": targets.water_ml,
                "warnings": targets.warnings,
            }
            fallback = (
                f"Aaj ka daily target {targets.calories} kcal hai. Ab tak {daily_logged_kcal:.0f} "
                f"kcal log hue hain — {remaining:.0f} kcal baki hain (protein goal: "
                f"{targets.protein_g}g, paani: {targets.water_ml} ml)."
            )
            return data, fallback, False

        if intent == CoachIntent.BILLING:
            data = {
                "plans": {
                    "free_trial": "7 days free",
                    "basic_pkr": 1499,
                    "pro_pkr": 2999,
                    "transformation_3mo_pkr": 6999,
                    "overseas_usd": 9.99,
                },
                "payment_methods": ["JazzCash", "Easypaisa", "Safepay", "PayFast", "LemonSqueezy"],
            }
            fallback = (
                "FitSoul AI ke plans: 7-day Free Trial, Basic (Rs. 1,499/mo), Pro (Rs. 2,999/mo "
                "— photo scanner + workouts + face yoga + weekly AI report), aur 3-month "
                "Transformation (Rs. 6,999). Local payments JazzCash, Easypaisa aur cards par "
                "available hain."
            )
            return data, fallback, False

        if intent == CoachIntent.WORKOUT_QUESTION:
            data = {
                "goal": profile.goal.value,
                "activity_level": profile.activity_level.value,
                "bmi": profile.bmi,
            }
            fallback = (
                "Ghar par 15–30 min brisk walk ya low-impact bodyweight routine best rehti hai. "
                "Agar knee ya back pain ho to jumping exercises skip kar ke chair squats, wall "
                "pushups aur gentle stretching karein."
            )
            return data, fallback, False

        if intent == CoachIntent.MOOD_EMOTIONAL:
            data = {"daily_target_kcal": targets.calories, "water_ml": targets.water_ml}
            fallback = (
                "Bilkul guilty feel na karein — ek cheat meal ya stressful din aap ki mehnat "
                "khatam nahi karta. Ek glass paani piyein aur agle meal se apna normal desi "
                "routine dobara shuru kar lein, main saath hoon!"
            )
            return data, fallback, False

        if intent == CoachIntent.MEAL_PLAN:
            data = {
                "daily_target_kcal": targets.calories,
                "protein_g": targets.protein_g,
                "carbs_g": targets.carbs_g,
                "fat_g": targets.fat_g,
                "applied_rules": targets.applied_rules,
            }
            fallback = (
                f"Aap ka daily target {targets.calories} kcal ({targets.protein_g}g protein, "
                f"{targets.carbs_g}g carbs, {targets.fat_g}g fat) hai. Desi plan ke liye subah "
                "boiled eggs/oats, dopehar roti + daal/sabzi + salad, sham bhune chanay aur raat "
                "grilled chicken/fish best rehte hain."
            )
            return data, fallback, False

        data = {"daily_target_kcal": targets.calories, "water_ml": targets.water_ml}
        fallback = (
            f"Assalam o alaikum! Aap ka daily target {targets.calories} kcal aur paani target "
            f"{targets.water_ml} ml hai. Aaj meal log karna hai, snack idea chahiye, ya workout "
            "poochhna hai?"
        )
        return data, fallback, False

    def _build_prompt(
        self,
        *,
        message: str,
        intent: CoachIntent,
        profile: UserProfile,
        targets: NutritionTargets,
        grounded_data: dict[str, Any],
        history: list[ChatTurn] | None,
        memories: list[str] | None = None,
    ) -> str:
        history_lines = []
        if history:
            for turn in history[-MAX_HISTORY_TURNS:]:
                history_lines.append(f"{turn.role}: {turn.content}")
        history_block = "\n".join(history_lines) if history_lines else "(none)"
        memory_block = "\n".join(f"- {m}" for m in memories) if memories else "(none)"

        return (
            f"User Profile Summary: {profile.age}y {profile.gender.value}, "
            f"goal={profile.goal.value}, diet={profile.diet_type.value}, "
            f"conditions={[c.value for c in profile.conditions]}, "
            f"daily_target={targets.calories} kcal.\n"
            f"Detected Intent: {intent.value}\n"
            f"Deterministic Grounded Context:\n{json.dumps(grounded_data, indent=2)}\n\n"
            f"Long-Term User Memories:\n{memory_block}\n\n"
            f"Recent History:\n{history_block}\n\n"
            f"User Message: {message}"
        )

    def respond(
        self,
        message: str,
        profile: UserProfile,
        *,
        history: list[ChatTurn] | None = None,
        memories: list[str] | None = None,
        daily_logged_kcal: float = 0.0,
        today: date | None = None,
    ) -> CoachReply:
        """Respond to a user message with safety guardrails and deterministic grounding."""
        safety = check_input_safety(message, profile=profile)
        if not safety.is_safe:
            return CoachReply(
                reply=safety.safe_response or SAFE_OUTPUT_FALLBACK,
                intent=CoachIntent.GENERAL,
                flagged_safety=safety.flagged_safety,
                safety_category=safety.category,
                stop_diet_advice=safety.stop_diet_advice,
                grounded_data={"matched_rule": safety.matched_rule} if safety.matched_rule else {},
                used_fallback=False,
                usage=None,
            )

        cleaned_memories = [m.strip() for m in (memories or []) if m.strip()]
        intent = classify_intent(message)
        targets = get_nutrition_targets(profile, today=today)
        grounded_data, fallback_reply, short_circuit = self._prepare_intent_context(
            intent=intent,
            message=message,
            profile=profile,
            targets=targets,
            daily_logged_kcal=daily_logged_kcal,
        )
        if cleaned_memories:
            grounded_data["used_memories"] = cleaned_memories

        if short_circuit:
            return CoachReply(
                reply=fallback_reply,
                intent=intent,
                flagged_safety=False,
                safety_category=SafetyCategory.SAFE,
                stop_diet_advice=False,
                grounded_data=grounded_data,
                used_fallback=False,
                usage=None,
            )

        prompt = self._build_prompt(
            message=message,
            intent=intent,
            profile=profile,
            targets=targets,
            grounded_data=grounded_data,
            history=history,
            memories=cleaned_memories,
        )
        try:
            ai_res = self.gemini_client.generate_text(
                prompt,
                system_instruction=self.system_prompt,
                trace_name=f"coach_{intent.value}",
                metadata={"intent": intent.value},
            )
        except GeminiClientError:
            return CoachReply(
                reply=fallback_reply,
                intent=intent,
                flagged_safety=False,
                safety_category=SafetyCategory.SAFE,
                stop_diet_advice=False,
                grounded_data=grounded_data,
                used_fallback=True,
                usage=None,
            )

        output_check = check_output_safety(ai_res.text, profile=profile)
        if not output_check.is_safe:
            return CoachReply(
                reply=output_check.sanitized_response,
                intent=intent,
                flagged_safety=True,
                safety_category=SafetyCategory.SAFE,
                stop_diet_advice=False,
                grounded_data={**grounded_data, "output_violations": output_check.violations},
                used_fallback=False,
                usage=ai_res.usage,
            )

        return CoachReply(
            reply=output_check.sanitized_response,
            intent=intent,
            flagged_safety=False,
            safety_category=SafetyCategory.SAFE,
            stop_diet_advice=False,
            grounded_data=grounded_data,
            used_fallback=False,
            usage=ai_res.usage,
        )
