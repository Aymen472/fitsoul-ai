import { describe, expect, it } from "vitest";

import type { GroceryItem, ValidatedMealPlan } from "@/lib/api";
import {
  computeGroceryProgress,
  extractGroceryMetadata,
  formatGroceryCategoryLabel,
  getDayLabel,
  groupGroceryByCategory,
  rebuildWeeklyGroceryList,
} from "@/lib/meal-plan-helpers";

describe("meal plan helpers", () => {
  it("formats day indices and grocery categories cleanly", () => {
    expect(getDayLabel(0)).toBe("Day 1");
    expect(getDayLabel(6)).toBe("Day 7");

    expect(formatGroceryCategoryLabel("daal")).toBe("Daal & Lentils");
    expect(formatGroceryCategoryLabel("eggs_dairy")).toBe("Eggs, Milk & Dahi");
    expect(formatGroceryCategoryLabel("custom_spices")).toBe("Custom Spices");
  });

  it("groups groceries by aisle label and sorts items alphabetically", () => {
    const items: GroceryItem[] = [
      {
        food_id: "roti_whole_wheat",
        name: "Whole Wheat Roti",
        urdu_name: "روٹی",
        category: "bread",
        total_servings: 7,
        total_grams: 315,
      },
      {
        food_id: "daal_moong",
        name: "Daal Moong",
        urdu_name: "دال مونگ",
        category: "daal",
        total_servings: 3,
        total_grams: 450,
      },
      {
        food_id: "boiled_egg",
        name: "Boiled Egg",
        urdu_name: "ابلا انڈا",
        category: "eggs_dairy",
        total_servings: 6,
        total_grams: 300,
      },
    ];

    const groups = groupGroceryByCategory(items);
    expect(groups.map((g) => g.label)).toEqual([
      "Daal & Lentils",
      "Eggs, Milk & Dahi",
      "Roti, Bread & Grains",
    ]);
    expect(groups[0].items[0].food_id).toBe("daal_moong");
  });

  it("extracts metadata, rebuilds weekly grocery totals across swapped days, and tracks progress", () => {
    const initialGrocery: GroceryItem[] = [
      {
        food_id: "boiled_egg",
        name: "Boiled Egg",
        urdu_name: "ابلا انڈا",
        category: "eggs_dairy",
        total_servings: 2,
        total_grams: 100,
      },
      {
        food_id: "daal_moong",
        name: "Daal Moong",
        urdu_name: "دال مونگ",
        category: "daal",
        total_servings: 1.5,
        total_grams: 225,
      },
    ];
    const meta = extractGroceryMetadata(initialGrocery);

    const days: ValidatedMealPlan[] = [
      {
        meals: [
          {
            meal_type: "breakfast",
            items: [
              {
                food_id: "boiled_egg",
                name: "Boiled Egg",
                servings: 2,
                grams: 100,
                kcal: 156,
                protein: 12.6,
                carbs: 1.1,
                fat: 10.6,
                fiber: 0,
                sodium_mg: 124,
              },
            ],
            kcal: 156,
            protein: 12.6,
            carbs: 1.1,
            fat: 10.6,
            fiber: 0,
            sodium_mg: 124,
          },
          {
            meal_type: "lunch",
            items: [
              {
                food_id: "daal_moong",
                name: "Daal Moong",
                servings: 1.5,
                grams: 225,
                kcal: 225,
                protein: 15,
                carbs: 36,
                fat: 1.5,
                fiber: 9,
                sodium_mg: 300,
              },
            ],
            kcal: 225,
            protein: 15,
            carbs: 36,
            fat: 1.5,
            fiber: 9,
            sodium_mg: 300,
          },
        ],
        total_kcal: 381,
        total_protein_g: 27.6,
        total_carbs_g: 37.1,
        total_fat_g: 12.1,
        total_fiber_g: 9,
        total_sodium_mg: 424,
        notes: "",
        used_fallback: true,
        attempts_used: 1,
      },
    ];

    const rebuilt = rebuildWeeklyGroceryList(days, meta);
    expect(rebuilt).toHaveLength(2);
    const daal = rebuilt.find((i) => i.food_id === "daal_moong");
    expect(daal).toMatchObject({
      urdu_name: "دال مونگ",
      category: "daal",
      total_servings: 1.5,
      total_grams: 225,
    });

    expect(computeGroceryProgress(rebuilt, { daal_moong: true })).toEqual({
      checked: 1,
      total: 2,
      percent: 50,
    });
    expect(computeGroceryProgress([], {})).toEqual({
      checked: 0,
      total: 0,
      percent: 0,
    });
  });
});
