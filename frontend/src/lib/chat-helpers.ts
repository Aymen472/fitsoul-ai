import type { ChatMessageRecord, UserMemoryRecord } from "@/lib/api";

export interface UiChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  flaggedSafety?: boolean;
  safetyCategory?: string;
  stopDietAdvice?: boolean;
  intent?: string;
  usedMemories?: string[];
  savedMemories?: UserMemoryRecord[];
  usedFallback?: boolean;
  groundedData?: Record<string, unknown>;
  pending?: boolean;
}

export interface QuickPrompt {
  label: string;
  prompt: string;
}

export const QUICK_PROMPTS: QuickPrompt[] = [
  {
    label: "Log Desi Lunch",
    prompt: "Maine lunch mein 2 roti aur 1 daal moong khai",
  },
  {
    label: "Chai-Time Craving",
    prompt: "Sham ki chai ke saath craving ho rahi hai",
  },
  {
    label: "Dawat Strategy",
    prompt: "Dawat mein chicken biryani hai, kya karun?",
  },
  {
    label: "Daily Calories Left",
    prompt: "Aaj kitni calories baki hain?",
  },
  {
    label: "Share Preference",
    prompt: "Mujhe daal moong bohat pasand hai aur karela pasand nahi",
  },
  {
    label: "Mood / Guilt Support",
    prompt: "Aaj cheat meal ho gaya, bohot guilty feel ho raha hai",
  },
];

const INTENT_LABELS: Record<string, string> = {
  meal_log: "Meal Logged",
  meal_plan: "Meal Plan",
  craving: "Craving Swap",
  eating_out: "Dawat / Eating Out",
  supplement_query: "Supplements",
  workout_question: "Workouts",
  mood_emotional: "Emotional Support",
  progress_query: "Daily Progress",
  billing: "Plans & Billing",
  general: "Coach Reply",
};

const MEMORY_CATEGORY_LABELS: Record<string, string> = {
  preference: "Preference",
  trigger: "Trigger",
  win: "Micro-Win",
  fact: "Lifestyle",
};

const PATTERN_LABELS: Record<string, string> = {
  late_night_craving: "Late-Night Cravings",
  weekend_calorie_slip: "Weekend Calorie Slips",
  stress_eating: "Stress / Emotional Eating",
  micro_win: "Healthy Momentum & Wins",
};

function humanizeSlug(raw: string): string {
  return raw
    .trim()
    .replace(/_/g, " ")
    .replace(/\b\w/g, (ch) => ch.toUpperCase());
}

export function formatIntentLabel(intent: string): string {
  return INTENT_LABELS[intent] ?? humanizeSlug(intent);
}

export function formatMemoryCategoryLabel(category: string): string {
  return MEMORY_CATEGORY_LABELS[category] ?? humanizeSlug(category);
}

export function formatPatternLabel(patternType: string): string {
  return PATTERN_LABELS[patternType] ?? humanizeSlug(patternType);
}

export function formatMessageTime(isoTimestamp: string): string {
  if (!isoTimestamp) {
    return "";
  }
  try {
    const parsed = new Date(isoTimestamp);
    if (Number.isNaN(parsed.getTime())) {
      return "";
    }
    return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export function mergeUniqueMemories(
  existing: UserMemoryRecord[],
  incoming: UserMemoryRecord[],
): UserMemoryRecord[] {
  const seen = new Set<string>();
  const merged: UserMemoryRecord[] = [];
  for (const item of [...incoming, ...existing]) {
    if (!seen.has(item.id)) {
      seen.add(item.id);
      merged.push(item);
    }
  }
  return merged;
}

export function mapHistoryToUiMessages(messages: ChatMessageRecord[]): UiChatMessage[] {
  return messages
    .filter((msg) => msg.role === "user" || msg.role === "assistant")
    .map((msg) => ({
      id: msg.id,
      role: msg.role as "user" | "assistant",
      content: msg.content,
      createdAt: msg.created_at,
      flaggedSafety: msg.flagged_safety,
    }));
}
