export type Gender = "female" | "male";

export type ActivityLevel =
  | "sedentary"
  | "light"
  | "moderate"
  | "active"
  | "very_active";

export type Goal = "lose" | "maintain" | "gain";

export type MedicalCondition =
  | "pcos"
  | "diabetes_t2"
  | "hypothyroid"
  | "hypertension";

export type HighRiskCondition =
  | "diabetes_t1"
  | "kidney_disease"
  | "liver_disease"
  | "eating_disorder_history";

export type DietType = "non_veg" | "veg" | "eggetarian";

export interface UserProfilePayload {
  age: number;
  gender: Gender;
  height_cm: number;
  weight_kg: number;
  target_weight_kg?: number | null;
  target_date?: string | null;
  activity_level: ActivityLevel;
  goal: Goal;
  conditions: MedicalCondition[];
  high_risk_conditions: HighRiskCondition[];
  is_pregnant: boolean;
  on_regular_medication: boolean;
  diet_type: DietType;
  allergies: string[];
  dislikes: string[];
  timezone?: string;
}

export interface UserProfileResponse extends UserProfilePayload {
  timezone: string;
  bmi: number;
  is_high_risk: boolean;
  high_risk_reasons: string[];
  supplements_allowed: boolean;
}

export interface NutritionTargets {
  calories: number;
  bmr: number;
  tdee: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  water_ml: number;
  sodium_mg_max: number;
  max_carbs_per_meal_g: number | null;
  forbidden_tags: string[];
  required_tags: string[];
  applied_rules: string[];
  warnings: string[];
}

export interface ProfileRecord {
  user_id: string;
  email: string | null;
  full_name: string | null;
  phone: string | null;
  profile: UserProfileResponse;
  targets: NutritionTargets;
}

export interface ProfileUpsertRequest {
  user_id?: string | null;
  email?: string | null;
  full_name?: string | null;
  phone?: string | null;
  profile: UserProfilePayload;
}

export interface ChatRequestPayload {
  user_id: string;
  message: string;
  channel?: "web" | "whatsapp";
}

export interface UserMemoryRecord {
  id: string;
  user_id: string;
  category: "preference" | "trigger" | "win" | "fact" | string;
  content: string;
  created_at: string;
}

export interface ChatResponse {
  user_id: string;
  reply: string;
  intent: string;
  flagged_safety: boolean;
  safety_category: string;
  stop_diet_advice: boolean;
  grounded_data: Record<string, unknown>;
  used_fallback: boolean;
  saved_memories: UserMemoryRecord[];
  used_memories: string[];
  user_message_id: string;
  assistant_message_id: string;
}

export interface ChatMessageRecord {
  id: string;
  user_id: string;
  role: "user" | "assistant" | string;
  content: string;
  channel: string;
  flagged_safety: boolean;
  created_at: string;
}

export interface ChatHistoryResponse {
  user_id: string;
  messages: ChatMessageRecord[];
}

export interface EmotionalPattern {
  pattern_type: string;
  severity: "positive" | "low" | "medium" | "high";
  occurrences: number;
  description: string;
  evidence: string[];
}

export interface ProactiveNudge {
  pattern_type: string;
  suggested_timing: string;
  channel: "web" | "whatsapp";
  message: string;
}

export interface PatternReport {
  patterns: EmotionalPattern[];
  nudges: ProactiveNudge[];
  summary: string;
}

export interface ScaledFoodItem {
  food_id: string;
  name: string;
  urdu_name: string;
  serving_desc: string;
  servings: number;
  grams: number;
  kcal: number;
  protein: number;
  carbs: number;
  fat: number;
  fiber: number;
  sodium_mg: number;
}

export interface ValidatedMeal {
  meal_type: "breakfast" | "lunch" | "snack" | "dinner";
  items: ScaledFoodItem[];
  kcal: number;
  protein: number;
  carbs: number;
  fat: number;
  fiber: number;
  sodium_mg: number;
}

export interface ValidatedMealPlan {
  meals: ValidatedMeal[];
  total_kcal: number;
  total_protein_g: number;
  total_carbs_g: number;
  total_fat_g: number;
  total_fiber_g: number;
  total_sodium_mg: number;
  notes: string;
  used_fallback: boolean;
  attempts_used: number;
}

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function extractErrorDetail(payload: unknown, fallbackStatusText: string): string {
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    const rawDetail = (payload as { detail: unknown }).detail;
    if (typeof rawDetail === "string" && rawDetail.trim()) {
      return rawDetail;
    }
    if (Array.isArray(rawDetail)) {
      const messages = rawDetail
        .map((entry) => {
          if (typeof entry === "object" && entry !== null && "msg" in entry) {
            const msg = (entry as { msg: unknown }).msg;
            return typeof msg === "string" ? msg : "";
          }
          return "";
        })
        .filter(Boolean);
      if (messages.length > 0) {
        return messages.join("; ");
      }
    }
  }
  return fallbackStatusText || "Request failed";
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  const text = await response.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text) as unknown;
    } catch {
      parsed = null;
    }
  }

  if (!response.ok) {
    const detail = extractErrorDetail(parsed, response.statusText);
    throw new ApiError(response.status, detail);
  }

  return parsed as T;
}

export async function checkHealth(): Promise<{ status: string }> {
  return requestJson<{ status: string }>("/health", { method: "GET" });
}

export async function createOrUpsertProfile(
  payload: ProfileUpsertRequest,
): Promise<ProfileRecord> {
  return requestJson<ProfileRecord>("/api/v1/profiles", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getProfile(userId: string): Promise<ProfileRecord> {
  return requestJson<ProfileRecord>(
    `/api/v1/profiles/${encodeURIComponent(userId)}`,
    { method: "GET" },
  );
}

export async function updateProfile(
  userId: string,
  payload: Omit<ProfileUpsertRequest, "user_id">,
): Promise<ProfileRecord> {
  return requestJson<ProfileRecord>(
    `/api/v1/profiles/${encodeURIComponent(userId)}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
}

export async function sendChatMessage(payload: ChatRequestPayload): Promise<ChatResponse> {
  return requestJson<ChatResponse>("/api/v1/chat", {
    method: "POST",
    body: JSON.stringify({ channel: "web", ...payload }),
  });
}

export async function getChatHistory(
  userId: string,
  limit = 100,
): Promise<ChatHistoryResponse> {
  return requestJson<ChatHistoryResponse>(
    `/api/v1/chat/${encodeURIComponent(userId)}/history?limit=${limit}`,
    { method: "GET" },
  );
}

export async function getUserPatterns(
  userId: string,
  days = 14,
): Promise<PatternReport> {
  return requestJson<PatternReport>(
    `/api/v1/chat/${encodeURIComponent(userId)}/patterns?days=${days}`,
    { method: "GET" },
  );
}

export async function generateDailyMealPlan(
  userId: string,
  dayIndex = 0,
): Promise<ValidatedMealPlan> {
  return requestJson<ValidatedMealPlan>(
    `/api/v1/meal-plans/${encodeURIComponent(userId)}/daily?day_index=${dayIndex}`,
    { method: "POST" },
  );
}
