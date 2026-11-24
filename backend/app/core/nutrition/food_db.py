"""Local Pakistani/South Asian food database, fuzzy search, and rule-based filtering."""

import csv
import re
from difflib import SequenceMatcher
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field

from app.core.rules import NutritionTargets
from app.models import DietType

DEFAULT_FOODS_CSV = Path(__file__).resolve().parents[4] / "data" / "foods" / "pakistani_foods.csv"


class GICategory(StrEnum):
    """Glycemic Index classification for a food item."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ScaledNutrition(BaseModel):
    """Nutrition totals scaled deterministically by serving count."""

    food_id: str
    name: str
    servings: float
    grams: float
    kcal: float
    protein: float
    carbs: float
    fat: float
    fiber: float
    sodium_mg: float


class FoodItem(BaseModel):
    """Verified nutrition entry for one standard serving of a food."""

    id: str
    name: str
    urdu_name: str = ""
    aliases: list[str] = Field(default_factory=list)
    category: str
    serving_desc: str
    grams: float = Field(gt=0)
    kcal: float = Field(ge=0)
    protein: float = Field(ge=0)
    carbs: float = Field(ge=0)
    fat: float = Field(ge=0)
    fiber: float = Field(ge=0)
    sodium_mg: float = Field(ge=0)
    gi_category: GICategory = GICategory.MEDIUM
    tags: list[str] = Field(default_factory=list)

    def scale(self, servings: float) -> ScaledNutrition:
        """Return deterministic macros and calories for the requested serving multiplier."""
        if servings <= 0:
            raise ValueError("servings must be positive")
        return ScaledNutrition(
            food_id=self.id,
            name=self.name,
            servings=servings,
            grams=round(self.grams * servings, 1),
            kcal=round(self.kcal * servings, 1),
            protein=round(self.protein * servings, 1),
            carbs=round(self.carbs * servings, 1),
            fat=round(self.fat * servings, 1),
            fiber=round(self.fiber * servings, 1),
            sodium_mg=round(self.sodium_mg * servings, 1),
        )


def _normalize_text(text: str) -> str:
    """Lowercase and collapse repeated whitespace."""
    return " ".join(text.lower().split())


def _split_pipe_field(raw: str | None) -> list[str]:
    """Split a pipe-delimited CSV field into clean non-empty items."""
    if not raw:
        return []
    return [part.strip() for part in raw.split("|") if part.strip()]


def _score_candidate(query_norm: str, query_tokens: set[str], candidate: str) -> float:
    """Compute a 0..1 similarity score between a normalized query and a candidate label."""
    cand_norm = _normalize_text(candidate)
    if not cand_norm:
        return 0.0
    if query_norm == cand_norm:
        return 1.0
    if cand_norm.startswith(query_norm):
        return 0.95
    if query_norm in cand_norm:
        return 0.88

    cand_tokens = set(cand_norm.split())
    if query_tokens and query_tokens.issubset(cand_tokens):
        return 0.85

    full_ratio = SequenceMatcher(None, query_norm, cand_norm).ratio()
    if query_tokens and cand_tokens:
        avg_token_best = sum(
            max((SequenceMatcher(None, qt, ct).ratio() for ct in cand_tokens), default=0.0)
            for qt in query_tokens
        ) / len(query_tokens)
    else:
        avg_token_best = 0.0

    return max(full_ratio, avg_token_best * 0.92)


def _matches_excluded_term(item: FoodItem, term_pattern: re.Pattern[str]) -> bool:
    """Return True if an allergy or dislike pattern matches any name, alias, or tag."""
    searchable = [item.name, item.urdu_name, *item.aliases, *item.tags]
    return any(term_pattern.search(_normalize_text(text)) for text in searchable if text)


class FoodDatabase:
    """In-memory food catalog supporting fuzzy search and medical rule filtering."""

    def __init__(self, foods: list[FoodItem]) -> None:
        self._foods: list[FoodItem] = []
        self._by_id: dict[str, FoodItem] = {}
        for food in foods:
            if food.id in self._by_id:
                raise ValueError(f"Duplicate food id: '{food.id}'")
            self._foods.append(food)
            self._by_id[food.id] = food

    @classmethod
    def from_csv(cls, csv_path: Path = DEFAULT_FOODS_CSV) -> Self:
        """Load and validate FoodItem records from a CSV table."""
        items: list[FoodItem] = []
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                items.append(
                    FoodItem(
                        id=row["id"].strip(),
                        name=row["name"].strip(),
                        urdu_name=row.get("urdu_name", "").strip(),
                        aliases=_split_pipe_field(row.get("aliases")),
                        category=row["category"].strip(),
                        serving_desc=row["serving_desc"].strip(),
                        grams=float(row["grams"]),
                        kcal=float(row["kcal"]),
                        protein=float(row["protein"]),
                        carbs=float(row["carbs"]),
                        fat=float(row["fat"]),
                        fiber=float(row["fiber"]),
                        sodium_mg=float(row["sodium_mg"]),
                        gi_category=GICategory(row["gi_category"].strip().lower()),
                        tags=_split_pipe_field(row.get("tags")),
                    )
                )
        return cls(items)

    @property
    def count(self) -> int:
        """Total number of foods loaded in the database."""
        return len(self._foods)

    def all_foods(self) -> list[FoodItem]:
        """Return a copy of all loaded FoodItem entries."""
        return list(self._foods)

    def get_by_id(self, food_id: str) -> FoodItem | None:
        """Look up a single food by its exact identifier."""
        return self._by_id.get(food_id)

    def search(self, query: str, limit: int = 10, min_score: float = 0.55) -> list[FoodItem]:
        """Fuzzy-match foods across English names, Urdu names, and aliases."""
        query_norm = _normalize_text(query)
        if not query_norm or limit <= 0:
            return []

        query_tokens = set(query_norm.split())
        scored: list[tuple[float, FoodItem]] = []
        for item in self._foods:
            candidates = [item.name, item.urdu_name, *item.aliases]
            best_score = max(_score_candidate(query_norm, query_tokens, c) for c in candidates)
            if best_score >= min_score:
                scored.append((best_score, item))

        scored.sort(key=lambda pair: (-pair[0], pair[1].name))
        return [item for _, item in scored[:limit]]

    def filter_for_targets(
        self,
        targets: NutritionTargets,
        diet_type: DietType = DietType.NON_VEG,
        allergies: list[str] | None = None,
        dislikes: list[str] | None = None,
    ) -> list[FoodItem]:
        """Filter foods according to forbidden rule tags, diet type, allergies, and dislikes."""
        forbidden = set(targets.forbidden_tags)
        raw_terms = [*(allergies or []), *(dislikes or [])]
        patterns = [
            re.compile(rf"\b{re.escape(norm)}(?:s|es)?\b")
            for term in raw_terms
            if (norm := _normalize_text(term))
        ]

        allowed: list[FoodItem] = []
        for food in self._foods:
            food_tags = set(food.tags)
            if forbidden & food_tags:
                continue
            if diet_type == DietType.VEG and "veg" not in food_tags:
                continue
            if diet_type == DietType.EGGETARIAN and "non_veg" in food_tags:
                continue
            if patterns and any(_matches_excluded_term(food, pat) for pat in patterns):
                continue
            allowed.append(food)

        return allowed


@lru_cache
def get_food_db(csv_path: Path = DEFAULT_FOODS_CSV) -> FoodDatabase:
    """Return a cached FoodDatabase instance loaded from CSV."""
    return FoodDatabase.from_csv(csv_path)
