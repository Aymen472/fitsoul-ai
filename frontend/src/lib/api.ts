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

export interface ChatMemoriesResponse {
  user_id: string;
  memories: UserMemoryRecord[];
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
  urdu_name?: string;
  serving_desc?: string;
  servings: number;
  grams: number;
  kcal: number;
  protein: number;
  carbs: number;
  fat: number;
  fiber: number;
  sodium_mg: number;
}

export interface GroceryItem {
  food_id: string;
  name: string;
  urdu_name: string;
  category: string;
  total_servings: number;
  total_grams: number;
}

export interface WeeklyMealPlan {
  days: ValidatedMealPlan[];
  grocery_list: GroceryItem[];
}

export interface MealSwapRequest {
  day_index: number;
  meal_type: "breakfast" | "lunch" | "snack" | "dinner";
  exclude_food_ids: string[];
  attempt: number;
}

export interface MealSwapResponse {
  day_index: number;
  meal_type: "breakfast" | "lunch" | "snack" | "dinner";
  meal: ValidatedMeal;
  updated_day: ValidatedMealPlan;
  day_grocery_items: GroceryItem[];
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

export interface FoodSearchItem {
  id: string;
  name: string;
  urdu_name: string;
  category: string;
  serving_desc: string;
  grams: number;
  kcal: number;
  protein: number;
  carbs: number;
  fat: number;
  fiber: number;
  sodium_mg: number;
  gi_category: string;
}

export interface MealEditItemInput {
  food_id: string;
  servings: number;
}

export interface QuickMealLogRequest {
  meal_type: "breakfast" | "lunch" | "snack" | "dinner";
  items: MealEditItemInput[];
  plate_notes?: string;
}

export interface MealLogRecord {
  id: string;
  user_id: string;
  meal_type: string;
  items: Record<string, unknown>[];
  total_kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  photo_url: string | null;
  logged_at: string;
}

export interface WaterLogRecord {
  id: string;
  user_id: string;
  amount_ml: number;
  logged_at: string;
}

export interface WeightLogRecord {
  id: string;
  user_id: string;
  weight_kg: number;
  logged_at: string;
}

export interface MoodLogRecord {
  id: string;
  user_id: string;
  mood: string;
  note: string | null;
  logged_at: string;
}

export interface WorkoutStep {
  id: string;
  name: string;
  instructions: string;
  duration_sec: number;
  rest_sec: number;
  muscle_groups: string[];
  contraindications: string[];
  easier_alternative_name: string | null;
  easier_alternative_instructions: string | null;
}

export interface WorkoutRoutine {
  id: string;
  name: string;
  urdu_subtitle: string;
  workout_type: "fitness" | "face_yoga";
  level: "beginner" | "intermediate";
  duration_minutes: number;
  met_value: number;
  focus_areas: string[];
  contraindications: string[];
  description: string;
  steps: WorkoutStep[];
}

export interface WorkoutLogRequest {
  routine_id?: string;
  routine_name?: string;
  workout_type?: "fitness" | "face_yoga";
  duration_minutes: number;
}

export interface WorkoutLogRecord {
  id: string;
  user_id: string;
  routine_name: string;
  workout_type: string;
  duration_minutes: number;
  calories_burned: number;
  completed_at: string;
}

export interface DashboardSummary {
  user_id: string;
  date: string;
  targets: NutritionTargets;
  consumed_kcal: number;
  remaining_kcal: number;
  consumed_protein_g: number;
  consumed_carbs_g: number;
  consumed_fat_g: number;
  water_ml: number;
  water_target_ml: number;
  streak_days: number;
  latest_weight_kg: number;
  target_weight_kg: number | null;
  weight_history: WeightLogRecord[];
  today_meals: MealLogRecord[];
  recent_meals: MealLogRecord[];
  recent_moods: MoodLogRecord[];
  patterns: PatternReport;
}

export interface WhatsAppTemplateDefinition {
  name: string;
  category: string;
  language_code: string;
  required_params: string[];
  default_path: string;
  preview_body: string;
}

export interface NotificationPreferences {
  user_id: string;
  whatsapp_opt_in: boolean;
  whatsapp_phone: string | null;
  meal_reminders: boolean;
  water_reminders: boolean;
  workout_reminders: boolean;
  night_summary: boolean;
  weekly_report: boolean;
  quiet_hours_start: string;
  quiet_hours_end: string;
  updated_at?: string | null;
}

export interface NotificationPreferencesUpdate {
  whatsapp_opt_in: boolean;
  whatsapp_phone: string | null;
  meal_reminders: boolean;
  water_reminders: boolean;
  workout_reminders: boolean;
  night_summary: boolean;
  weekly_report: boolean;
  quiet_hours_start: string;
  quiet_hours_end: string;
}

export interface NotificationLogEntry {
  id: string;
  user_id: string | null;
  channel: string;
  direction: string;
  template_name: string | null;
  recipient_phone: string;
  provider_message_id: string | null;
  status: string;
  deep_link: string | null;
  payload: Record<string, unknown>;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface SendNotificationPayload {
  template_name: string;
  params: Record<string, string | number>;
  language_code?: string;
  query_params?: Record<string, string>;
  dry_run?: boolean;
}

export interface SendNotificationResponse {
  log: NotificationLogEntry;
  preview_text: string;
  dry_run: boolean;
}

export interface UpcomingSlotSummary {
  slot_type: string;
  label: string;
  local_time: string;
  enabled: boolean;
  template_name: string;
}

export interface ScheduledNotificationJob {
  user_id: string;
  template_name: string;
  slot_key: string;
  recipient_phone: string;
  params: Record<string, string>;
  reason: string;
}

export interface SchedulePreviewResponse {
  user_id: string;
  timezone: string;
  local_time: string;
  in_quiet_hours: boolean;
  whatsapp_opt_in: boolean;
  due_jobs: ScheduledNotificationJob[];
  upcoming_slots: UpcomingSlotSummary[];
}

export type PlanId = "trial" | "basic" | "pro" | "transformation" | "overseas";

export type PaymentProvider =
  | "safepay"
  | "payfast"
  | "jazzcash"
  | "easypaisa"
  | "lemonsqueezy"
  | "mock";

export interface PlanDefinition {
  id: PlanId;
  name: string;
  tagline: string;
  price_amount: number;
  currency: "PKR" | "USD";
  duration_days: number;
  is_popular: boolean;
  features: string[];
  supported_providers: PaymentProvider[];
}

export interface AccessEntitlements {
  access_mode: "full" | "basic" | "limited";
  is_active: boolean;
  is_trial: boolean;
  days_remaining: number;
  renewal_due_soon: boolean;
  can_use_ai_chat: boolean;
  can_use_photo_scanner: boolean;
  can_use_workouts_face_yoga: boolean;
  can_use_weekly_meal_plan: boolean;
  can_use_whatsapp_reminders: boolean;
  daily_chat_limit: number | null;
}

export interface SubscriptionRecord {
  id: string;
  user_id: string;
  plan: string;
  status: string;
  provider: string | null;
  starts_at: string;
  expires_at: string | null;
  created_at: string;
}

export interface PaymentTransactionRecord {
  id: string;
  user_id: string;
  plan: string;
  provider: string;
  amount: number;
  currency: string;
  status: string;
  provider_order_id: string;
  checkout_url: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  paid_at: string | null;
}

export interface BillingStatusResponse {
  user_id: string;
  subscription: SubscriptionRecord | null;
  entitlements: AccessEntitlements;
  trial_eligible: boolean;
  transactions: PaymentTransactionRecord[];
}

export interface CheckoutResponse {
  transaction: PaymentTransactionRecord;
  checkout_url: string;
  sandbox_mode: boolean;
  instructions: string;
}

export interface PaymentWebhookAckResponse {
  status: string;
  already_processed: boolean;
  transaction: PaymentTransactionRecord;
  subscription: SubscriptionRecord | null;
}

export interface AdminOverviewMetrics {
  total_users: number;
  total_profiles: number;
  active_subscriptions: number;
  trial_subscriptions: number;
  paid_subscriptions: number;
  revenue_pkr: number;
  revenue_usd: number;
  flagged_safety_count: number;
  total_messages: number;
  estimated_ai_cost_usd: number;
  avg_ai_cost_per_user_usd: number;
  total_foods: number;
}

export interface AdminUserSummary {
  user_id: string;
  full_name: string | null;
  email: string | null;
  phone: string | null;
  goal: string | null;
  is_high_risk: boolean;
  subscription_plan: string | null;
  subscription_status: string;
  message_count: number;
  flagged_count: number;
  estimated_ai_cost_usd: number;
  created_at: string;
}

export interface FlaggedMessageRecord {
  id: string;
  user_id: string;
  user_full_name: string | null;
  user_email: string | null;
  role: string;
  content: string;
  channel: string;
  created_at: string;
}

export interface AdminFoodItem {
  id: string;
  name: string;
  urdu_name: string;
  aliases: string[];
  category: string;
  serving_desc: string;
  grams: number;
  kcal: number;
  protein: number;
  carbs: number;
  fat: number;
  fiber: number;
  sodium_mg: number;
  gi_category: "low" | "medium" | "high";
  tags: string[];
}

export type AdminFoodUpsertPayload = Omit<AdminFoodItem, "id">;

export interface UserDeletionSummary {
  user_id: string;
  deleted: boolean;
  records_removed: Record<string, number>;
  deleted_at: string;
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

export async function getUserMemories(userId: string): Promise<ChatMemoriesResponse> {
  return requestJson<ChatMemoriesResponse>(
    `/api/v1/chat/${encodeURIComponent(userId)}/memories`,
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

export async function generateWeeklyMealPlan(
  userId: string,
  days = 7,
): Promise<WeeklyMealPlan> {
  return requestJson<WeeklyMealPlan>(
    `/api/v1/meal-plans/${encodeURIComponent(userId)}/weekly?days=${days}`,
    { method: "POST" },
  );
}

export async function swapMealPlanSlot(
  userId: string,
  payload: MealSwapRequest,
): Promise<MealSwapResponse> {
  return requestJson<MealSwapResponse>(
    `/api/v1/meal-plans/${encodeURIComponent(userId)}/swap`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function searchFoods(query = "", limit = 12): Promise<FoodSearchItem[]> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  return requestJson<FoodSearchItem[]>(`/api/v1/foods/search?${params.toString()}`, {
    method: "GET",
  });
}

export async function getDashboard(userId: string): Promise<DashboardSummary> {
  return requestJson<DashboardSummary>(
    `/api/v1/tracking/${encodeURIComponent(userId)}/dashboard`,
    { method: "GET" },
  );
}

export async function logQuickMeal(
  userId: string,
  payload: QuickMealLogRequest,
): Promise<MealLogRecord> {
  return requestJson<MealLogRecord>(
    `/api/v1/tracking/${encodeURIComponent(userId)}/meals`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function logWater(userId: string, amountMl: number): Promise<WaterLogRecord> {
  return requestJson<WaterLogRecord>(
    `/api/v1/tracking/${encodeURIComponent(userId)}/water`,
    {
      method: "POST",
      body: JSON.stringify({ amount_ml: amountMl }),
    },
  );
}

export async function logWeight(userId: string, weightKg: number): Promise<WeightLogRecord> {
  return requestJson<WeightLogRecord>(
    `/api/v1/tracking/${encodeURIComponent(userId)}/weight`,
    {
      method: "POST",
      body: JSON.stringify({ weight_kg: weightKg }),
    },
  );
}

export async function logMood(
  userId: string,
  mood: string,
  note?: string,
): Promise<MoodLogRecord> {
  return requestJson<MoodLogRecord>(
    `/api/v1/tracking/${encodeURIComponent(userId)}/mood`,
    {
      method: "POST",
      body: JSON.stringify({ mood, note: note?.trim() ? note.trim() : null }),
    },
  );
}

export async function getWorkoutRoutines(options?: {
  workoutType?: "fitness" | "face_yoga";
  avoid?: string[];
}): Promise<WorkoutRoutine[]> {
  const params = new URLSearchParams();
  if (options?.workoutType) {
    params.set("workout_type", options.workoutType);
  }
  if (options?.avoid && options.avoid.length > 0) {
    params.set("avoid", options.avoid.join(","));
  }
  const qs = params.toString();
  const path = qs ? `/api/v1/workouts/routines?${qs}` : "/api/v1/workouts/routines";
  return requestJson<WorkoutRoutine[]>(path, { method: "GET" });
}

export async function logWorkout(
  userId: string,
  payload: WorkoutLogRequest,
): Promise<WorkoutLogRecord> {
  return requestJson<WorkoutLogRecord>(
    `/api/v1/tracking/${encodeURIComponent(userId)}/workouts`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function getWorkoutHistory(
  userId: string,
  days = 30,
): Promise<WorkoutLogRecord[]> {
  return requestJson<WorkoutLogRecord[]>(
    `/api/v1/tracking/${encodeURIComponent(userId)}/workouts?days=${days}`,
    { method: "GET" },
  );
}

export async function getNotificationTemplates(): Promise<WhatsAppTemplateDefinition[]> {
  return requestJson<WhatsAppTemplateDefinition[]>("/api/v1/notifications/templates", {
    method: "GET",
  });
}

export async function getNotificationPreferences(
  userId: string,
): Promise<NotificationPreferences> {
  return requestJson<NotificationPreferences>(
    `/api/v1/notifications/${encodeURIComponent(userId)}/preferences`,
    { method: "GET" },
  );
}

export async function updateNotificationPreferences(
  userId: string,
  payload: NotificationPreferencesUpdate,
): Promise<NotificationPreferences> {
  return requestJson<NotificationPreferences>(
    `/api/v1/notifications/${encodeURIComponent(userId)}/preferences`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
}

export async function sendUserNotification(
  userId: string,
  payload: SendNotificationPayload,
): Promise<SendNotificationResponse> {
  return requestJson<SendNotificationResponse>(
    `/api/v1/notifications/${encodeURIComponent(userId)}/send`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function getNotificationLogs(
  userId: string,
  limit = 30,
): Promise<NotificationLogEntry[]> {
  return requestJson<NotificationLogEntry[]>(
    `/api/v1/notifications/${encodeURIComponent(userId)}/logs?limit=${limit}`,
    { method: "GET" },
  );
}

export async function getNotificationSchedulePreview(
  userId: string,
): Promise<SchedulePreviewResponse> {
  return requestJson<SchedulePreviewResponse>(
    `/api/v1/notifications/${encodeURIComponent(userId)}/schedule-preview`,
    { method: "GET" },
  );
}

export async function getBillingPlans(): Promise<PlanDefinition[]> {
  return requestJson<PlanDefinition[]>("/api/v1/billing/plans", { method: "GET" });
}

export async function getBillingStatus(userId: string): Promise<BillingStatusResponse> {
  return requestJson<BillingStatusResponse>(
    `/api/v1/billing/${encodeURIComponent(userId)}/subscription`,
    { method: "GET" },
  );
}

export async function startFreeTrial(userId: string): Promise<SubscriptionRecord> {
  return requestJson<SubscriptionRecord>(
    `/api/v1/billing/${encodeURIComponent(userId)}/trial`,
    { method: "POST" },
  );
}

export async function createBillingCheckout(
  userId: string,
  payload: { plan_id: PlanId; provider: PaymentProvider },
): Promise<CheckoutResponse> {
  return requestJson<CheckoutResponse>(
    `/api/v1/billing/${encodeURIComponent(userId)}/checkout`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function cancelUserSubscription(userId: string): Promise<SubscriptionRecord> {
  return requestJson<SubscriptionRecord>(
    `/api/v1/billing/${encodeURIComponent(userId)}/cancel`,
    { method: "POST" },
  );
}

export async function confirmSandboxPayment(
  provider: PaymentProvider,
  payload: {
    order_id: string;
    event: "payment.succeeded" | "payment.failed" | "payment.refunded";
    provider_reference?: string;
  },
): Promise<PaymentWebhookAckResponse> {
  return requestJson<PaymentWebhookAckResponse>(
    `/webhooks/payments/${encodeURIComponent(provider)}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

function buildAdminHeaders(adminKey?: string): Record<string, string> {
  const cleaned = adminKey?.trim() ?? "";
  return cleaned ? { "X-Admin-Key": cleaned } : {};
}

export async function getAdminOverview(adminKey?: string): Promise<AdminOverviewMetrics> {
  return requestJson<AdminOverviewMetrics>("/api/v1/admin/overview", {
    method: "GET",
    headers: buildAdminHeaders(adminKey),
  });
}

export async function getAdminUsers(
  adminKey?: string,
  limit = 50,
): Promise<AdminUserSummary[]> {
  return requestJson<AdminUserSummary[]>(`/api/v1/admin/users?limit=${limit}`, {
    method: "GET",
    headers: buildAdminHeaders(adminKey),
  });
}

export async function getAdminFlaggedMessages(
  adminKey?: string,
  limit = 50,
): Promise<FlaggedMessageRecord[]> {
  return requestJson<FlaggedMessageRecord[]>(`/api/v1/admin/flagged-messages?limit=${limit}`, {
    method: "GET",
    headers: buildAdminHeaders(adminKey),
  });
}

export async function getAdminFoods(options?: {
  query?: string;
  category?: string;
  limit?: number;
  adminKey?: string;
}): Promise<AdminFoodItem[]> {
  const params = new URLSearchParams();
  if (options?.query) {
    params.set("q", options.query);
  }
  if (options?.category) {
    params.set("category", options.category);
  }
  if (options?.limit !== undefined) {
    params.set("limit", String(options.limit));
  }
  const qs = params.toString();
  const path = qs ? `/api/v1/admin/foods?${qs}` : "/api/v1/admin/foods";
  return requestJson<AdminFoodItem[]>(path, {
    method: "GET",
    headers: buildAdminHeaders(options?.adminKey),
  });
}

export async function upsertAdminFood(
  foodId: string,
  payload: AdminFoodUpsertPayload,
  adminKey?: string,
): Promise<AdminFoodItem> {
  return requestJson<AdminFoodItem>(`/api/v1/admin/foods/${encodeURIComponent(foodId)}`, {
    method: "PUT",
    headers: buildAdminHeaders(adminKey),
    body: JSON.stringify(payload),
  });
}

export async function deleteAdminFood(
  foodId: string,
  adminKey?: string,
): Promise<{ deleted: boolean; food_id: string }> {
  return requestJson<{ deleted: boolean; food_id: string }>(
    `/api/v1/admin/foods/${encodeURIComponent(foodId)}`,
    {
      method: "DELETE",
      headers: buildAdminHeaders(adminKey),
    },
  );
}

export async function deleteUserAccountData(userId: string): Promise<UserDeletionSummary> {
  return requestJson<UserDeletionSummary>(
    `/api/v1/profiles/${encodeURIComponent(userId)}/data`,
    { method: "DELETE" },
  );
}
