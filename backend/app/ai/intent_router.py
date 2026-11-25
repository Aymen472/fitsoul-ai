"""Deterministic conversation intent classifier and chat text meal parser."""

import re
from enum import StrEnum

from app.core.nutrition import FoodDatabase, ScaledNutrition


class CoachIntent(StrEnum):
    """Supported conversation intents for the FitSoul AI coach."""

    MEAL_LOG = "meal_log"
    MEAL_PLAN = "meal_plan"
    CRAVING = "craving"
    EATING_OUT = "eating_out"
    SUPPLEMENT_QUERY = "supplement_query"
    WORKOUT_QUESTION = "workout_question"
    MOOD_EMOTIONAL = "mood_emotional"
    PROGRESS_QUERY = "progress_query"
    BILLING = "billing"
    GENERAL = "general"


_INTENT_RULES: tuple[tuple[CoachIntent, tuple[re.Pattern[str], ...]], ...] = (
    (
        CoachIntent.BILLING,
        tuple(
            re.compile(p, re.IGNORECASE)
            for p in (
                r"\b(?:subscription|billing|payment|pricing|price|trial|renew|upgrade)\b",
                r"\b(?:jazzcash|easypaisa|safepay|payfast|lemonsqueezy)\b",
                r"\b(?:plan\s+kitne\s+ka|fees|charges)\b",
            )
        ),
    ),
    (
        CoachIntent.SUPPLEMENT_QUERY,
        tuple(
            re.compile(p, re.IGNORECASE)
            for p in (
                r"\b(?:supplements?|vitamins?|vitamin\s*d\d?|vitamin\s*b12|omega[- ]?3)\b",
                r"\b(?:magnesium|inositol|myo[- ]?inositol|multivitamin|fish oil|probiotic)\b",
            )
        ),
    ),
    (
        CoachIntent.EATING_OUT,
        tuple(
            re.compile(p, re.IGNORECASE)
            for p in (
                r"\b(?:dawa?t|shaadi|wedding|restaurant|menu|eating out|eat out|buffet)\b",
                r"\b(?:bahar khana|takeout|foodpanda|party mein|hotel)\b",
            )
        ),
    ),
    (
        CoachIntent.CRAVING,
        tuple(
            re.compile(p, re.IGNORECASE)
            for p in (
                r"\b(?:cravings?|meetha|sweet tooth|snack idea|healthy snack|chai[- ]?time)\b",
                r"\b(?:bhook lag|kuch chatpata|chai ke saath|biscuit|crave)\b",
            )
        ),
    ),
    (
        CoachIntent.MOOD_EMOTIONAL,
        tuple(
            re.compile(p, re.IGNORECASE)
            for p in (
                r"\b(?:stress(?:ed)?|sad|low mood|anxious|guilt(?:y)?|demotivated|lonely)\b",
                r"\b(?:cheat meal|cheated|overeat(?:ing)?|mood off|tension|thak gay[aei])\b",
            )
        ),
    ),
    (
        CoachIntent.WORKOUT_QUESTION,
        tuple(
            re.compile(p, re.IGNORECASE)
            for p in (
                r"\b(?:workouts?|exercises?|gym|cardio|walk(?:ing)?|steps|face yoga)\b",
                r"\b(?:jawline|double chin|knee pain|back pain|squat|plank|varzish|warjish)\b",
            )
        ),
    ),
    (
        CoachIntent.MEAL_PLAN,
        tuple(
            re.compile(p, re.IGNORECASE)
            for p in (
                r"\b(?:meal plan|diet plan|weekly plan|grocery list)\b",
                r"\b(?:kya kha+[ou]n|kya bana+[ou]n|aaj ka plan|kal ka plan)\b",
                r"\b(?:breakfast|lunch|dinner)\s+(?:options?|ideas?)\b",
            )
        ),
    ),
    (
        CoachIntent.PROGRESS_QUERY,
        tuple(
            re.compile(p, re.IGNORECASE)
            for p in (
                r"\b(?:remaining calories|kitni calories baki|baki calories|aaj kitna)\b",
                r"\b(?:progress|weekly report|plateau|weight stuck|kitna kam|streak)\b",
                r"\b(?:target calories|meri calories|daily target|macros)\b",
            )
        ),
    ),
    (
        CoachIntent.MEAL_LOG,
        tuple(
            re.compile(p, re.IGNORECASE)
            for p in (
                r"\b(?:i ate|i had|just had|log meal|khaya|khai|khayi|kha liya|khaa liya)\b",
                r"\b(?:piya|pee li|pi li|(?:nashte|breakfast|lunch|dinner)\s+mein)\b",
                r"^\s*(?:\d+(?:\.\d+)?|half|aadha|aadhi|ek|do|teen)\s+[a-z]+",
            )
        ),
    ),
)

