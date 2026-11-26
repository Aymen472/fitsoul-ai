"""Approved Meta WhatsApp Cloud API notification templates and PWA deep-link builder."""

from enum import StrEnum
from typing import Any
from urllib.parse import urlencode

from pydantic import BaseModel


class WhatsAppTemplateName(StrEnum):
    """Pre-approved Meta WhatsApp utility/notification templates for FitSoul AI."""

    MEAL_REMINDER = "fitsoul_meal_reminder"
    WATER_REMINDER = "fitsoul_water_reminder"
    WORKOUT_NUDGE = "fitsoul_workout_nudge"
    NIGHT_SUMMARY = "fitsoul_night_summary"
    WEEKLY_REPORT = "fitsoul_weekly_report"
    PROACTIVE_SUPPORT = "fitsoul_proactive_support"
    SUBSCRIPTION_RENEWAL = "fitsoul_subscription_renewal"


class TemplateDefinition(BaseModel):
    """Schema and preview copy for an approved WhatsApp notification template."""

    name: WhatsAppTemplateName
    category: str = "UTILITY"
    language_code: str = "en"
    required_params: list[str]
    default_path: str
    preview_body: str


class RenderedTemplateMessage(BaseModel):
    """Validated Meta Cloud API template payload and human-readable preview."""

    template_name: WhatsAppTemplateName
    recipient_phone: str
    language_code: str
    deep_link: str
    preview_text: str
    request_payload: dict[str, Any]


TEMPLATE_CATALOG: dict[WhatsAppTemplateName, TemplateDefinition] = {
    WhatsAppTemplateName.MEAL_REMINDER: TemplateDefinition(
        name=WhatsAppTemplateName.MEAL_REMINDER,
        required_params=["user_name", "meal_slot", "suggested_meal", "target_kcal"],
        default_path="/plan",
        preview_body=(
            "Assalam-o-Alaikum {user_name}! Aap ke {meal_slot} ka waqt ho gaya hai. "
            "Aaj ka suggested option: {suggested_meal} (~{target_kcal} kcal). "
            "Apna meal log aur swap karne ke liye FitSoul AI app kholein."
        ),
    ),
    WhatsAppTemplateName.WATER_REMINDER: TemplateDefinition(
        name=WhatsAppTemplateName.WATER_REMINDER,
        required_params=["user_name", "consumed_ml", "target_ml"],
        default_path="/",
        preview_body=(
            "Hydration check {user_name}: Aap ne abhi tak {consumed_ml} ml / {target_ml} ml "
            "paani piya hai. Ek glass paani peein aur dashboard par tap karke log karein."
        ),
    ),
    WhatsAppTemplateName.WORKOUT_NUDGE: TemplateDefinition(
        name=WhatsAppTemplateName.WORKOUT_NUDGE,
        required_params=["user_name", "routine_name", "duration_minutes"],
        default_path="/workouts",
        preview_body=(
            "Chalein {user_name}, aaj ka {duration_minutes}-minute '{routine_name}' session "
            "ready hai! Guided timer player start karne ke liye neeche tap karein."
        ),
    ),
    WhatsAppTemplateName.NIGHT_SUMMARY: TemplateDefinition(
        name=WhatsAppTemplateName.NIGHT_SUMMARY,
        required_params=["user_name", "consumed_kcal", "target_kcal", "streak_days"],
        default_path="/",
        preview_body=(
            "Shab-ba-khair {user_name}! Aaj aap ne {consumed_kcal} / {target_kcal} kcal "
            "log kiye aur aap ka streak {streak_days} din par hai. Kal ke plan ke liye "
            "apna dashboard check karein."
        ),
    ),
    WhatsAppTemplateName.WEEKLY_REPORT: TemplateDefinition(
        name=WhatsAppTemplateName.WEEKLY_REPORT,
        required_params=["user_name", "avg_kcal", "workouts_completed", "weight_delta"],
        default_path="/",
        preview_body=(
            "Weekly Check-in {user_name}: Is haftay aap ka average {avg_kcal} kcal/day, "
            "{workouts_completed} workouts complete, aur weight change {weight_delta} raha. "
            "Poori progress report app mein dekhein."
        ),
    ),
    WhatsAppTemplateName.PROACTIVE_SUPPORT: TemplateDefinition(
        name=WhatsAppTemplateName.PROACTIVE_SUPPORT,
        required_params=["user_name", "support_message"],
        default_path="/chat",
        preview_body=(
            "{user_name}, aap ke FitSoul AI coach ka ek quick note hai: "
            "{support_message} Chat mein aa kar apna plan adjust kar lein."
        ),
    ),
    WhatsAppTemplateName.SUBSCRIPTION_RENEWAL: TemplateDefinition(
        name=WhatsAppTemplateName.SUBSCRIPTION_RENEWAL,
        required_params=["user_name", "days_remaining", "plan_name"],
        default_path="/",
        preview_body=(
            "Reminder {user_name}: Aap ka FitSoul AI {plan_name} plan {days_remaining} din "
            "mein renew hoga. Details aur continuity ke liye apna account check karein."
        ),
    ),
}


