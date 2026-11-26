import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  cancelUserSubscription,
  checkHealth,
  confirmSandboxPayment,
  createBillingCheckout,
  createOrUpsertProfile,
  deleteAdminFood,
  deleteUserAccountData,
  generateWeeklyMealPlan,
  getAdminFlaggedMessages,
  getAdminFoods,
  getAdminOverview,
  getAdminUsers,
  getBillingPlans,
  getBillingStatus,
  getChatHistory,
  getDashboard,
  getNotificationLogs,
  getNotificationPreferences,
  getNotificationSchedulePreview,
  getNotificationTemplates,
  getProfile,
  getUserMemories,
  getUserPatterns,
  getWorkoutHistory,
  getWorkoutRoutines,
  logMood,
  logQuickMeal,
  logWater,
  logWeight,
  logWorkout,
  searchFoods,
  sendChatMessage,
  sendUserNotification,
  startFreeTrial,
  swapMealPlanSlot,
  updateNotificationPreferences,
  upsertAdminFood,
  type ProfileUpsertRequest,
} from "@/lib/api";
import { deriveLocalUserId, isSupabaseConfigured } from "@/lib/auth";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("auth helpers", () => {
  it("normalizes emails into deterministic URL-safe local user IDs", () => {
    expect(deriveLocalUserId("  Aymen.Khan+1@Example.COM ")).toBe(
      "local-aymen-khan-1-example-com",
    );
    expect(deriveLocalUserId("")).toBe("local-guest");
  });

  it("reports Supabase unconfigured when env vars are missing", () => {
    expect(isSupabaseConfigured()).toBe(false);
  });
});