_WORD_NUMBERS: dict[str, float] = {
    "a": 1.0,
    "an": 1.0,
    "ek": 1.0,
    "one": 1.0,
    "half": 0.5,
    "aadha": 0.5,
    "aadhi": 0.5,
    "do": 2.0,
    "two": 2.0,
    "teen": 3.0,
    "three": 3.0,
    "char": 4.0,
    "chaar": 4.0,
    "four": 4.0,
    "paanch": 5.0,
    "five": 5.0,
}

_SPLIT_RE = re.compile(r"\s*(?:,|&|\+|\baur\b|\band\b|\bwith\b|\bke saath\b)\s*", re.IGNORECASE)

_LEADING_FILLER_RE = re.compile(
    r"^(?:maine|main|aaj|abhi|just|please|log|i ate|i had|ate|had|"
    r"(?:breakfast|lunch|dinner|nashte|snack)\s+(?:mein|me)|mein|me|ka|ki|ke|sirf|only)\b\s*",
    re.IGNORECASE,
)

_TRAILING_FILLER_RE = re.compile(
    r"\s*\b(?:khaya|khai|khayi|khaa?\s*liya|khaa?\s*li|piya|pee?\s*li|liya|li|hai|hain|hoon)[.!?]*$",
    re.IGNORECASE,
)

_UNIT_PREFIX_RE = re.compile(
    r"^(?:cups?|bowls?|plates?|pieces?|slices?|glass(?:es)?|servings?|tbsp|tsp|medium|small|large)\b\s*",
    re.IGNORECASE,
)


def classify_intent(message: str) -> CoachIntent:
    """Classify a user message into a deterministic CoachIntent."""
    text = message.strip()
    if not text:
        return CoachIntent.GENERAL

    for intent, patterns in _INTENT_RULES:
        if any(pattern.search(text) for pattern in patterns):
            return intent
    return CoachIntent.GENERAL


def _clean_meal_segment(segment: str) -> tuple[float, str]:
    """Extract serving quantity and cleaned food phrase from a single meal clause."""
    phrase = segment.strip(" .!?")

    while True:
        updated = _LEADING_FILLER_RE.sub("", phrase).strip()
        if updated == phrase:
            break
        phrase = updated

    while True:
        updated = _TRAILING_FILLER_RE.sub("", phrase).strip(" .!?")
        if updated == phrase:
            break
        phrase = updated

    servings = 1.0
    num_match = re.match(r"^(\d+(?:\.\d+)?)\s+(.+)$", phrase)
    if num_match is not None:
        servings = min(20.0, max(0.1, float(num_match.group(1))))
        phrase = num_match.group(2).strip()
    else:
        word_match = re.match(r"^([a-zA-Z]+)\s+(.+)$", phrase)
        if word_match is not None and word_match.group(1).lower() in _WORD_NUMBERS:
            servings = _WORD_NUMBERS[word_match.group(1).lower()]
            phrase = word_match.group(2).strip()

    while True:
        updated = _UNIT_PREFIX_RE.sub("", phrase).strip()
        if updated == phrase:
            break
        phrase = updated

    return servings, phrase


def parse_text_meal_items(message: str, food_db: FoodDatabase) -> list[ScaledNutrition]:
    """Parse free-text meal descriptions and calculate exact nutrition via FoodDatabase."""
    if not message.strip():
        return []

    parsed: list[ScaledNutrition] = []
    for raw_segment in _SPLIT_RE.split(message):
        servings, phrase = _clean_meal_segment(raw_segment)
        if len(phrase) < 2 or phrase.isdigit():
            continue
        matches = food_db.search(phrase, limit=1, min_score=0.72)
        if matches:
            parsed.append(matches[0].scale(servings))
    return parsed
