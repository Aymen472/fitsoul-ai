"use client";

import Link from "next/link";
import {
  ArrowRight,
  Brain,
  MessageCircleHeart,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { ChatMessageBubble } from "@/components/chat/ChatMessageBubble";
import { CoachInsightsPanel } from "@/components/chat/CoachInsightsPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ApiError,
  getChatHistory,
  getUserMemories,
  getUserPatterns,
  sendChatMessage,
  type PatternReport,
  type UserMemoryRecord,
} from "@/lib/api";
import {
  QUICK_PROMPTS,
  mapHistoryToUiMessages,
  mergeUniqueMemories,
  type UiChatMessage,
} from "@/lib/chat-helpers";

export default function ChatPage() {
  const { user, profileRecord, isLoading, isProfileLoading } = useAuth();

  const [messages, setMessages] = useState<UiChatMessage[]>([]);
  const [memories, setMemories] = useState<UserMemoryRecord[]>([]);
  const [patterns, setPatterns] = useState<PatternReport | null>(null);
  const [draft, setDraft] = useState("");
  const [loadingInitial, setLoadingInitial] = useState(false);
  const [refreshingInsights, setRefreshingInsights] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showMobileInsights, setShowMobileInsights] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const loadCoachWorkspace = useCallback(async (userId: string) => {
    setLoadingInitial(true);
    setError(null);

    const [historyRes, memoriesRes, patternsRes] = await Promise.allSettled([
      getChatHistory(userId),
      getUserMemories(userId),
      getUserPatterns(userId),
    ]);

    if (historyRes.status === "fulfilled") {
      setMessages(mapHistoryToUiMessages(historyRes.value.messages));
    } else if (
      !(historyRes.reason instanceof ApiError && historyRes.reason.status === 404)
    ) {
      setError("Chat history load nahi ho saki — check karein ke FastAPI backend chal raha hai.");
    }

    if (memoriesRes.status === "fulfilled") {
      setMemories(memoriesRes.value.memories);
    }

    if (patternsRes.status === "fulfilled") {
      setPatterns(patternsRes.value);
    }

    setLoadingInitial(false);
  }, []);

  useEffect(() => {
    if (!user || !profileRecord) {
      return;
    }
    void loadCoachWorkspace(user.id);
  }, [user, profileRecord, loadCoachWorkspace]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, sending]);

  const handleRefreshInsights = useCallback(async () => {
    if (!user) {
      return;
    }
    setRefreshingInsights(true);
    const [memoriesRes, patternsRes] = await Promise.allSettled([
      getUserMemories(user.id),
      getUserPatterns(user.id),
    ]);
    if (memoriesRes.status === "fulfilled") {
      setMemories(memoriesRes.value.memories);
    }
    if (patternsRes.status === "fulfilled") {
      setPatterns(patternsRes.value);
    }
    setRefreshingInsights(false);
  }, [user]);

  const submitMessage = async (rawText: string) => {
    if (!user || sending) {
      return;
    }
    const trimmed = rawText.trim();
    if (!trimmed) {
      return;
    }

    const tempId = `temp-${Date.now()}`;
    const optimisticUserMsg: UiChatMessage = {
      id: tempId,
      role: "user",
      content: trimmed,
      createdAt: new Date().toISOString(),
      pending: true,
    };

    setError(null);
    setDraft("");
    setSending(true);
    setMessages((prev) => [...prev, optimisticUserMsg]);

    try {
      const response = await sendChatMessage({
        user_id: user.id,
        message: trimmed,
        channel: "web",
      });

      const assistantMsg: UiChatMessage = {
        id: response.assistant_message_id,
        role: "assistant",
        content: response.reply,
        createdAt: new Date().toISOString(),
        flaggedSafety: response.flagged_safety,
        safetyCategory: response.safety_category,
        stopDietAdvice: response.stop_diet_advice,
        intent: response.intent,
        usedMemories: response.used_memories,
        savedMemories: response.saved_memories,
        usedFallback: response.used_fallback,
        groundedData: response.grounded_data,
      };

      setMessages((prev) => [
        ...prev.map((msg) =>
          msg.id === tempId
            ? {
                ...msg,
                id: response.user_message_id,
                flaggedSafety: response.flagged_safety,
                pending: false,
              }
            : msg,
        ),
        assistantMsg,
      ]);

      if (response.saved_memories.length > 0) {
        setMemories((prev) => mergeUniqueMemories(prev, response.saved_memories));
      }

      getUserPatterns(user.id)
        .then((report) => setPatterns(report))
        .catch(() => undefined);
    } catch (err) {
      setMessages((prev) => prev.filter((msg) => msg.id !== tempId));
      setDraft((prev) => prev || trimmed);
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Message send nahi ho saka. Check karein ke FastAPI backend (:8000) chal raha hai.");
      }
    } finally {
      setSending(false);
    }
  };

  const handleFormSubmit = async (e: FormEvent) => {
    e.preventDefault();
    await submitMessage(draft);
  };

  const handleTextareaKeyDown = async (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      await submitMessage(draft);
    }
  };

  if (!isLoading && !user) {
    return (
      <Card className="mx-auto max-w-lg">
        <CardHeader>
          <CardTitle>Sign in to chat with FitSoul AI</CardTitle>
          <CardDescription>
            Aap ki conversation history, saved preferences, aur safety settings har device par
            persist hoti hain.
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
          <CardTitle>Complete Onboarding before chatting</CardTitle>
          <CardDescription>
            Coach ko aap ke exact calories, allergies, aur medical conditions (PCOS / Diabetes / BP)
            chahiye taake har reply bilkul safe ho.
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

  return (
    <div className="space-y-4">
      {/* Page Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0f766e] text-white shadow-sm">
            <MessageCircleHeart className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              FitSoul AI Coach
            </h1>
            <p className="text-xs text-slate-600">
              Roman Urdu & English • Safety guardrails & deterministic nutrition grounding active
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {profileRecord && (
            <Badge variant="teal">
              <ShieldCheck className="h-3.5 w-3.5" />
              Target {profileRecord.targets.calories} kcal
            </Badge>
          )}
          <Button
            variant="outline"
            size="sm"
            className="lg:hidden"
            onClick={() => setShowMobileInsights((prev) => !prev)}
          >
            <Brain className="h-4 w-4" />
            {showMobileInsights ? "Hide Insights" : `Insights (${memories.length})`}
          </Button>
        </div>
      </div>

      {/* Main Responsive Split Grid */}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* Chat Column */}
        <Card className="flex flex-col overflow-hidden">
          <div className="min-h-[380px] max-h-[60vh] flex-1 space-y-4 overflow-y-auto bg-[#fafaf7]/60 p-4 sm:p-5">
            {loadingInitial ? (
              <div className="flex h-64 items-center justify-center text-sm text-slate-500">
                Loading your conversation history...
              </div>
            ) : messages.length === 0 ? (
              <div className="mx-auto max-w-lg space-y-5 py-4 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#f0f7f4] text-[#0f766e]">
                  <Sparkles className="h-6 w-6" />
                </div>
                <div className="space-y-1.5">
                  <h2 className="text-lg font-semibold text-slate-900">
                    Assalam o alaikum, {user?.fullName ?? "Friend"}!
                  </h2>
                  <p className="text-sm text-slate-600">
                    Aaj aap ne kya khaya, sham ki chai mein kya crave ho raha hai, ya dawat ka
                    plan chahiye? Neeche kisi prompt par tap karein ya apna message likhein.
                  </p>
                </div>

                <div className="grid gap-2 text-left sm:grid-cols-2">
                  {QUICK_PROMPTS.map((item) => (
                    <button
                      key={item.label}
                      type="button"
                      onClick={() => void submitMessage(item.prompt)}
                      disabled={sending}
                      className="rounded-xl border border-slate-200 bg-white p-3 text-left transition-colors hover:border-[#0f766e]/50 hover:bg-[#f0f7f4]/50 cursor-pointer disabled:opacity-50"
                    >
                      <p className="text-xs font-semibold text-[#0f766e]">{item.label}</p>
                      <p className="mt-0.5 line-clamp-2 text-xs text-slate-600">{item.prompt}</p>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg) => <ChatMessageBubble key={msg.id} message={msg} />)
            )}

            {sending && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 text-xs text-slate-500 shadow-sm">
                  FitSoul Coach is thinking...
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Quick Prompt Bar when chat has messages */}
          {messages.length > 0 && (
            <div className="flex gap-2 overflow-x-auto border-t border-slate-100 bg-white px-4 py-2.5">
              {QUICK_PROMPTS.map((item) => (
                <button
                  key={item.label}
                  type="button"
                  onClick={() => void submitMessage(item.prompt)}
                  disabled={sending}
                  className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700 transition-colors hover:border-[#0f766e]/40 hover:bg-[#f0f7f4] hover:text-[#0f766e] cursor-pointer disabled:opacity-50"
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}

          {error && (
            <div className="border-t border-rose-200 bg-rose-50 px-4 py-2.5 text-xs text-rose-700">
              {error}
            </div>
          )}

          {/* Message Composer */}
          <form
            onSubmit={handleFormSubmit}
            className="flex items-end gap-2.5 border-t border-slate-200 bg-white p-3 sm:p-4"
          >
            <textarea
              rows={2}
              maxLength={4000}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => void handleTextareaKeyDown(e)}
              disabled={sending}
              placeholder="Likhein... e.g. 'Maine 2 roti aur daal khai' ya 'Chai ke saath kya khaun?'"
              aria-label="Message FitSoul AI Coach"
              className="max-h-36 min-h-[44px] flex-1 resize-none rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-[#0f766e] focus:outline-none focus:ring-2 focus:ring-[#0f766e]/20 disabled:bg-slate-100"
            />
            <Button
              type="submit"
              size="md"
              disabled={sending || !draft.trim()}
              className="h-11 shrink-0 px-4"
            >
              <Send className="h-4 w-4" />
              <span className="hidden sm:inline">Send</span>
            </Button>
          </form>
        </Card>

        {/* Insights & Memory Column */}
        <aside className={showMobileInsights ? "block" : "hidden lg:block"}>
          <CoachInsightsPanel
            patterns={patterns}
            memories={memories}
            isRefreshing={refreshingInsights}
            onRefresh={() => void handleRefreshInsights()}
            dailyTargetKcal={profileRecord?.targets.calories}
          />
        </aside>
      </div>
    </div>
  );
}
