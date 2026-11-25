"""Long-term semantic memory extraction, retrieval, and emotional pattern detection."""

import math
import re
import zlib
from collections import defaultdict
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

from app.db.repository import MealLogRecord, MessageRecord, MoodLogRecord, UserMemoryRecord

DEFAULT_EMBEDDING_DIM = 64
MAX_MEMORY_CONTENT_CHARS = 200
WEEKEND_SLIP_THRESHOLD_RATIO = 1.15
DEFAULT_TIMEZONE = "Asia/Karachi"

_WORD_RE = re.compile(r"[a-z0-9]+")
_CLAUSE_SPLIT_RE = re.compile(r"[!?\n;]+|\.(?!\d)")

_WIN_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(?:lost\s+\d+(?:\.\d+)?\s*(?:kg|kilo|kgs|lb|lbs))\b",
        r"\b\d+(?:\.\d+)?\s*(?:kg|kilo|kgs)\s+(?:kam|weight\s+kam|down|lost)\b",
        r"\b(?:is\s+hafte|this\s+week)\b.*\b\d+(?:\.\d+)?\s*(?:kg|kilo|kgs)\b",
        r"\b\d+\s*(?:days?|din)\s+(?:ka\s+)?streak\b",
        r"\b(?:completed\s+(?:my\s+)?workout|workout\s+(?:complete|kiya|kar\s+liya|ho\s+gaya))\b",
        r"\b(?:aaj\s+(?:maine\s+)?walk\s+ki|sugar\s+skip\s+ki|no\s+sugar\s+(?:for|today)|craving\s+control\s+ki)\b",
    )
)

_TRIGGER_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\braat\s+ko\b.*\b(?:craving|bhook|meetha|snack|kha|khane|ice\s*cream|chocolate|sweet)\b",
        r"\b(?:late[- ]?night|midnight)\b.*\b(?:craving|snack|eat|eating|hunger|sweet)\b",
        r"\b(?:stress|tension)\s+(?:mein|me|ki\s+wajah\s+se)\b",
        r"\bwhen\s+(?:i'?m|i\s+am)\s+(?:stressed|bored|tired|anxious|sad)\b",
        r"\b(?:bored(?:om)?\s+eat(?:ing)?|emotional\s+eat(?:ing)?|stress\s+eat(?:ing)?|office\s+stress)\b",
    )
)

_PREFERENCE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(?:i\s+love|i\s+really\s+like|i\s+prefer|i\s+hate|i\s+dislike|i\s+don'?t\s+like|i\s+do\s+not\s+like|allergic\s+to)\b",
        r"\b(?:pasand\s+hai|bohat\s+pasand|pasand\s+nahi|nahi\s+pasand|ach[aei]\s+lagta|bura\s+lagta|nahi\s+khat[aei])\b",
    )
)

_FACT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(?:night\s+shift|work\s+from\s+home|office\s+(?:timing|hours)|hostel\s+mein)\b",
        r"\b(?:shaadi\s+(?:hai|in\s+\d+)|wedding\s+in\s+\d+|ramadan|roza|sehri|iftar)\b",
    )
)

_LATE_NIGHT_CUE_RE = re.compile(
    r"\b(?:craving|crave|hungry|bhook|meetha|sweet|snack|eat|ate|kha|khaya|khai|chai|biscuit|chocolate|ice\s*cream|chips)\b",
    re.IGNORECASE,
)
_STRESS_MESSAGE_RE = re.compile(
    r"\b(?:stress(?:ed)?|tension|overwhelmed|guilt(?:y)?|anxious|"
    r"mood off|emotional eat(?:ing)?|binge|comfort food)\b",
    re.IGNORECASE,
)

_STRESS_MOODS = frozenset(
    {"stressed", "stress", "anxious", "guilty", "sad", "overwhelmed", "frustrated", "low"}
)
_POSITIVE_MOODS = frozenset({"happy", "proud", "motivated", "energized", "great"})


class MemoryCategory(StrEnum):
    """Supported categories of extracted long-term user memories."""

    PREFERENCE = "preference"
    TRIGGER = "trigger"
    WIN = "win"
    FACT = "fact"


class ExtractedMemory(BaseModel):
    """Structured memory fact extracted from a user message."""

    category: MemoryCategory
    content: str


class PatternType(StrEnum):
    """Behavioral and emotional patterns surfaced from user history."""

    LATE_NIGHT_CRAVING = "late_night_craving"
    WEEKEND_CALORIE_SLIP = "weekend_calorie_slip"
    STRESS_EATING = "stress_eating"
    MICRO_WIN = "micro_win"


