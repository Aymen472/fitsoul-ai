"use client";

import { Flame } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { clampPercent } from "@/lib/dashboard-helpers";

interface CalorieRingCardProps {
  consumedKcal: number;
  remainingKcal: number;
  targetKcal: number;
  bmr: number;
  tdee: number;
  consumedProteinG: number;
  targetProteinG: number;
  consumedCarbsG: number;
  targetCarbsG: number;
  consumedFatG: number;
  targetFatG: number;
  streakDays: number;
}

interface MacroBarProps {
  label: string;
  consumed: number;
  target: number;
  barClassName: string;
}

function MacroProgressRow({ label, consumed, target, barClassName }: MacroBarProps) {
  const pct = clampPercent(consumed, target);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-slate-700">{label}</span>
        <span className="text-slate-600">
          <strong className="text-slate-900">{Math.round(consumed)}g</strong> / {target}g
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full transition-all duration-300 ${barClassName}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function CalorieRingCard({
  consumedKcal,
  remainingKcal,
  targetKcal,
  bmr,
  tdee,
  consumedProteinG,
  targetProteinG,
  consumedCarbsG,
  targetCarbsG,
  consumedFatG,
  targetFatG,
  streakDays,
}: CalorieRingCardProps) {
  const radius = 62;
  const circumference = 2 * Math.PI * radius;
  const pct = clampPercent(consumedKcal, targetKcal);
  const dashOffset = circumference * (1 - pct / 100);
  const isOverTarget = consumedKcal > targetKcal * 1.05;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <CardTitle>Daily Calories & Macros</CardTitle>
            <CardDescription>
              BMR {bmr} kcal • TDEE {tdee} kcal
            </CardDescription>
          </div>
          <Badge variant={streakDays > 0 ? "amber" : "outline"}>
            <Flame className="h-3.5 w-3.5" />
            {streakDays}d streak
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="grid items-center gap-6 sm:grid-cols-[170px_minmax(0,1fr)]">
        <div className="relative mx-auto flex h-40 w-40 items-center justify-center">
          <svg viewBox="0 0 160 160" className="h-40 w-40 -rotate-90">
            <circle
              cx="80"
              cy="80"
              r={radius}
              fill="none"
              stroke="#e2e8f0"
              strokeWidth="12"
            />
            <circle
              cx="80"
              cy="80"
              r={radius}
              fill="none"
              stroke={isOverTarget ? "#d97706" : "#0f766e"}
              strokeWidth="12"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              className="transition-all duration-500"
            />
          </svg>

          <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
            <span className="text-2xl font-bold tracking-tight text-slate-900">
              {Math.round(consumedKcal)}
            </span>
            <span className="text-[11px] font-medium text-slate-500">
              of {targetKcal} kcal
            </span>
            <span
              className={`mt-0.5 text-[11px] font-semibold ${
                isOverTarget ? "text-[#d97706]" : "text-[#0f766e]"
              }`}
            >
              {isOverTarget
                ? `+${Math.round(consumedKcal - targetKcal)} over`
                : `${Math.round(remainingKcal)} left`}
            </span>
          </div>
        </div>

        <div className="space-y-3.5">
          <MacroProgressRow
            label="Protein (Muscle & Satiety)"
            consumed={consumedProteinG}
            target={targetProteinG}
            barClassName="bg-[#0f766e]"
          />
          <MacroProgressRow
            label="Carbohydrates"
            consumed={consumedCarbsG}
            target={targetCarbsG}
            barClassName="bg-[#d97706]"
          />
          <MacroProgressRow
            label="Healthy Fats"
            consumed={consumedFatG}
            target={targetFatG}
            barClassName="bg-sky-600"
          />
        </div>
      </CardContent>
    </Card>
  );
}
