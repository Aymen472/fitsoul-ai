import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  checkHealth,
  createOrUpsertProfile,
  getProfile,
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
});
