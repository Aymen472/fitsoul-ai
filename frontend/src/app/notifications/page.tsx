"use client";

import Link from "next/link";
import {
  ArrowRight,
  BellRing,
  CheckCircle2,
  Clock,
  ExternalLink,
  MoonStar,
  RefreshCw,
  Send,
  ShieldCheck,
} from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import {
  ApiError,
  getNotificationLogs,
  getNotificationPreferences,
  getNotificationSchedulePreview,
  getNotificationTemplates,
  sendUserNotification,
  updateNotificationPreferences,
  type NotificationLogEntry,
  type NotificationPreferences,
  type ProfileRecord,
  type SchedulePreviewResponse,
  type SendNotificationResponse,
  type WhatsAppTemplateDefinition,
} from "@/lib/api";
import { formatMessageTime } from "@/lib/chat-helpers";
import {
  formatNotificationStatus,
  formatQuietWindow,
  formatTemplateLabel,
  isValidPhoneInput,
  type StatusTone,
} from "@/lib/notification-helpers";

function mapToneToBadgeVariant(tone: StatusTone): "teal" | "amber" | "rose" | "outline" {
  switch (tone) {
    case "teal":
      return "teal";
    case "amber":
      return "amber";
    case "red":
      return "rose";
    default:
      return "outline";
  }
}

function buildPreviewParams(
  templateName: string,
  profileRecord: ProfileRecord | null,
): Record<string, string | number> {
  const userName = profileRecord?.full_name?.trim() || "Aymen";
  const targetKcal = profileRecord?.targets.calories ?? 1550;
  const targetWater = profileRecord?.targets.water_ml ?? 2500;

  switch (templateName) {
    case "fitsoul_meal_reminder":
      return {
        user_name: userName,
        meal_slot: "Lunch",
        suggested_meal: "Daal moong + 1 whole wheat chapati + kachumber salad",
        target_kcal: Math.round(targetKcal * 0.35),
      };
    case "fitsoul_water_reminder":
      return {
        user_name: userName,
        consumed_ml: Math.round(targetWater * 0.45),
        target_ml: targetWater,
      };
    case "fitsoul_workout_nudge":
      return {
        user_name: userName,
        routine_name: "PCOS Low-Impact Walk & Tone",
        duration_minutes: 15,
      };
    case "fitsoul_night_summary":
      return {
        user_name: userName,
        consumed_kcal: Math.max(0, targetKcal - 120),
        target_kcal: targetKcal,
        streak_days: 5,
      };
    case "fitsoul_weekly_report":
      return {
        user_name: userName,
        avg_kcal: targetKcal - 50,
        workouts_completed: 4,
        weight_delta: "-0.5 kg",
      };
    case "fitsoul_proactive_support":
      return {
        user_name: userName,
        support_message:
          "Shaam ki chai cravings ke liye almonds aur elaichi sabz chai best rehti hai!",
      };
    case "fitsoul_subscription_renewal":
      return {
        user_name: userName,
        days_remaining: 3,
        plan_name: "FitSoul Pro Monthly",
      };
    default:
      return { user_name: userName };
  }
}