class EmotionalPattern(BaseModel):
    """Detected behavioral or emotional eating pattern."""

    pattern_type: PatternType
    severity: Literal["positive", "low", "medium", "high"]
    occurrences: int
    description: str
    evidence: list[str] = Field(default_factory=list)


class ProactiveNudge(BaseModel):
    """Targeted compassionate check-in suggested for an active pattern."""

    pattern_type: PatternType
    suggested_timing: str
    channel: Literal["web", "whatsapp"] = "web"
    message: str


class PatternReport(BaseModel):
    """Summary of emotional patterns and proactive coaching nudges."""

    patterns: list[EmotionalPattern] = Field(default_factory=list)
    nudges: list[ProactiveNudge] = Field(default_factory=list)
    summary: str


def _ensure_utc(dt: datetime) -> datetime:
    """Normalize naive or tz-aware datetimes to UTC."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _to_local_dt(dt: datetime, tz: ZoneInfo) -> datetime:
    """Convert any datetime safely into the target user timezone."""
    return _ensure_utc(dt).astimezone(tz)


def _resolve_timezone(timezone_name: str) -> ZoneInfo:
    """Resolve an IANA timezone string with a safe Asia/Karachi fallback."""
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def _feature_bucket(feature: str, dim: int) -> tuple[int, float]:
    """Map a text feature deterministically to a vector index and +/-1 sign."""
    idx = zlib.crc32(f"idx:{feature}".encode()) % dim
    sign = 1.0 if (zlib.crc32(f"sgn:{feature}".encode()) & 1) == 0 else -1.0
    return idx, sign


def compute_text_embedding(text: str, dim: int = DEFAULT_EMBEDDING_DIM) -> list[float]:
    """Compute a deterministic signed hashed token + character-trigram unit vector."""
    if dim < 1:
        raise ValueError("Embedding dimension must be at least 1")

    tokens = _WORD_RE.findall(text.lower())
    if not tokens:
        return [0.0] * dim

    vec = [0.0] * dim
    for tok in tokens:
        word_idx, word_sign = _feature_bucket(f"w:{tok}", dim)
        vec[word_idx] += word_sign * 3.0
        if len(tok) >= 4:
            for start in range(len(tok) - 2):
                trigram = tok[start : start + 3]
                tri_idx, tri_sign = _feature_bucket(f"g:{trigram}", dim)
                vec[tri_idx] += tri_sign * 1.0

    norm = math.sqrt(sum(val * val for val in vec))
    if norm == 0.0:
        return [0.0] * dim
    return [val / norm for val in vec]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two equal-length vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=True))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve_relevant_memories(
    query: str,
    memories: list[UserMemoryRecord],
    *,
    top_k: int = 5,
    min_similarity: float = 0.1,
) -> list[UserMemoryRecord]:
    """Rank and return the top-K persisted memories most relevant to `query`."""
    if not memories or top_k < 1:
        return []

    query_vec = compute_text_embedding(query)
    dim = len(query_vec)
    scored: list[tuple[float, datetime, UserMemoryRecord]] = []

    for mem in memories:
        mem_vec = (
            mem.embedding
            if mem.embedding and len(mem.embedding) == dim
            else compute_text_embedding(mem.content, dim=dim)
        )
        score = cosine_similarity(query_vec, mem_vec)
        if score >= min_similarity:
            scored.append((score, _ensure_utc(mem.created_at), mem))

    scored.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    return [entry[2] for entry in scored[:top_k]]


def _truncate_memory(text: str) -> str:
    if len(text) <= MAX_MEMORY_CONTENT_CHARS:
        return text
    return f"{text[: MAX_MEMORY_CONTENT_CHARS - 3].rstrip()}..."


def extract_memory_facts(message: str) -> list[ExtractedMemory]:
    """Deterministically extract preferences, triggers, wins, and facts from chat text."""
    results: list[ExtractedMemory] = []
    seen: set[tuple[MemoryCategory, str]] = set()

    ordered_rules: tuple[tuple[MemoryCategory, tuple[re.Pattern[str], ...]], ...] = (
        (MemoryCategory.WIN, _WIN_PATTERNS),
        (MemoryCategory.TRIGGER, _TRIGGER_PATTERNS),
        (MemoryCategory.PREFERENCE, _PREFERENCE_PATTERNS),
        (MemoryCategory.FACT, _FACT_PATTERNS),
    )

    for raw_clause in _CLAUSE_SPLIT_RE.split(message):
        clause = " ".join(raw_clause.split()).strip()
        if len(clause) < 5:
            continue

        matched_category: MemoryCategory | None = None
        for category, patterns in ordered_rules:
            if any(pat.search(clause) for pat in patterns):
                matched_category = category
                break

        if matched_category is None:
            continue

        content = _truncate_memory(clause)
        key = (matched_category, content.lower())
        if key in seen:
            continue
        seen.add(key)
        results.append(ExtractedMemory(category=matched_category, content=content))

    return results


def _detect_late_night_pattern(
    messages: list[MessageRecord],
    meal_logs: list[MealLogRecord],
    tz: ZoneInfo,
) -> tuple[EmotionalPattern, ProactiveNudge] | None:
    evidence: list[str] = []
    for msg in messages:
        if msg.role != "user":
            continue
        local_dt = _to_local_dt(msg.created_at, tz)
        if (local_dt.hour >= 22 or local_dt.hour < 4) and _LATE_NIGHT_CUE_RE.search(msg.content):
            snippet = msg.content[:80].strip()
            evidence.append(f"Chat at {local_dt:%Y-%m-%d %H:%M}: {snippet}")

    for meal in meal_logs:
        local_dt = _to_local_dt(meal.logged_at, tz)
        if local_dt.hour >= 22 or local_dt.hour < 4:
            evidence.append(
                f"Meal logged at {local_dt:%Y-%m-%d %H:%M} "
                f"({meal.meal_type}, {meal.total_kcal:.0f} kcal)"
            )

    if len(evidence) < 2:
        return None

    severity: Literal["medium", "high"] = "high" if len(evidence) >= 4 else "medium"
    pattern = EmotionalPattern(
        pattern_type=PatternType.LATE_NIGHT_CRAVING,
        severity=severity,
        occurrences=len(evidence),
        description=(
            f"Detected {len(evidence)} late-night food cravings or meals between 10 PM and 4 AM."
        ),
        evidence=evidence[:5],
    )
    nudge = ProactiveNudge(
        pattern_type=PatternType.LATE_NIGHT_CRAVING,
        suggested_timing="21:30 daily",
        channel="web",
        message=(
            "Raat 9:30 baje ka quick check-in: agar late-night craving aaye to ek cup garam "
            "chamomile/sabz chai, roasted makhana (25g), ya 1 boiled egg try karein — bina "
            "guilt ke cravings calm ho jayengi!"
        ),
    )
    return pattern, nudge


def _detect_weekend_slip_pattern(
    meal_logs: list[MealLogRecord],
    daily_target_kcal: int,
    tz: ZoneInfo,
) -> tuple[EmotionalPattern, ProactiveNudge] | None:
    if daily_target_kcal <= 0:
        return None

    daily_totals: dict[date, float] = defaultdict(float)
    for meal in meal_logs:
        local_date = _to_local_dt(meal.logged_at, tz).date()
        daily_totals[local_date] += meal.total_kcal

    threshold = daily_target_kcal * WEEKEND_SLIP_THRESHOLD_RATIO
    evidence: list[str] = []
    for day in sorted(daily_totals):
        if day.weekday() in (5, 6) and daily_totals[day] > threshold:
            day_name = "Saturday" if day.weekday() == 5 else "Sunday"
            evidence.append(
                f"{day:%Y-%m-%d} ({day_name}): {daily_totals[day]:.0f} kcal vs "
                f"{daily_target_kcal} kcal target"
            )

    if len(evidence) < 2:
        return None

    severity: Literal["medium", "high"] = "high" if len(evidence) >= 4 else "medium"
    pattern = EmotionalPattern(
        pattern_type=PatternType.WEEKEND_CALORIE_SLIP,
        severity=severity,
        occurrences=len(evidence),
        description=(
            f"Weekend intake exceeded your {daily_target_kcal} kcal target by >15% on "
            f"{len(evidence)} days."
        ),
        evidence=evidence[:5],
    )
    nudge = ProactiveNudge(
        pattern_type=PatternType.WEEKEND_CALORIE_SLIP,
        suggested_timing="Friday 19:00",
        channel="web",
        message=(
            "Weekend aur dawat plan ready rakhein! Family dinners par half portion + pehle "
            "kachumber salad ya raita lein — enjoy poora karein aur routine balanced rahega."
        ),
    )
    return pattern, nudge


def _detect_stress_eating_pattern(
    messages: list[MessageRecord],
    mood_logs: list[MoodLogRecord],
    tz: ZoneInfo,
) -> tuple[EmotionalPattern, ProactiveNudge] | None:
    evidence: list[str] = []
    for mood in mood_logs:
        if mood.mood.strip().lower() in _STRESS_MOODS:
            local_dt = _to_local_dt(mood.logged_at, tz)
            note_suffix = f" ({mood.note})" if mood.note else ""
            evidence.append(f"Mood '{mood.mood}' at {local_dt:%Y-%m-%d %H:%M}{note_suffix}")

    for msg in messages:
        if msg.role == "user" and _STRESS_MESSAGE_RE.search(msg.content):
            local_dt = _to_local_dt(msg.created_at, tz)
            evidence.append(f"Stress signal at {local_dt:%Y-%m-%d %H:%M}: {msg.content[:80]}")

    if len(evidence) < 2:
        return None

    severity: Literal["medium", "high"] = "high" if len(evidence) >= 4 else "medium"
    pattern = EmotionalPattern(
        pattern_type=PatternType.STRESS_EATING,
        severity=severity,
        occurrences=len(evidence),
        description=f"Identified {len(evidence)} stress, guilt, or emotional-eating signals.",
        evidence=evidence[:5],
    )
    nudge = ProactiveNudge(
        pattern_type=PatternType.STRESS_EATING,
        suggested_timing="16:00 daily",
        channel="web",
        message=(
            "Aap ka din stressful lag raha ho to pehle 2 minute deep breathing aur ek glass "
            "paani piyein. Thora pause le kar decide karein — emotional hunger aur physical "
            "bhook alag hoti hain, main saath hoon."
        ),
    )
    return pattern, nudge


def _detect_micro_win_pattern(
    messages: list[MessageRecord],
    mood_logs: list[MoodLogRecord],
    memories: list[UserMemoryRecord] | None,
    tz: ZoneInfo,
) -> tuple[EmotionalPattern, ProactiveNudge] | None:
    evidence: list[str] = []
    if memories:
        for mem in memories:
            if mem.category == MemoryCategory.WIN.value:
                evidence.append(f"Saved win: {mem.content}")

    for mood in mood_logs:
        if mood.mood.strip().lower() in _POSITIVE_MOODS:
            local_dt = _to_local_dt(mood.logged_at, tz)
            evidence.append(f"Positive mood '{mood.mood}' at {local_dt:%Y-%m-%d %H:%M}")

    for msg in messages:
        if msg.role == "user" and any(pat.search(msg.content) for pat in _WIN_PATTERNS):
            local_dt = _to_local_dt(msg.created_at, tz)
            evidence.append(f"Chat win at {local_dt:%Y-%m-%d %H:%M}: {msg.content[:80]}")

    if not evidence:
        return None

    pattern = EmotionalPattern(
        pattern_type=PatternType.MICRO_WIN,
        severity="positive",
        occurrences=len(evidence),
        description=f"Celebrated {len(evidence)} healthy milestones and micro-wins.",
        evidence=evidence[:5],
    )
    nudge = ProactiveNudge(
        pattern_type=PatternType.MICRO_WIN,
        suggested_timing="09:00 morning",
        channel="web",
        message=(
            "Shabash! Aap ke chhote-chhote consistent steps mil kar bara farq la rahe hain "
            "— aaj bhi apna paani aur ek balanced desi meal log zaroor karein!"
        ),
    )
    return pattern, nudge


def detect_emotional_patterns(
    messages: list[MessageRecord],
    meal_logs: list[MealLogRecord],
    mood_logs: list[MoodLogRecord],
    daily_target_kcal: int,
    *,
    timezone_name: str = DEFAULT_TIMEZONE,
    memories: list[UserMemoryRecord] | None = None,
) -> PatternReport:
    """Analyze user chats, meal timestamps, mood check-ins, and memories for patterns."""
    tz = _resolve_timezone(timezone_name)
    candidates = (
        _detect_late_night_pattern(messages, meal_logs, tz),
        _detect_weekend_slip_pattern(meal_logs, daily_target_kcal, tz),
        _detect_stress_eating_pattern(messages, mood_logs, tz),
        _detect_micro_win_pattern(messages, mood_logs, memories, tz),
    )

    patterns: list[EmotionalPattern] = []
    nudges: list[ProactiveNudge] = []
    for item in candidates:
        if item is not None:
            patterns.append(item[0])
            nudges.append(item[1])

    if not patterns:
        summary = (
            "No strong late-night craving, weekend slip, or stress-eating patterns detected yet."
        )
    else:
        labels = ", ".join(p.pattern_type.value for p in patterns)
        summary = f"Detected {len(patterns)} behavioral pattern(s): {labels}."

    return PatternReport(patterns=patterns, nudges=nudges, summary=summary)
