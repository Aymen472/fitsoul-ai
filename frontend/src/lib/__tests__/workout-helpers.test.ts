import { describe, expect, it } from "vitest";

import {
  computeWorkoutTotals,
  estimateWorkoutCalories,
  formatTimer,
  formatWorkoutCategory,
  speakCue,
} from "@/lib/workout-helpers";

describe("workout helpers", () => {
  it("formats timer seconds cleanly as MM:SS", () => {
    expect(formatTimer(0)).toBe("00:00");
    expect(formatTimer(-5)).toBe("00:00");
    expect(formatTimer(65)).toBe("01:05");
    expect(formatTimer(600)).toBe("10:00");
  });

  it("estimates MET calorie burn accurately and handles invalid inputs", () => {
    expect(estimateWorkoutCalories(4.0, 75, 15)).toBe(75);
    expect(estimateWorkoutCalories(1.8, 70, 8)).toBe(16.8);
    expect(estimateWorkoutCalories(0, 75, 15)).toBe(0);
    expect(estimateWorkoutCalories(4.0, -60, 15)).toBe(0);
  });

  it("aggregates completed workout totals and formats category labels", () => {
    const totals = computeWorkoutTotals([
      {
        id: "w1",
        user_id: "u1",
        routine_name: "PCOS Walk",
        workout_type: "fitness",
        duration_minutes: 15,
        calories_burned: 75.0,
        completed_at: "2026-11-26T10:00:00Z",
      },
      {
        id: "w2",
        user_id: "u1",
        routine_name: "Jawline Sculpt",
        workout_type: "face_yoga",
        duration_minutes: 8,
        calories_burned: 18.0,
        completed_at: "2026-11-26T12:00:00Z",
      },
    ]);

    expect(totals).toEqual({
      sessions: 2,
      totalMinutes: 23,
      totalCalories: 93,
    });
    expect(formatWorkoutCategory("fitness")).toBe("Home Fitness");
    expect(formatWorkoutCategory("face_yoga")).toBe("Face Yoga");
    expect(formatWorkoutCategory("mobility")).toBe("Mobility");
  });

  it("handles voice synthesis safely in non-browser Node environments", () => {
    expect(() => speakCue("Start squat", true)).not.toThrow();
    expect(() => speakCue("", false)).not.toThrow();
  });
});
