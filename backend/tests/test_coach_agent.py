"""Unit tests for CoachIntent router, text meal parser, and safety-wrapped CoachAgent."""

import json

import httpx
import pytest

from app.ai import (
    ChatTurn,
    CoachAgent,
    CoachIntent,
    GeminiClient,
    classify_intent,
    parse_text_meal_items,
)
from app.core.nutrition import get_food_db
from app.core.rules import get_nutrition_targets
from app.core.safety import SAFE_OUTPUT_FALLBACK, SafetyCategory
from app.models import ActivityLevel, Gender, Goal, MedicalCondition, UserProfile


def _make_profile(**overrides: object) -> UserProfile:
    """Create a valid UserProfile for coach agent tests."""
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


def _gemini_text_response(text: str) -> httpx.Response:
    payload = {
        "candidates": [{"content": {"parts": [{"text": text}]}}],
        "usageMetadata": {
            "promptTokenCount": 180,
            "candidatesTokenCount": 60,
            "totalTokenCount": 240,
        },
    }
    return httpx.Response(200, text=json.dumps(payload))


@pytest.mark.parametrize(
    ("message", "expected_intent"),
    [
        ("Maine lunch mein 2 roti aur 1 daal moong khai", CoachIntent.MEAL_LOG),
        ("I ate 1 boiled egg and brown bread", CoachIntent.MEAL_LOG),
        ("Mujhe aaj ka diet plan bata dein", CoachIntent.MEAL_PLAN),
        ("What are good breakfast options?", CoachIntent.MEAL_PLAN),
        ("Sham ki chai ke saath craving ho rahi hai", CoachIntent.CRAVING),
        ("I need a healthy snack idea", CoachIntent.CRAVING),
        ("Dawat mein chicken biryani hai, kya karun?", CoachIntent.EATING_OUT),
        ("I am at a restaurant today", CoachIntent.EATING_OUT),
        ("Kya PCOS ke liye Inositol ya Vitamin D le sakti hoon?", CoachIntent.SUPPLEMENT_QUERY),
        ("Should I take Omega-3 supplements?", CoachIntent.SUPPLEMENT_QUERY),
        ("Knee pain hai, kaun sa workout karun?", CoachIntent.WORKOUT_QUESTION),
        ("How many minutes of face yoga today?", CoachIntent.WORKOUT_QUESTION),
        ("Aaj cheat meal ho gaya, bohot guilty feel ho raha hai", CoachIntent.MOOD_EMOTIONAL),
        ("I am really stressed and demotivated", CoachIntent.MOOD_EMOTIONAL),
        ("Aaj kitni calories baki hain?", CoachIntent.PROGRESS_QUERY),
        ("What is my daily target and remaining calories?", CoachIntent.PROGRESS_QUERY),
        ("Pro plan kitne ka hai aur JazzCash chalta hai?", CoachIntent.BILLING),
        ("How do I renew my subscription?", CoachIntent.BILLING),
        ("Assalam o alaikum FitSoul!", CoachIntent.GENERAL),
        ("Hi coach, kaise ho?", CoachIntent.GENERAL),
    ],
)
def test_classify_intent_covers_all_ten_intents(message: str, expected_intent: CoachIntent) -> None:
    assert classify_intent(message) == expected_intent


def test_parse_text_meal_items_english_and_roman_urdu() -> None:
    db = get_food_db()

    items_1 = parse_text_meal_items("Maine lunch mein 2 roti aur 1 daal moong khai", db)
    assert [i.food_id for i in items_1] == ["roti_whole_wheat", "daal_moong"]
    assert round(sum(i.kcal for i in items_1), 1) == 435.0

    items_2 = parse_text_meal_items("do boiled egg aur ek apple", db)
    assert [i.food_id for i in items_2] == ["boiled_egg", "apple"]
    assert round(sum(i.kcal for i in items_2), 1) == 234.0

    items_3 = parse_text_meal_items("1.5 chicken biryani + 1 kheera raita", db)
    assert [i.food_id for i in items_3] == ["chicken_biryani", "cucumber_raita"]
    assert round(sum(i.kcal for i in items_3), 1) == 802.5


@pytest.mark.parametrize(
    ("unsafe_msg", "expected_cat"),
    [
        ("I want to kill myself", SafetyCategory.SELF_HARM),
        ("Can I take Ozempic for weight loss?", SafetyCategory.PRESCRIPTION_MEDICINE),
        ("Sirf 500 calories ka plan do", SafetyCategory.EXTREME_DIET),
    ],
)
def test_input_safety_short_circuits_before_gemini(
    unsafe_msg: str, expected_cat: SafetyCategory
) -> None:
    called = False

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return _gemini_text_response("Should never run")

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        gemini = GeminiClient(api_key="test-key", client=http_client, trace_sink=lambda _: None)
        coach = CoachAgent(gemini_client=gemini)
        res = coach.respond(unsafe_msg, _make_profile())

    assert called is False
    assert res.safety_category == expected_cat
    assert res.used_fallback is False
    if expected_cat == SafetyCategory.SELF_HARM:
        assert res.flagged_safety is True
        assert res.stop_diet_advice is True


