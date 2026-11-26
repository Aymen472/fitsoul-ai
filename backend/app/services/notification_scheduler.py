"""Timezone- and quiet-hours-aware proactive WhatsApp notification scheduler."""

import math
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.workouts import list_routines
from app.db.repository import (
    MealLogRepository,
    MemoryRepository,
    MessageRepository,
    MoodLogRepository,
    NotificationPreferenceRecord,
    NotificationRepository,
    ProfileRepository,
    WaterLogRepository,
    WeightLogRepository,
    WorkoutRepository,
)
from app.db.tables import SubscriptionRow
from app.models import MedicalCondition, UserProfile
from app.services.whatsapp_client import WhatsAppClientError, WhatsAppCloudClient
from app.services.whatsapp_templates import WhatsAppTemplateName

DEFAULT_TIMEZONE = "Asia/Karachi"

_MEAL_SUGGESTIONS: dict[str, dict[str, str]] = {
    "non_veg": {
        "breakfast": "2 boiled eggs + 1 multigrain toast + chai (no sugar)",
        "lunch": "Grilled chicken / tikka + 1 whole wheat chapati + kachumber salad",
        "dinner": "Baked fish or chicken shorba + sabzi + 1 small chapati",
    },
    "eggetarian": {
        "breakfast": "2-egg veggie omelette + 1 bran roti + green tea",
        "lunch": "Daal moong + 1 boiled egg + 1 whole wheat chapati + raita",
        "dinner": "Egg curry (light oil) + mixed sabzi + 1 small chapati",
    },
    "veg": {
        "breakfast": "Oats porridge with chia seeds & almonds + herbal tea",
        "lunch": "Daal moong + 1 whole wheat chapati + cucumber raita",
        "dinner": "Mixed seasonal sabzi + lauki/masoor daal + 1 chapati",
    },
}

_MEAL_KCAL_SHARE: dict[str, float] = {
    "breakfast": 0.25,
    "lunch": 0.35,
    "dinner": 0.30,
}


class UpcomingSlotSummary(BaseModel):
    """Scheduled daily or weekly notification slot displayed in the PWA schedule preview."""

    slot_type: str
    label: str
    local_time: str
    enabled: bool
    template_name: WhatsAppTemplateName


class ScheduledNotificationJob(BaseModel):
    """Concrete due notification ready for WhatsApp template dispatch."""

    user_id: str
    template_name: WhatsAppTemplateName
    slot_key: str
    recipient_phone: str
    params: dict[str, str]
    reason: str


class ScheduledNotificationResult(BaseModel):
    """Outcome for a single scheduled notification dispatch."""

    user_id: str
    template_name: WhatsAppTemplateName
    slot_key: str
    status: str
    provider_message_id: str | None = None
    deep_link: str | None = None
    preview_text: str = ""
    error_message: str | None = None


class SchedulePreviewResponse(BaseModel):
    """User's local clock, quiet hours state, currently due jobs, and daily/weekly schedule."""

    user_id: str
    timezone: str
    local_time: str
    in_quiet_hours: bool
    whatsapp_opt_in: bool
    due_jobs: list[ScheduledNotificationJob] = Field(default_factory=list)
    upcoming_slots: list[UpcomingSlotSummary] = Field(default_factory=list)


class SchedulerRunSummary(BaseModel):
    """Aggregate execution report returned by a proactive scheduler run."""

    evaluated_users: int = 0
    due_count: int = 0
    sent_count: int = 0
    skipped_quiet_hours: int = 0
    skipped_duplicate: int = 0
    failed_count: int = 0
    dry_run: bool = False
    dispatched: list[ScheduledNotificationResult] = Field(default_factory=list)


