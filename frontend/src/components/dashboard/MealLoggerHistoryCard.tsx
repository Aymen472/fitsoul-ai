"use client";

import { Minus, Plus, Search, Trash2, Utensils } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import {
  searchFoods,
  type FoodSearchItem,
  type MealLogRecord,
  type QuickMealLogRequest,
} from "@/lib/api";
import { formatMessageTime } from "@/lib/chat-helpers";
import { formatMealTypeLabel, formatShortDate } from "@/lib/dashboard-helpers";

interface MealLoggerHistoryCardProps {
  todayMeals: MealLogRecord[];
  recentMeals: MealLogRecord[];
  onLogMeal: (payload: QuickMealLogRequest) => Promise<void>;
}

interface PlateSelection {
  food: FoodSearchItem;
  servings: number;
}

function summarizeLoggedItems(items: Record<string, unknown>[]): string {
  const labels = items
    .map((item) => {
      const name =
        typeof item.matched_name === "string"
          ? item.matched_name
          : typeof item.detected_name === "string"
            ? item.detected_name
            : "";
      const servings = typeof item.servings === "number" ? item.servings : null;
      if (!name) {
        return "";
      }
      return servings !== null ? `${servings}x ${name}` : name;
    })
    .filter(Boolean);

  return labels.join(", ") || "Logged meal";
}

