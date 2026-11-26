"""Subscription plan catalog, pricing tiers, and deterministic access entitlements."""

import math
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class PlanId(StrEnum):
    """Supported FitSoul AI subscription tiers."""

    TRIAL = "trial"
    BASIC = "basic"
    PRO = "pro"
    TRANSFORMATION = "transformation"
    OVERSEAS = "overseas"


class PaymentProvider(StrEnum):
    """Supported Pakistani local and international payment gateways."""

    SAFEPAY = "safepay"
    PAYFAST = "payfast"
    JAZZCASH = "jazzcash"
    EASYPAISA = "easypaisa"
    LEMONSQUEEZY = "lemonsqueezy"
    MOCK = "mock"


class SubscriptionStatus(StrEnum):
    """Lifecycle status of a user's subscription."""

    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    LIMITED = "limited"


class PlanDefinition(BaseModel):
    """Public plan metadata, pricing, duration, and supported payment methods."""

    id: PlanId
    name: str
    tagline: str
    price_amount: float
    currency: Literal["PKR", "USD"]
    duration_days: int
    is_popular: bool = False
    features: list[str] = Field(default_factory=list)
    supported_providers: list[PaymentProvider] = Field(default_factory=list)


class AccessEntitlements(BaseModel):
    """Feature gates and limits enforced across PWA and backend APIs."""

    access_mode: Literal["full", "basic", "limited"]
    is_active: bool
    is_trial: bool
    days_remaining: int
    renewal_due_soon: bool
    can_use_ai_chat: bool
    can_use_photo_scanner: bool
    can_use_workouts_face_yoga: bool
    can_use_weekly_meal_plan: bool
    can_use_whatsapp_reminders: bool
    daily_chat_limit: int | None = None


_LOCAL_PROVIDERS: list[PaymentProvider] = [
    PaymentProvider.SAFEPAY,
    PaymentProvider.PAYFAST,
    PaymentProvider.JAZZCASH,
    PaymentProvider.EASYPAISA,
    PaymentProvider.MOCK,
]

_OVERSEAS_PROVIDERS: list[PaymentProvider] = [
    PaymentProvider.LEMONSQUEEZY,
    PaymentProvider.SAFEPAY,
    PaymentProvider.MOCK,
]

PLAN_CATALOG: dict[PlanId, PlanDefinition] = {
    PlanId.TRIAL: PlanDefinition(
        id=PlanId.TRIAL,
        name="Free Trial",
        tagline="7-day full experience to build your daily healthy habit",
        price_amount=0.0,
        currency="PKR",
        duration_days=7,
        features=[
            "Unlimited AI Coach Chat (Roman Urdu & English)",
            "Meal Photo Scanner + Pakistani Food DB",
            "7-Day Personalized Meal Plan & Grocery List",
            "Workouts, Face Yoga & WhatsApp Reminders",
        ],
        supported_providers=[],
    ),
    PlanId.BASIC: PlanDefinition(
        id=PlanId.BASIC,
        name="Basic Monthly",
        tagline="Personalized desi diet plan, text logging, and WhatsApp reminders",
        price_amount=1499.0,
        currency="PKR",
        duration_days=30,
        features=[
            "7-Day Personalized Pakistani Meal Plan + Swaps",
            "5 AI Coach messages per day + text calorie logging",
            "Water, Weight & Mood Dashboard tracking",
            "Daily WhatsApp meal & water reminders",
        ],
        supported_providers=list(_LOCAL_PROVIDERS),
    ),
    PlanId.PRO: PlanDefinition(
        id=PlanId.PRO,
        name="Pro Monthly",
        tagline="Complete nutritionist, workout studio, photo scanner, and emotional support",
        price_amount=2999.0,
        currency="PKR",
        duration_days=30,
        is_popular=True,
        features=[
            "Everything in Basic + Unlimited AI Coach Chat",
            "Meal Photo Scanner (Gemini Vision + Pakistani Food DB)",
            "Guided Home Workouts & Face Yoga Timer Player",
            "Weekly AI Progress Report & Emotional Pattern Nudges",
        ],
        supported_providers=list(_LOCAL_PROVIDERS),
    ),
    PlanId.TRANSFORMATION: PlanDefinition(
        id=PlanId.TRANSFORMATION,
        name="Transformation (3 Months)",
        tagline="Bride, groom & 90-day milestone package with best monthly savings",
        price_amount=6999.0,
        currency="PKR",
        duration_days=90,
        features=[
            "Full Pro access locked for 90 days (save Rs. 1,998)",
            "Goal-deadline tracking & safe weekly weight roadmap",
            "Unlimited Meal Swaps, Photo Scans & Guided Routines",
            "Priority Weekly AI Reports & WhatsApp Check-ins",
        ],
        supported_providers=list(_LOCAL_PROVIDERS),
    ),
    PlanId.OVERSEAS: PlanDefinition(
        id=PlanId.OVERSEAS,
        name="Overseas Monthly",
        tagline="Full Pro plan for South Asians in UAE, Saudi, UK & global timezones",
        price_amount=9.99,
        currency="USD",
        duration_days=30,
        features=[
            "Full Pro access (Unlimited AI Coach + Photo Scanner)",
            "Multi-timezone scheduling & desi + USDA foods",
            "Guided Home Workouts & Face Yoga Routines",
            "Card / Apple Pay / Global checkout via LemonSqueezy",
        ],
        supported_providers=list(_OVERSEAS_PROVIDERS),
    ),
}


