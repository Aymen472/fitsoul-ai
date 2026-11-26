"use client";

import { CheckCircle2, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { ValidatedMeal } from "@/lib/api";
import { formatMealTypeLabel } from "@/lib/dashboard-helpers";

interface MealSlotCardProps {
  meal: ValidatedMeal;
  isSwapping: boolean;
  isLogging: boolean;
  wasLogged: boolean;
  onSwap: (meal: ValidatedMeal) => void;
  onLogMeal: (meal: ValidatedMeal) => void;
}

export function MealSlotCard({
  meal,
  isSwapping,
  isLogging,
  wasLogged,
  onSwap,
  onLogMeal,
}: MealSlotCardProps) {
  return (
    <Card className="flex flex-col justify-between">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-base">{formatMealTypeLabel(meal.meal_type)}</CardTitle>
          <Badge variant="teal">{Math.round(meal.kcal)} kcal</Badge>
        </div>
        <CardDescription className="flex flex-wrap gap-2 text-xs">
          <span>Protein {Math.round(meal.protein)}g</span>
          <span>•</span>
          <span>Carbs {Math.round(meal.carbs)}g</span>
          <span>•</span>
          <span>Fat {Math.round(meal.fat)}g</span>
          <span>•</span>
          <span>Na {Math.round(meal.sodium_mg)} mg</span>
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col justify-between space-y-4">
        <ul className="space-y-2">
          {meal.items.map((item) => (
            <li
              key={`${meal.meal_type}-${item.food_id}`}
              className="flex items-center justify-between gap-3 rounded-xl border border-slate-200/80 bg-[#fafaf7]/80 px-3 py-2 text-xs"
            >
              <div className="min-w-0">
                <p className="truncate font-semibold text-slate-900">
                  {item.servings}x {item.name}
                </p>
                <p className="text-[11px] text-slate-500">
                  {Math.round(item.grams)}g • P {item.protein}g • C {item.carbs}g
                </p>
              </div>
              <span className="shrink-0 font-semibold text-[#0f766e]">
                {Math.round(item.kcal)} kcal
              </span>
            </li>
          ))}
        </ul>

        <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-3">
          <Button
            variant="outline"
            size="sm"
            className="flex-1"
            disabled={isSwapping || isLogging}
            onClick={() => onSwap(meal)}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isSwapping ? "animate-spin" : ""}`} />
            {isSwapping ? "Swapping..." : "Swap Meal"}
          </Button>

          <Button
            variant={wasLogged ? "secondary" : "primary"}
            size="sm"
            className="flex-1"
            disabled={isLogging || isSwapping}
            onClick={() => onLogMeal(meal)}
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            {isLogging ? "Logging..." : wasLogged ? "Logged Today!" : "Log to Today"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
