import { describe, expect, it } from "vitest";

import {
  formatAccessModeBadge,
  formatPlanPrice,
  formatProviderLabel,
  formatTransactionStatus,
} from "@/lib/billing-helpers";

describe("billing-helpers", () => {
  it("formats PKR, USD, and free trial prices cleanly", () => {
    expect(formatPlanPrice(0, "PKR", 7)).toBe("Free (7 days)");
    expect(formatPlanPrice(2999, "PKR", 30)).toBe("Rs. 2,999 / month");
    expect(formatPlanPrice(6999, "PKR", 90)).toBe("Rs. 6,999 / 3 months");
    expect(formatPlanPrice(9.99, "USD", 30)).toBe("$9.99 / month");
  });

  it("formats Pakistani and overseas payment providers", () => {
    expect(formatProviderLabel("safepay")).toBe("Safepay");
    expect(formatProviderLabel("payfast")).toBe("PayFast");
    expect(formatProviderLabel("jazzcash")).toBe("JazzCash");
    expect(formatProviderLabel("easypaisa")).toBe("Easypaisa");
    expect(formatProviderLabel("lemonsqueezy")).toBe("LemonSqueezy");
    expect(formatProviderLabel(null)).toBe("Free Trial");
  });

  it("maps access entitlements to clear status badges", () => {
    expect(
      formatAccessModeBadge({
        access_mode: "limited",
        is_active: false,
        is_trial: false,
        days_remaining: 0,
        renewal_due_soon: false,
        can_use_ai_chat: true,
        can_use_photo_scanner: false,
        can_use_workouts_face_yoga: false,
        can_use_weekly_meal_plan: false,
        can_use_whatsapp_reminders: false,
        daily_chat_limit: 2,
      }),
    ).toEqual({ label: "Limited Mode", variant: "rose" });

    expect(
      formatAccessModeBadge({
        access_mode: "full",
        is_active: true,
        is_trial: true,
        days_remaining: 7,
        renewal_due_soon: false,
        can_use_ai_chat: true,
        can_use_photo_scanner: true,
        can_use_workouts_face_yoga: true,
        can_use_weekly_meal_plan: true,
        can_use_whatsapp_reminders: true,
        daily_chat_limit: null,
      }),
    ).toEqual({ label: "Free Trial Active", variant: "teal" });

    expect(
      formatAccessModeBadge({
        access_mode: "basic",
        is_active: true,
        is_trial: false,
        days_remaining: 15,
        renewal_due_soon: false,
        can_use_ai_chat: true,
        can_use_photo_scanner: false,
        can_use_workouts_face_yoga: false,
        can_use_weekly_meal_plan: true,
        can_use_whatsapp_reminders: true,
        daily_chat_limit: 5,
      }),
    ).toEqual({ label: "Basic Active", variant: "amber" });
  });

  it("maps transaction statuses to badge labels and variants", () => {
    expect(formatTransactionStatus("paid")).toEqual({ label: "Paid", variant: "teal" });
    expect(formatTransactionStatus("pending")).toEqual({ label: "Pending", variant: "amber" });
    expect(formatTransactionStatus("failed")).toEqual({ label: "Failed", variant: "rose" });
    expect(formatTransactionStatus("refunded")).toEqual({
      label: "Refunded",
      variant: "outline",
    });
  });
});
