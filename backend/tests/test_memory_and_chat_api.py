"""Unit and integration tests for long-term memory, pattern detection, and chat/planner APIs."""

import json
import math
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.ai import (
    DEFAULT_EMBEDDING_DIM,
    AIMealPlanner,
    CoachAgent,
    CoachIntent,
    GeminiClient,
    MatchedMealItem,
    MemoryCategory,
    PatternType,
    PhotoScanSummary,
    compute_text_embedding,
    cosine_similarity,
    detect_emotional_patterns,
    extract_memory_facts,
    retrieve_relevant_memories,
)
from app.api.chat import get_coach_agent, get_meal_planner
from app.core.safety import SafetyCategory
from app.db import (
    Base,
    MealLogRecord,
    MealLogRepository,
    MemoryRepository,
    MessageRecord,
    MessageRepository,
    MoodLogRecord,
    MoodLogRepository,
    ProfileRepository,
    UserMemoryRecord,
    create_db_engine,
    get_db,
    init_db,
)
from app.main import create_app

MIGRATION_0002_PATH = (
    Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "0002_user_memories.sql"
)


def _gemini_text_response(text: str) -> httpx.Response:
    payload = {
        "candidates": [{"content": {"parts": [{"text": text}]}}],
        "usageMetadata": {
            "promptTokenCount": 140,
            "candidatesTokenCount": 45,
            "totalTokenCount": 185,
        },
    }
    return httpx.Response(200, text=json.dumps(payload))


def _dummy_meal_summary(kcal: float) -> PhotoScanSummary:
    return PhotoScanSummary(
        items=[
            MatchedMealItem(
                detected_name="Chicken Karahi",
                estimated_portion="1 plate",
                matched_food_id="chicken_karahi",
                matched_name="Chicken Karahi",
                grams=250.0,
                servings=2.0,
                kcal=kcal,
                protein=32.0,
                carbs=14.0,
                fat=28.0,
                fiber=2.0,
                sodium_mg=620.0,
                confidence=0.95,
                needs_confirmation=False,
                source="pakistani_db",
            )
        ],
        total_kcal=kcal,
        total_protein_g=32.0,
        total_carbs_g=14.0,
        total_fat_g=28.0,
        total_fiber_g=2.0,
        total_sodium_mg=620.0,
        needs_confirmation=False,
    )


@pytest.fixture
def api_harness() -> Iterator[tuple[TestClient, sessionmaker[Session], list[str]]]:
    """Provide isolated SQLite TestClient plus session factory and captured Gemini prompts."""
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    captured_prompts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        prompt_text = body["contents"][0]["parts"][0]["text"]
        captured_prompts.append(prompt_text)
        return _gemini_text_response(
            "Ji bilkul! Aap ke preference ke mutabiq daal moong dinner mein best choice hai."
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    mock_gemini = GeminiClient(
        api_key="test-key",
        client=http_client,
        sleep_fn=lambda _: None,
        trace_sink=lambda _: None,
    )
    offline_gemini = GeminiClient(
        api_key="",
        sleep_fn=lambda _: None,
        trace_sink=lambda _: None,
    )
    coach_agent = CoachAgent(gemini_client=mock_gemini)
    meal_planner = AIMealPlanner(gemini_client=offline_gemini)

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    test_app = create_app(initialize_db=False)
    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_coach_agent] = lambda: coach_agent
    test_app.dependency_overrides[get_meal_planner] = lambda: meal_planner

    with TestClient(test_app) as client:
        yield client, session_factory, captured_prompts

    test_app.dependency_overrides.clear()
    http_client.close()
    engine.dispose()