describe("typed FastAPI client", () => {
  it("calls GET /health and parses ok JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await checkHealth();

    expect(res).toEqual({ status: "ok" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/health",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("posts profile payload to POST /api/v1/profiles", async () => {
    const payload: ProfileUpsertRequest = {
      user_id: "local-aymen-example-com",
      email: "aymen@example.com",
      full_name: "Aymen",
      profile: {
        age: 28,
        gender: "female",
        height_cm: 165,
        weight_kg: 75,
        activity_level: "sedentary",
        goal: "lose",
        conditions: ["pcos"],
        high_risk_conditions: [],
        is_pregnant: false,
        on_regular_medication: false,
        diet_type: "non_veg",
        allergies: [],
        dislikes: ["karela"],
        timezone: "Asia/Karachi",
      },
    };

    const fakeRecord = {
      ...payload,
      phone: null,
      profile: {
        ...payload.profile,
        bmi: 27.5,
        is_high_risk: false,
        high_risk_reasons: [],
        supplements_allowed: true,
      },
      targets: {
        calories: 1376,
        bmr: 1500,
        tdee: 1800,
        protein_g: 103,
        carbs_g: 103,
        fat_g: 61,
        fiber_g: 25,
        water_ml: 2625,
        sodium_mg_max: 2300,
        max_carbs_per_meal_g: 45,
        forbidden_tags: [],
        required_tags: [],
        applied_rules: ["pcos"],
        warnings: [],
      },
    };

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(fakeRecord), { status: 201 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const saved = await createOrUpsertProfile(payload);

    expect(saved.targets.calories).toBe(1376);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/profiles",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(payload),
      }),
    );
  });

  it("throws ApiError with status and detail on 404 or 422 FastAPI responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Profile not found" }), {
          status: 404,
          statusText: "Not Found",
        }),
      ),
    );

    await expect(getProfile("missing-id")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      detail: "Profile not found",
    });

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: [{ msg: "Value error, PCOS condition is only applicable to female profiles" }],
          }),
          { status: 422, statusText: "Unprocessable Entity" },
        ),
      ),
    );

    await expect(
      createOrUpsertProfile({
        profile: {
          age: 30,
          gender: "male",
          height_cm: 175,
          weight_kg: 80,
          activity_level: "sedentary",
          goal: "lose",
          conditions: ["pcos"],
          high_risk_conditions: [],
          is_pregnant: false,
          on_regular_medication: false,
          diet_type: "non_veg",
          allergies: [],
          dislikes: [],
        },
      }),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("calls chat, history, memories, and patterns endpoints cleanly", async () => {
    const mockChatRes = {
      user_id: "u1",
      reply: "Meal note ho gaya!",
      intent: "meal_log",
      flagged_safety: false,
      safety_category: "safe",
      stop_diet_advice: false,
      grounded_data: { logged_kcal: 435 },
      used_fallback: false,
      saved_memories: [],
      used_memories: [],
      user_message_id: "um-1",
      assistant_message_id: "am-1",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(mockChatRes), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ user_id: "u1", messages: [] }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ user_id: "u1", memories: [] }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ patterns: [], nudges: [], summary: "OK" }), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const chat = await sendChatMessage({ user_id: "u1", message: "2 roti" });
    const history = await getChatHistory("u1", 50);
    const memories = await getUserMemories("u1");
    const patterns = await getUserPatterns("u1", 14);

    expect(chat.reply).toBe("Meal note ho gaya!");
    expect(history.messages).toEqual([]);
    expect(memories.memories).toEqual([]);
    expect(patterns.summary).toBe("OK");
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8000/api/v1/chat",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8000/api/v1/chat/u1/history?limit=50",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://127.0.0.1:8000/api/v1/chat/u1/memories",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://127.0.0.1:8000/api/v1/chat/u1/patterns?days=14",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("calls food search, tracking mutations, and dashboard endpoint", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "meal-1", total_kcal: 435 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "w-1", amount_ml: 250 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "wt-1", weight_kg: 74.2 }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "m-1", mood: "happy" }), { status: 201 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ user_id: "u1", consumed_kcal: 435 }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await searchFoods("daal", 8);
    await logQuickMeal("u1", { meal_type: "lunch", items: [{ food_id: "daal_moong", servings: 1 }] });
    await logWater("u1", 250);
    await logWeight("u1", 74.2);
    await logMood("u1", "happy", "Good energy");
    const dash = await getDashboard("u1");

    expect(dash.consumed_kcal).toBe(435);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8000/api/v1/foods/search?q=daal&limit=8",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8000/api/v1/tracking/u1/meals",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://127.0.0.1:8000/api/v1/tracking/u1/water",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://127.0.0.1:8000/api/v1/tracking/u1/weight",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "http://127.0.0.1:8000/api/v1/tracking/u1/mood",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "http://127.0.0.1:8000/api/v1/tracking/u1/dashboard",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("calls weekly meal plan and meal swap endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ days: [], grocery_list: [] }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ day_index: 0, meal_type: "lunch" }), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const weekly = await generateWeeklyMealPlan("u1", 7);
    const swapped = await swapMealPlanSlot("u1", {
      day_index: 0,
      meal_type: "lunch",
      exclude_food_ids: ["daal_moong"],
      attempt: 1,
    });

    expect(weekly.days).toEqual([]);
    expect(swapped.meal_type).toBe("lunch");
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8000/api/v1/meal-plans/u1/weekly?days=7",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8000/api/v1/meal-plans/u1/swap",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("calls workout routines, workout log, and workout history endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "wk-1", calories_burned: 75 }), { status: 201 }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await getWorkoutRoutines({ workoutType: "face_yoga", avoid: ["neck"] });
    const logged = await logWorkout("u1", {
      routine_id: "pcos_low_impact_cardio",
      duration_minutes: 15,
    });
    const history = await getWorkoutHistory("u1", 30);

    expect(logged.calories_burned).toBe(75);
    expect(history).toEqual([]);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8000/api/v1/workouts/routines?workout_type=face_yoga&avoid=neck",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8000/api/v1/tracking/u1/workouts",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://127.0.0.1:8000/api/v1/tracking/u1/workouts?days=30",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("calls WhatsApp notification templates, preferences, preview, send, and logs endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ user_id: "u1", whatsapp_opt_in: false, whatsapp_phone: null }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            user_id: "u1",
            whatsapp_opt_in: true,
            whatsapp_phone: "923001234567",
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            user_id: "u1",
            timezone: "Asia/Karachi",
            local_time: "2026-11-26 13:00",
            in_quiet_hours: false,
            whatsapp_opt_in: true,
            due_jobs: [],
            upcoming_slots: [],
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            log: { id: "log-1", status: "dry_run" },
            preview_text: "Preview",
            dry_run: true,
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await getNotificationTemplates();
    const prefs = await getNotificationPreferences("u1");
    const updated = await updateNotificationPreferences("u1", {
      whatsapp_opt_in: true,
      whatsapp_phone: "+92 300 1234567",
      meal_reminders: true,
      water_reminders: true,
      workout_reminders: true,
      night_summary: true,
      weekly_report: true,
      quiet_hours_start: "22:30",
      quiet_hours_end: "07:00",
    });
    const schedule = await getNotificationSchedulePreview("u1");
    const sent = await sendUserNotification("u1", {
      template_name: "fitsoul_meal_reminder",
      params: { user_name: "Aymen" },
      dry_run: true,
    });
    const logs = await getNotificationLogs("u1", 30);

    expect(prefs.whatsapp_opt_in).toBe(false);
    expect(updated.whatsapp_phone).toBe("923001234567");
    expect(schedule.timezone).toBe("Asia/Karachi");
    expect(sent.dry_run).toBe(true);
    expect(logs).toEqual([]);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8000/api/v1/notifications/templates",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://127.0.0.1:8000/api/v1/notifications/u1/preferences",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://127.0.0.1:8000/api/v1/notifications/u1/schedule-preview",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "http://127.0.0.1:8000/api/v1/notifications/u1/send",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "http://127.0.0.1:8000/api/v1/notifications/u1/logs?limit=30",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("calls billing plans, subscription status, trial, checkout, cancel, and webhook endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ user_id: "u1", trial_eligible: true }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "sub-1", plan: "trial" }), { status: 201 }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            transaction: { id: "tx-1", provider_order_id: "fs_abc", provider: "jazzcash" },
            checkout_url: "http://localhost:3000/billing?checkout_order=fs_abc",
            sandbox_mode: true,
            instructions: "Pay",
          }),
          { status: 201 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            status: "ok",
            already_processed: false,
            transaction: { status: "paid" },
            subscription: { plan: "pro", status: "active" },
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "sub-1", status: "cancelled" }), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await getBillingPlans();
    const statusRes = await getBillingStatus("u1");
    const trialRes = await startFreeTrial("u1");
    const checkoutRes = await createBillingCheckout("u1", {
      plan_id: "pro",
      provider: "jazzcash",
    });
    const webhookRes = await confirmSandboxPayment("jazzcash", {
      order_id: "fs_abc",
      event: "payment.succeeded",
    });
    const cancelRes = await cancelUserSubscription("u1");

    expect(statusRes.trial_eligible).toBe(true);
    expect(trialRes.plan).toBe("trial");
    expect(checkoutRes.sandbox_mode).toBe(true);
    expect(webhookRes.transaction.status).toBe("paid");
    expect(cancelRes.status).toBe("cancelled");
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8000/api/v1/billing/plans",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8000/api/v1/billing/u1/subscription",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://127.0.0.1:8000/api/v1/billing/u1/trial",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://127.0.0.1:8000/api/v1/billing/u1/checkout",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "http://127.0.0.1:8000/webhooks/payments/jazzcash",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      6,
      "http://127.0.0.1:8000/api/v1/billing/u1/cancel",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("calls admin overview, users, flagged messages, food CRUD, and data deletion endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ total_users: 2 }), { status: 200 }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "custom_daal", name: "Custom Daal" }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ deleted: true, food_id: "custom_daal" }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ user_id: "u1", deleted: true, records_removed: { users: 1 } }),
          { status: 200 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    const ov = await getAdminOverview("ops-key");
    await getAdminUsers("ops-key", 25);
    await getAdminFlaggedMessages("ops-key", 25);
    await getAdminFoods({ query: "daal", limit: 10, adminKey: "ops-key" });
    const food = await upsertAdminFood(
      "custom_daal",
      {
        name: "Custom Daal",
        urdu_name: "",
        aliases: [],
        category: "lentils",
        serving_desc: "1 cup",
        grams: 150,
        kcal: 180,
        protein: 10,
        carbs: 28,
        fat: 2,
        fiber: 6,
        sodium_mg: 200,
        gi_category: "low",
        tags: ["desi"],
      },
      "ops-key",
    );
    const delFood = await deleteAdminFood("custom_daal", "ops-key");
    const delAccount = await deleteUserAccountData("u1");

    expect(ov.total_users).toBe(2);
    expect(food.id).toBe("custom_daal");
    expect(delFood.deleted).toBe(true);
    expect(delAccount.deleted).toBe(true);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://127.0.0.1:8000/api/v1/admin/overview",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ "X-Admin-Key": "ops-key" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://127.0.0.1:8000/api/v1/admin/foods?q=daal&limit=10",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      7,
      "http://127.0.0.1:8000/api/v1/profiles/u1/data",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
