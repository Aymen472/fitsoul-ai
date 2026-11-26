import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  checkHealth,
  createOrUpsertProfile,
  generateWeeklyMealPlan,
  getChatHistory,
  getDashboard,
  getProfile,
  getUserMemories,
  getUserPatterns,
  logMood,
  logQuickMeal,
  logWater,
  logWeight,
  searchFoods,
  sendChatMessage,
  swapMealPlanSlot,
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
});
