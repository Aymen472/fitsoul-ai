"""Live AI coach chat, history, pattern detection, and daily meal-plan API routes."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai import (
    AIMealPlanner,
    ChatTurn,
    CoachAgent,
    CoachIntent,
    MealSwapResult,
    PatternReport,
    WeeklyMealPlan,
    compute_text_embedding,
    detect_emotional_patterns,
    extract_memory_facts,
    retrieve_relevant_memories,
)
from app.core.safety import MealType, SafetyCategory, ValidatedMealPlan
from app.db import (
    MealLogRepository,
    MemoryRepository,
    MessageRecord,
    MessageRepository,
    MoodLogRepository,
    ProfileRepository,
    UserMemoryRecord,
    get_db,
)

router = APIRouter(prefix="/api/v1", tags=["chat", "meal-plans"])


def get_coach_agent() -> CoachAgent:
    """FastAPI dependency returning the default CoachAgent instance."""
    return CoachAgent()


def get_meal_planner() -> AIMealPlanner:
    """FastAPI dependency returning the default AIMealPlanner instance."""
    return AIMealPlanner()


DbSession = Annotated[Session, Depends(get_db)]
CoachAgentDep = Annotated[CoachAgent, Depends(get_coach_agent)]
MealPlannerDep = Annotated[AIMealPlanner, Depends(get_meal_planner)]


class ChatRequest(BaseModel):
    """Incoming chat message payload from web PWA or WhatsApp channel."""

    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=4000)
    channel: Literal["web", "whatsapp"] = "web"


class ChatResponse(BaseModel):
    """Structured response returned by POST /api/v1/chat."""

    user_id: str
    reply: str
    intent: CoachIntent
    flagged_safety: bool
    safety_category: SafetyCategory
    stop_diet_advice: bool
    grounded_data: dict[str, Any]
    used_fallback: bool
    saved_memories: list[UserMemoryRecord]
    used_memories: list[str]
    user_message_id: str
    assistant_message_id: str


class ChatHistoryResponse(BaseModel):
    """Persisted conversation history for a user."""

    user_id: str
    messages: list[MessageRecord]


class ChatMemoriesResponse(BaseModel):
    """Persisted long-term semantic memories for a user."""

    user_id: str
    memories: list[UserMemoryRecord]


class MealSwapRequest(BaseModel):
    """Request payload for swapping a meal slot with a fresh desi alternative."""

    day_index: int = Field(default=0, ge=0, le=30)
    meal_type: MealType
    exclude_food_ids: list[str] = Field(default_factory=list, max_length=20)
    attempt: int = Field(default=1, ge=1, le=20)


@router.post("/chat", response_model=ChatResponse)
def post_chat_message(
    payload: ChatRequest,
    db: DbSession,
    coach: CoachAgentDep,
) -> ChatResponse:
    """Process a user message with safety guardrails, memory recall, and persistence."""
    record = ProfileRepository.get_profile(db, payload.user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    recent_messages = MessageRepository.get_recent_messages(db, payload.user_id, limit=20)
    history = [
        ChatTurn(role=msg.role, content=msg.content)
        for msg in recent_messages
        if msg.role in ("user", "assistant")
    ]

    all_memories = MemoryRepository.list_memories(db, payload.user_id)
    relevant_memories = retrieve_relevant_memories(payload.message, all_memories, top_k=5)
    today_summary = MealLogRepository.get_daily_meal_logs(
        db, payload.user_id, datetime.now(UTC).date()
    )

    coach_reply = coach.respond(
        payload.message,
        record.profile,
        history=history,
        memories=[mem.content for mem in relevant_memories],
        daily_logged_kcal=today_summary.total_kcal,
    )

    now = datetime.now(UTC)
    user_msg = MessageRepository.save_message(
        db,
        payload.user_id,
        "user",
        payload.message,
        channel=payload.channel,
        flagged_safety=coach_reply.flagged_safety,
        embedding=compute_text_embedding(payload.message),
        created_at=now,
    )
    assistant_msg = MessageRepository.save_message(
        db,
        payload.user_id,
        "assistant",
        coach_reply.reply,
        channel=payload.channel,
        flagged_safety=False,
        embedding=compute_text_embedding(coach_reply.reply),
        created_at=now + timedelta(microseconds=1),
    )

    saved_memories: list[UserMemoryRecord] = []
    if not coach_reply.stop_diet_advice and not coach_reply.flagged_safety:
        for extracted in extract_memory_facts(payload.message):
            saved = MemoryRepository.save_memory(
                db,
                payload.user_id,
                extracted.category.value,
                extracted.content,
                embedding=compute_text_embedding(extracted.content),
            )
            saved_memories.append(saved)

    used_memories = list(coach_reply.grounded_data.get("used_memories", []))

    return ChatResponse(
        user_id=payload.user_id,
        reply=coach_reply.reply,
        intent=coach_reply.intent,
        flagged_safety=coach_reply.flagged_safety,
        safety_category=coach_reply.safety_category,
        stop_diet_advice=coach_reply.stop_diet_advice,
        grounded_data=coach_reply.grounded_data,
        used_fallback=coach_reply.used_fallback,
        saved_memories=saved_memories,
        used_memories=used_memories,
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
    )


@router.get("/chat/{user_id}/history", response_model=ChatHistoryResponse)
def get_chat_history(
    user_id: str,
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=500),
) -> ChatHistoryResponse:
    """Return persistent chat history for a user in chronological order."""
    record = ProfileRepository.get_profile(db, user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    messages = MessageRepository.get_recent_messages(db, user_id, limit=limit)
    return ChatHistoryResponse(user_id=user_id, messages=messages)


@router.get("/chat/{user_id}/memories", response_model=ChatMemoriesResponse)
def get_user_memories(user_id: str, db: DbSession) -> ChatMemoriesResponse:
    """Return all persisted long-term memories for a user (newest first)."""
    record = ProfileRepository.get_profile(db, user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    memories = MemoryRepository.list_memories(db, user_id)
    return ChatMemoriesResponse(user_id=user_id, memories=memories)


@router.get("/chat/{user_id}/patterns", response_model=PatternReport)
def get_user_patterns(
    user_id: str,
    db: DbSession,
    days: int = Query(default=14, ge=1, le=90),
) -> PatternReport:
    """Analyze recent chat, meal, mood, and memory logs for emotional patterns."""
    record = ProfileRepository.get_profile(db, user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    now = datetime.now(UTC)
    messages = MessageRepository.get_messages_since(db, user_id, days=days, now=now)
    meal_logs = MealLogRepository.get_recent_meal_logs(db, user_id, days=days, now=now)
    mood_logs = MoodLogRepository.get_recent_mood_logs(db, user_id, days=days, now=now)
    memories = MemoryRepository.list_memories(db, user_id)

    return detect_emotional_patterns(
        messages=messages,
        meal_logs=meal_logs,
        mood_logs=mood_logs,
        daily_target_kcal=record.targets.calories,
        timezone_name=record.profile.timezone,
        memories=memories,
    )


@router.post("/meal-plans/{user_id}/daily", response_model=ValidatedMealPlan)
def generate_daily_meal_plan(
    user_id: str,
    db: DbSession,
    planner: MealPlannerDep,
    day_index: int = Query(default=0, ge=0, le=30),
) -> ValidatedMealPlan:
    """Generate and deterministically validate a daily Pakistani meal plan."""
    record = ProfileRepository.get_profile(db, user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    return planner.generate_daily_plan(record.profile, day_index=day_index)


@router.post("/meal-plans/{user_id}/weekly", response_model=WeeklyMealPlan)
def generate_weekly_meal_plan(
    user_id: str,
    db: DbSession,
    planner: MealPlannerDep,
    days: int = Query(default=7, ge=1, le=7),
) -> WeeklyMealPlan:
    """Generate a multi-day validated Pakistani meal plan and consolidated grocery list."""
    record = ProfileRepository.get_profile(db, user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    return planner.generate_weekly_plan(record.profile, days=days)


@router.post("/meal-plans/{user_id}/swap", response_model=MealSwapResult)
def swap_meal_plan_slot(
    user_id: str,
    payload: MealSwapRequest,
    db: DbSession,
    planner: MealPlannerDep,
) -> MealSwapResult:
    """Swap a meal slot in a day's plan while preserving all clinical nutrition limits."""
    record = ProfileRepository.get_profile(db, user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    return planner.swap_meal_day(
        record.profile,
        meal_type=payload.meal_type,
        day_index=payload.day_index,
        exclude_food_ids=payload.exclude_food_ids,
        attempt=payload.attempt,
    )
