import type { GroceryItem, ValidatedMealPlan } from "@/lib/api";

export interface GroceryCategoryGroup {
  category: string;
  label: string;
  items: GroceryItem[];
}

export interface GroceryMeta {
  urdu_name: string;
  category: string;
}

const GROCERY_CATEGORY_LABELS: Record<string, string> = {
  breakfast: "Breakfast & Cereals",
  bread: "Roti, Bread & Grains",
  rice: "Rice & Pulao",
  daal: "Daal & Lentils",
  chicken: "Chicken & Poultry",
  meat: "Meat (Beef & Mutton)",
  fish: "Fish & Seafood",
  eggs_dairy: "Eggs, Milk & Dahi",
  sabzi: "Vegetables & Sabzi",
  fruit: "Fresh Fruits",
  snacks: "Healthy Snacks & Nuts",
  salad_condiment: "Salads, Raita & Chutneys",
  beverages: "Chai & Drinks",
  fats_oils: "Fats & Oils",
  sweets: "Occasional Sweets",
};

export function getDayLabel(dayIndex: number): string {
  return `Day ${dayIndex + 1}`;
}

export function formatGroceryCategoryLabel(category: string): string {
  const key = category.trim().toLowerCase();
  if (key in GROCERY_CATEGORY_LABELS) {
    return GROCERY_CATEGORY_LABELS[key];
  }
  return key
    ? key.replace(/_/g, " ").replace(/\b\w/g, (ch) => ch.toUpperCase())
    : "Other Items";
}

export function groupGroceryByCategory(items: GroceryItem[]): GroceryCategoryGroup[] {
  const byCategory = new Map<string, GroceryItem[]>();
  for (const item of items) {
    const key = item.category || "other";
    const list = byCategory.get(key) ?? [];
    list.push(item);
    byCategory.set(key, list);
  }

  return Array.from(byCategory.entries())
    .map(([category, groupItems]) => ({
      category,
      label: formatGroceryCategoryLabel(category),
      items: [...groupItems].sort((a, b) => a.name.localeCompare(b.name)),
    }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

export function extractGroceryMetadata(items: GroceryItem[]): Record<string, GroceryMeta> {
  const map: Record<string, GroceryMeta> = {};
  for (const item of items) {
    map[item.food_id] = {
      urdu_name: item.urdu_name ?? "",
      category: item.category || "other",
    };
  }
  return map;
}

export function rebuildWeeklyGroceryList(
  days: ValidatedMealPlan[],
  metadata: Record<string, GroceryMeta>,
): GroceryItem[] {
  const totals = new Map<
    string,
    { name: string; total_servings: number; total_grams: number }
  >();

  for (const day of days) {
    for (const meal of day.meals) {
      for (const item of meal.items) {
        const existing = totals.get(item.food_id);
        if (existing) {
          existing.total_servings += item.servings;
          existing.total_grams += item.grams;
        } else {
          totals.set(item.food_id, {
            name: item.name,
            total_servings: item.servings,
            total_grams: item.grams,
          });
        }
      }
    }
  }

  const list: GroceryItem[] = [];
  for (const [food_id, agg] of totals.entries()) {
    const meta = metadata[food_id];
    list.push({
      food_id,
      name: agg.name,
      urdu_name: meta?.urdu_name ?? "",
      category: meta?.category ?? "other",
      total_servings: Math.round(agg.total_servings * 100) / 100,
      total_grams: Math.round(agg.total_grams * 10) / 10,
    });
  }

  list.sort((a, b) => {
    const catCmp = a.category.localeCompare(b.category);
    return catCmp !== 0 ? catCmp : a.name.localeCompare(b.name);
  });
  return list;
}

export function computeGroceryProgress(
  items: GroceryItem[],
  checkedMap: Record<string, boolean>,
): { checked: number; total: number; percent: number } {
  const total = items.length;
  if (total === 0) {
    return { checked: 0, total: 0, percent: 0 };
  }
  const checked = items.filter((item) => Boolean(checkedMap[item.food_id])).length;
  return {
    checked,
    total,
    percent: Math.round((checked / total) * 100),
  };
}

function groceryStorageKey(userId: string): string {
  return `fitsoul_grocery_checked_v1_${userId}`;
}

export function loadCheckedGroceries(userId: string): Record<string, boolean> {
  if (typeof window === "undefined" || !userId) {
    return {};
  }
  try {
    const raw = window.localStorage.getItem(groceryStorageKey(userId));
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as unknown;
    if (typeof parsed !== "object" || parsed === null) {
      return {};
    }
    const out: Record<string, boolean> = {};
    for (const [k, v] of Object.entries(parsed)) {
      if (typeof v === "boolean") {
        out[k] = v;
      }
    }
    return out;
  } catch {
    return {};
  }
}

export function saveCheckedGroceries(
  userId: string,
  checked: Record<string, boolean>,
): void {
  if (typeof window === "undefined" || !userId) {
    return;
  }
  try {
    window.localStorage.setItem(groceryStorageKey(userId), JSON.stringify(checked));
  } catch {
    // Ignore storage quota / private browsing errors cleanly.
  }
}
