"use client";

import Link from "next/link";
import {
  ArrowRight,
  Dumbbell,
  MessageCircleHeart,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Utensils,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { CalorieRingCard } from "@/components/dashboard/CalorieRingCard";
import { HydrationMoodCard } from "@/components/dashboard/HydrationMoodCard";
import { MealLoggerHistoryCard } from "@/components/dashboard/MealLoggerHistoryCard";
import { WeightTrendCard } from "@/components/dashboard/WeightTrendCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ApiError,
  checkHealth,
  getDashboard,
  logMood,
  logQuickMeal,
  logWater,
  logWeight,
  type DashboardSummary,
  type QuickMealLogRequest,
} from "@/lib/api";
import { formatPatternLabel } from "@/lib/chat-helpers";

export default function HomePage() {
  const { user, profileRecord, isLoading, isProfileLoading } = useAuth();
  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">(
    "checking",
  );
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [loadingDash, setLoadingDash] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    checkHealth()
      .then((res) => {
        if (active) {
          setBackendStatus(res.status === "ok" ? "online" : "offline");
        }
      })
      .catch(() => {
        if (active) {
          setBackendStatus("offline");
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const refreshDashboard = useCallback(async (userId: string) => {
    setLoadingDash(true);
    try {
      const data = await getDashboard(userId);
      setDashboard(data);
      setActionError(null);
    } catch (err) {
      if (err instanceof ApiError) {
        setActionError(err.detail);
      } else {
        setActionError("Dashboard data load nahi ho saka — FastAPI backend check karein.");
      }
    } finally {
      setLoadingDash(false);
    }
  }, []);

  useEffect(() => {
    if (!user || !profileRecord) {
      setDashboard(null);
      return;
    }
    void refreshDashboard(user.id);
  }, [user, profileRecord, refreshDashboard]);

  const handleLogWater = async (amountMl: number) => {
    if (!user) {
      return;
    }
    try {
      await logWater(user.id, amountMl);
      await refreshDashboard(user.id);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : "Water log save nahi ho saka.");
    }
  };

  const handleLogWeight = async (weightKg: number) => {
    if (!user) {
      return;
    }
    try {
      await logWeight(user.id, weightKg);
      await refreshDashboard(user.id);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : "Weight log save nahi ho saka.");
    }
  };

  const handleLogMood = async (mood: string, note?: string) => {
    if (!user) {
      return;
    }
    try {
      await logMood(user.id, mood, note);
      await refreshDashboard(user.id);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : "Mood log save nahi ho saka.");
    }
  };

  const handleLogMeal = async (payload: QuickMealLogRequest) => {
    if (!user) {
      return;
    }
    try {
      await logQuickMeal(user.id, payload);
      await refreshDashboard(user.id);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : "Meal log save nahi ho saka.");
    }
  };

  const targets = dashboard?.targets ?? profileRecord?.targets;
  const profile = profileRecord?.profile;

  return (
    <div className="space-y-6">
      {/* Top Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            {user ? `Assalam o alaikum, ${user.fullName}!` : "FitSoul AI Wellness Hub"}
          </h1>
          <p className="text-sm text-slate-600">
            {profileRecord
              ? "Aaj ka live nutrition progress, hydration, weight trend aur coaching hub."
              : "Science-backed desi nutrition, clinical safety guardrails, aur 24/7 support."}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge
            variant={
              backendStatus === "online"
                ? "teal"
                : backendStatus === "offline"
                  ? "amber"
                  : "default"
            }
          >
            <span
              className={
                backendStatus === "online"
                  ? "h-2 w-2 rounded-full bg-emerald-500"
                  : backendStatus === "offline"
                    ? "h-2 w-2 rounded-full bg-amber-500"
                    : "h-2 w-2 rounded-full bg-slate-400"
              }
            />
            {backendStatus === "online"
              ? "FastAPI Connected"
              : backendStatus === "offline"
                ? "Backend Offline (:8000)"
                : "Checking Backend..."}
          </Badge>

          {user && profileRecord && (
            <Link href="/chat">
              <Button size="sm">
                <MessageCircleHeart className="h-4 w-4" />
                Open AI Coach
              </Button>
            </Link>
          )}
        </div>
      </div>

      {/* State 1: Not Signed In */}
      {!isLoading && !user && (
        <Card className="border-[#0f766e]/20 bg-gradient-to-br from-white via-white to-[#f0f7f4]">
          <CardHeader>
            <Badge variant="teal" className="w-fit">
              <Sparkles className="h-3.5 w-3.5" />
              Built for Pakistani Lifestyles
            </Badge>
            <CardTitle className="mt-2 text-xl">
              Ghar ke khane (roti, daal, sabzi) ke sath apna healthy goal achieve karein
            </CardTitle>
            <CardDescription>
              Sign in karein aur apni health profile set karein taake hamara clinical nutrition
              engine aap ke liye exact calories, macros, aur PCOS/Diabetes-safe plan calculate kare.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            <Link href="/login">
              <Button size="lg">
                Get Started / Sign In
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {/* State 2: Signed In without Profile */}
      {!isLoading && !isProfileLoading && user && !profileRecord && (
        <Card className="border-amber-200 bg-amber-50/40">
          <CardHeader>
            <CardTitle>Complete your Health Onboarding (1 min)</CardTitle>
            <CardDescription>
              Aap ke calories aur condition rules abhi calculate nahi hue. Apni measurements aur
              medical preferences enter karein.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/onboarding">
              <Button size="lg">
                Set Up My Health Profile
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {actionError && (
        <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {actionError}
        </p>
      )}

      {/* State 3: Interactive Live Dashboard */}
      {user && profile && targets && (
        <>
          {loadingDash && !dashboard ? (
            <Card>
              <CardContent className="py-10 text-center text-sm text-slate-500">
                Loading your daily dashboard...
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="grid gap-6 lg:grid-cols-2">
                <CalorieRingCard
                  consumedKcal={dashboard?.consumed_kcal ?? 0}
                  remainingKcal={dashboard?.remaining_kcal ?? targets.calories}
                  targetKcal={targets.calories}
                  bmr={targets.bmr}
                  tdee={targets.tdee}
                  consumedProteinG={dashboard?.consumed_protein_g ?? 0}
                  targetProteinG={targets.protein_g}
                  consumedCarbsG={dashboard?.consumed_carbs_g ?? 0}
                  targetCarbsG={targets.carbs_g}
                  consumedFatG={dashboard?.consumed_fat_g ?? 0}
                  targetFatG={targets.fat_g}
                  streakDays={dashboard?.streak_days ?? 0}
                />

                <HydrationMoodCard
                  waterMl={dashboard?.water_ml ?? 0}
                  waterTargetMl={dashboard?.water_target_ml ?? targets.water_ml}
                  recentMoods={dashboard?.recent_moods ?? []}
                  onLogWater={handleLogWater}
                  onLogMood={handleLogMood}
                />
              </div>

              <div className="grid gap-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,0.9fr)]">
                <MealLoggerHistoryCard
                  todayMeals={dashboard?.today_meals ?? []}
                  recentMeals={dashboard?.recent_meals ?? []}
                  onLogMeal={handleLogMeal}
                />

                <WeightTrendCard
                  latestWeightKg={dashboard?.latest_weight_kg ?? profile.weight_kg}
                  targetWeightKg={dashboard?.target_weight_kg ?? profile.target_weight_kg ?? null}
                  bmi={profile.bmi}
                  weightHistory={dashboard?.weight_history ?? []}
                  onLogWeight={handleLogWeight}
                />
              </div>
            </>
          )}

          {/* Medical Rules & Active Behavioral Patterns */}
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="h-4 w-4 text-[#0f766e]" />
                    <CardTitle className="text-base">Active Clinical Rules</CardTitle>
                  </div>
                  <Link href="/onboarding">
                    <Button variant="outline" size="sm">
                      Edit Profile
                    </Button>
                  </Link>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  {targets.applied_rules.map((rule) => (
                    <Badge key={rule} variant="teal">
                      {rule}
                    </Badge>
                  ))}
                  {targets.max_carbs_per_meal_g !== null && (
                    <Badge variant="amber">
                      Max {targets.max_carbs_per_meal_g}g carbs/meal
                    </Badge>
                  )}
                  <Badge variant={profile.supplements_allowed ? "outline" : "rose"}>
                    {profile.supplements_allowed
                      ? "OTC Supplements Allowed"
                      : "Supplements Locked (Safe Mode)"}
                  </Badge>
                </div>

                {targets.warnings.length > 0 && (
                  <div className="space-y-1 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                    {targets.warnings.map((warning) => (
                      <p key={warning}>• {warning}</p>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-[#0f766e]" />
                    <CardTitle className="text-base">Coach Pattern Watch</CardTitle>
                  </div>
                  <Link href="/chat">
                    <Button variant="ghost" size="sm">
                      View Details
                    </Button>
                  </Link>
                </div>
                <CardDescription className="text-xs">
                  {dashboard?.patterns.summary ??
                    "Consistent logging se emotional triggers aur wins detect hote hain."}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {dashboard && dashboard.patterns.nudges.length > 0 ? (
                  dashboard.patterns.nudges.slice(0, 2).map((nudge) => (
                    <div
                      key={nudge.pattern_type}
                      className="rounded-xl border border-[#0f766e]/15 bg-[#f0f7f4]/70 p-3 text-xs text-[#115e59]"
                    >
                      <p className="font-semibold">
                        {formatPatternLabel(nudge.pattern_type)} ({nudge.suggested_timing})
                      </p>
                      <p className="mt-0.5 leading-relaxed">{nudge.message}</p>
                    </div>
                  ))
                ) : (
                  <p className="rounded-xl bg-slate-50 p-3 text-xs text-slate-600">
                    Abhi koi negative trigger pattern active nahi — shabash!
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}

      {/* Quick Feature Links */}
      <div className="grid gap-4 md:grid-cols-3">
        <Link href="/chat" className="group block">
          <Card className="h-full transition-colors group-hover:border-[#0f766e]/50">
            <CardHeader>
              <MessageCircleHeart className="h-6 w-6 text-[#0f766e]" />
              <CardTitle className="mt-2 text-base">AI Coach Chat</CardTitle>
              <CardDescription>
                Roman Urdu + English coaching, craving swaps, aur persistent history.
              </CardDescription>
            </CardHeader>
          </Card>
        </Link>

        <Link href="/plan" className="group block">
          <Card className="h-full transition-colors group-hover:border-[#0f766e]/50">
            <CardHeader>
              <Utensils className="h-6 w-6 text-[#d97706]" />
              <CardTitle className="mt-2 text-base">Pakistani Meal Plan</CardTitle>
              <CardDescription>
                Desi balanced plans strictly verified against your calorie & macro limits.
              </CardDescription>
            </CardHeader>
          </Card>
        </Link>

        <Link href="/workouts" className="group block">
          <Card className="h-full transition-colors group-hover:border-[#0f766e]/50">
            <CardHeader>
              <Dumbbell className="h-6 w-6 text-[#0f766e]" />
              <CardTitle className="mt-2 text-base">Workouts & Face Yoga</CardTitle>
              <CardDescription>
                Joint-friendly home routines aur guided timer player.
              </CardDescription>
            </CardHeader>
          </Card>
        </Link>
      </div>
    </div>
  );
}
