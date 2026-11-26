export type StatusTone = "teal" | "amber" | "red" | "neutral";

const TEMPLATE_LABELS: Record<string, string> = {
  fitsoul_meal_reminder: "Meal Reminder",
  fitsoul_water_reminder: "Water Check",
  fitsoul_workout_nudge: "Workout Nudge",
  fitsoul_night_summary: "Night Wrap-up",
  fitsoul_weekly_report: "Weekly Report",
  fitsoul_proactive_support: "Coach Check-in",
  fitsoul_subscription_renewal: "Plan Renewal",
};

export function formatNotificationStatus(status: string): {
  label: string;
  tone: StatusTone;
} {
  switch (status.trim().toLowerCase()) {
    case "read":
      return { label: "Read", tone: "teal" };
    case "delivered":
      return { label: "Delivered", tone: "teal" };
    case "sent":
      return { label: "Sent", tone: "teal" };
    case "dry_run":
      return { label: "Preview", tone: "amber" };
    case "queued":
      return { label: "Queued", tone: "amber" };
    case "failed":
      return { label: "Failed", tone: "red" };
    case "received":
      return { label: "Received", tone: "neutral" };
    default:
      return { label: status || "Unknown", tone: "neutral" };
  }
}

export function formatTemplateLabel(templateName: string | null): string {
  if (!templateName) {
    return "Direct Reply";
  }
  const key = templateName.trim();
  if (key in TEMPLATE_LABELS) {
    return TEMPLATE_LABELS[key];
  }
  return key
    .replace(/^fitsoul_/, "")
    .split("_")
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatQuietWindow(start: string, end: string): string {
  const s = start.trim();
  const e = end.trim();
  if (!s || !e) {
    return "Not set";
  }
  if (s === e) {
    return "Disabled";
  }
  return `${s} – ${e}`;
}

export function isValidPhoneInput(raw: string): boolean {
  let cleaned = raw.trim().replace(/[\s\-()]+/g, "");
  if (cleaned.startsWith("+")) {
    cleaned = cleaned.slice(1);
  }
  if (!cleaned || !/^\d+$/.test(cleaned)) {
    return false;
  }
  if (cleaned.length === 11 && cleaned.startsWith("03")) {
    cleaned = `92${cleaned.slice(1)}`;
  }
  return cleaned.length >= 10 && cleaned.length <= 15;
}
