"use client";

import { Scale } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { WeightLogRecord } from "@/lib/api";
import { buildSparklinePoints, formatShortDate } from "@/lib/dashboard-helpers";

interface WeightTrendCardProps {
  latestWeightKg: number;
  targetWeightKg: number | null;
  bmi: number;
  weightHistory: WeightLogRecord[];
  onLogWeight: (weightKg: number) => Promise<void>;
}

export function WeightTrendCard({
  latestWeightKg,
  targetWeightKg,
  bmi,
  weightHistory,
  onLogWeight,
}: WeightTrendCardProps) {
  const [weightInput, setWeightInput] = useState(String(latestWeightKg));
  const [submitting, setSubmitting] = useState(false);

  const values = weightHistory.map((item) => item.weight_kg);
  const width = 280;
  const height = 96;
  const points = buildSparklinePoints(values, width, height, 12);
  const polylinePoints = points.map((pt) => `${pt.x},${pt.y}`).join(" ");

  const minWeight = values.length > 0 ? Math.min(...values) : latestWeightKg;
  const maxWeight = values.length > 0 ? Math.max(...values) : latestWeightKg;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const numeric = Number(weightInput);
    if (!Number.isFinite(numeric) || numeric < 30 || numeric > 250) {
      return;
    }
    setSubmitting(true);
    try {
      await onLogWeight(numeric);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Scale className="h-4 w-4 text-[#0f766e]" />
            <CardTitle>Weight Trend</CardTitle>
          </div>
          <Badge variant="teal">BMI {bmi}</Badge>
        </div>
        <CardDescription>
          Current: <strong className="text-slate-900">{latestWeightKg} kg</strong>
          {targetWeightKg !== null ? ` • Goal: ${targetWeightKg} kg` : ""}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {weightHistory.length >= 2 ? (
          <div className="rounded-xl border border-slate-200/80 bg-[#fafaf7] p-3">
            <div className="mb-1 flex items-center justify-between text-[11px] text-slate-500">
              <span>Max: {maxWeight} kg</span>
              <span>Last {weightHistory.length} check-ins</span>
              <span>Min: {minWeight} kg</span>
            </div>
            <svg viewBox={`0 0 ${width} ${height}`} className="h-24 w-full overflow-visible">
              <polyline
                fill="none"
                stroke="#0f766e"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={polylinePoints}
              />
              {points.map((pt, index) => (
                <circle
                  key={`${pt.x}-${pt.y}-${index}`}
                  cx={pt.x}
                  cy={pt.y}
                  r="3.5"
                  fill="#ffffff"
                  stroke="#0f766e"
                  strokeWidth="2"
                />
              ))}
            </svg>
            <div className="mt-1 flex justify-between text-[11px] text-slate-400">
              <span>{formatShortDate(weightHistory[0].logged_at)}</span>
              <span>{formatShortDate(weightHistory[weightHistory.length - 1].logged_at)}</span>
            </div>
          </div>
        ) : (
          <div className="rounded-xl bg-slate-50 p-3.5 text-xs text-slate-600">
            Kam az kam 2 weight check-ins log karein taake aap ka trend graph nazar aaye.
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          <Input
            type="number"
            step="0.1"
            min={30}
            max={250}
            value={weightInput}
            onChange={(e) => setWeightInput(e.target.value)}
            aria-label="Current weight in kg"
            className="mt-0 flex-1"
            required
          />
          <Button type="submit" size="md" disabled={submitting}>
            {submitting ? "Saving..." : "Log Weight"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
