"""Meal photo scanner using Gemini Vision, FoodDatabase matching, and deterministic scaling."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.ai.client import GeminiClient
from app.ai.tracing import AIUsage
from app.core.nutrition import FoodDatabase, FoodItem, get_food_db
from app.services import USDAClient, USDAClientError

LOW_CONFIDENCE_THRESHOLD = 0.75
MAX_CANDIDATES = 3
MIN_SERVING_MULTIPLIER = 0.1
DEFAULT_VISION_PROMPT_PATH = (
    Path(__file__).resolve().parent / "prompts" / "photo_scanner_system.txt"
)


class DetectedFoodItem(BaseModel):
    """Single food item identified in a photo by Gemini Vision."""

    food_name: str
    estimated_portion: str
    grams: float = Field(gt=0, le=2000)
    confidence: float = Field(ge=0.0, le=1.0)


class RawPhotoScanResult(BaseModel):
    """Structured JSON response expected from Gemini Vision."""

    items: list[DetectedFoodItem]
    plate_notes: str = ""


class FoodCandidate(BaseModel):
    """Suggested FoodDatabase candidate for low-confidence confirmation."""

    food_id: str
    name: str
    urdu_name: str = ""
    serving_desc: str


class MatchedMealItem(BaseModel):
    """Detected food item matched to a DB record with deterministic nutrition totals."""

    detected_name: str
    estimated_portion: str
    matched_food_id: str | None
    matched_name: str
    grams: float
    servings: float
    kcal: float
    protein: float
    carbs: float
    fat: float
    fiber: float
    sodium_mg: float
    confidence: float
    needs_confirmation: bool
    confirmation_question: str | None = None
    candidate_options: list[FoodCandidate] = Field(default_factory=list)
    source: Literal["pakistani_db", "usda", "unmatched"]


class MealEditItem(BaseModel):
    """User-confirmed or edited food selection and serving count."""

    food_id: str
    servings: float = Field(gt=0, le=20.0)


class PhotoScanSummary(BaseModel):
    """Complete meal nutrition breakdown computed deterministically from food databases."""

    items: list[MatchedMealItem]
    total_kcal: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    total_fiber_g: float
    total_sodium_mg: float
    needs_confirmation: bool
    confirmation_prompts: list[str] = Field(default_factory=list)
    plate_notes: str = ""
    usage: AIUsage | None = None


def _to_candidate(food: FoodItem) -> FoodCandidate:
    return FoodCandidate(
        food_id=food.id,
        name=food.name,
        urdu_name=food.urdu_name,
        serving_desc=food.serving_desc,
    )


def _build_confirmation_question(
    detected: DetectedFoodItem,
    candidates: list[FoodCandidate],
) -> str:
    if len(candidates) >= 2:
        return (
            f"Kya yeh {candidates[0].name} hai ya {candidates[1].name}? "
            "Portion confirm ya edit kar dein."
        )
    if len(candidates) == 1:
        return (
            f"Kya yeh {candidates[0].name} ({detected.estimated_portion}) hai? "
            "Confirm ya edit kar dein."
        )
    return f"'{detected.food_name}' food database mein match nahi hua — sahi dish select karein."


def _summarize_items(
    items: list[MatchedMealItem],
    *,
    plate_notes: str = "",
    usage: AIUsage | None = None,
) -> PhotoScanSummary:
    confirmation_prompts = [
        item.confirmation_question
        for item in items
        if item.needs_confirmation and item.confirmation_question
    ]
    return PhotoScanSummary(
        items=items,
        total_kcal=round(sum(item.kcal for item in items), 1),
        total_protein_g=round(sum(item.protein for item in items), 1),
        total_carbs_g=round(sum(item.carbs for item in items), 1),
        total_fat_g=round(sum(item.fat for item in items), 1),
        total_fiber_g=round(sum(item.fiber for item in items), 1),
        total_sodium_mg=round(sum(item.sodium_mg for item in items), 1),
        needs_confirmation=any(item.needs_confirmation for item in items),
        confirmation_prompts=confirmation_prompts,
        plate_notes=plate_notes,
        usage=usage,
    )


class MealPhotoScanner:
    """Identifies foods in meal photos via Gemini Vision and computes calories from Food DB."""

    def __init__(
        self,
        gemini_client: GeminiClient | None = None,
        food_db: FoodDatabase | None = None,
        usda_client: USDAClient | None = None,
        confidence_threshold: float = LOW_CONFIDENCE_THRESHOLD,
        system_prompt_path: Path = DEFAULT_VISION_PROMPT_PATH,
    ) -> None:
        self.gemini_client = gemini_client if gemini_client is not None else GeminiClient()
        self.food_db = food_db if food_db is not None else get_food_db()
        self.usda_client = usda_client if usda_client is not None else USDAClient()
        self.confidence_threshold = confidence_threshold
        self.system_prompt = system_prompt_path.read_text(encoding="utf-8")

    def _match_detected_item(self, detected: DetectedFoodItem) -> MatchedMealItem:
        local_matches = self.food_db.search(detected.food_name, limit=MAX_CANDIDATES)
        source: Literal["pakistani_db", "usda", "unmatched"] = "pakistani_db"
        matches = local_matches

        if not matches:
            try:
                usda_matches = self.usda_client.search(detected.food_name, page_size=MAX_CANDIDATES)
            except USDAClientError:
                usda_matches = []
            if usda_matches:
                matches = usda_matches
                source = "usda"

        if not matches:
            question = _build_confirmation_question(detected, [])
            return MatchedMealItem(
                detected_name=detected.food_name,
                estimated_portion=detected.estimated_portion,
                matched_food_id=None,
                matched_name=detected.food_name,
                grams=round(detected.grams, 1),
                servings=0.0,
                kcal=0.0,
                protein=0.0,
                carbs=0.0,
                fat=0.0,
                fiber=0.0,
                sodium_mg=0.0,
                confidence=detected.confidence,
                needs_confirmation=True,
                confirmation_question=question,
                candidate_options=[],
                source="unmatched",
            )

        best = matches[0]
        servings = max(MIN_SERVING_MULTIPLIER, round(detected.grams / best.grams, 2))
        scaled = best.scale(servings)
        candidates = [_to_candidate(item) for item in matches]
        needs_confirm = detected.confidence < self.confidence_threshold
        question = _build_confirmation_question(detected, candidates) if needs_confirm else None

        return MatchedMealItem(
            detected_name=detected.food_name,
            estimated_portion=detected.estimated_portion,
            matched_food_id=best.id,
            matched_name=best.name,
            grams=scaled.grams,
            servings=servings,
            kcal=scaled.kcal,
            protein=scaled.protein,
            carbs=scaled.carbs,
            fat=scaled.fat,
            fiber=scaled.fiber,
            sodium_mg=scaled.sodium_mg,
            confidence=detected.confidence,
            needs_confirmation=needs_confirm,
            confirmation_question=question,
            candidate_options=candidates,
            source=source,
        )

    def scan_photo(
        self,
        image_bytes: bytes,
        mime_type: str,
        *,
        user_hint: str | None = None,
    ) -> PhotoScanSummary:
        """Analyze a meal photo via Gemini Vision and match all items to verified Food DB."""
        prompt = "Identify every food item on this plate, its portion, grams, and confidence."
        if user_hint and user_hint.strip():
            prompt = f"{prompt}\nUser context: {user_hint.strip()}"

        raw_result, usage = self.gemini_client.analyze_image(
            image_bytes=image_bytes,
            mime_type=mime_type,
            prompt=prompt,
            response_schema=RawPhotoScanResult,
            system_instruction=self.system_prompt,
            trace_name="meal_photo_scan",
        )
        matched = [self._match_detected_item(item) for item in raw_result.items]
        return _summarize_items(matched, plate_notes=raw_result.plate_notes, usage=usage)

    def recalculate_from_edits(
        self,
        edits: list[MealEditItem],
        *,
        plate_notes: str = "",
    ) -> PhotoScanSummary:
        """Recalculate exact meal nutrition after a user confirms or edits portions."""
        matched: list[MatchedMealItem] = []
        for edit in edits:
            food = self.food_db.get_by_id(edit.food_id)
            if food is None:
                raise ValueError(f"Unknown food_id: '{edit.food_id}'")
            scaled = food.scale(edit.servings)
            matched.append(
                MatchedMealItem(
                    detected_name=food.name,
                    estimated_portion=food.serving_desc,
                    matched_food_id=food.id,
                    matched_name=food.name,
                    grams=scaled.grams,
                    servings=edit.servings,
                    kcal=scaled.kcal,
                    protein=scaled.protein,
                    carbs=scaled.carbs,
                    fat=scaled.fat,
                    fiber=scaled.fiber,
                    sodium_mg=scaled.sodium_mg,
                    confidence=1.0,
                    needs_confirmation=False,
                    confirmation_question=None,
                    candidate_options=[_to_candidate(food)],
                    source="pakistani_db",
                )
            )
        return _summarize_items(matched, plate_notes=plate_notes, usage=None)