export default function NotificationsPage() {
  const { user, profileRecord, isLoading, isProfileLoading } = useAuth();

  const [savedPrefs, setSavedPrefs] = useState<NotificationPreferences | null>(null);
  const [templates, setTemplates] = useState<WhatsAppTemplateDefinition[]>([]);
  const [schedulePreview, setSchedulePreview] = useState<SchedulePreviewResponse | null>(null);
  const [logs, setLogs] = useState<NotificationLogEntry[]>([]);

  const [whatsappOptIn, setWhatsappOptIn] = useState(false);
  const [whatsappPhone, setWhatsappPhone] = useState("");
  const [mealReminders, setMealReminders] = useState(true);
  const [waterReminders, setWaterReminders] = useState(true);
  const [workoutReminders, setWorkoutReminders] = useState(true);
  const [nightSummary, setNightSummary] = useState(true);
  const [weeklyReport, setWeeklyReport] = useState(true);
  const [quietHoursStart, setQuietHoursStart] = useState("22:30");
  const [quietHoursEnd, setQuietHoursEnd] = useState("07:00");

  const [selectedTemplate, setSelectedTemplate] = useState("fitsoul_meal_reminder");
  const [previewResult, setPreviewResult] = useState<SendNotificationResponse | null>(null);

  const [loadingPage, setLoadingPage] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sendingPreview, setSendingPreview] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const applyPrefsToForm = useCallback((prefs: NotificationPreferences) => {
    setSavedPrefs(prefs);
    setWhatsappOptIn(prefs.whatsapp_opt_in);
    setWhatsappPhone(prefs.whatsapp_phone ?? "");
    setMealReminders(prefs.meal_reminders);
    setWaterReminders(prefs.water_reminders);
    setWorkoutReminders(prefs.workout_reminders);
    setNightSummary(prefs.night_summary);
    setWeeklyReport(prefs.weekly_report);
    setQuietHoursStart(prefs.quiet_hours_start);
    setQuietHoursEnd(prefs.quiet_hours_end);
  }, []);

  const loadWorkspace = useCallback(
    async (userId: string) => {
      setLoadingPage(true);
      setPageError(null);
      const [prefsRes, templatesRes, previewRes, logsRes] = await Promise.allSettled([
        getNotificationPreferences(userId),
        getNotificationTemplates(),
        getNotificationSchedulePreview(userId),
        getNotificationLogs(userId, 30),
      ]);

      if (prefsRes.status === "fulfilled") {
        applyPrefsToForm(prefsRes.value);
      } else {
        const err = prefsRes.reason;
        setPageError(
          err instanceof ApiError
            ? err.detail
            : "Notification settings load nahi ho sakin — FastAPI backend check karein.",
        );
      }

      if (templatesRes.status === "fulfilled") {
        setTemplates(templatesRes.value);
        if (templatesRes.value.length > 0) {
          setSelectedTemplate((prev) => prev || templatesRes.value[0].name);
        }
      }

      if (previewRes.status === "fulfilled") {
        setSchedulePreview(previewRes.value);
      }

      if (logsRes.status === "fulfilled") {
        setLogs(logsRes.value);
      }

      setLoadingPage(false);
    },
    [applyPrefsToForm],
  );

  useEffect(() => {
    if (!user || !profileRecord) {
      return;
    }
    void loadWorkspace(user.id);
  }, [user, profileRecord, loadWorkspace]);

  const handleSavePreferences = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!user) {
      return;
    }

    setPageError(null);
    setSaveMessage(null);

    if (whatsappOptIn && !isValidPhoneInput(whatsappPhone)) {
      setPageError(
        "Valid WhatsApp number enter karein (jaise 0300-1234567 ya +92 300 1234567).",
      );
      return;
    }

    if (!whatsappOptIn && whatsappPhone.trim() && !isValidPhoneInput(whatsappPhone)) {
      setPageError("Phone number format valid nahi hai (10–15 digits ya 03XXXXXXXXX).");
      return;
    }

    setSaving(true);
    try {
      const updated = await updateNotificationPreferences(user.id, {
        whatsapp_opt_in: whatsappOptIn,
        whatsapp_phone: whatsappPhone.trim() ? whatsappPhone.trim() : null,
        meal_reminders: mealReminders,
        water_reminders: waterReminders,
        workout_reminders: workoutReminders,
        night_summary: nightSummary,
        weekly_report: weeklyReport,
        quiet_hours_start: quietHoursStart,
        quiet_hours_end: quietHoursEnd,
      });
      applyPrefsToForm(updated);
      setSaveMessage("WhatsApp notification preferences save ho gayi hain!");

      const [previewRes, logsRes] = await Promise.allSettled([
        getNotificationSchedulePreview(user.id),
        getNotificationLogs(user.id, 30),
      ]);
      if (previewRes.status === "fulfilled") {
        setSchedulePreview(previewRes.value);
      }
      if (logsRes.status === "fulfilled") {
        setLogs(logsRes.value);
      }
    } catch (err) {
      setPageError(
        err instanceof ApiError ? err.detail : "Settings save karne mein masla aaya.",
      );
    } finally {
      setSaving(false);
    }
  };

  const handleSendTestPreview = async () => {
    if (!user) {
      return;
    }
    setPageError(null);
    setSendingPreview(true);
    try {
      const response = await sendUserNotification(user.id, {
        template_name: selectedTemplate,
        params: buildPreviewParams(selectedTemplate, profileRecord),
        dry_run: true,
      });
      setPreviewResult(response);
      const updatedLogs = await getNotificationLogs(user.id, 30);
      setLogs(updatedLogs);
    } catch (err) {
      setPageError(
        err instanceof ApiError ? err.detail : "Test preview render nahi ho saka.",
      );
    } finally {
      setSendingPreview(false);
    }
  };

  if (!isLoading && !user) {
    return (
      <Card className="mx-auto max-w-lg">
        <CardHeader>
          <CardTitle>Sign in to manage WhatsApp Reminders</CardTitle>
          <CardDescription>
            Apni proactive reminder timings, sleep window, aur WhatsApp opt-in settings manage karne
            ke liye sign in karein.
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
            Reminders aap ke timezone aur daily calorie/water targets ke mutabiq schedule hote
            hain — pehle apni health profile set karein.
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

  const activeTemplateDef = templates.find((t) => t.name === selectedTemplate) ?? null;

  return (
    <div className="space-y-6">
      {/* Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0f766e] text-white shadow-sm">
            <BellRing className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              WhatsApp Reminders &amp; Sleep Window
            </h1>
            <p className="text-xs text-slate-600">
              Approved Meta templates with direct deep links back to your FitSoul AI PWA
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={savedPrefs?.whatsapp_opt_in ? "teal" : "outline"}>
            {savedPrefs?.whatsapp_opt_in ? "WhatsApp Opted In" : "Reminders Paused"}
          </Badge>
          {schedulePreview && (
            <Badge variant={schedulePreview.in_quiet_hours ? "amber" : "teal"}>
              <MoonStar className="h-3.5 w-3.5" />
              {schedulePreview.in_quiet_hours ? "Quiet Hours Active" : "Awake Window"}
            </Badge>
          )}
          <Button
            variant="outline"
            size="sm"
            disabled={loadingPage || !user}
            onClick={() => user && void loadWorkspace(user.id)}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loadingPage ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Inline Status Banners */}
      {pageError && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {pageError}
        </div>
      )}
      {saveMessage && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{saveMessage}</span>
        </div>
      )}

      {/* Main Two-Column Settings + Preview Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left: Opt-In, Phone, Toggles & Sleep Window Form */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">1. Notification Preferences</CardTitle>
            <CardDescription className="text-xs">
              Apna WhatsApp number, reminder categories, aur quiet sleep hours set karein.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSavePreferences} className="space-y-4">
              <label className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50/70 p-3.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={whatsappOptIn}
                  onChange={(e) => setWhatsappOptIn(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-slate-300 text-[#0f766e] focus:ring-[#0f766e]"
                />
                <div className="space-y-0.5">
                  <p className="text-sm font-semibold text-slate-900">
                    Enable WhatsApp Proactive Reminders
                  </p>
                  <p className="text-xs text-slate-600">
                    Kisi bhi waqt WhatsApp par <span className="font-mono font-semibold">STOP</span>{" "}
                    bhej kar pause karein aur <span className="font-mono font-semibold">START</span>{" "}
                    se resume karein.
                  </p>
                </div>
              </label>

              <div>
                <Label htmlFor="wa-phone">WhatsApp Phone Number</Label>
                <Input
                  id="wa-phone"
                  type="tel"
                  placeholder="0300-1234567 ya +92 300 1234567"
                  value={whatsappPhone}
                  onChange={(e) => setWhatsappPhone(e.target.value)}
                />
                <p className="mt-1 text-[11px] text-slate-500">
                  Pakistani local format (<span className="font-mono">03XXXXXXXXX</span>) khud{" "}
                  <span className="font-mono">923XXXXXXXXX</span> mein normalize ho jata hai.
                </p>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium text-slate-800">Reminder Categories</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {[
                    {
                      label: "Meal Reminders (3x/day)",
                      checked: mealReminders,
                      onChange: setMealReminders,
                    },
                    {
                      label: "Water Reminders (2x/day)",
                      checked: waterReminders,
                      onChange: setWaterReminders,
                    },
                    {
                      label: "Workout / Face Yoga Nudge",
                      checked: workoutReminders,
                      onChange: setWorkoutReminders,
                    },
                    {
                      label: "Night Wrap-up (21:00)",
                      checked: nightSummary,
                      onChange: setNightSummary,
                    },
                    {
                      label: "Weekly Report (Sun 10:00)",
                      checked: weeklyReport,
                      onChange: setWeeklyReport,
                    },
                  ].map((item) => (
                    <label
                      key={item.label}
                      className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-800 cursor-pointer hover:bg-slate-50"
                    >
                      <input
                        type="checkbox"
                        checked={item.checked}
                        onChange={(e) => item.onChange(e.target.checked)}
                        className="h-4 w-4 rounded border-slate-300 text-[#0f766e] focus:ring-[#0f766e]"
                      />
                      <span>{item.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <Label htmlFor="quiet-start">Quiet Hours Start (Sleep)</Label>
                  <Input
                    id="quiet-start"
                    type="time"
                    value={quietHoursStart}
                    onChange={(e) => setQuietHoursStart(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="quiet-end">Quiet Hours End (Wake)</Label>
                  <Input
                    id="quiet-end"
                    type="time"
                    value={quietHoursEnd}
                    onChange={(e) => setQuietHoursEnd(e.target.value)}
                    required
                  />
                </div>
              </div>

              <div className="flex items-center justify-between gap-3 pt-1">
                <span className="text-xs text-slate-500">
                  Sleep Window: <strong>{formatQuietWindow(quietHoursStart, quietHoursEnd)}</strong>
                </span>
                <Button type="submit" disabled={saving}>
                  {saving ? "Saving..." : "Save Preferences"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {/* Right: Local Schedule Preview & Template Dry-Run Tester */}
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-[#0f766e]" />
                  <CardTitle className="text-base">2. Local Schedule Preview</CardTitle>
                </div>
                {schedulePreview && (
                  <Badge variant="outline">{schedulePreview.timezone}</Badge>
                )}
              </div>
              <CardDescription className="text-xs">
                {schedulePreview
                  ? `Local time: ${schedulePreview.local_time} — ${schedulePreview.due_jobs.length} slot(s) currently due.`
                  : "Loading your timezone schedule..."}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {schedulePreview ? (
                <div className="space-y-2">
                  {schedulePreview.upcoming_slots.map((slot) => (
                    <div
                      key={slot.slot_type}
                      className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/70 px-3 py-2 text-xs"
                    >
                      <div className="min-w-0">
                        <p className="font-semibold text-slate-900">{slot.label}</p>
                        <p className="text-[11px] text-slate-500">
                          {formatTemplateLabel(slot.template_name)}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="font-mono text-slate-700">{slot.local_time}</span>
                        <Badge variant={slot.enabled ? "teal" : "outline"}>
                          {slot.enabled ? "On" : "Off"}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500">Schedule preview unavailable.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center gap-2">
                <Send className="h-4 w-4 text-[#0f766e]" />
                <CardTitle className="text-base">3. Test Notification Preview</CardTitle>
              </div>
              <CardDescription className="text-xs">
                Approved template + PWA deep link ko dry-run mode mein test karein (real Meta
                quota kharch kiye baghair).
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <Label htmlFor="wa-template-select">Approved Template</Label>
                <Select
                  id="wa-template-select"
                  value={selectedTemplate}
                  onChange={(e) => setSelectedTemplate(e.target.value)}
                >
                  {templates.map((tpl) => (
                    <option key={tpl.name} value={tpl.name}>
                      {formatTemplateLabel(tpl.name)} ({tpl.default_path})
                    </option>
                  ))}
                </Select>
              </div>

              {activeTemplateDef && (
                <p className="rounded-xl bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
                  {activeTemplateDef.preview_body}
                </p>
              )}

              <div className="flex flex-wrap items-center justify-between gap-2">
                {!savedPrefs?.whatsapp_opt_in ? (
                  <p className="text-xs text-amber-700">
                    Test preview chalane ke liye pehle WhatsApp Opt-In save karein.
                  </p>
                ) : (
                  <p className="text-xs text-slate-500">
                    Dry-run message logs mein save ho jayega.
                  </p>
                )}
                <Button
                  type="button"
                  size="sm"
                  disabled={!savedPrefs?.whatsapp_opt_in || sendingPreview}
                  onClick={() => void handleSendTestPreview()}
                >
                  <Send className="h-3.5 w-3.5" />
                  {sendingPreview ? "Rendering..." : "Send Test Preview"}
                </Button>
              </div>

              {previewResult && (
                <div className="rounded-xl border border-[#0f766e]/20 bg-[#f0f7f4]/80 p-3.5 space-y-2 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-[#115e59]">WhatsApp Preview Output</span>
                    <Badge variant="amber">Dry Run</Badge>
                  </div>
                  <p className="whitespace-pre-line leading-relaxed text-slate-800">
                    {previewResult.preview_text}
                  </p>
                  {previewResult.log.deep_link && (
                    <p className="flex items-center gap-1.5 text-[11px] font-medium text-[#0f766e]">
                      <ExternalLink className="h-3 w-3 shrink-0" />
                      <span>Deep link: {previewResult.log.deep_link}</span>
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Recent Notification Delivery & Webhook Activity */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-base">Recent Notification Activity</CardTitle>
            <Badge variant="outline">{logs.length} record(s)</Badge>
          </div>
          <CardDescription className="text-xs">
            Outbound template deliveries, Meta webhook status updates, aur inbound STOP/START logs.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {logs.length === 0 ? (
            <p className="rounded-xl bg-slate-50 p-4 text-xs text-slate-600">
              Abhi tak koi WhatsApp notification log nahi hai — upar opt-in save karke ek test
              preview bhejein!
            </p>
          ) : (
            <div className="space-y-2">
              {logs.map((entry) => {
                const statusInfo = formatNotificationStatus(entry.status);
                return (
                  <div
                    key={entry.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/70 px-3.5 py-2.5 text-xs"
                  >
                    <div className="min-w-0 space-y-0.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-slate-900">
                          {formatTemplateLabel(entry.template_name)}
                        </span>
                        <Badge variant="outline">{entry.direction}</Badge>
                        <Badge variant={mapToneToBadgeVariant(statusInfo.tone)}>
                          {statusInfo.label}
                        </Badge>
                      </div>
                      <p className="text-[11px] text-slate-500">
                        To: {entry.recipient_phone}
                        {entry.deep_link ? ` · Link: ${entry.deep_link}` : ""}
                      </p>
                      {entry.error_message && (
                        <p className="text-[11px] text-rose-700">Error: {entry.error_message}</p>
                      )}
                    </div>
                    <span className="text-[11px] text-slate-500 shrink-0">
                      {formatMessageTime(entry.created_at)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          <div className="mt-4 flex items-center gap-2 rounded-xl border border-[#0f766e]/15 bg-[#f0f7f4]/60 px-3.5 py-2.5 text-[11px] text-[#115e59]">
            <ShieldCheck className="h-4 w-4 shrink-0" />
            <span>
              FitSoul AI WhatsApp channel sirf approved notifications aur deep links bhejta hai;
              full AI coaching, meal plans, aur workouts isi PWA mein available hain.
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
