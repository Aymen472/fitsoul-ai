import { describe, expect, it } from "vitest";

import {
  QUICK_PROMPTS,
  formatIntentLabel,
  formatMemoryCategoryLabel,
  formatMessageTime,
  formatPatternLabel,
  mapHistoryToUiMessages,
  mergeUniqueMemories,
} from "@/lib/chat-helpers";

describe("chat helpers", () => {
  it("provides culturally relevant quick prompts", () => {
    expect(QUICK_PROMPTS.length).toBeGreaterThanOrEqual(4);
    for (const item of QUICK_PROMPTS) {
      expect(item.label.trim().length).toBeGreaterThan(0);
      expect(item.prompt.trim().length).toBeGreaterThan(0);
    }
  });

  it("formats intent, memory category, and pattern labels cleanly", () => {
    expect(formatIntentLabel("meal_log")).toBe("Meal Logged");
    expect(formatIntentLabel("eating_out")).toBe("Dawat / Eating Out");
    expect(formatIntentLabel("custom_topic")).toBe("Custom Topic");

    expect(formatMemoryCategoryLabel("win")).toBe("Micro-Win");
    expect(formatMemoryCategoryLabel("trigger")).toBe("Trigger");
    expect(formatMemoryCategoryLabel("other_tag")).toBe("Other Tag");

    expect(formatPatternLabel("late_night_craving")).toBe("Late-Night Cravings");
    expect(formatPatternLabel("micro_win")).toBe("Healthy Momentum & Wins");
    expect(formatPatternLabel("new_pattern")).toBe("New Pattern");
  });

  it("formats valid timestamps safely and rejects invalid inputs", () => {
    expect(formatMessageTime("2026-11-25T14:30:00Z")).not.toBe("");
    expect(formatMessageTime("not-a-date")).toBe("");
    expect(formatMessageTime("")).toBe("");
  });

  it("deduplicates merged memories with incoming entries prioritized first", () => {
    const existing = [
      {
        id: "m1",
        user_id: "u1",
        category: "preference",
        content: "Daal moong pasand hai",
        created_at: "2026-11-25T10:00:00Z",
      },
      {
        id: "m2",
        user_id: "u1",
        category: "trigger",
        content: "Raat ko craving hoti hai",
        created_at: "2026-11-25T11:00:00Z",
      },
    ];
    const incoming = [
      {
        id: "m2",
        user_id: "u1",
        category: "trigger",
        content: "Raat ko craving hoti hai",
        created_at: "2026-11-25T11:00:00Z",
      },
      {
        id: "m3",
        user_id: "u1",
        category: "win",
        content: "Is hafte 1 kg kam hua",
        created_at: "2026-11-25T12:00:00Z",
      },
    ];

    const merged = mergeUniqueMemories(existing, incoming);
    expect(merged.map((m) => m.id)).toEqual(["m2", "m3", "m1"]);
  });

  it("maps persisted history records into UI chat bubbles and skips system rows", () => {
    const mapped = mapHistoryToUiMessages([
      {
        id: "msg-0",
        user_id: "u1",
        role: "system",
        content: "Internal note",
        channel: "web",
        flagged_safety: false,
        created_at: "2026-11-25T10:00:00Z",
      },
      {
        id: "msg-1",
        user_id: "u1",
        role: "user",
        content: "Salam",
        channel: "web",
        flagged_safety: true,
        created_at: "2026-11-25T10:01:00Z",
      },
      {
        id: "msg-2",
        user_id: "u1",
        role: "assistant",
        content: "Walaikum assalam!",
        channel: "web",
        flagged_safety: false,
        created_at: "2026-11-25T10:01:01Z",
      },
    ]);

    expect(mapped).toHaveLength(2);
    expect(mapped[0]).toMatchObject({
      id: "msg-1",
      role: "user",
      content: "Salam",
      flaggedSafety: true,
    });
    expect(mapped[1]).toMatchObject({
      id: "msg-2",
      role: "assistant",
      content: "Walaikum assalam!",
      flaggedSafety: false,
    });
  });
});
