"use client";

import { Droplets, SmilePlus } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { MoodLogRecord } from "@/lib/api";
import { formatMessageTime } from "@/lib/chat-helpers";
import { MOOD_OPTIONS, clampPercent, formatShortDate } from "@/lib/dashboard-helpers";
import { cn } from "@/lib/utils";

interface HydrationMoodCardProps {
  waterMl: number;
  waterTargetMl: number;
  recentMoods: MoodLogRecord[];
  onLogWater: (amountMl: number) => Promise<void>;
  onLogMood: (mood: string, note?: string) => Promise<void>;
}

export function HydrationMoodCard({
  waterMl,
  waterTargetMl,
  recentMoods,
  onLogWater,
  onLogMood,
}: HydrationMoodCardProps) {
  const [submittingWater, setSubmittingWater] = useState(false);
  const [selectedMood, setSelectedMood] = useState("happy");
  const [note, setNote] = useState("");
  const [submittingMood, setSubmittingMood] = useState(false);

  const waterPct = clampPercent(waterMl, waterTargetMl);

  const handleAddWater = async (amountMl: number) => {
    setSubmittingWater(true);
    try {
      await onLogWater(amountMl);
    } finally {
      setSubmittingWater(false);
    }
  };

  const handleSaveMood = async (e: FormEvent) => {
    e.preventDefault();
    setSubmittingMood(true);
    try {
      await onLogMood(selectedMood, note);
      setNote("");
    } finally {
      setSubmittingMood(false);
    }
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle>Hydration & Mood Check-in</CardTitle>
        <CardDescription>
          Paani aur mood log karne se Coach patterns aur cravings samajhta hai.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-5">
        {/* Water Tracker */}
        <div className="space-y-2.5 rounded-xl bg-[#f0f7f4]/70 p-3.5">
          <div className="flex items-center justify-between text-sm">
            <span className="inline-flex items-center gap-1.5 font-semibold text-slate-900">
              <Droplets className="h-4 w-4 text-sky-600" />
              Water Today
            </span>
            <span className="text-xs font-medium text-slate-700">
              <strong>{waterMl} ml</strong> / {waterTargetMl} ml ({waterPct}%)
            </span>
          </div>

          <div className="h-2.5 w-full overflow-hidden rounded-full bg-white">
            <div
              className="h-full rounded-full bg-sky-500 transition-all duration-300"
              style={{ width: `${waterPct}%` }}
            />
          </div>

          <div className="flex flex-wrap gap-2 pt-1">
            <Button
              variant="outline"
              size="sm"
              disabled={submittingWater}
              onClick={() => void handleAddWater(250)}
            >
              +250 ml (Glass)
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={submittingWater}
              onClick={() => void handleAddWater(500)}
            >
              +500 ml (Bottle)
            </Button>
          </div>
        </div>

        {/* Mood Check-in */}
        <form onSubmit={handleSaveMood} className="space-y-3 border-t border-slate-100 pt-4">
          <div className="flex items-center gap-1.5 text-sm font-semibold text-slate-900">
            <SmilePlus className="h-4 w-4 text-[#0f766e]" />
            <span>How are you feeling today?</span>
          </div>

          <div className="flex flex-wrap gap-1.5">
            {MOOD_OPTIONS.map((opt) => {
              const active = selectedMood === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setSelectedMood(opt.value)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs font-medium transition-colors cursor-pointer",
                    active
                      ? "border-[#0f766e] bg-[#0f766e] text-white"
                      : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
                  )}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>

          <div className="flex gap-2">
            <Input
              type="text"
              placeholder="Optional note (e.g. office busy, walked 20 min)..."
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="mt-0 flex-1"
            />
            <Button type="submit" size="md" disabled={submittingMood}>
              {submittingMood ? "Saving..." : "Log Mood"}
            </Button>
          </div>

          {recentMoods.length > 0 && (
            <div className="space-y-1.5 pt-1">
              <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
                Recent Check-ins
              </p>
              <div className="flex flex-wrap gap-1.5">
                {recentMoods.slice(0, 3).map((entry) => {
                  const matchedTone =
                    MOOD_OPTIONS.find((opt) => opt.value === entry.mood.toLowerCase())?.tone ??
                    "outline";
                  return (
                    <Badge key={entry.id} variant={matchedTone}>
                      {entry.mood}
                      {entry.logged_at
                        ? ` (${formatShortDate(entry.logged_at)} ${formatMessageTime(entry.logged_at)})`
                        : ""}
                    </Badge>
                  );
                })}
              </div>
            </div>
          )}
        </form>
      </CardContent>
    </Card>
  );
}
