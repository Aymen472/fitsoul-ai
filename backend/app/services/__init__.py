"""External service integrations (USDA, WhatsApp, payments, scheduler)."""

from app.services.notification_scheduler import (
    ScheduledNotificationJob,
    ScheduledNotificationResult,
    SchedulePreviewResponse,
    SchedulerRunSummary,
    UpcomingSlotSummary,
    build_upcoming_slots,
    evaluate_due_notifications_for_user,
    is_within_quiet_hours,
    run_proactive_scheduler,
)
from app.services.payment_gateway import (
    CheckoutSessionResult,
    PaymentGatewayService,
    verify_payment_webhook_signature,
)
from app.services.usda_client import USDAClient, USDAClientError
from app.services.whatsapp_client import (
    ParsedWebhookBatch,
    WebhookIncomingMessage,
    WebhookStatusUpdate,
    WhatsAppClientError,
    WhatsAppCloudClient,
    WhatsAppSendResult,
    parse_webhook_events,
    verify_webhook_signature,
)
from app.services.whatsapp_templates import (
    RenderedTemplateMessage,
    TemplateDefinition,
    WhatsAppTemplateName,
    build_pwa_deep_link,
    get_template_definition,
    list_template_definitions,
    render_template_payload,
)

__all__ = [
    "CheckoutSessionResult",
    "ParsedWebhookBatch",
    "PaymentGatewayService",
    "RenderedTemplateMessage",
    "SchedulePreviewResponse",
    "ScheduledNotificationJob",
    "ScheduledNotificationResult",
    "SchedulerRunSummary",
    "TemplateDefinition",
    "USDAClient",
    "USDAClientError",
    "UpcomingSlotSummary",
    "WebhookIncomingMessage",
    "WebhookStatusUpdate",
    "WhatsAppClientError",
    "WhatsAppCloudClient",
    "WhatsAppSendResult",
    "WhatsAppTemplateName",
    "build_pwa_deep_link",
    "build_upcoming_slots",
    "evaluate_due_notifications_for_user",
    "get_template_definition",
    "is_within_quiet_hours",
    "list_template_definitions",
    "parse_webhook_events",
    "render_template_payload",
    "run_proactive_scheduler",
    "verify_payment_webhook_signature",
    "verify_webhook_signature",
]