def list_template_definitions() -> list[TemplateDefinition]:
    """Return all approved WhatsApp template definitions in catalog order."""
    return list(TEMPLATE_CATALOG.values())


def get_template_definition(template_name: WhatsAppTemplateName | str) -> TemplateDefinition:
    """Resolve a template name to its approved definition or raise ValueError."""
    try:
        key = (
            template_name
            if isinstance(template_name, WhatsAppTemplateName)
            else WhatsAppTemplateName(str(template_name).strip())
        )
    except ValueError as exc:
        raise ValueError(f"Unknown WhatsApp template '{template_name}'") from exc
    return TEMPLATE_CATALOG[key]


def build_pwa_deep_link(
    base_url: str,
    path: str,
    query_params: dict[str, str] | None = None,
) -> str:
    """Build a canonical PWA deep-link URL combining base_url, path, and optional query params."""
    clean_base = base_url.strip().rstrip("/") or "http://localhost:3000"
    stripped_path = path.strip()
    clean_path = (
        "/" if not stripped_path or stripped_path == "/" else f"/{stripped_path.lstrip('/')}"
    )
    query_suffix = f"?{urlencode(query_params)}" if query_params else ""
    return f"{clean_base}{clean_path}{query_suffix}"


def render_template_payload(
    template_name: WhatsAppTemplateName | str,
    params: dict[str, Any],
    *,
    base_url: str,
    recipient_phone: str,
    language_code: str = "en",
    query_params: dict[str, str] | None = None,
) -> RenderedTemplateMessage:
    """Validate template parameters and construct the Meta WhatsApp Cloud API JSON body."""
    definition = get_template_definition(template_name)

    missing: list[str] = []
    clean_params: dict[str, str] = {}
    for key in definition.required_params:
        raw_value = params.get(key)
        text_value = "" if raw_value is None else str(raw_value).strip()
        if not text_value:
            missing.append(key)
        else:
            clean_params[key] = text_value

    if missing:
        raise ValueError(
            f"Missing required parameters for '{definition.name.value}': {', '.join(missing)}"
        )

    deep_link = build_pwa_deep_link(base_url, definition.default_path, query_params=query_params)
    query_suffix = f"?{urlencode(query_params)}" if query_params else ""
    relative_suffix = f"{definition.default_path}{query_suffix}"
    lang = language_code.strip() or definition.language_code

    request_payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_phone,
        "type": "template",
        "template": {
            "name": definition.name.value,
            "language": {"code": lang},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": clean_params[param_name]}
                        for param_name in definition.required_params
                    ],
                },
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": "0",
                    "parameters": [{"type": "text", "text": relative_suffix}],
                },
            ],
        },
    }

    preview_body = definition.preview_body.format(**clean_params)
    preview_text = f"{preview_body}\n\nOpen FitSoul AI: {deep_link}"

    return RenderedTemplateMessage(
        template_name=definition.name,
        recipient_phone=recipient_phone,
        language_code=lang,
        deep_link=deep_link,
        preview_text=preview_text,
        request_payload=request_payload,
    )
