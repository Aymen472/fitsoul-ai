export interface SparklinePoint {
  x: number;
  y: number;
}

export interface MoodOption {
  value: string;
  label: string;
  tone: "teal" | "amber" | "rose" | "outline";
}

export const MOOD_OPTIONS: MoodOption[] = [
  { value: "happy", label: "Happy", tone: "teal" },
  { value: "motivated", label: "Motivated", tone: "teal" },
  { value: "calm", label: "Calm", tone: "outline" },
  { value: "tired", label: "Tired", tone: "amber" },
  { value: "stressed", label: "Stressed", tone: "rose" },
  { value: "guilty", label: "Guilty", tone: "rose" },
];

export function clampPercent(current: number, target: number): number {
  if (!Number.isFinite(current) || !Number.isFinite(target) || target <= 0) {
    return 0;
  }
  const pct = Math.round((current / target) * 100);
  return Math.max(0, Math.min(100, pct));
}

export function buildSparklinePoints(
  values: number[],
  width: number,
  height: number,
  padding = 10,
): SparklinePoint[] {
  const clean = values.filter((v) => Number.isFinite(v));
  if (clean.length === 0 || width <= 0 || height <= 0) {
    return [];
  }

  const safePadX = Math.min(padding, width / 4);
  const safePadY = Math.min(padding, height / 4);
  const innerW = Math.max(1, width - safePadX * 2);
  const innerH = Math.max(1, height - safePadY * 2);

  if (clean.length === 1) {
    return [{ x: Math.round((width / 2) * 10) / 10, y: Math.round((height / 2) * 10) / 10 }];
  }

  const minVal = Math.min(...clean);
  const maxVal = Math.max(...clean);
  const span = maxVal - minVal;

  return clean.map((val, idx) => {
    const x = safePadX + (idx / (clean.length - 1)) * innerW;
    const y =
      span === 0
        ? height / 2
        : safePadY + ((maxVal - val) / span) * innerH;
    return {
      x: Math.round(x * 10) / 10,
      y: Math.round(y * 10) / 10,
    };
  });
}

export function formatShortDate(isoOrDate: string): string {
  if (!isoOrDate) {
    return "";
  }
  try {
    const parsed = new Date(isoOrDate);
    if (Number.isNaN(parsed.getTime())) {
      return "";
    }
    return parsed.toLocaleDateString([], { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

export function formatMealTypeLabel(mealType: string): string {
  const cleaned = mealType.trim().toLowerCase();
  if (cleaned === "breakfast") {
    return "Breakfast";
  }
  if (cleaned === "lunch") {
    return "Lunch";
  }
  if (cleaned === "snack") {
    return "Snack";
  }
  if (cleaned === "dinner") {
    return "Dinner";
  }
  return cleaned ? cleaned.charAt(0).toUpperCase() + cleaned.slice(1) : "Meal";
}
