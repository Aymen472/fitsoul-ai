"use client";

import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  RefreshCw,
  ShieldCheck,
  ShoppingBasket,
  Utensils,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { GroceryListPanel } from "@/components/meal-plan/GroceryListPanel";
import { MealSlotCard } from "@/components/meal-plan/MealSlotCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ApiError,
  generateWeeklyMealPlan,
  logQuickMeal,
  swapMealPlanSlot,
  type ValidatedMeal,
  type WeeklyMealPlan,
} from "@/lib/api";
import { formatMealTypeLabel } from "@/lib/dashboard-helpers";
import {
  extractGroceryMetadata,
  getDayLabel,
  loadCheckedGroceries,
  rebuildWeeklyGroceryList,
  saveCheckedGroceries,
  type GroceryMeta,
} from "@/lib/meal-plan-helpers";
import { cn } from "@/lib/utils";

export default function PlanPage() {
  const { user, profileRecord, isLoading, isProfileLoading } = useAuth();

  const [weeklyPlan, setWeeklyPlan] = useState<WeeklyMealPlan | null>(null);
  const [groceryMeta, setGroceryMeta] = useState<Record<string, GroceryMeta>>({});
  const [checkedGroceries, setCheckedGroceries] = useState<Record<string, boolean>>({});
  const [selectedDayIndex, setSelectedDayIndex] = useState(0);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [swappingSlot, setSwappingSlot] = useState<string | null>(null);
  const [loggingSlot, setLoggingSlot] = useState<string | null>(null);
  const [loggedSlots, setLoggedSlots] = useState<Record<string, boolean>>({});
  const [swapAttempts, setSwapAttempts] = useState<Record<string, number>>({});
  const [mobileTab, setMobileTab] = useState<"meals" | "grocery">("meals");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadWeeklyPlan = useCallback(async (userId: string) => {
    setLoadingPlan(true);
    setError(null);
    try {
      const plan = await generateWeeklyMealPlan(userId, 7);
      setWeeklyPlan(plan);
      setGroceryMeta(extractGroceryMetadata(plan.grocery_list));
      setSelectedDayIndex(0);
      setSwapAttempts({});
      setLoggedSlots({});
      setNotice(null);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Meal plan load nahi ho saka — check karein ke FastAPI backend chal raha hai.");
      }
    } finally {
      setLoadingPlan(false);
    }
  }, []);

  useEffect(() => {
    if (!user || !profileRecord) {
      return;
    }
    setCheckedGroceries(loadCheckedGroceries(user.id));
    void loadWeeklyPlan(user.id);
  }, [user, profileRecord, loadWeeklyPlan]);

  const handleToggleGrocery = (foodId: string) => {
    if (!user) {
      return;
    }
    setCheckedGroceries((prev) => {
      const next = { ...prev, [foodId]: !prev[foodId] };
      saveCheckedGroceries(user.id, next);
      return next;
    });
  };

  const handleClearCheckedGroceries = () => {
    if (!user) {
      return;
    }
    setCheckedGroceries({});
    saveCheckedGroceries(user.id, {});
  };

  const handleSwapMeal = async (meal: ValidatedMeal) => {
    if (!user || !weeklyPlan) {
      return;
    }
    const slotKey = `${selectedDayIndex}-${meal.meal_type}`;
    const nextAttempt = (swapAttempts[slotKey] ?? 0) + 1;

    setSwappingSlot(slotKey);
    setError(null);
    setNotice(null);

    try {
      const res = await swapMealPlanSlot(user.id, {
        day_index: selectedDayIndex,
        meal_type: meal.meal_type,
        exclude_food_ids: meal.items.map((item) => item.food_id),
        attempt: nextAttempt,
      });

      const mergedMeta = {
        ...groceryMeta,
        ...extractGroceryMetadata(res.day_grocery_items),
      };
      const updatedDays = weeklyPlan.days.map((day, idx) =>
        idx === selectedDayIndex ? res.updated_day : day,
      );
      const rebuiltGrocery = rebuildWeeklyGroceryList(updatedDays, mergedMeta);

      setGroceryMeta(mergedMeta);
      setWeeklyPlan({ days: updatedDays, grocery_list: rebuiltGrocery });
      setSwapAttempts((prev) => ({ ...prev, [slotKey]: nextAttempt }));
      setLoggedSlots((prev) => ({ ...prev, [slotKey]: false }));
      setNotice(
        `${getDayLabel(selectedDayIndex)} ${formatMealTypeLabel(meal.meal_type)} swapped — saare macros aur medical rules abhi bhi verified hain!`,
      );
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : "Meal swap fail ho gaya — dobara koshish karein.",
      );
    } finally {
      setSwappingSlot(null);
    }
  };

  const handleLogPlannedMeal = async (meal: ValidatedMeal) => {
    if (!user) {
      return;
    }
    const slotKey = `${selectedDayIndex}-${meal.meal_type}`;
    setLoggingSlot(slotKey);
    setError(null);
    try {
      await logQuickMeal(user.id, {
        meal_type: meal.meal_type,
        items: meal.items.map((item) => ({
          food_id: item.food_id,
          servings: item.servings,
        })),
        plate_notes: `Logged from ${getDayLabel(selectedDayIndex)} meal plan`,
      });
      setLoggedSlots((prev) => ({ ...prev, [slotKey]: true }));
      setNotice(
        `${formatMealTypeLabel(meal.meal_type)} (${Math.round(meal.kcal)} kcal) aaj ke Dashboard mein log ho gaya!`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Meal log save nahi ho saka.");
    } finally {
      setLoggingSlot(null);
    }
  };

  if (!isLoading && !user) {
    return (
      <Card className="mx-auto max-w-lg">
        <CardHeader>
          <CardTitle>Sign in to view your Pakistani Meal Plan</CardTitle>
          <CardDescription>
            Sign in karein taake aap ka personalized 7-day desi meal plan aur grocery list ban sake.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Link href="/login">
            <Button>
              Go to Sign In
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </CardContent>
      </Card>
    );
  }

  if (!isLoading && !isProfileLoading && user && !profileRecord) {
    return (
      <Card className="mx-auto max-w-lg border-amber-200 bg-amber-50/40">
        <CardHeader>
          <CardTitle>Complete Onboarding to unlock Meal Plans</CardTitle>
          <CardDescription>
            Calories, PCOS/Diabetes limits, aur disliked foods set karne ke baad 7-day verified
            plan generate hota hai.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Link href="/onboarding">
            <Button>
              Set Up My Health Profile
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </CardContent>
      </Card>
    );
  }

  const activeDay = weeklyPlan?.days[selectedDayIndex] ?? null;
  const targets = profileRecord?.targets;

  return (
    <div className="space-y-5">
      {/* Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#d97706] text-white shadow-sm">
            <Utensils className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              7-Day Pakistani Meal Plan
            </h1>
            <p className="text-xs text-slate-600">
              {targets
                ? `Target ${targets.calories} kcal/day • ${targets.protein_g}g+ Protein • Medical & Safety Verified`
                : "Verified against your daily calorie floor and condition rules"}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {user && (
            <Button
              variant="outline"
              size="sm"
              disabled={loadingPlan}
              onClick={() => void loadWeeklyPlan(user.id)}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loadingPlan ? "animate-spin" : ""}`} />
              {loadingPlan ? "Generating..." : "Regenerate Week"}
            </Button>
          )}
        </div>
      </div>

      {/* Mobile Tab Switcher */}
      {weeklyPlan && (
        <div className="flex gap-2 lg:hidden">
          <Button
            variant={mobileTab === "meals" ? "primary" : "outline"}
            size="sm"
            className="flex-1"
            onClick={() => setMobileTab("meals")}
          >
            <Utensils className="h-4 w-4" />
            Meals (7 Days)
          </Button>
          <Button
            variant={mobileTab === "grocery" ? "primary" : "outline"}
            size="sm"
            className="flex-1"
            onClick={() => setMobileTab("grocery")}
          >
            <ShoppingBasket className="h-4 w-4" />
            Grocery List ({weeklyPlan.grocery_list.length})
          </Button>
        </div>
      )}

      {error && (
        <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </p>
      )}

      {notice && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[#0f766e]/25 bg-[#f0f7f4] px-4 py-3 text-xs text-[#115e59]">
          <span className="inline-flex items-center gap-1.5 font-medium">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-[#0f766e]" />
            {notice}
          </span>
          <Link href="/" className="font-semibold underline hover:text-[#0f766e]">
            View on Dashboard
          </Link>
        </div>
      )}

      {loadingPlan && !weeklyPlan ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-slate-500">
            Generating your verified 7-day desi meal plan and grocery list...
          </CardContent>
        </Card>
      ) : weeklyPlan && activeDay ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          {/* Left: 7-Day Tabs + Selected Day Summary + 4 Meals */}
          <div className={cn("space-y-5", mobileTab !== "meals" && "hidden lg:block")}>
            {/* Day Selector Tabs */}
            <div className="flex gap-2 overflow-x-auto pb-1">
              {weeklyPlan.days.map((day, idx) => {
                const active = idx === selectedDayIndex;
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setSelectedDayIndex(idx)}
                    className={cn(
                      "shrink-0 rounded-xl border px-3.5 py-2 text-left transition-colors cursor-pointer",
                      active
                        ? "border-[#0f766e] bg-[#0f766e] text-white shadow-sm"
                        : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
                    )}
                  >
                    <p className="text-xs font-semibold">{getDayLabel(idx)}</p>
                    <p
                      className={cn(
                        "text-[11px]",
                        active ? "text-teal-100" : "text-slate-500",
                      )}
                    >
                      {Math.round(day.total_kcal)} kcal
                    </p>
                  </button>
                );
              })}
            </div>

            {/* Verified Day Summary Strip */}
            <Card className="border-[#0f766e]/20 bg-[#f0f7f4]/50">
              <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-slate-900">
                      {getDayLabel(selectedDayIndex)} Summary
                    </span>
                    <Badge variant="teal">
                      <ShieldCheck className="h-3.5 w-3.5" />
                      Safety & Macro Verified
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-600">
                    {Math.round(activeDay.total_kcal)} kcal • Protein{" "}
                    <strong>{Math.round(activeDay.total_protein_g)}g</strong> • Carbs{" "}
                    <strong>{Math.round(activeDay.total_carbs_g)}g</strong> • Fat{" "}
                    <strong>{Math.round(activeDay.total_fat_g)}g</strong> • Fiber{" "}
                    <strong>{Math.round(activeDay.total_fiber_g)}g</strong> • Sodium{" "}
                    <strong>{Math.round(activeDay.total_sodium_mg)} mg</strong>
                  </p>
                </div>

                {activeDay.notes && (
                  <p className="text-xs text-[#115e59]">{activeDay.notes}</p>
                )}
              </CardContent>
            </Card>

            {/* 4 Meals Grid */}
            <div className="grid gap-4 md:grid-cols-2">
              {activeDay.meals.map((meal) => {
                const slotKey = `${selectedDayIndex}-${meal.meal_type}`;
                return (
                  <MealSlotCard
                    key={slotKey}
                    meal={meal}
                    isSwapping={swappingSlot === slotKey}
                    isLogging={loggingSlot === slotKey}
                    wasLogged={Boolean(loggedSlots[slotKey])}
                    onSwap={(m) => void handleSwapMeal(m)}
                    onLogMeal={(m) => void handleLogPlannedMeal(m)}
                  />
                );
              })}
            </div>
          </div>

          {/* Right: Interactive Grocery List */}
          <aside className={cn(mobileTab === "grocery" ? "block" : "hidden lg:block")}>
            <GroceryListPanel
              items={weeklyPlan.grocery_list}
              checkedMap={checkedGroceries}
              onToggleItem={handleToggleGrocery}
              onClearChecked={handleClearCheckedGroceries}
            />
          </aside>
        </div>
      ) : null}
    </div>
  );
}
