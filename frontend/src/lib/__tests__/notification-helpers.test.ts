import { describe, expect, it } from "vitest";

import {
  formatNotificationStatus,
  formatQuietWindow,
  formatTemplateLabel,
  isValidPhoneInput,
} from "@/lib/notification-helpers";

describe("notification-helpers", () => {
  it("maps notification statuses to labels and UI tones", () => {
    expect(formatNotificationStatus("read")).toEqual({ label: "Read", tone: "teal" });
    expect(formatNotificationStatus("dry_run")).toEqual({ label: "Preview", tone: "amber" });
    expect(formatNotificationStatus("failed")).toEqual({ label: "Failed", tone: "red" });
    expect(formatNotificationStatus("received")).toEqual({ label: "Received", tone: "neutral" });
  });

  it("formats approved template names and direct replies cleanly", () => {
    expect(formatTemplateLabel("fitsoul_meal_reminder")).toBe("Meal Reminder");
    expect(formatTemplateLabel("fitsoul_workout_nudge")).toBe("Workout Nudge");
    expect(formatTemplateLabel(null)).toBe("Direct Reply");
    expect(formatTemplateLabel("fitsoul_custom_alert")).toBe("Custom Alert");
  });

  it("formats quiet sleep window strings cleanly", () => {
    expect(formatQuietWindow("22:30", "07:00")).toBe("22:30 – 07:00");
    expect(formatQuietWindow("00:00", "00:00")).toBe("Disabled");
    expect(formatQuietWindow("", "")).toBe("Not set");
  });

  it("validates Pakistani and international phone numbers", () => {
    expect(isValidPhoneInput("0300-1234567")).toBe(true);
    expect(isValidPhoneInput("+92 321 7654321")).toBe(true);
    expect(isValidPhoneInput("923001234567")).toBe(true);
    expect(isValidPhoneInput("")).toBe(false);
    expect(isValidPhoneInput("12345")).toBe(false);
    expect(isValidPhoneInput("+92-300-abc")).toBe(false);
  });
});