def _resolve_timezone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo((tz_name or "").strip() or DEFAULT_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def _ensure_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _to_local_dt(dt: datetime, tz: ZoneInfo) -> datetime:
    return _ensure_utc(dt).astimezone(tz)


def _parse_hhmm(value: str) -> time:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid HH:MM time '{value}'")
    return time(hour=int(parts[0]), minute=int(parts[1]))


def is_within_quiet_hours(local_time: time, quiet_start: str, quiet_end: str) -> bool:
    """Return True when `local_time` falls inside the [quiet_start, quiet_end) sleep window."""
    start = _parse_hhmm(quiet_start)
    end = _parse_hhmm(quiet_end)
    if start == end:
        return False
    if start > end:
        return local_time >= start or local_time < end
    return start <= local_time < end


def _is_in_window(
    local_time: time,
    target_hour: int,
    target_minute: int = 0,
    window_minutes: int = 60,
) -> bool:
    """Return True when `local_time` sits inside [target, target + window_minutes)."""
    now_minutes = local_time.hour * 60 + local_time.minute
    start_minutes = target_hour * 60 + target_minute
    return 0 <= (now_minutes - start_minutes) % 1440 < window_minutes


def _compute_streak_days(
    timestamps: Iterable[datetime],
    *,
    today_local: date,
    tz: ZoneInfo,
) -> int:
    active_dates = {_to_local_dt(ts, tz).date() for ts in timestamps}
    if today_local in active_dates:
        cursor = today_local
    elif (today_local - timedelta(days=1)) in active_dates:
        cursor = today_local - timedelta(days=1)
    else:
        return 0

    streak = 0
    while cursor in active_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def build_upcoming_slots(
    profile: UserProfile,
    prefs: NotificationPreferenceRecord,
) -> list[UpcomingSlotSummary]:
    """Build the ordered daily/weekly notification slot schedule for a user."""
    workout_hhmm = profile.workout_time.strftime("%H:%M") if profile.workout_time else "18:00"
    return [
        UpcomingSlotSummary(
            slot_type="meal_breakfast",
            label="Breakfast Reminder",
            local_time="08:00",
            enabled=prefs.meal_reminders,
            template_name=WhatsAppTemplateName.MEAL_REMINDER,
        ),
        UpcomingSlotSummary(
            slot_type="water_midday",
            label="Midday Water Check",
            local_time="11:00",
            enabled=prefs.water_reminders,
            template_name=WhatsAppTemplateName.WATER_REMINDER,
        ),
        UpcomingSlotSummary(
            slot_type="meal_lunch",
            label="Lunch Reminder",
            local_time="13:00",
            enabled=prefs.meal_reminders,
            template_name=WhatsAppTemplateName.MEAL_REMINDER,
        ),
        UpcomingSlotSummary(
            slot_type="water_afternoon",
            label="Afternoon Water Check",
            local_time="16:00",
            enabled=prefs.water_reminders,
            template_name=WhatsAppTemplateName.WATER_REMINDER,
        ),
        UpcomingSlotSummary(
            slot_type="workout",
            label="Workout / Face Yoga Nudge",
            local_time=workout_hhmm,
            enabled=prefs.workout_reminders,
            template_name=WhatsAppTemplateName.WORKOUT_NUDGE,
        ),
        UpcomingSlotSummary(
            slot_type="meal_dinner",
            label="Dinner Reminder",
            local_time="19:30",
            enabled=prefs.meal_reminders,
            template_name=WhatsAppTemplateName.MEAL_REMINDER,
        ),
        UpcomingSlotSummary(
            slot_type="night_summary",
            label="Night Calorie & Streak Wrap-up",
            local_time="21:00",
            enabled=prefs.night_summary,
            template_name=WhatsAppTemplateName.NIGHT_SUMMARY,
        ),
        UpcomingSlotSummary(
            slot_type="weekly_report",
            label="Weekly Progress Report",
            local_time="Sun 10:00",
            enabled=prefs.weekly_report,
            template_name=WhatsAppTemplateName.WEEKLY_REPORT,
        ),
    ]


def _pick_workout_routine(profile: UserProfile) -> tuple[str, int]:
    routines = list_routines()
    if not routines:
        return "PCOS Low-Impact Walk & Tone", 15

    preferred_id = (
        "pcos_low_impact_cardio"
        if MedicalCondition.PCOS in profile.conditions
        else "joint_friendly_mobility"
    )
    for routine in routines:
        if routine.id == preferred_id:
            return routine.name, routine.duration_minutes
    return routines[0].name, routines[0].duration_minutes


def evaluate_due_notifications_for_user(
    session: Session,
    user_id: str,
    *,
    now: datetime | None = None,
) -> tuple[list[ScheduledNotificationJob], bool, int, SchedulePreviewResponse]:
    """Evaluate which proactive notifications are currently due for one user."""
    profile_record = ProfileRepository.get_profile(session, user_id)
    if profile_record is None:
        raise ValueError("Profile not found")

    profile = profile_record.profile
    targets = profile_record.targets
    prefs = NotificationRepository.get_preferences(session, user_id)
    if prefs is None:
        prefs = NotificationPreferenceRecord(
            user_id=user_id,
            whatsapp_opt_in=False,
            whatsapp_phone=profile_record.phone,
        )

    tz = _resolve_timezone(profile.timezone)
    reference = _ensure_utc(now) if now is not None else datetime.now(UTC)
    local_dt = reference.astimezone(tz)
    local_date = local_dt.date()
    local_time = local_dt.time()
    in_quiet = is_within_quiet_hours(local_time, prefs.quiet_hours_start, prefs.quiet_hours_end)
    upcoming = build_upcoming_slots(profile, prefs)

    if in_quiet or not prefs.whatsapp_opt_in or not prefs.whatsapp_phone:
        preview = SchedulePreviewResponse(
            user_id=user_id,
            timezone=profile.timezone,
            local_time=local_dt.strftime("%Y-%m-%d %H:%M"),
            in_quiet_hours=in_quiet,
            whatsapp_opt_in=prefs.whatsapp_opt_in,
            due_jobs=[],
            upcoming_slots=upcoming,
        )
        return [], in_quiet, 0, preview

    recipient_phone = prefs.whatsapp_phone
    user_name = (profile_record.full_name or "Friend").strip() or "Friend"

    meals_30d = MealLogRepository.get_recent_meal_logs(session, user_id, days=30, now=reference)
    water_30d = WaterLogRepository.get_recent_water_logs(session, user_id, days=30, now=reference)
    workouts_30d = WorkoutRepository.get_recent_workouts(session, user_id, days=30, now=reference)
    weights_90d = WeightLogRepository.get_recent_weight_logs(
        session, user_id, days=90, limit=60, now=reference
    )
    moods_30d = MoodLogRepository.get_recent_mood_logs(session, user_id, days=30, now=reference)
    messages_14d = MessageRepository.get_messages_since(session, user_id, days=14, now=reference)
    memories = MemoryRepository.list_memories(session, user_id)

    today_meals = [m for m in meals_30d if _to_local_dt(m.logged_at, tz).date() == local_date]
    logged_meal_types = {m.meal_type.strip().lower() for m in today_meals}
    today_water_ml = sum(
        w.amount_ml for w in water_30d if _to_local_dt(w.logged_at, tz).date() == local_date
    )
    today_workouts = [
        wk for wk in workouts_30d if _to_local_dt(wk.completed_at, tz).date() == local_date
    ]

    due_jobs: list[ScheduledNotificationJob] = []
    skipped_duplicate = 0

    def _maybe_add(
        template_name: WhatsAppTemplateName,
        slot_key: str,
        params: dict[str, str],
        reason: str,
    ) -> None:
        nonlocal skipped_duplicate
        if NotificationRepository.has_sent_slot(session, user_id, slot_key, now=reference):
            skipped_duplicate += 1
            return
        due_jobs.append(
            ScheduledNotificationJob(
                user_id=user_id,
                template_name=template_name,
                slot_key=slot_key,
                recipient_phone=recipient_phone,
                params=params,
                reason=reason,
            )
        )

    # 1. Meal reminders (Breakfast 08:00, Lunch 13:00, Dinner 19:30)
    if prefs.meal_reminders:
        diet_suggestions = _MEAL_SUGGESTIONS.get(
            profile.diet_type.value,
            _MEAL_SUGGESTIONS["non_veg"],
        )
        meal_windows = (
            (8, 0, "breakfast", "Breakfast"),
            (13, 0, "lunch", "Lunch"),
            (19, 30, "dinner", "Dinner"),
        )
        for hour, minute, meal_key, meal_label in meal_windows:
            if _is_in_window(local_time, hour, minute) and meal_key not in logged_meal_types:
                meal_kcal = round(targets.calories * _MEAL_KCAL_SHARE[meal_key])
                _maybe_add(
                    WhatsAppTemplateName.MEAL_REMINDER,
                    f"meal_{meal_key}:{local_date.isoformat()}",
                    {
                        "user_name": user_name,
                        "meal_slot": meal_label,
                        "suggested_meal": diet_suggestions[meal_key],
                        "target_kcal": str(meal_kcal),
                    },
                    f"{meal_label} window ({hour:02d}:{minute:02d}) and not logged yet",
                )

    # 2. Hydration reminders (11:00, 16:00)
    if prefs.water_reminders and today_water_ml < targets.water_ml:
        water_windows = (
            (11, 0, "water_midday"),
            (16, 0, "water_afternoon"),
        )
        for hour, minute, prefix in water_windows:
            if _is_in_window(local_time, hour, minute):
                _maybe_add(
                    WhatsAppTemplateName.WATER_REMINDER,
                    f"{prefix}:{local_date.isoformat()}",
                    {
                        "user_name": user_name,
                        "consumed_ml": str(today_water_ml),
                        "target_ml": str(targets.water_ml),
                    },
                    f"Hydration {today_water_ml}/{targets.water_ml} ml below daily goal",
                )

    # 3. Workout nudge (custom workout_time or 18:00)
    if prefs.workout_reminders and not today_workouts:
        wk_hour = profile.workout_time.hour if profile.workout_time else 18
        wk_minute = profile.workout_time.minute if profile.workout_time else 0
        if _is_in_window(local_time, wk_hour, wk_minute):
            routine_name, duration_minutes = _pick_workout_routine(profile)
            _maybe_add(
                WhatsAppTemplateName.WORKOUT_NUDGE,
                f"workout:{local_date.isoformat()}",
                {
                    "user_name": user_name,
                    "routine_name": routine_name,
                    "duration_minutes": str(duration_minutes),
                },
                f"Scheduled workout window ({wk_hour:02d}:{wk_minute:02d}) with no session logged",
            )

    # 4. Night summary (21:00)
    if prefs.night_summary and _is_in_window(local_time, 21, 0):
        consumed_kcal = round(sum(m.total_kcal for m in today_meals))
        streak_days = _compute_streak_days(
            [
                *(m.logged_at for m in meals_30d),
                *(w.logged_at for w in water_30d),
                *(wk.completed_at for wk in workouts_30d),
                *(mood.logged_at for mood in moods_30d),
                *(wt.logged_at for wt in weights_90d),
            ],
            today_local=local_date,
            tz=tz,
        )
        _maybe_add(
            WhatsAppTemplateName.NIGHT_SUMMARY,
            f"night_summary:{local_date.isoformat()}",
            {
                "user_name": user_name,
                "consumed_kcal": str(consumed_kcal),
                "target_kcal": str(targets.calories),
                "streak_days": str(streak_days),
            },
            "Night wrap-up summary window (21:00)",
        )

    # 5. Weekly report (Sunday 10:00)
    if prefs.weekly_report and local_dt.weekday() == 6 and _is_in_window(local_time, 10, 0):
        iso_year, iso_week, _ = local_date.isocalendar()
        cutoff_7d = reference - timedelta(days=7)
        daily_kcals: dict[date, float] = defaultdict(float)
        for meal in meals_30d:
            if _ensure_utc(meal.logged_at) >= cutoff_7d:
                daily_kcals[_to_local_dt(meal.logged_at, tz).date()] += meal.total_kcal
        avg_kcal = round(sum(daily_kcals.values()) / len(daily_kcals)) if daily_kcals else 0

        workouts_7d = sum(1 for wk in workouts_30d if _ensure_utc(wk.completed_at) >= cutoff_7d)
        weights_7d = [wt for wt in weights_90d if _ensure_utc(wt.logged_at) >= cutoff_7d]
        if len(weights_7d) >= 2:
            delta = weights_7d[-1].weight_kg - weights_7d[0].weight_kg
            weight_delta = "steady" if abs(delta) < 0.05 else f"{delta:+.1f} kg"
        else:
            weight_delta = "steady"

        _maybe_add(
            WhatsAppTemplateName.WEEKLY_REPORT,
            f"weekly_report:{iso_year}-W{iso_week:02d}",
            {
                "user_name": user_name,
                "avg_kcal": str(avg_kcal),
                "workouts_completed": str(workouts_7d),
                "weight_delta": weight_delta,
            },
            "Sunday weekly progress report window (10:00)",
        )

    # 6. Proactive emotional pattern support (17:00-19:59)
    if _is_in_window(local_time, 17, 0, window_minutes=180):
        # Deferred import avoids services <-> ai circular init when app.services loads first.
        from app.ai.memory import detect_emotional_patterns

        cutoff_14d = reference - timedelta(days=14)
        patterns = detect_emotional_patterns(
            messages=messages_14d,
            meal_logs=[m for m in meals_30d if _ensure_utc(m.logged_at) >= cutoff_14d],
            mood_logs=[m for m in moods_30d if _ensure_utc(m.logged_at) >= cutoff_14d],
            daily_target_kcal=targets.calories,
            timezone_name=profile.timezone,
            memories=memories,
        )
        if patterns.nudges:
            top_nudge = patterns.nudges[0]
            _maybe_add(
                WhatsAppTemplateName.PROACTIVE_SUPPORT,
                f"proactive_support:{local_date.isoformat()}",
                {
                    "user_name": user_name,
                    "support_message": top_nudge.message,
                },
                f"Detected behavioral pattern ({top_nudge.pattern_type.value})",
            )

    # 7. Subscription renewal reminder (within 3 days of expiration)
    subscription = session.scalar(select(SubscriptionRow).where(SubscriptionRow.user_id == user_id))
    if (
        subscription is not None
        and subscription.status == "active"
        and subscription.expires_at is not None
    ):
        delta_seconds = (_ensure_utc(subscription.expires_at) - reference).total_seconds()
        if 0 < delta_seconds <= 3 * 86400:
            days_remaining = max(1, math.ceil(delta_seconds / 86400))
            plan_name = (subscription.plan or "FitSoul Pro").strip() or "FitSoul Pro"
            _maybe_add(
                WhatsAppTemplateName.SUBSCRIPTION_RENEWAL,
                f"subscription_renewal:{local_date.isoformat()}",
                {
                    "user_name": user_name,
                    "days_remaining": str(days_remaining),
                    "plan_name": plan_name,
                },
                f"Subscription expires within {days_remaining} day(s)",
            )

    preview = SchedulePreviewResponse(
        user_id=user_id,
        timezone=profile.timezone,
        local_time=local_dt.strftime("%Y-%m-%d %H:%M"),
        in_quiet_hours=False,
        whatsapp_opt_in=True,
        due_jobs=due_jobs,
        upcoming_slots=upcoming,
    )
    return due_jobs, False, skipped_duplicate, preview


def run_proactive_scheduler(
    session: Session,
    whatsapp_client: WhatsAppCloudClient,
    *,
    now: datetime | None = None,
    user_id: str | None = None,
    dry_run: bool = False,
) -> SchedulerRunSummary:
    """Evaluate due reminder slots and dispatch WhatsApp templates across opted-in users."""
    reference = _ensure_utc(now) if now is not None else datetime.now(UTC)

    if user_id is not None:
        user_ids = [user_id]
    else:
        user_ids = [p.user_id for p in NotificationRepository.list_opted_in_preferences(session)]

    due_count = 0
    sent_count = 0
    skipped_quiet_hours = 0
    skipped_duplicate = 0
    failed_count = 0
    dispatched: list[ScheduledNotificationResult] = []

    for uid in user_ids:
        jobs, in_quiet, skipped_dups, _preview = evaluate_due_notifications_for_user(
            session,
            uid,
            now=reference,
        )
        skipped_duplicate += skipped_dups
        if in_quiet:
            skipped_quiet_hours += 1
            continue

        due_count += len(jobs)
        for job in jobs:
            try:
                result = whatsapp_client.send_template(
                    job.recipient_phone,
                    job.template_name,
                    job.params,
                    dry_run=dry_run,
                )
            except WhatsAppClientError as exc:
                NotificationRepository.log_notification(
                    session,
                    user_id=job.user_id,
                    direction="outbound",
                    status="failed",
                    template_name=job.template_name.value,
                    recipient_phone=job.recipient_phone,
                    payload={
                        "params": job.params,
                        "slot_key": job.slot_key,
                        "reason": job.reason,
                    },
                    error_message=str(exc),
                )
                failed_count += 1
                dispatched.append(
                    ScheduledNotificationResult(
                        user_id=job.user_id,
                        template_name=job.template_name,
                        slot_key=job.slot_key,
                        status="failed",
                        error_message=str(exc),
                    )
                )
                continue

            NotificationRepository.log_notification(
                session,
                user_id=job.user_id,
                direction="outbound",
                status=result.status,
                template_name=result.template_name,
                recipient_phone=result.recipient_phone,
                provider_message_id=result.provider_message_id,
                deep_link=result.deep_link,
                payload={
                    "params": job.params,
                    "slot_key": job.slot_key,
                    "reason": job.reason,
                    "preview_text": result.preview_text,
                },
            )
            sent_count += 1
            dispatched.append(
                ScheduledNotificationResult(
                    user_id=job.user_id,
                    template_name=job.template_name,
                    slot_key=job.slot_key,
                    status=result.status,
                    provider_message_id=result.provider_message_id,
                    deep_link=result.deep_link,
                    preview_text=result.preview_text,
                )
            )

    return SchedulerRunSummary(
        evaluated_users=len(user_ids),
        due_count=due_count,
        sent_count=sent_count,
        skipped_quiet_hours=skipped_quiet_hours,
        skipped_duplicate=skipped_duplicate,
        failed_count=failed_count,
        dry_run=dry_run,
        dispatched=dispatched,
    )
