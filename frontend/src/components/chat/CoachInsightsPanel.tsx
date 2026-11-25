"use client";

import { Brain, RefreshCw, Sparkles, TrendingUp } from "lucide-react";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { PatternReport, UserMemoryRecord } from "@/lib/api";
import { formatMemoryCategoryLabel, formatPatternLabel } from "@/lib/chat-helpers";

interface CoachInsightsPanelProps {
  patterns: PatternReport | null;
  memories: UserMemoryRecord[];
  isRefreshing: boolean;
  onRefresh: () => void;
  dailyTargetKcal?: number;
}

function severityBadgeVariant(severity: string): BadgeProps["variant"] {
  if (severity === "positive") {
    return "teal";
  }
  if (severity === "high") {
    return "rose";
  }
  return "amber";
}

function memoryBadgeVariant(category: string): BadgeProps["variant"] {
  if (category === "win") {
    return "teal";
  }
  if (category === "trigger") {
    return "amber";
  }
  if (category === "preference") {
    return "outline";
  }
  return "default";
}

export function CoachInsightsPanel({
  patterns,
  memories,
  isRefreshing,
  onRefresh,
  dailyTargetKcal,
}: CoachInsightsPanelProps) {
  return (
    <div className="space-y-4">
      {/* Emotional Patterns & Proactive Nudges */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-[#0f766e]" />
              <CardTitle className="text-base">Emotional Patterns</CardTitle>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={onRefresh}
              disabled={isRefreshing}
              aria-label="Refresh patterns and memories"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
          <CardDescription className="text-xs">
            {dailyTargetKcal
              ? `14-day behavioral check against your ${dailyTargetKcal} kcal target.`
              : "14-day behavioral check across chats, meals, and mood logs."}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-3">
          {!patterns || patterns.patterns.length === 0 ? (
            <div className="rounded-xl bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
              {patterns?.summary ??
                "Abhi koi strong late-night ya weekend slip pattern detect nahi hua. Rozana chat aur meals log karte rahein!"}
            </div>
          ) : (
            patterns.patterns.map((pattern) => {
              const matchingNudge = patterns.nudges.find(
                (nudge) => nudge.pattern_type === pattern.pattern_type,
              );
              return (
                <div
                  key={pattern.pattern_type}
                  className="space-y-2 rounded-xl border border-slate-200/80 bg-slate-50/70 p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-slate-900">
                      {formatPatternLabel(pattern.pattern_type)}
                    </span>
                    <Badge variant={severityBadgeVariant(pattern.severity)}>
                      {pattern.severity} ({pattern.occurrences}x)
                    </Badge>
                  </div>
                  <p className="text-xs leading-relaxed text-slate-600">{pattern.description}</p>
                  {matchingNudge && (
                    <div className="rounded-lg border border-[#0f766e]/15 bg-[#f0f7f4] p-2.5 text-xs text-[#115e59]">
                      <p className="font-semibold">
                        Check-in ({matchingNudge.suggested_timing}):
                      </p>
                      <p className="mt-0.5 leading-relaxed">{matchingNudge.message}</p>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      {/* Long-Term Coach Memories */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Brain className="h-4 w-4 text-[#0f766e]" />
              <CardTitle className="text-base">Saved Coach Memories</CardTitle>
            </div>
            <Badge variant="teal">{memories.length}</Badge>
          </div>
          <CardDescription className="text-xs">
            Food pasand/napasand, triggers, aur wins automatically yaad rakhe jate hain.
          </CardDescription>
        </CardHeader>

        <CardContent>
          {memories.length === 0 ? (
            <div className="rounded-xl bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
              <p className="inline-flex items-center gap-1 font-medium text-slate-700">
                <Sparkles className="h-3.5 w-3.5 text-[#0f766e]" />
                Tip: Try sharing a food preference or win!
              </p>
              <p className="mt-1">
                Misal: &quot;Mujhe daal moong bohat pasand hai&quot; ya &quot;Is hafte 1 kg kam
                hua&quot;.
              </p>
            </div>
          ) : (
            <ul className="max-h-64 space-y-2 overflow-y-auto pr-1">
              {memories.map((mem) => (
                <li
                  key={mem.id}
                  className="rounded-xl border border-slate-200/80 bg-white p-2.5 text-xs text-slate-700"
                >
                  <Badge variant={memoryBadgeVariant(mem.category)} className="mb-1.5">
                    {formatMemoryCategoryLabel(mem.category)}
                  </Badge>
                  <p className="leading-relaxed">{mem.content}</p>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
