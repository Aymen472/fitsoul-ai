"use client";

import { BookmarkCheck, Brain, ShieldAlert, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  formatIntentLabel,
  formatMemoryCategoryLabel,
  formatMessageTime,
  type UiChatMessage,
} from "@/lib/chat-helpers";
import { cn } from "@/lib/utils";

function readNumericMetric(
  groundedData: Record<string, unknown> | undefined,
  key: string,
): number | null {
  if (!groundedData || !(key in groundedData)) {
    return null;
  }
  const value = groundedData[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function ChatMessageBubble({ message }: { message: UiChatMessage }) {
  const isUser = message.role === "user";
  const timeLabel = formatMessageTime(message.createdAt);

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] space-y-1.5 sm:max-w-[75%]">
          <div className="rounded-2xl rounded-br-sm bg-[#0f766e] px-4 py-3 text-sm leading-relaxed text-white shadow-sm">
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
          </div>
          <div className="flex items-center justify-end gap-2 px-1 text-[11px] text-slate-400">
            {message.flaggedSafety && (
              <Badge variant="rose" className="text-[10px]">
                Care Alert Triggered
              </Badge>
            )}
            {message.pending && <span>Sending...</span>}
            {timeLabel && <span>{timeLabel}</span>}
          </div>
        </div>
      </div>
    );
  }

  const loggedKcal = readNumericMetric(message.groundedData, "logged_kcal");
  const remainingKcal = readNumericMetric(message.groundedData, "remaining_kcal");
  const dailyTargetKcal = readNumericMetric(message.groundedData, "daily_target_kcal");
  const usedMemories = message.usedMemories ?? [];
  const savedMemories = message.savedMemories ?? [];

  return (
    <div className="flex justify-start">
      <div className="max-w-[90%] space-y-2 sm:max-w-[82%]">
        <div
          className={cn(
            "rounded-2xl rounded-bl-sm border px-4 py-3.5 shadow-sm",
            message.stopDietAdvice
              ? "border-rose-200 bg-rose-50/80 text-rose-950"
              : "border-slate-200/90 bg-white text-slate-900",
          )}
        >
          {message.stopDietAdvice && (
            <div className="mb-2.5 flex items-center gap-2 rounded-xl border border-rose-200 bg-white/80 px-3 py-2 text-xs font-semibold text-rose-800">
              <ShieldAlert className="h-4 w-4 shrink-0 text-rose-600" />
              <span>Safety & Care Mode — Diet advice paused</span>
            </div>
          )}

          {(loggedKcal !== null || remainingKcal !== null) && !message.stopDietAdvice && (
            <div className="mb-2.5 flex flex-wrap gap-1.5">
              {loggedKcal !== null && (
                <Badge variant="teal">Logged: {loggedKcal} kcal</Badge>
              )}
              {remainingKcal !== null && (
                <Badge variant="amber">
                  Remaining: {remainingKcal}
                  {dailyTargetKcal !== null ? ` / ${dailyTargetKcal}` : ""} kcal
                </Badge>
              )}
            </div>
          )}

          <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">
            {message.content}
          </p>

          {(message.intent ||
            message.usedFallback ||
            usedMemories.length > 0 ||
            savedMemories.length > 0) && (
            <div className="mt-3 space-y-2 border-t border-slate-100 pt-2.5">
              <div className="flex flex-wrap items-center gap-1.5">
                {message.intent && (
                  <Badge variant={message.stopDietAdvice ? "rose" : "teal"}>
                    <Sparkles className="h-3 w-3" />
                    {formatIntentLabel(message.intent)}
                  </Badge>
                )}

                {message.usedFallback && (
                  <Badge variant="outline">Deterministic Coach Mode</Badge>
                )}

                {usedMemories.length > 0 && (
                  <Badge variant="teal">
                    <Brain className="h-3 w-3" />
                    Recalled {usedMemories.length}{" "}
                    {usedMemories.length === 1 ? "memory" : "memories"}
                  </Badge>
                )}

                {savedMemories.length > 0 && (
                  <Badge variant="amber">
                    <BookmarkCheck className="h-3 w-3" />
                    Saved {savedMemories.length} new{" "}
                    {savedMemories.length === 1 ? "memory" : "memories"}
                  </Badge>
                )}
              </div>

              {usedMemories.length > 0 && (
                <div className="rounded-xl bg-[#f0f7f4] px-3 py-2 text-xs text-[#115e59]">
                  <p className="font-semibold">Using your saved context:</p>
                  <ul className="mt-1 space-y-0.5">
                    {usedMemories.slice(0, 3).map((mem) => (
                      <li key={mem} className="truncate">
                        • {mem}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {savedMemories.length > 0 && (
                <div className="rounded-xl bg-amber-50/80 px-3 py-2 text-xs text-amber-900">
                  <p className="font-semibold">Remembered for future chats:</p>
                  <ul className="mt-1 space-y-0.5">
                    {savedMemories.map((mem) => (
                      <li key={mem.id}>
                        • [{formatMemoryCategoryLabel(mem.category)}] {mem.content}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 px-1 text-[11px] text-slate-400">
          <span>FitSoul Coach</span>
          {timeLabel && <span>• {timeLabel}</span>}
        </div>
      </div>
    </div>
  );
}