def list_plans() -> list[PlanDefinition]:
    """Return all subscription plans in catalog display order."""
    return list(PLAN_CATALOG.values())


def get_plan(plan_id: PlanId | str) -> PlanDefinition:
    """Resolve a plan identifier to its catalog definition or raise ValueError."""
    try:
        key = plan_id if isinstance(plan_id, PlanId) else PlanId(str(plan_id).strip().lower())
    except ValueError as exc:
        raise ValueError(f"Unknown subscription plan '{plan_id}'") from exc
    return PLAN_CATALOG[key]


def _ensure_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def compute_entitlements(
    plan: str | None,
    status: str | None,
    expires_at: datetime | None,
    *,
    now: datetime | None = None,
) -> tuple[SubscriptionStatus, AccessEntitlements]:
    """Derive effective subscription status and deterministic feature gates."""
    reference = _ensure_utc(now) if now is not None else datetime.now(UTC)
    normalized_status = (status or "").strip().lower()
    normalized_plan = (plan or "").strip().lower()
    expires_utc = _ensure_utc(expires_at) if expires_at is not None else None

    is_unexpired = expires_utc is None or expires_utc > reference
    if normalized_status == SubscriptionStatus.ACTIVE.value and is_unexpired:
        days_remaining = (
            30
            if expires_utc is None
            else max(1, math.ceil((expires_utc - reference).total_seconds() / 86400))
        )
        renewal_due_soon = 1 <= days_remaining <= 3

        if normalized_plan == PlanId.BASIC.value:
            return (
                SubscriptionStatus.ACTIVE,
                AccessEntitlements(
                    access_mode="basic",
                    is_active=True,
                    is_trial=False,
                    days_remaining=days_remaining,
                    renewal_due_soon=renewal_due_soon,
                    can_use_ai_chat=True,
                    can_use_photo_scanner=False,
                    can_use_workouts_face_yoga=False,
                    can_use_weekly_meal_plan=True,
                    can_use_whatsapp_reminders=True,
                    daily_chat_limit=5,
                ),
            )

        return (
            SubscriptionStatus.ACTIVE,
            AccessEntitlements(
                access_mode="full",
                is_active=True,
                is_trial=(normalized_plan == PlanId.TRIAL.value),
                days_remaining=days_remaining,
                renewal_due_soon=renewal_due_soon,
                can_use_ai_chat=True,
                can_use_photo_scanner=True,
                can_use_workouts_face_yoga=True,
                can_use_weekly_meal_plan=True,
                can_use_whatsapp_reminders=True,
                daily_chat_limit=None,
            ),
        )

    if normalized_status == SubscriptionStatus.CANCELLED.value:
        resolved_status = SubscriptionStatus.CANCELLED
    elif normalized_status in {SubscriptionStatus.ACTIVE.value, SubscriptionStatus.EXPIRED.value}:
        resolved_status = SubscriptionStatus.EXPIRED
    else:
        resolved_status = SubscriptionStatus.LIMITED

    return (
        resolved_status,
        AccessEntitlements(
            access_mode="limited",
            is_active=False,
            is_trial=False,
            days_remaining=0,
            renewal_due_soon=False,
            can_use_ai_chat=True,
            can_use_photo_scanner=False,
            can_use_workouts_face_yoga=False,
            can_use_weekly_meal_plan=False,
            can_use_whatsapp_reminders=False,
            daily_chat_limit=2,
        ),
    )