export function MealLoggerHistoryCard({
  todayMeals,
  recentMeals,
  onLogMeal,
}: MealLoggerHistoryCardProps) {
  const [mealType, setMealType] = useState<QuickMealLogRequest["meal_type"]>("lunch");
  const [query, setQuery] = useState("");
  const [catalog, setCatalog] = useState<FoodSearchItem[]>([]);
  const [loadingFoods, setLoadingFoods] = useState(false);
  const [plate, setPlate] = useState<PlateSelection[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [feedTab, setFeedTab] = useState<"today" | "recent">("today");

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      setLoadingFoods(true);
      searchFoods(query, 8)
        .then((items) => {
          if (active) {
            setCatalog(items);
          }
        })
        .catch(() => undefined)
        .finally(() => {
          if (active) {
            setLoadingFoods(false);
          }
        });
    }, 200);

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query]);

  const addFoodToPlate = (food: FoodSearchItem) => {
    setPlate((prev) => {
      const existing = prev.find((entry) => entry.food.id === food.id);
      if (existing) {
        return prev.map((entry) =>
          entry.food.id === food.id
            ? { ...entry, servings: Math.min(20, entry.servings + 0.5) }
            : entry,
        );
      }
      return [...prev, { food, servings: 1 }];
    });
  };

  const adjustServings = (foodId: string, delta: number) => {
    setPlate((prev) =>
      prev
        .map((entry) =>
          entry.food.id === foodId
            ? { ...entry, servings: Math.round((entry.servings + delta) * 10) / 10 }
            : entry,
        )
        .filter((entry) => entry.servings > 0),
    );
  };

  const previewKcal = Math.round(
    plate.reduce((acc, entry) => acc + entry.food.kcal * entry.servings, 0),
  );
  const previewProtein =
    Math.round(plate.reduce((acc, entry) => acc + entry.food.protein * entry.servings, 0) * 10) /
    10;

  const handleSubmitPlate = async () => {
    if (plate.length === 0) {
      return;
    }
    setSubmitting(true);
    try {
      await onLogMeal({
        meal_type: mealType,
        items: plate.map((entry) => ({
          food_id: entry.food.id,
          servings: entry.servings,
        })),
      });
      setPlate([]);
      setFeedTab("today");
    } finally {
      setSubmitting(false);
    }
  };

  const displayedMeals = feedTab === "today" ? todayMeals : recentMeals;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Utensils className="h-4 w-4 text-[#d97706]" />
          <CardTitle>Quick Pakistani Meal Logger & History</CardTitle>
        </div>
        <CardDescription>
          Verified Food DB se exact calories aur macros log karein.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-5">
        {/* Search & Slot Controls */}
        <div className="grid gap-2.5 sm:grid-cols-[150px_minmax(0,1fr)]">
          <Select
            aria-label="Meal slot"
            value={mealType}
            onChange={(e) => setMealType(e.target.value as QuickMealLogRequest["meal_type"])}
            className="mt-0"
          >
            <option value="breakfast">Breakfast</option>
            <option value="lunch">Lunch</option>
            <option value="snack">Snack</option>
            <option value="dinner">Dinner</option>
          </Select>

          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <Input
              type="text"
              placeholder="Search desi foods (e.g. roti, daal moong, biryani, chai)..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="mt-0 pl-9"
            />
          </div>
        </div>

        {/* Food Search Results */}
        <div className="grid max-h-48 gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
          {loadingFoods && catalog.length === 0 ? (
            <p className="text-xs text-slate-500">Searching Pakistani Food DB...</p>
          ) : catalog.length === 0 ? (
            <p className="text-xs text-slate-500">Koi dish match nahi hui — aur simple likhein.</p>
          ) : (
            catalog.map((food) => (
              <button
                key={food.id}
                type="button"
                onClick={() => addFoodToPlate(food)}
                className="flex items-center justify-between gap-2 rounded-xl border border-slate-200/90 bg-white px-3 py-2 text-left transition-colors hover:border-[#0f766e]/50 hover:bg-[#f0f7f4]/50 cursor-pointer"
              >
                <div className="min-w-0">
                  <p className="truncate text-xs font-semibold text-slate-900">{food.name}</p>
                  <p className="truncate text-[11px] text-slate-500">
                    {food.serving_desc} • {Math.round(food.kcal)} kcal
                  </p>
                </div>
                <Plus className="h-4 w-4 shrink-0 text-[#0f766e]" />
              </button>
            ))
          )}
        </div>

        {/* Selected Plate Tray */}
        {plate.length > 0 && (
          <div className="space-y-3 rounded-xl border border-[#0f766e]/25 bg-[#f0f7f4]/70 p-3.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-semibold text-[#115e59]">
                Selected for {formatMealTypeLabel(mealType)}:
              </p>
              <Badge variant="teal">
                {previewKcal} kcal • {previewProtein}g protein
              </Badge>
            </div>

            <div className="space-y-2">
              {plate.map(({ food, servings }) => (
                <div
                  key={food.id}
                  className="flex items-center justify-between gap-2 rounded-lg bg-white px-3 py-2 text-xs"
                >
                  <span className="min-w-0 flex-1 truncate font-medium text-slate-800">
                    {food.name} ({Math.round(food.kcal * servings)} kcal)
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => adjustServings(food.id, -0.5)}
                      aria-label={`Decrease ${food.name}`}
                      className="rounded border border-slate-200 p-1 hover:bg-slate-50 cursor-pointer"
                    >
                      <Minus className="h-3 w-3" />
                    </button>
                    <span className="w-8 text-center font-semibold">{servings}x</span>
                    <button
                      type="button"
                      onClick={() => adjustServings(food.id, 0.5)}
                      aria-label={`Increase ${food.name}`}
                      className="rounded border border-slate-200 p-1 hover:bg-slate-50 cursor-pointer"
                    >
                      <Plus className="h-3 w-3" />
                    </button>
                    <button
                      type="button"
                      onClick={() => adjustServings(food.id, -servings)}
                      aria-label={`Remove ${food.name}`}
                      className="ml-1 rounded p-1 text-slate-400 hover:text-rose-600 cursor-pointer"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <Button
              size="md"
              className="w-full"
              disabled={submitting}
              onClick={() => void handleSubmitPlate()}
            >
              {submitting ? "Logging Meal..." : `Log ${formatMealTypeLabel(mealType)}`}
            </Button>
          </div>
        )}

        {/* Meal History Feed */}
        <div className="space-y-3 border-t border-slate-100 pt-4">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-semibold text-slate-900">Meal History</p>
            <div className="flex gap-1.5">
              <Button
                variant={feedTab === "today" ? "secondary" : "ghost"}
                size="sm"
                onClick={() => setFeedTab("today")}
              >
                Today ({todayMeals.length})
              </Button>
              <Button
                variant={feedTab === "recent" ? "secondary" : "ghost"}
                size="sm"
                onClick={() => setFeedTab("recent")}
              >
                Recent ({recentMeals.length})
              </Button>
            </div>
          </div>

          {displayedMeals.length === 0 ? (
            <p className="rounded-xl bg-slate-50 p-3 text-xs text-slate-600">
              {feedTab === "today"
                ? "Aaj abhi koi meal log nahi hua. Upar se desi items select kar ke log karein!"
                : "Abhi koi recent meal history available nahi hai."}
            </p>
          ) : (
            <ul className="max-h-56 space-y-2 overflow-y-auto pr-1">
              {displayedMeals.map((meal) => (
                <li
                  key={meal.id}
                  className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-3 text-xs"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Badge variant="outline">{formatMealTypeLabel(meal.meal_type)}</Badge>
                    <span className="font-semibold text-[#0f766e]">
                      {Math.round(meal.total_kcal)} kcal • P {Math.round(meal.protein_g)}g • C{" "}
                      {Math.round(meal.carbs_g)}g
                    </span>
                  </div>
                  <p className="mt-1.5 font-medium text-slate-800">
                    {summarizeLoggedItems(meal.items)}
                  </p>
                  <p className="mt-0.5 text-[11px] text-slate-400">
                    {formatShortDate(meal.logged_at)} {formatMessageTime(meal.logged_at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