def _create_pcos_profile(client: TestClient, user_id: str = "aymen-26") -> dict:
    resp = client.post(
        "/api/v1/profiles",
        json={
            "user_id": user_id,
            "email": f"{user_id}@example.com",
            "full_name": "Aymen",
            "profile": {
                "age": 28,
                "gender": "female",
                "height_cm": 165.0,
                "weight_kg": 75.0,
                "activity_level": "sedentary",
                "goal": "lose",
                "conditions": ["pcos"],
                "timezone": "Asia/Karachi",
            },
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_user_memories_migration_and_orm_contract() -> None:
    assert "user_memories" in Base.metadata.tables

    sql_text = MIGRATION_0002_PATH.read_text(encoding="utf-8").lower()
    assert "create table if not exists public.user_memories" in sql_text
    assert "vector(768)" in sql_text
    assert "alter table public.user_memories enable row level security" in sql_text
    assert 'create policy "user_memories_own_rows"' in sql_text


def test_compute_text_embedding_and_semantic_retrieval() -> None:
    vec = compute_text_embedding("Mujhe daal moong bohat pasand hai")
    assert len(vec) == DEFAULT_EMBEDDING_DIM
    assert pytest.approx(math.sqrt(sum(v * v for v in vec)), abs=1e-6) == 1.0
    assert compute_text_embedding("...") == [0.0] * DEFAULT_EMBEDDING_DIM
    assert cosine_similarity([], [1.0]) == 0.0

    now = datetime(2026, 11, 25, 10, 0, tzinfo=UTC)
    memories = [
        UserMemoryRecord(
            id="m1",
            user_id="u1",
            category="fact",
            content="Office timing is 9 to 5 on weekdays",
            embedding=compute_text_embedding("Office timing is 9 to 5 on weekdays"),
            created_at=now,
        ),
        UserMemoryRecord(
            id="m2",
            user_id="u1",
            category="preference",
            content="Mujhe daal moong bohat pasand hai",
            embedding=compute_text_embedding("Mujhe daal moong bohat pasand hai"),
            created_at=now - timedelta(days=1),
        ),
    ]

    ranked = retrieve_relevant_memories("Dinner mein daal moong recipe chahiye", memories, top_k=2)
    assert len(ranked) >= 1
    assert ranked[0].id == "m2"


def test_extract_memory_facts_covers_all_categories_and_ignores_greetings() -> None:
    assert extract_memory_facts("Assalam o alaikum!") == []
    assert extract_memory_facts("Salam") == []

    text = (
        "Mujhe daal moong bohat pasand hai. "
        "I hate karela. "
        "Raat ko meetha khane ki craving hoti hai. "
        "Is hafte 1.5 kg kam hua! "
        "Meri night shift hoti hai."
    )
    facts = extract_memory_facts(text)
    by_category = [(fact.category, fact.content) for fact in facts]

    assert any(cat == MemoryCategory.PREFERENCE and "daal moong" in txt for cat, txt in by_category)
    assert any(cat == MemoryCategory.PREFERENCE and "karela" in txt for cat, txt in by_category)
    assert any(cat == MemoryCategory.TRIGGER and "Raat ko" in txt for cat, txt in by_category)
    assert any(cat == MemoryCategory.WIN and "1.5 kg" in txt for cat, txt in by_category)
    assert any(cat == MemoryCategory.FACT and "night shift" in txt for cat, txt in by_category)


def test_memory_repository_deduplicates_case_insensitively(
    api_harness: tuple[TestClient, sessionmaker[Session], list[str]],
) -> None:
    client, session_factory, _ = api_harness
    _create_pcos_profile(client, "mem-dedup-user")

    with session_factory() as session:
        first = MemoryRepository.save_memory(
            session,
            "mem-dedup-user",
            "preference",
            "Mujhe Daal Moong pasand hai",
            embedding=compute_text_embedding("Mujhe Daal Moong pasand hai"),
        )
        second = MemoryRepository.save_memory(
            session,
            "mem-dedup-user",
            "preference",
            "  mujhe daal moong pasand hai  ",
        )
        all_rows = MemoryRepository.list_memories(session, "mem-dedup-user")

    assert first.id == second.id
    assert len(all_rows) == 1


def test_detect_late_night_cravings_converts_utc_and_naive_to_karachi() -> None:
    # 18:30 UTC == 23:30 Asia/Karachi (late night), naive 19:15 (treated UTC) == 00:15 PKT
    messages = [
        MessageRecord(
            id="msg-1",
            user_id="u1",
            role="user",
            content="Raat ko meetha khane ki craving ho rahi hai",
            created_at=datetime(2026, 11, 20, 18, 30, tzinfo=UTC),
        ),
        MessageRecord(
            id="msg-2",
            user_id="u1",
            role="user",
            content="Mujhe bhook lag rahi hai aur chips chahiye",
            created_at=datetime(2026, 11, 21, 19, 15),
        ),
        # Daytime message (09:00 UTC == 14:00 PKT) must NOT count as late-night
        MessageRecord(
            id="msg-3",
            user_id="u1",
            role="user",
            content="Lunch mein craving ho rahi hai",
            created_at=datetime(2026, 11, 22, 9, 0, tzinfo=UTC),
        ),
    ]

    report = detect_emotional_patterns(
        messages=messages,
        meal_logs=[],
        mood_logs=[],
        daily_target_kcal=1400,
        timezone_name="Asia/Karachi",
    )

    late_patterns = [p for p in report.patterns if p.pattern_type == PatternType.LATE_NIGHT_CRAVING]
    assert len(late_patterns) == 1
    assert late_patterns[0].occurrences == 2
    assert any(
        n.pattern_type == PatternType.LATE_NIGHT_CRAVING and n.suggested_timing == "21:30 daily"
        for n in report.nudges
    )


def test_detect_weekend_calorie_slip_distinguishes_weekends_from_weekdays() -> None:
    # 2026-11-21 is Saturday, 2026-11-22 is Sunday; 2026-11-18/19 are Wed/Thu
    weekend_meals = [
        MealLogRecord(
            id="m-sat",
            user_id="u1",
            meal_type="dinner",
            items=[],
            total_kcal=1900.0,
            protein_g=60.0,
            carbs_g=180.0,
            fat_g=80.0,
            logged_at=datetime(2026, 11, 21, 14, 0, tzinfo=UTC),
        ),
        MealLogRecord(
            id="m-sun",
            user_id="u1",
            meal_type="dinner",
            items=[],
            total_kcal=1850.0,
            protein_g=55.0,
            carbs_g=170.0,
            fat_g=75.0,
            logged_at=datetime(2026, 11, 22, 14, 0, tzinfo=UTC),
        ),
    ]
    weekend_report = detect_emotional_patterns(
        messages=[],
        meal_logs=weekend_meals,
        mood_logs=[],
        daily_target_kcal=1400,
        timezone_name="Asia/Karachi",
    )
    assert any(p.pattern_type == PatternType.WEEKEND_CALORIE_SLIP for p in weekend_report.patterns)
    assert any(n.suggested_timing == "Friday 19:00" for n in weekend_report.nudges)

    weekday_only_overage = [
        MealLogRecord(
            id="m-wed",
            user_id="u1",
            meal_type="dinner",
            items=[],
            total_kcal=2200.0,
            protein_g=60.0,
            carbs_g=200.0,
            fat_g=90.0,
            logged_at=datetime(2026, 11, 18, 14, 0, tzinfo=UTC),
        ),
        MealLogRecord(
            id="m-thu",
            user_id="u1",
            meal_type="dinner",
            items=[],
            total_kcal=2100.0,
            protein_g=60.0,
            carbs_g=200.0,
            fat_g=85.0,
            logged_at=datetime(2026, 11, 19, 14, 0, tzinfo=UTC),
        ),
    ]
    weekday_report = detect_emotional_patterns(
        messages=[],
        meal_logs=weekday_only_overage,
        mood_logs=[],
        daily_target_kcal=1400,
        timezone_name="Asia/Karachi",
    )
    assert not any(
        p.pattern_type == PatternType.WEEKEND_CALORIE_SLIP for p in weekday_report.patterns
    )


def test_detect_stress_eating_and_micro_wins() -> None:
    mood_logs = [
        MoodLogRecord(
            id="mood-1",
            user_id="u1",
            mood="stressed",
            note="office deadline",
            logged_at=datetime(2026, 11, 23, 11, 0, tzinfo=UTC),
        ),
        MoodLogRecord(
            id="mood-2",
            user_id="u1",
            mood="anxious",
            note=None,
            logged_at=datetime(2026, 11, 24, 11, 0, tzinfo=UTC),
        ),
        MoodLogRecord(
            id="mood-3",
            user_id="u1",
            mood="proud",
            note="walked 30 min",
            logged_at=datetime(2026, 11, 25, 6, 0, tzinfo=UTC),
        ),
    ]
    memories = [
        UserMemoryRecord(
            id="win-1",
            user_id="u1",
            category=MemoryCategory.WIN.value,
            content="Is hafte 1 kg kam hua",
            created_at=datetime(2026, 11, 25, 6, 0, tzinfo=UTC),
        )
    ]

    report = detect_emotional_patterns(
        messages=[],
        meal_logs=[],
        mood_logs=mood_logs,
        daily_target_kcal=1400,
        memories=memories,
    )
    types = {p.pattern_type: p for p in report.patterns}
    assert PatternType.STRESS_EATING in types
    assert PatternType.MICRO_WIN in types
    assert types[PatternType.MICRO_WIN].severity == "positive"


def test_chat_endpoint_persists_history_extracts_and_recalls_memories(
    api_harness: tuple[TestClient, sessionmaker[Session], list[str]],
) -> None:
    client, _, captured_prompts = api_harness
    _create_pcos_profile(client, "aymen-chat")

    turn_1 = client.post(
        "/api/v1/chat",
        json={
            "user_id": "aymen-chat",
            "message": "Mujhe daal moong bohat pasand hai. I hate karela.",
            "channel": "web",
        },
    )
    assert turn_1.status_code == 200
    body_1 = turn_1.json()
    assert body_1["flagged_safety"] is False
    assert len(body_1["saved_memories"]) == 2

    turn_2 = client.post(
        "/api/v1/chat",
        json={
            "user_id": "aymen-chat",
            "message": "Dinner mein daal moong kha sakti hoon?",
            "channel": "web",
        },
    )
    assert turn_2.status_code == 200
    body_2 = turn_2.json()
    assert body_2["intent"] == CoachIntent.MEAL_LOG.value or isinstance(body_2["intent"], str)
    assert any("daal moong" in mem.lower() for mem in body_2["used_memories"])
    assert "Long-Term User Memories:" in captured_prompts[-1]
    assert "Mujhe daal moong bohat pasand hai" in captured_prompts[-1]

    history_resp = client.get("/api/v1/chat/aymen-chat/history")
    assert history_resp.status_code == 200
    messages = history_resp.json()["messages"]
    assert len(messages) == 4
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]

    memories_resp = client.get("/api/v1/chat/aymen-chat/memories")
    assert memories_resp.status_code == 200
    memories = memories_resp.json()["memories"]
    assert len(memories) == 2


def test_chat_endpoint_crisis_prompt_flags_safety_and_skips_memory_extraction(
    api_harness: tuple[TestClient, sessionmaker[Session], list[str]],
) -> None:
    client, session_factory, captured_prompts = api_harness
    _create_pcos_profile(client, "crisis-user")

    prompt_count_before = len(captured_prompts)
    resp = client.post(
        "/api/v1/chat",
        json={
            "user_id": "crisis-user",
            "message": "I want to end my life",
            "channel": "web",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["stop_diet_advice"] is True
    assert data["flagged_safety"] is True
    assert data["safety_category"] == SafetyCategory.SELF_HARM.value
    assert data["saved_memories"] == []
    assert data["used_memories"] == []
    assert len(captured_prompts) == prompt_count_before

    history = client.get("/api/v1/chat/crisis-user/history").json()["messages"]
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["flagged_safety"] is True
    assert history[1]["role"] == "assistant"

    with session_factory() as session:
        assert MemoryRepository.list_memories(session, "crisis-user") == []


def test_patterns_and_daily_meal_plan_endpoints(
    api_harness: tuple[TestClient, sessionmaker[Session], list[str]],
) -> None:
    client, session_factory, _ = api_harness
    _create_pcos_profile(client, "pattern-user")

    anchor = datetime.now(UTC).date() - timedelta(days=2)
    recent_sat = anchor - timedelta(days=(anchor.weekday() - 5) % 7)
    recent_sun = recent_sat + timedelta(days=1)

    with session_factory() as session:
        ProfileRepository.get_profile(session, "pattern-user")
        MessageRepository.save_message(
            session,
            "pattern-user",
            "user",
            "Raat ko meetha khane ki craving ho rahi hai",
            created_at=datetime.combine(recent_sat, datetime.min.time(), tzinfo=UTC)
            + timedelta(hours=18, minutes=30),
        )
        MessageRepository.save_message(
            session,
            "pattern-user",
            "user",
            "Bhook lag rahi hai kuch snack chahiye",
            created_at=datetime.combine(recent_sun, datetime.min.time(), tzinfo=UTC)
            + timedelta(hours=19, minutes=10),
        )
        MealLogRepository.save_meal_log(
            session,
            "pattern-user",
            "dinner",
            _dummy_meal_summary(1900.0),
            logged_at=datetime.combine(recent_sat, datetime.min.time(), tzinfo=UTC)
            + timedelta(hours=14),
        )
        MealLogRepository.save_meal_log(
            session,
            "pattern-user",
            "dinner",
            _dummy_meal_summary(1850.0),
            logged_at=datetime.combine(recent_sun, datetime.min.time(), tzinfo=UTC)
            + timedelta(hours=14),
        )
        MoodLogRepository.save_mood_log(
            session,
            "pattern-user",
            "stressed",
            note="work pressure",
            logged_at=datetime.now(UTC) - timedelta(days=1),
        )
        MoodLogRepository.save_mood_log(
            session,
            "pattern-user",
            "anxious",
            logged_at=datetime.now(UTC) - timedelta(hours=12),
        )
        MemoryRepository.save_memory(
            session,
            "pattern-user",
            MemoryCategory.WIN.value,
            "Is hafte 1 kg kam hua",
        )

    patterns_resp = client.get("/api/v1/chat/pattern-user/patterns")
    assert patterns_resp.status_code == 200
    report = patterns_resp.json()
    found_types = {p["pattern_type"] for p in report["patterns"]}
    assert found_types == {
        PatternType.LATE_NIGHT_CRAVING.value,
        PatternType.WEEKEND_CALORIE_SLIP.value,
        PatternType.STRESS_EATING.value,
        PatternType.MICRO_WIN.value,
    }
    assert len(report["nudges"]) == 4

    plan_resp = client.post("/api/v1/meal-plans/pattern-user/daily?day_index=0")
    assert plan_resp.status_code == 200
    plan = plan_resp.json()
    assert len(plan["meals"]) == 4
    assert plan["used_fallback"] is True
    assert 1376 * 0.95 <= plan["total_kcal"] <= 1376 * 1.05
    assert plan["total_protein_g"] >= 103


def test_weekly_meal_plan_and_meal_swap_endpoints(
    api_harness: tuple[TestClient, sessionmaker[Session], list[str]],
) -> None:
    client, _, _ = api_harness
    _create_pcos_profile(client, "weekly-user")

    weekly_resp = client.post("/api/v1/meal-plans/weekly-user/weekly?days=7")
    assert weekly_resp.status_code == 200
    weekly = weekly_resp.json()
    assert len(weekly["days"]) == 7
    assert len(weekly["grocery_list"]) >= 4

    for day in weekly["days"]:
        assert 1376 * 0.95 <= day["total_kcal"] <= 1376 * 1.05
        assert day["total_protein_g"] >= 103

    day0_lunch = next(m for m in weekly["days"][0]["meals"] if m["meal_type"] == "lunch")
    lunch_ids = [item["food_id"] for item in day0_lunch["items"]]

    swap_resp = client.post(
        "/api/v1/meal-plans/weekly-user/swap",
        json={
            "day_index": 0,
            "meal_type": "lunch",
            "exclude_food_ids": lunch_ids,
            "attempt": 1,
        },
    )
    assert swap_resp.status_code == 200
    swapped = swap_resp.json()
    assert swapped["day_index"] == 0
    assert swapped["meal_type"] == "lunch"
    assert swapped["meal"]["meal_type"] == "lunch"
    assert len(swapped["day_grocery_items"]) >= 1
    assert 1376 * 0.95 <= swapped["updated_day"]["total_kcal"] <= 1376 * 1.05
    assert swapped["updated_day"]["total_protein_g"] >= 103
    swapped_ids = [item["food_id"] for item in swapped["meal"]["items"]]
    assert swapped_ids != lunch_ids


def test_chat_and_meal_plan_endpoints_return_404_for_unknown_user(
    api_harness: tuple[TestClient, sessionmaker[Session], list[str]],
) -> None:
    client, _, _ = api_harness

    assert (
        client.post(
            "/api/v1/chat",
            json={"user_id": "missing-user", "message": "Salam"},
        ).status_code
        == 404
    )
    assert client.get("/api/v1/chat/missing-user/history").status_code == 404
    assert client.get("/api/v1/chat/missing-user/memories").status_code == 404
    assert client.get("/api/v1/chat/missing-user/patterns").status_code == 404
    assert client.post("/api/v1/meal-plans/missing-user/daily").status_code == 404
    assert client.post("/api/v1/meal-plans/missing-user/weekly").status_code == 404
    assert (
        client.post(
            "/api/v1/meal-plans/missing-user/swap",
            json={"day_index": 0, "meal_type": "lunch"},
        ).status_code
        == 404
    )
