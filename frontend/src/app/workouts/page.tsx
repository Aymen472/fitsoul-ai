"use client";

import Link from "next/link";
import {
  ArrowRight,
  Clock,
  Dumbbell,
  Flame,
  Play,
  ShieldCheck,
  Sparkles,
  Trophy,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { GuidedWorkoutPlayer } from "@/components/workouts/GuidedWorkoutPlayer";
import {
  ApiError,
  getWorkoutHistory,
  getWorkoutRoutines,
  logWorkout,
  type WorkoutLogRecord,
  type WorkoutRoutine,
} from "@/lib/api";
import { formatMessageTime } from "@/lib/chat-helpers";
import { formatShortDate } from "@/lib/dashboard-helpers";
import {
  computeWorkoutTotals,
  estimateWorkoutCalories,
  formatWorkoutCategory,
} from "@/lib/workout-helpers";

const JOINT_FILTER_OPTIONS = [
  { tag: "knee", label: "Knee-Friendly" },
  { tag: "back", label: "Back-Friendly" },
  { tag: "neck", label: "Neck-Friendly" },
];

export default function WorkoutsPage() {
  const { user, profileRecord, isLoading, isProfileLoading } = useAuth();

  const [category, setCategory] = useState<"all" | "fitness" | "face_yoga">("all");
  const [avoidTags, setAvoidTags] = useState<string[]>([]);
  const [routines, setRoutines] = useState<WorkoutRoutine[]>([]);
  const [history, setHistory] = useState<WorkoutLogRecord[]>([]);
  const [activeRoutine, setActiveRoutine] = useState<WorkoutRoutine | null>(null);
  const [loadingRoutines, setLoadingRoutines] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRoutines = useCallback(async () => {
    setLoadingRoutines(true);
    setError(null);
    try {
      const list = await getWorkoutRoutines({
        workoutType: category === "all" ? undefined : category,
        avoid: avoidTags,
      });
      setRoutines(list);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : "Workouts load nahi ho sake — check karein ke FastAPI backend chal raha hai.",
      );
    } finally {
      setLoadingRoutines(false);
    }
  }, [category, avoidTags]);

  const fetchHistory = useCallback(async (userId: string) => {
    try {
      const logs = await getWorkoutHistory(userId, 30);
      setHistory(logs);
    } catch {
      // Non-fatal if workout history fails on first load.
    }
  }, []);

  useEffect(() => {
    if (!user || !profileRecord) {
      return;
    }
    void fetchRoutines();
  }, [user, profileRecord, fetchRoutines]);

  useEffect(() => {
    if (!user || !profileRecord) {
      return;
    }
    void fetchHistory(user.id);
  }, [user, profileRecord, fetchHistory]);

  const toggleAvoidTag = (tag: string) => {
    setAvoidTags((prev) =>
      prev.includes(tag) ? prev.filter((item) => item !== tag) : [...prev, tag],
    );
  };

  const handleStartRoutine = (routine: WorkoutRoutine) => {
    setActiveRoutine(routine);
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const handleCompleteSession = async (durationMinutes: number) => {
    if (!user || !activeRoutine) {
      return;
    }
    await logWorkout(user.id, {
      routine_id: activeRoutine.id,
      duration_minutes: durationMinutes,
    });
    await fetchHistory(user.id);
  };

  if (!isLoading && !user) {
    return (
      <Card className="mx-auto max-w-lg">
        <CardHeader>
          <CardTitle>Sign in to open Workouts & Face Yoga</CardTitle>
          <CardDescription>
            Guided timers, joint-friendly swaps, aur calorie burn history save karne ke liye sign in
            karein.
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
          <CardTitle>Complete Onboarding first</CardTitle>
          <CardDescription>
            Exact calorie burn (MET formula) aap ke weight ke mutabiq calculate hota hai — pehle
            apni health profile set kar lein.
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

  const userWeightKg = profileRecord?.profile.weight_kg ?? 70;
  const totals = computeWorkoutTotals(history);

  return (
    <div className="space-y-6">
      {/* Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0f766e] text-white shadow-sm">
            <Dumbbell className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              Workouts & Face Yoga Studio
            </h1>
            <p className="text-xs text-slate-600">
              Zero-equipment home routines, joint-safe swaps, aur deterministic MET calorie burn
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="teal">
            <Trophy className="h-3.5 w-3.5" />
            {totals.sessions} sessions (30d)
          </Badge>
          <Badge variant="outline">
            <Clock className="h-3.5 w-3.5" />
            {totals.totalMinutes} mins
          </Badge>
          <Badge variant="amber">
            <Flame className="h-3.5 w-3.5" />
            {totals.totalCalories} kcal burned
          </Badge>
        </div>
      </div>

      {/* Active Guided Player */}
      {activeRoutine && (
        <GuidedWorkoutPlayer
          routine={activeRoutine}
          weightKg={userWeightKg}
          onComplete={handleCompleteSession}
          onClose={() => setActiveRoutine(null)}
        />
      )}

      {/* Filter Controls */}
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-4 p-4">
          <div className="flex flex-wrap gap-2">
            <Button
              variant={category === "all" ? "primary" : "outline"}
              size="sm"
              onClick={() => setCategory("all")}
            >
              All Routines
            </Button>
            <Button
              variant={category === "fitness" ? "primary" : "outline"}
              size="sm"
              onClick={() => setCategory("fitness")}
            >
              <Dumbbell className="h-3.5 w-3.5" />
              Home Fitness
            </Button>
            <Button
              variant={category === "face_yoga" ? "primary" : "outline"}
              size="sm"
              onClick={() => setCategory("face_yoga")}
            >
              <Sparkles className="h-3.5 w-3.5" />
              Face Yoga
            </Button>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-600">
              <ShieldCheck className="h-4 w-4 text-[#0f766e]" />
              Safety filters:
            </span>
            {JOINT_FILTER_OPTIONS.map((opt) => {
              const active = avoidTags.includes(opt.tag);
              return (
                <Button
                  key={opt.tag}
                  variant={active ? "secondary" : "outline"}
                  size="sm"
                  onClick={() => toggleAvoidTag(opt.tag)}
                >
                  {opt.label}
                </Button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {error && (
        <p className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </p>
      )}

      {/* Routine Catalog Grid */}
      {loadingRoutines ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-slate-500">
            Loading guided routines...
          </CardContent>
        </Card>
      ) : routines.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-slate-600">
            Selected filters ke mutabiq koi routine nahi mili — &quot;All Routines&quot; select ya
            filter clear karein.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {routines.map((routine) => {
            const estBurn = estimateWorkoutCalories(
              routine.met_value,
              userWeightKg,
              routine.duration_minutes,
            );
            return (
              <Card key={routine.id} className="flex flex-col justify-between">
                <CardHeader className="pb-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Badge variant={routine.workout_type === "face_yoga" ? "amber" : "teal"}>
                      {formatWorkoutCategory(routine.workout_type)}
                    </Badge>
                    <Badge variant="outline">{routine.level}</Badge>
                  </div>
                  <CardTitle className="mt-2 text-base">{routine.name}</CardTitle>
                  <CardDescription className="text-xs">{routine.urdu_subtitle}</CardDescription>
                </CardHeader>

                <CardContent className="flex flex-1 flex-col justify-between space-y-4">
                  <div className="space-y-2.5 text-xs text-slate-600">
                    <p className="leading-relaxed">{routine.description}</p>
                    <div className="flex flex-wrap gap-1.5">
                      <Badge variant="outline">
                        {routine.duration_minutes} min • {routine.steps.length} steps
                      </Badge>
                      <Badge variant="teal">~{estBurn} kcal</Badge>
                      {routine.contraindications.map((flag) => (
                        <Badge key={flag} variant="rose">
                          Caution: {flag}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <Button
                    size="sm"
                    className="w-full"
                    onClick={() => handleStartRoutine(routine)}
                  >
                    <Play className="h-3.5 w-3.5" />
                    Start Guided Session
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Completed Sessions History */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Recent Completed Sessions</CardTitle>
          <CardDescription>
            Har completed session Dashboard streak aur daily activity mein add hota hai.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {history.length === 0 ? (
            <p className="rounded-xl bg-slate-50 p-3.5 text-xs text-slate-600">
              Abhi koi workout ya face yoga session log nahi hua. Upar kisi routine par &quot;Start
              Guided Session&quot; dabayein!
            </p>
          ) : (
            <ul className="space-y-2">
              {history.slice(0, 10).map((log) => (
                <li
                  key={log.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200/80 bg-slate-50/70 px-3.5 py-2.5 text-xs"
                >
                  <div className="flex items-center gap-2">
                    <Badge variant={log.workout_type === "face_yoga" ? "amber" : "teal"}>
                      {formatWorkoutCategory(log.workout_type)}
                    </Badge>
                    <span className="font-semibold text-slate-900">{log.routine_name}</span>
                  </div>
                  <div className="text-slate-600">
                    <strong>{log.duration_minutes} min</strong> •{" "}
                    <strong className="text-[#0f766e]">{log.calories_burned} kcal</strong> •{" "}
                    {formatShortDate(log.completed_at)} {formatMessageTime(log.completed_at)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
