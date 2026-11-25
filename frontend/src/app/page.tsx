"use client";

import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Droplets,
  Dumbbell,
  Flame,
  MessageCircleHeart,
  ShieldCheck,
  Sparkles,
  Utensils,
} from "lucide-react";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { checkHealth } from "@/lib/api";

export default function HomePage() {
  const { user, profileRecord, isLoading, isProfileLoading } = useAuth();
  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">(
    "checking",
  );

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

  const targets = profileRecord?.targets;
  const profile = profileRecord?.profile;

  return (
    <div className="space-y-6">
      {/* Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            {user ? `Assalam o alaikum, ${user.fullName}!` : "FitSoul AI Wellness Hub"}
          </h1>
          <p className="text-sm text-slate-600">
            {profileRecord
              ? "Aap ke deterministic daily nutrition targets aur coaching hub."
              : "Science-backed desi nutrition, clinical safety guardrails, aur 24/7 support."}
          </p>
        </div>

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
            ? "FastAPI Backend Connected"
            : backendStatus === "offline"
              ? "Backend Offline (start uvicorn :8000)"
              : "Checking Backend..."}
        </Badge>
      </div>

      {/* State 1: Not Signed In */}
      {!isLoading && !user && (
        <Card className="border-[#0f766e]/20 bg-gradient-to-br from-white via-white to-[#f0f7f4]">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Badge variant="teal">
                <Sparkles className="h-3.5 w-3.5" />
                Built for Pakistani Lifestyles
              </Badge>
            </div>
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

      {/* State 3: Signed In WITH Deterministic Targets */}
      {targets && profile && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center gap-1.5 text-slate-600">
                  <Flame className="h-4 w-4 text-[#d97706]" />
                  Daily Calorie Target
                </CardDescription>
                <CardTitle className="text-3xl font-bold text-[#0f766e]">
                  {targets.calories} <span className="text-base font-medium">kcal</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-slate-500">
                BMR {targets.bmr} • TDEE {targets.tdee} kcal
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center gap-1.5 text-slate-600">
                  <Activity className="h-4 w-4 text-[#0f766e]" />
                  Daily Macro Split
                </CardDescription>
                <CardTitle className="text-2xl font-bold text-slate-900">
                  {targets.protein_g}g P • {targets.carbs_g}g C
                </CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-slate-500">
                Healthy Fat {targets.fat_g}g • Fiber {targets.fiber_g}g+
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center gap-1.5 text-slate-600">
                  <Droplets className="h-4 w-4 text-sky-600" />
                  Hydration & Sodium Cap
                </CardDescription>
                <CardTitle className="text-2xl font-bold text-slate-900">
                  {(targets.water_ml / 1000).toFixed(1)} L{" "}
                  <span className="text-sm font-normal text-slate-500">
                    ({targets.water_ml} ml)
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-slate-500">
                Max Sodium {targets.sodium_mg_max} mg/day
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardDescription className="flex items-center gap-1.5 text-slate-600">
                  <ShieldCheck className="h-4 w-4 text-[#0f766e]" />
                  Clinical Profile
                </CardDescription>
                <CardTitle className="text-2xl font-bold text-slate-900">
                  BMI {profile.bmi}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-1.5 text-xs">
                <Badge variant="teal">{profile.goal.toUpperCase()}</Badge>
                <Badge variant="outline">{profile.diet_type}</Badge>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle>Active Medical Rules & Safety Guardrails</CardTitle>
                <Link href="/onboarding">
                  <Button variant="outline" size="sm">
                    Edit Profile
                  </Button>
                </Link>
              </div>
              <CardDescription>
                Deterministic rules enforced across AI coaching and meal planning.
              </CardDescription>
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
                    ? "OTC Supplement Info Allowed (with doctor note)"
                    : "Supplements Locked (High-Risk / Medicated Safe Mode)"}
                </Badge>
              </div>

              {targets.warnings.length > 0 && (
                <div className="space-y-1.5 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                  {targets.warnings.map((warning) => (
                    <p key={warning}>• {warning}</p>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
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
