"""Unit tests for Pakistani food DB, fuzzy search, rule filtering, and USDA client."""

import json

import httpx
import pytest

from app.core.nutrition import FoodDatabase, get_food_db
from app.core.rules import get_nutrition_targets
from app.models import ActivityLevel, DietType, Gender, Goal, MedicalCondition, UserProfile
from app.services import USDAClient, USDAClientError


def _make_profile(**overrides: object) -> UserProfile:
    """Create a valid UserProfile for food filtering tests."""
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


def test_dataset_integrity_and_macro_consistency() -> None:
    db = get_food_db()

    assert db.count >= 150
    for item in db.all_foods():
        assert item.grams > 0
        assert item.kcal >= 0
        macro_kcal = (item.protein * 4) + (item.carbs * 4) + (item.fat * 9)
        tolerance = max(35.0, item.kcal * 0.25)
        assert abs(item.kcal - macro_kcal) <= tolerance, (
            f"Macro/kcal mismatch on '{item.id}': kcal={item.kcal}, macros={macro_kcal}"
        )
        assert {"veg", "eggetarian", "non_veg"} & set(item.tags), f"Missing diet tag on '{item.id}'"


def test_duplicate_food_id_raises() -> None:
    db = get_food_db()
    roti = db.get_by_id("roti_whole_wheat")
    assert roti is not None

    with pytest.raises(ValueError, match="Duplicate food id"):
        FoodDatabase([roti, roti])


@pytest.mark.parametrize("query", ["roti", "chapati", "phulka"])
def test_roti_alias_search(query: str) -> None:
    db = get_food_db()
    results = db.search(query, limit=3)

    assert results
    assert results[0].id == "roti_whole_wheat"


def test_fuzzy_typo_and_roman_urdu_search() -> None:
    db = get_food_db()

    biryani_results = db.search("biryni", limit=4)
    assert any("biryani" in item.id for item in biryani_results)
    assert "chicken_biryani" in [item.id for item in biryani_results]

    paratha_results = db.search("partha", limit=3)
    assert any("paratha" in item.id for item in paratha_results)

    chanay_results = db.search("bhune chanay", limit=3)
    assert chanay_results
    assert chanay_results[0].id == "bhune_chanay"


def test_empty_or_unmatched_search_returns_empty_list() -> None:
    db = get_food_db()

    assert db.search("") == []
    assert db.search("   ") == []
    assert db.search("zzzzqqqqxxxx") == []


def test_portion_scaling() -> None:
    db = get_food_db()
    roti = db.get_by_id("roti_whole_wheat")
    assert roti is not None

    two_rotis = roti.scale(2.0)
    assert two_rotis.grams == 90.0
    assert two_rotis.kcal == 240.0
    assert two_rotis.protein == 7.6

    half_roti = roti.scale(0.5)
    assert half_roti.grams == 22.5
    assert half_roti.kcal == 60.0

    with pytest.raises(ValueError, match="servings must be positive"):
        roti.scale(0)


def test_filter_for_pcos_and_diabetes_targets() -> None:
    db = get_food_db()
    profile = _make_profile(conditions=[MedicalCondition.PCOS, MedicalCondition.DIABETES_T2])
    targets = get_nutrition_targets(profile)

    allowed_ids = {item.id for item in db.filter_for_targets(targets, diet_type=profile.diet_type)}

    assert "gulab_jamun" not in allowed_ids
    assert "cola_soda" not in allowed_ids
    assert "roti_whole_wheat" in allowed_ids
    assert "daal_moong" in allowed_ids


def test_filter_for_hypertension_excludes_high_sodium() -> None:
    db = get_food_db()
    profile = _make_profile(conditions=[MedicalCondition.HYPERTENSION])
    targets = get_nutrition_targets(profile)

    allowed_ids = {item.id for item in db.filter_for_targets(targets, diet_type=profile.diet_type)}

    assert "mango_achaar" not in allowed_ids
    assert "bhindi_masala" in allowed_ids


def test_filter_respects_diet_type() -> None:
    db = get_food_db()
    targets = get_nutrition_targets(_make_profile())

    veg_ids = {item.id for item in db.filter_for_targets(targets, diet_type=DietType.VEG)}
    assert "chicken_karahi" not in veg_ids
    assert "boiled_egg" not in veg_ids
    assert "daal_moong" in veg_ids
    assert "plain_dahi" in veg_ids

    egg_ids = {item.id for item in db.filter_for_targets(targets, diet_type=DietType.EGGETARIAN)}
    assert "chicken_karahi" not in egg_ids
    assert "boiled_egg" in egg_ids
    assert "daal_moong" in egg_ids


def test_filter_respects_allergies_and_dislikes() -> None:
    db = get_food_db()
    targets = get_nutrition_targets(_make_profile())

    no_dairy_ids = {item.id for item in db.filter_for_targets(targets, allergies=["dairy"])}
    assert "plain_dahi" not in no_dairy_ids
    assert "palak_paneer" not in no_dairy_ids
    assert "daal_moong" in no_dairy_ids

    no_egg_ids = {item.id for item in db.filter_for_targets(targets, allergies=["egg"])}
    assert "boiled_egg" not in no_egg_ids
    assert "desi_omelette" not in no_egg_ids
    assert "baingan_bharta" in no_egg_ids

    no_karela_ids = {item.id for item in db.filter_for_targets(targets, dislikes=["karela"])}
    assert "karela_sabzi" not in no_karela_ids
    assert "bharwa_karela" not in no_karela_ids


def test_usda_client_search_parsing_and_caching() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        assert request.url.params["query"] == "avocado"
        assert request.url.params["api_key"] == "TEST_KEY"
        payload = {
            "foods": [
                {
                    "fdcId": 171705,
                    "description": "Avocado, raw",
                    "foodCategory": "Fruits and Fruit Juices",
                    "foodNutrients": [
                        {"nutrientId": 1008, "value": 160},
                        {"nutrientId": 1003, "value": 2.0},
                        {"nutrientId": 1005, "value": 8.53},
                        {"nutrientId": 1004, "value": 14.66},
                        {"nutrientId": 1079, "value": 6.7},
                        {"nutrientId": 1093, "value": 7.0},
                    ],
                }
            ]
        }
        return httpx.Response(200, text=json.dumps(payload))

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        usda = USDAClient(api_key="TEST_KEY", client=http_client)
        first = usda.search("avocado", page_size=5)
        second = usda.search("  Avocado  ", page_size=5)

    assert call_count == 1
    assert len(first) == 1
    assert len(second) == 1
    item = first[0]
    assert item.id == "usda_171705"
    assert item.name == "Avocado, raw"
    assert item.grams == 100.0
    assert item.kcal == 160.0
    assert item.protein == 2.0
    assert item.carbs == 8.5
    assert item.fat == 14.7
    assert item.fiber == 6.7
    assert item.sodium_mg == 7.0


def test_usda_client_http_error_raises() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(500, text="Server error"))
    with httpx.Client(transport=transport) as http_client:
        usda = USDAClient(api_key="TEST_KEY", client=http_client)
        with pytest.raises(USDAClientError, match="USDA API lookup failed"):
            usda.search("avocado")
