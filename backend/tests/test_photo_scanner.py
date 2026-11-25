"""Unit and 30-meal evaluation tests for meal photo scanner and MealLogRepository."""

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime

import httpx
import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.ai import (
    DetectedFoodItem,
    GeminiClient,
    MealEditItem,
    MealPhotoScanner,
    RawPhotoScanResult,
)
from app.core.nutrition import get_food_db
from app.db import MealLogRepository, UserRow, create_db_engine, init_db
from app.services import USDAClient

FAKE_JPEG = b"\xff\xd8\xff\xe0fake-plate-photo"


def _vision_ok_response(raw_scan: RawPhotoScanResult) -> httpx.Response:
    payload = {
        "candidates": [{"content": {"parts": [{"text": raw_scan.model_dump_json()}]}}],
        "usageMetadata": {
            "promptTokenCount": 420,
            "candidatesTokenCount": 95,
            "totalTokenCount": 515,
        },
    }
    return httpx.Response(200, text=json.dumps(payload))


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Provide an isolated in-memory SQLite session with a seeded test user."""
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    with session_factory() as session:
        session.add(UserRow(id="scanner-user-1", email="aymen@example.com"))
        session.commit()
        yield session
    engine.dispose()


def test_scan_photo_matches_pakistani_db_and_computes_exact_kcal() -> None:
    raw_scan = RawPhotoScanResult(
        items=[
            DetectedFoodItem(
                food_name="chapati",
                estimated_portion="2 medium rotis",
                grams=90.0,
                confidence=0.92,
            ),
            DetectedFoodItem(
                food_name="daal moong",
                estimated_portion="1 bowl",
                grams=200.0,
                confidence=0.88,
            ),
        ],
        plate_notes="Ghar ka lunch",
    )

    transport = httpx.MockTransport(lambda _: _vision_ok_response(raw_scan))
    with httpx.Client(transport=transport) as http_client:
        gemini = GeminiClient(api_key="test-key", client=http_client, trace_sink=lambda _: None)
        scanner = MealPhotoScanner(gemini_client=gemini)
        summary = scanner.scan_photo(FAKE_JPEG, "image/jpeg", user_hint="Lunch plate")

    assert summary.needs_confirmation is False
    assert summary.confirmation_prompts == []
    assert len(summary.items) == 2

    roti_item, daal_item = summary.items
    assert roti_item.matched_food_id == "roti_whole_wheat"
    assert roti_item.servings == 2.0
    assert roti_item.kcal == 240.0
    assert roti_item.source == "pakistani_db"

    assert daal_item.matched_food_id == "daal_moong"
    assert daal_item.servings == 1.0
    assert daal_item.kcal == 195.0

    assert summary.total_kcal == 435.0
    assert summary.total_protein_g == 20.1
    assert summary.usage is not None
    assert summary.usage.total_tokens == 515


def test_low_confidence_scan_triggers_roman_urdu_confirmation() -> None:
    raw_scan = RawPhotoScanResult(
        items=[
            DetectedFoodItem(
                food_name="daal",
                estimated_portion="1 bowl yellow curry",
                grams=200.0,
                confidence=0.55,
            )
        ]
    )

    transport = httpx.MockTransport(lambda _: _vision_ok_response(raw_scan))
    with httpx.Client(transport=transport) as http_client:
        gemini = GeminiClient(api_key="test-key", client=http_client, trace_sink=lambda _: None)
        scanner = MealPhotoScanner(gemini_client=gemini)
        summary = scanner.scan_photo(FAKE_JPEG, "image/jpeg")

    assert summary.needs_confirmation is True
    assert len(summary.confirmation_prompts) == 1
    assert "Kya yeh" in summary.confirmation_prompts[0]
    assert len(summary.items[0].candidate_options) >= 2


def test_recalculate_from_edits_updates_totals_and_clears_confirmation() -> None:
    scanner = MealPhotoScanner(gemini_client=GeminiClient(api_key="test-key"))

    updated = scanner.recalculate_from_edits(
        [
            MealEditItem(food_id="roti_whole_wheat", servings=2.0),
            MealEditItem(food_id="daal_moong", servings=1.0),
        ],
        plate_notes="Confirmed by user",
    )

    assert updated.needs_confirmation is False
    assert updated.total_kcal == 435.0
    assert updated.items[0].servings == 2.0

    with pytest.raises(ValueError, match="Unknown food_id"):
        scanner.recalculate_from_edits([MealEditItem(food_id="missing_dish", servings=1.0)])


def test_usda_fallback_and_unmatched_graceful_handling() -> None:
    raw_scan = RawPhotoScanResult(
        items=[
            DetectedFoodItem(
                food_name="avocado",
                estimated_portion="1/2 medium fruit",
                grams=100.0,
                confidence=0.90,
            ),
            DetectedFoodItem(
                food_name="xyzzq mystery snack",
                estimated_portion="1 piece",
                grams=50.0,
                confidence=0.40,
            ),
        ]
    )

    def usda_handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["query"] == "avocado":
            return httpx.Response(
                200,
                text=json.dumps(
                    {
                        "foods": [
                            {
                                "fdcId": 171705,
                                "description": "Avocado, raw",
                                "foodCategory": "Fruits",
                                "foodNutrients": [
                                    {"nutrientId": 1008, "value": 160},
                                    {"nutrientId": 1003, "value": 2.0},
                                    {"nutrientId": 1005, "value": 8.5},
                                    {"nutrientId": 1004, "value": 14.7},
                                    {"nutrientId": 1079, "value": 6.7},
                                    {"nutrientId": 1093, "value": 7.0},
                                ],
                            }
                        ]
                    }
                ),
            )
        return httpx.Response(500, text="USDA error")

    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _: _vision_ok_response(raw_scan))
        ) as g_hc,
        httpx.Client(transport=httpx.MockTransport(usda_handler)) as u_hc,
    ):
        gemini = GeminiClient(api_key="test-key", client=g_hc, trace_sink=lambda _: None)
        usda = USDAClient(api_key="TEST_KEY", client=u_hc)
        scanner = MealPhotoScanner(gemini_client=gemini, usda_client=usda)
        summary = scanner.scan_photo(FAKE_JPEG, "image/jpeg")

    avocado, unknown = summary.items
    assert avocado.source == "usda"
    assert avocado.matched_food_id == "usda_171705"
    assert avocado.kcal == 160.0

    assert unknown.source == "unmatched"
    assert unknown.matched_food_id is None
    assert unknown.needs_confirmation is True
    assert summary.needs_confirmation is True


# 30 authentic Pakistani meal plates evaluation suite
THIRTY_DESI_MEAL_PLATES: list[tuple[str, list[tuple[str, float, str]]]] = [
    (
        "01_aloo_paratha_dahi_chai",
        [
            ("aloo paratha", 130.0, "aloo_paratha"),
            ("dahi", 100.0, "plain_dahi"),
            ("doodh patti chai", 180.0, "doodh_patti_chai"),
        ],
    ),
    (
        "02_paratha_omelette",
        [
            ("plain paratha", 70.0, "plain_paratha"),
            ("desi masala omelette", 130.0, "desi_omelette"),
        ],
    ),
    (
        "03_halwa_puri_chana",
        [("halwa puri", 280.0, "halwa_puri"), ("lahori chanay", 200.0, "lahori_cholay")],
    ),
    (
        "04_oats_eggs_chai",
        [
            ("oats porridge", 220.0, "oats_porridge"),
            ("boiled egg", 100.0, "boiled_egg"),
            ("sugar free chai", 180.0, "chai_sugar_free"),
        ],
    ),
    (
        "05_besan_chilla_raita",
        [("besan chilla", 120.0, "besan_chilla"), ("podina raita", 100.0, "mint_raita")],
    ),
    (
        "06_daliya_almonds",
        [("broken wheat porridge", 220.0, "wheat_daliya"), ("badaam", 18.0, "almonds")],
    ),
    (
        "07_shakshuka_brown_bread",
        [("shakshuka", 240.0, "shakshuka"), ("brown bread", 60.0, "brown_bread")],
    ),
    (
        "08_roti_daal_salad",
        [
            ("chapati", 90.0, "roti_whole_wheat"),
            ("daal moong", 200.0, "daal_moong"),
            ("kachumber salad", 150.0, "kachumber_salad"),
        ],
    ),
    (
        "09_chicken_biryani_raita",
        [("chicken biryani", 300.0, "chicken_biryani"), ("kheera raita", 120.0, "cucumber_raita")],
    ),
    (
        "10_beef_biryani_salad",
        [("beef biryani", 300.0, "beef_biryani"), ("green salad", 150.0, "green_salad")],
    ),
    (
        "11_pulao_shami_kabab",
        [("chicken yakhni pulao", 280.0, "chicken_pulao"), ("shami kabab", 100.0, "shami_kabab")],
    ),
    (
        "12_roti_bhindi_dahi",
        [
            ("phulka", 90.0, "roti_whole_wheat"),
            ("bhindi masala", 180.0, "bhindi_masala"),
            ("plain yogurt", 100.0, "plain_dahi"),
        ],
    ),
    (
        "13_tandoori_roti_palak_paneer",
        [("tandoori roti", 60.0, "roti_tandoori"), ("palak paneer", 200.0, "palak_paneer")],
    ),
    (
        "14_roti_daal_chana_chutney",
        [
            ("roti", 90.0, "roti_whole_wheat"),
            ("daal chana", 200.0, "daal_chana"),
            ("green chutney", 30.0, "mint_chutney"),
        ],
    ),
    (
        "15_khichdi_dahi",
        [("moong dal khichdi", 220.0, "moong_khichdi"), ("dahi", 150.0, "plain_dahi")],
    ),
    (
        "16_rice_rajma",
        [
            ("boiled basmati rice", 150.0, "basmati_rice_boiled"),
            ("rajma masala", 200.0, "rajma_lobia"),
        ],
    ),
    (
        "17_haleem_naan",
        [("chicken haleem", 250.0, "chicken_haleem"), ("plain naan", 90.0, "plain_naan")],
    ),
    (
        "18_bhune_chanay_kahwa",
        [("bhune chanay", 40.0, "bhune_chanay"), ("kahwa", 240.0, "green_tea_kahwa")],
    ),
    (
        "19_samosa_chutney_chai",
        [
            ("aloo samosa", 80.0, "aloo_samosa"),
            ("imli chutney", 30.0, "imli_chutney"),
            ("karak chai", 180.0, "doodh_patti_chai"),
        ],
    ),
    (
        "20_pakora_raita",
        [("mixed vegetable pakora", 100.0, "mixed_pakora"), ("podina raita", 100.0, "mint_raita")],
    ),
    ("21_chana_chaat", [("chana chaat", 180.0, "chana_chaat")]),
    ("22_dahi_bhalla", [("dahi bhalla", 180.0, "dahi_bhalla")]),
    (
        "23_amrood_makhana",
        [("amrood", 130.0, "guava"), ("roasted makhana", 30.0, "roasted_makhana")],
    ),
    (
        "24_karahi_roti_salad",
        [
            ("chicken karahi", 220.0, "chicken_karahi"),
            ("whole wheat roti", 90.0, "roti_whole_wheat"),
            ("kachumber salad", 150.0, "kachumber_salad"),
        ],
    ),
    (
        "25_nihari_garlic_naan",
        [("beef nihari", 250.0, "beef_nihari"), ("garlic naan", 95.0, "garlic_naan")],
    ),
    (
        "26_grilled_chicken_brown_rice",
        [
            ("grilled chicken breast", 150.0, "grilled_chicken_breast"),
            ("brown rice", 150.0, "brown_rice_boiled"),
            ("green salad", 150.0, "green_salad"),
        ],
    ),
    (
        "27_grilled_fish_roti",
        [
            ("grilled rahu fish", 150.0, "grilled_rahu_fish"),
            ("whole wheat roti", 45.0, "roti_whole_wheat"),
        ],
    ),
    (
        "28_mutton_karahi_roti",
        [("mutton karahi", 220.0, "mutton_karahi"), ("tandoori roti", 60.0, "roti_tandoori")],
    ),
    (
        "29_chicken_tikka_roti_raita",
        [
            ("chicken tikka", 180.0, "chicken_tikka"),
            ("chapati", 45.0, "roti_whole_wheat"),
            ("podina raita", 100.0, "mint_raita"),
        ],
    ),
    (
        "30_aloo_keema_roti_achaar",
        [
            ("aloo keema", 200.0, "aloo_keema"),
            ("chapati", 90.0, "roti_whole_wheat"),
            ("mango achaar", 15.0, "mango_achaar"),
        ],
    ),
]


@pytest.mark.parametrize(("plate_name", "plate_items"), THIRTY_DESI_MEAL_PLATES)
def test_thirty_desi_meal_evaluation_dataset(
    plate_name: str,
    plate_items: list[tuple[str, float, str]],
) -> None:
    raw_scan = RawPhotoScanResult(
        items=[
            DetectedFoodItem(
                food_name=food_name,
                estimated_portion="standard serving",
                grams=grams,
                confidence=0.90,
            )
            for food_name, grams, _ in plate_items
        ]
    )
    food_db = get_food_db()

    transport = httpx.MockTransport(lambda _: _vision_ok_response(raw_scan))
    with httpx.Client(transport=transport) as http_client:
        gemini = GeminiClient(api_key="test-key", client=http_client, trace_sink=lambda _: None)
        scanner = MealPhotoScanner(gemini_client=gemini, food_db=food_db)
        summary = scanner.scan_photo(FAKE_JPEG, "image/jpeg")

    assert len(summary.items) == len(plate_items), plate_name
    for matched, (_, _, expected_id) in zip(summary.items, plate_items, strict=True):
        assert matched.source == "pakistani_db", plate_name
        assert matched.matched_food_id == expected_id, (
            f"{plate_name}: expected {expected_id}, got {matched.matched_food_id}"
        )
    assert summary.total_kcal == round(sum(item.kcal for item in summary.items), 1)
    assert summary.total_kcal > 0


def test_meal_log_repository_saves_and_aggregates_daily_logs(db_session: Session) -> None:
    scanner = MealPhotoScanner(gemini_client=GeminiClient(api_key="test-key"))
    breakfast_summary = scanner.recalculate_from_edits(
        [MealEditItem(food_id="boiled_egg", servings=2.0)]
    )
    lunch_summary = scanner.recalculate_from_edits(
        [
            MealEditItem(food_id="roti_whole_wheat", servings=2.0),
            MealEditItem(food_id="daal_moong", servings=1.0),
        ]
    )

    target_day = date(2026, 11, 25)
    prev_day = date(2026, 11, 24)

    MealLogRepository.save_meal_log(
        db_session,
        user_id="scanner-user-1",
        meal_type="breakfast",
        summary=breakfast_summary,
        photo_url="https://example.com/bfast.jpg",
        logged_at=datetime(2026, 11, 25, 8, 30, tzinfo=UTC),
    )
    MealLogRepository.save_meal_log(
        db_session,
        user_id="scanner-user-1",
        meal_type="lunch",
        summary=lunch_summary,
        logged_at=datetime(2026, 11, 25, 13, 15, tzinfo=UTC),
    )
    # Log on previous day must not leak into target_day summary
    MealLogRepository.save_meal_log(
        db_session,
        user_id="scanner-user-1",
        meal_type="dinner",
        summary=breakfast_summary,
        logged_at=datetime(2026, 11, 24, 20, 0, tzinfo=UTC),
    )

    daily = MealLogRepository.get_daily_meal_logs(db_session, "scanner-user-1", target_day)
    prev = MealLogRepository.get_daily_meal_logs(db_session, "scanner-user-1", prev_day)

    assert len(daily.logs) == 2
    assert [log.meal_type for log in daily.logs] == ["breakfast", "lunch"]
    assert daily.logs[0].photo_url == "https://example.com/bfast.jpg"
    assert daily.total_kcal == round(breakfast_summary.total_kcal + lunch_summary.total_kcal, 1)
    assert daily.total_protein_g == round(
        breakfast_summary.total_protein_g + lunch_summary.total_protein_g, 1
    )

    assert len(prev.logs) == 1
    assert prev.total_kcal == breakfast_summary.total_kcal