def test_output_safety_blocks_unsafe_llm_reply() -> None:
    transport = httpx.MockTransport(
        lambda _: _gemini_text_response("Aap PCOS ke liye rozana Metformin 500 mg start kar lein.")
    )
    with httpx.Client(transport=transport) as http_client:
        gemini = GeminiClient(api_key="test-key", client=http_client, trace_sink=lambda _: None)
        coach = CoachAgent(gemini_client=gemini)
        res = coach.respond("PCOS ke liye snack bata dein", _make_profile())

    assert res.flagged_safety is True
    assert res.reply == SAFE_OUTPUT_FALLBACK
    assert "output_violations" in res.grounded_data


def test_craving_handler_returns_pcos_safe_desi_snacks() -> None:
    pcos_profile = _make_profile(conditions=[MedicalCondition.PCOS])
    coach = CoachAgent(gemini_client=GeminiClient(api_key="", trace_sink=lambda _: None))

    res = coach.respond("Sham ko craving ho rahi hai, healthy snack batao", pcos_profile)

    assert res.intent == CoachIntent.CRAVING
    assert res.used_fallback is True
    snack_ids = {s["food_id"] for s in res.grounded_data["snack_options"]}
    assert "gulab_jamun" not in snack_ids
    assert "bhune_chanay" in snack_ids


def test_supplement_query_lockout_and_pcos_whitelist() -> None:
    called = False

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return _gemini_text_response(
            "You can consider Myo-Inositol or Vitamin D3; confirm with doctor."
        )

    pregnant = _make_profile(is_pregnant=True, goal=Goal.MAINTAIN)
    pcos = _make_profile(conditions=[MedicalCondition.PCOS])

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        gemini = GeminiClient(api_key="test-key", client=http_client, trace_sink=lambda _: None)
        coach = CoachAgent(gemini_client=gemini)

        # High-risk pregnant user must short-circuit without calling Gemini
        pregnant_res = coach.respond("Which vitamin supplement should I take?", pregnant)
        assert called is False
        assert pregnant_res.intent == CoachIntent.SUPPLEMENT_QUERY
        assert pregnant_res.grounded_data["allowed"] is False

        # Normal PCOS user receives grounded whitelist info via Gemini
        pcos_res = coach.respond("Kya PCOS ke liye Inositol supplement theek hai?", pcos)
        assert called is True
        assert pcos_res.grounded_data["allowed"] is True
        assert pcos_res.grounded_data["supplements"][0]["id"] == "inositol"


def test_progress_eating_out_meal_log_and_history_grounding() -> None:
    captured_prompts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        captured_prompts.append(body["contents"][0]["parts"][0]["text"])
        return _gemini_text_response("Bilkul, aapka calorie balance track par hai!")

    profile = _make_profile()
    targets = get_nutrition_targets(profile)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        gemini = GeminiClient(api_key="test-key", client=http_client, trace_sink=lambda _: None)
        coach = CoachAgent(gemini_client=gemini)

        progress_res = coach.respond(
            "Aaj kitni calories baki hain?",
            profile,
            daily_logged_kcal=600.0,
            history=[
                ChatTurn(role="user", content="Hi"),
                ChatTurn(role="assistant", content="Hello!"),
            ],
        )
        assert progress_res.intent == CoachIntent.PROGRESS_QUERY
        assert progress_res.grounded_data["remaining_kcal"] == round(targets.calories - 600.0, 1)
        assert "assistant: Hello!" in captured_prompts[-1]

        dawat_res = coach.respond("Dawat mein chicken biryani hai, kya karun?", profile)
        assert dawat_res.intent == CoachIntent.EATING_OUT
        assert dawat_res.grounded_data["matched_dishes"][0]["food_id"] == "chicken_biryani"
        assert dawat_res.grounded_data["matched_dishes"][0]["full_serving_kcal"] == 485.0

        log_res = coach.respond(
            "Maine lunch mein 2 roti aur 1 daal moong khai",
            profile,
            daily_logged_kcal=300.0,
        )
        assert log_res.intent == CoachIntent.MEAL_LOG
        assert log_res.grounded_data["logged_kcal"] == 435.0
        assert log_res.grounded_data["new_daily_kcal"] == 735.0


def test_mood_and_billing_fallbacks() -> None:
    coach = CoachAgent(gemini_client=GeminiClient(api_key="", trace_sink=lambda _: None))
    profile = _make_profile()

    mood_res = coach.respond("Aaj cheat meal ho gaya aur bohot guilty feel ho raha hai", profile)
    assert mood_res.intent == CoachIntent.MOOD_EMOTIONAL
    assert mood_res.used_fallback is True
    assert "guilty" in mood_res.reply.lower()

    billing_res = coach.respond("Pro plan kitne ka hai aur JazzCash chalta hai?", profile)
    assert billing_res.intent == CoachIntent.BILLING
    assert "2,999" in billing_res.reply
    assert "JazzCash" in billing_res.reply
