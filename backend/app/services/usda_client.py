"""USDA FoodData Central fallback client with in-memory caching."""

from typing import Any

import httpx

from app.config import get_settings
from app.core.nutrition.food_db import FoodItem, GICategory

USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

NUTRIENT_ENERGY_KCAL = 1008
NUTRIENT_PROTEIN = 1003
NUTRIENT_CARBS = 1005
NUTRIENT_FAT = 1004
NUTRIENT_FIBER = 1079
NUTRIENT_SODIUM_MG = 1093


class USDAClientError(Exception):
    """Raised when a USDA FoodData Central lookup fails."""


def _extract_nutrients(raw_nutrients: list[dict[str, Any]]) -> dict[int, float]:
    """Map USDA nutrient IDs to numeric values."""
    extracted: dict[int, float] = {}
    for nutrient in raw_nutrients:
        nutrient_id = nutrient.get("nutrientId")
        value = nutrient.get("value")
        if isinstance(nutrient_id, int) and isinstance(value, (int, float)):
            extracted[nutrient_id] = max(0.0, float(value))
    return extracted


def _parse_usda_food(entry: dict[str, Any]) -> FoodItem:
    """Convert a USDA search result entry into a normalized 100g FoodItem."""
    fdc_id = entry["fdcId"]
    nutrients = _extract_nutrients(entry.get("foodNutrients") or [])
    description = str(entry.get("description", "")).strip() or f"USDA Food {fdc_id}"
    category = str(entry.get("foodCategory") or "usda").strip().lower()

    return FoodItem(
        id=f"usda_{fdc_id}",
        name=description,
        urdu_name="",
        aliases=[],
        category=category,
        serving_desc="100 g",
        grams=100.0,
        kcal=round(nutrients.get(NUTRIENT_ENERGY_KCAL, 0.0), 1),
        protein=round(nutrients.get(NUTRIENT_PROTEIN, 0.0), 1),
        carbs=round(nutrients.get(NUTRIENT_CARBS, 0.0), 1),
        fat=round(nutrients.get(NUTRIENT_FAT, 0.0), 1),
        fiber=round(nutrients.get(NUTRIENT_FIBER, 0.0), 1),
        sodium_mg=round(nutrients.get(NUTRIENT_SODIUM_MG, 0.0), 1),
        gi_category=GICategory.MEDIUM,
        tags=["usda"],
    )


class USDAClient:
    """Fallback client for looking up foods missing from the local Pakistani food table."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else get_settings().usda_api_key
        self.timeout_seconds = timeout_seconds
        self._client = client
        self._cache: dict[tuple[str, int], list[FoodItem]] = {}

    def _request_search(self, query: str, page_size: int) -> dict[str, Any]:
        """Execute the HTTP GET request against the USDA FDC search endpoint."""
        params: dict[str, str | int] = {
            "query": query,
            "pageSize": page_size,
            "api_key": self.api_key,
        }
        try:
            if self._client is not None:
                response = self._client.get(USDA_SEARCH_URL, params=params)
                response.raise_for_status()
                return response.json()

            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(USDA_SEARCH_URL, params=params)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise USDAClientError(f"USDA API lookup failed: {exc}") from exc

    def search(self, query: str, page_size: int = 5) -> list[FoodItem]:
        """Search USDA FoodData Central and cache normalized results per query."""
        query_clean = query.strip()
        if not query_clean or page_size <= 0:
            return []

        cache_key = (query_clean.lower(), page_size)
        if cache_key in self._cache:
            return list(self._cache[cache_key])

        payload = self._request_search(query_clean, page_size)
        raw_foods = payload.get("foods") or []
        items = [_parse_usda_food(entry) for entry in raw_foods if "fdcId" in entry]
        self._cache[cache_key] = items
        return list(items)
