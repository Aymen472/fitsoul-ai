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
from app.ai.meal_planner import (
    AIMealPlanner,
    GroceryItem,
    WeeklyMealPlan,
    build_fallback_meal_plan,
    build_grocery_list,
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
    "DEFAULT_FLASH_MODEL",
    "DEFAULT_PRO_MODEL",
    "GeminiAuthError",
    "GeminiClient",
    "GeminiClientError",
    "GeminiResponseFormatError",
    "GroceryItem",
    "LangfuseTraceSink",
    "TraceSink",
    "WeeklyMealPlan",
    "build_default_trace_sink",
    "build_fallback_meal_plan",
    "build_grocery_list",
    "estimate_cost_usd",
    "log_trace_event",
]
