"""AI clients, prompts, and conversation agents."""

from app.ai.client import (
    DEFAULT_FLASH_MODEL,
    DEFAULT_PRO_MODEL,
    AITextResponse,
    GeminiAuthError,
    GeminiClient,
    GeminiClientError,
    GeminiResponseFormatError,
    estimate_cost_usd,
)
from app.ai.coach import ChatTurn, CoachAgent, CoachReply
from app.ai.intent_router import CoachIntent, classify_intent, parse_text_meal_items
from app.ai.meal_planner import (
    AIMealPlanner,
    GroceryItem,
    WeeklyMealPlan,
    build_fallback_meal_plan,
    build_grocery_list,
)
from app.ai.photo_scanner import (
    LOW_CONFIDENCE_THRESHOLD,
    DetectedFoodItem,
    FoodCandidate,
    MatchedMealItem,
    MealEditItem,
    MealPhotoScanner,
    PhotoScanSummary,
    RawPhotoScanResult,
)
from app.ai.tracing import (
    AITraceEvent,
    AIUsage,
    LangfuseTraceSink,
    TraceSink,
    build_default_trace_sink,
    log_trace_event,
)

__all__ = [
    "AIMealPlanner",
    "AITextResponse",
    "AITraceEvent",
    "AIUsage",
    "ChatTurn",
    "CoachAgent",
    "CoachIntent",
    "CoachReply",
    "DEFAULT_FLASH_MODEL",
    "DEFAULT_PRO_MODEL",
    "DetectedFoodItem",
    "FoodCandidate",
    "GeminiAuthError",
    "GeminiClient",
    "GeminiClientError",
    "GeminiResponseFormatError",
    "GroceryItem",
    "LOW_CONFIDENCE_THRESHOLD",
    "LangfuseTraceSink",
    "MatchedMealItem",
    "MealEditItem",
    "MealPhotoScanner",
    "PhotoScanSummary",
    "RawPhotoScanResult",
    "TraceSink",
    "WeeklyMealPlan",
    "build_default_trace_sink",
    "build_fallback_meal_plan",
    "build_grocery_list",
    "classify_intent",
    "estimate_cost_usd",
    "log_trace_event",
    "parse_text_meal_items",
]
