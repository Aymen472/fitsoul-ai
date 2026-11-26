import type { WorkoutLogRecord } from "@/lib/api";

export function formatTimer(totalSeconds: number): string {
  const safe = Number.isFinite(totalSeconds) ? Math.max(0, Math.floor(totalSeconds)) : 0;
  const mins = Math.floor(safe / 60);
  const secs = safe % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export function estimateWorkoutCalories(
  metValue: number,
  weightKg: number,
  durationMinutes: number,
): number {
  if (
    !Number.isFinite(metValue) ||
    !Number.isFinite(weightKg) ||
    !Number.isFinite(durationMinutes) ||
    metValue <= 0 ||
    weightKg <= 0 ||
    durationMinutes <= 0
  ) {
    return 0;
  }
  return Math.round(metValue * weightKg * (durationMinutes / 60) * 10) / 10;
}

export function computeWorkoutTotals(logs: WorkoutLogRecord[]): {
  sessions: number;
  totalMinutes: number;
  totalCalories: number;
} {
  let totalMinutes = 0;
  let totalCalories = 0;
  for (const log of logs) {
    totalMinutes += log.duration_minutes;
    totalCalories += log.calories_burned;
  }
  return {
    sessions: logs.length,
    totalMinutes,
    totalCalories: Math.round(totalCalories * 10) / 10,
  };
}

export function formatWorkoutCategory(workoutType: string): string {
  const cleaned = workoutType.trim().toLowerCase();
  if (cleaned === "face_yoga") {
    return "Face Yoga";
  }
  if (cleaned === "fitness") {
    return "Home Fitness";
  }
  return cleaned ? cleaned.charAt(0).toUpperCase() + cleaned.slice(1) : "Workout";
}

export function speakCue(text: string, enabled: boolean): void {
  if (!enabled || !text.trim() || typeof window === "undefined") {
    return;
  }
  try {
    if (!("speechSynthesis" in window) || typeof SpeechSynthesisUtterance === "undefined") {
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.95;
    window.speechSynthesis.speak(utterance);
  } catch {
    // Ignore browser speech synthesis restrictions cleanly.
  }
}
