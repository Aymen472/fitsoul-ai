import { describe, expect, it } from "vitest";

import {
  MOOD_OPTIONS,
  buildSparklinePoints,
  clampPercent,
  formatMealTypeLabel,
  formatShortDate,
} from "@/lib/dashboard-helpers";

describe("dashboard helpers", () => {
  it("clamps percentage progress between 0 and 100 safely", () => {
    expect(clampPercent(688, 1376)).toBe(50);
    expect(clampPercent(-50, 1376)).toBe(0);
    expect(clampPercent(2200, 1376)).toBe(100);
    expect(clampPercent(500, 0)).toBe(0);
    expect(clampPercent(Number.NaN, 1376)).toBe(0);
  });

  it("builds valid SVG sparkline coordinates across edge cases", () => {
    expect(buildSparklinePoints([], 280, 96)).toEqual([]);

    const single = buildSparklinePoints([74.5], 280, 96);
    expect(single).toEqual([{ x: 140, y: 48 }]);

    const flat = buildSparklinePoints([74.0, 74.0, 74.0], 280, 96, 12);
    expect(flat).toHaveLength(3);
    expect(flat.every((pt) => pt.y === 48)).toBe(true);

    const trend = buildSparklinePoints([76.0, 75.0, 74.0], 280, 96, 10);
    expect(trend).toHaveLength(3);
    expect(trend[0].y).toBe(10); // max value at top
    expect(trend[2].y).toBe(86); // min value at bottom
    expect(trend[1].y).toBe(48); // midpoint
  });

  it("formats short dates, meal types, and exposes mood options", () => {
    expect(MOOD_OPTIONS.length).toBeGreaterThanOrEqual(5);
    expect(formatShortDate("2026-11-25T10:00:00Z")).not.toBe("");
    expect(formatShortDate("bad-date")).toBe("");
    expect(formatShortDate("")).toBe("");

    expect(formatMealTypeLabel("breakfast")).toBe("Breakfast");
    expect(formatMealTypeLabel("DINNER")).toBe("Dinner");
    expect(formatMealTypeLabel("sehri")).toBe("Sehri");
  });
});
