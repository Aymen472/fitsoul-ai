"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  CreditCard,
  Crown,
  Lock,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label, Select } from "@/components/ui/input";
import {
  ApiError,
  cancelUserSubscription,
  confirmSandboxPayment,
  createBillingCheckout,
  getBillingPlans,
  getBillingStatus,
  startFreeTrial,
  type BillingStatusResponse,
  type CheckoutResponse,
  type PaymentProvider,
  type PlanDefinition,
  type PlanId,
} from "@/lib/api";
import {
  formatAccessModeBadge,
  formatPlanPrice,
  formatProviderLabel,
  formatTransactionStatus,
} from "@/lib/billing-helpers";
import { formatMessageTime } from "@/lib/chat-helpers";

function resolvePlanDisplayName(planId: string | undefined, plans: PlanDefinition[]): string {
  if (!planId) {
    return "Free / Limited Tier";
  }
  const match = plans.find((p) => p.id === planId);
  return match ? match.name : planId;
}

export default function BillingPage() {
  const { user, profileRecord, isLoading, isProfileLoading } = useAuth();

  const [plans, setPlans] = useState<PlanDefinition[]>([]);
  const [billingStatus, setBillingStatus] = useState<BillingStatusResponse | null>(null);
  const [selectedProviders, setSelectedProviders] = useState<Record<string, PaymentProvider>>({});
  const [activeCheckout, setActiveCheckout] = useState<CheckoutResponse | null>(null);

  const [loadingPage, setLoadingPage] = useState(false);
  const [submittingAction, setSubmittingAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const loadBillingWorkspace = useCallback(async (userId: string) => {
    setLoadingPage(true);
    setError(null);
    const [plansRes, statusRes] = await Promise.allSettled([
      getBillingPlans(),
      getBillingStatus(userId),
    ]);

    if (plansRes.status === "fulfilled") {
      setPlans(plansRes.value);
      setSelectedProviders((prev) => {
        const next = { ...prev };
        for (const plan of plansRes.value) {
          if (!next[plan.id] && plan.supported_providers.length > 0) {
            next[plan.id] = plan.supported_providers[0];
          }
        }
        return next;
      });
    } else {
      const err = plansRes.reason;
      setError(
        err instanceof ApiError
          ? err.detail
          : "Subscription plans load nahi ho sake — FastAPI backend check karein.",
      );
    }

    if (statusRes.status === "fulfilled") {
      setBillingStatus(statusRes.value);
    } else {
      const err = statusRes.reason;
      setError(
        err instanceof ApiError
          ? err.detail
          : "Subscription status load nahi ho saka — FastAPI backend check karein.",
      );
    }

    setLoadingPage(false);
  }, []);

  useEffect(() => {
    if (!user || !profileRecord) {
      return;
    }
    void loadBillingWorkspace(user.id);
  }, [user, profileRecord, loadBillingWorkspace]);

  const handleStartTrial = async () => {
    if (!user) {
      return;
    }
    setSubmittingAction("trial");
    setError(null);
    setSuccessMessage(null);
    try {
      await startFreeTrial(user.id);
      setSuccessMessage("Aap ka 7-day Free Trial active ho gaya hai — full FitSoul AI enjoy karein!");
      await loadBillingWorkspace(user.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Free trial start nahi ho saka.");
    } finally {
      setSubmittingAction(null);
    }
  };

  const handleCreateCheckout = async (planId: PlanId) => {
    if (!user) {
      return;
    }
    const plan = plans.find((p) => p.id === planId);
    const provider = selectedProviders[planId] ?? plan?.supported_providers[0] ?? "safepay";

    setSubmittingAction(`checkout:${planId}`);
    setError(null);
    setSuccessMessage(null);
    try {
      const res = await createBillingCheckout(user.id, { plan_id: planId, provider });
      setActiveCheckout(res);
      setSuccessMessage(
        `Order ${res.transaction.provider_order_id} (${formatProviderLabel(provider)}) create ho gaya hai.`,
      );
      await loadBillingWorkspace(user.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Checkout session start nahi ho saka.");
    } finally {
      setSubmittingAction(null);
    }
  };

  const handleConfirmSandboxPayment = async () => {
    if (!user || !activeCheckout) {
      return;
    }
    setSubmittingAction("confirm");
    setError(null);
    setSuccessMessage(null);
    try {
      const ack = await confirmSandboxPayment(
        activeCheckout.transaction.provider as PaymentProvider,
        {
          order_id: activeCheckout.transaction.provider_order_id,
          event: "payment.succeeded",
          provider_reference: `sbx_${Date.now()}`,
        },
      );
      setActiveCheckout(null);
      setSuccessMessage(
        `Payment verified! ${resolvePlanDisplayName(ack.subscription?.plan, plans)} ab active hai.`,
      );
      await loadBillingWorkspace(user.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Sandbox payment webhook verify nahi ho saka.");
    } finally {
      setSubmittingAction(null);
    }
  };

  const handleCancelSubscription = async () => {
    if (!user) {
      return;
    }
    setSubmittingAction("cancel");
    setError(null);
    setSuccessMessage(null);
    try {
      await cancelUserSubscription(user.id);
      setSuccessMessage("Subscription cancel ho gayi hai. Account ab limited mode par hai.");
      await loadBillingWorkspace(user.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Subscription cancel nahi ho saki.");
    } finally {
      setSubmittingAction(null);
    }
  };

  if (!isLoading && !user) {
    return (
      <Card className="mx-auto max-w-lg">
        <CardHeader>
          <CardTitle>Sign in to manage Subscription &amp; Billing</CardTitle>
          <CardDescription>
            Apna 7-day free trial start karne ya JazzCash, Easypaisa, Safepay, PayFast, ya
            LemonSqueezy se upgrade karne ke liye sign in karein.
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
            Plan aur WhatsApp renewal alerts setup karne ke liye pehle apni health profile save
            karein.
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

  const sub = billingStatus?.subscription ?? null;
  const entitlements = billingStatus?.entitlements ?? null;
  const badgeInfo = entitlements ? formatAccessModeBadge(entitlements) : null;
  const paidPlans = plans.filter((p) => p.id !== "trial");
  const transactions = billingStatus?.transactions ?? [];

  return (
    <div className="space-y-6">
      {/* Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0f766e] text-white shadow-sm">
            <CreditCard className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              Subscription &amp; Billing
            </h1>
            <p className="text-xs text-slate-600">
              7-day Free Trial, JazzCash / Easypaisa / Safepay / PayFast (PKR), aur LemonSqueezy
              (USD)
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {badgeInfo && <Badge variant={badgeInfo.variant}>{badgeInfo.label}</Badge>}
          <Button
            variant="outline"
            size="sm"
            disabled={loadingPage || !user}
            onClick={() => user && void loadBillingWorkspace(user.id)}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loadingPage ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Inline Feedback Banners */}
      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {error}
        </div>
      )}
      {successMessage && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {/* Current Subscription & Entitlements Card */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base">
                Current Plan: {resolvePlanDisplayName(sub?.plan, plans)}
              </CardTitle>
              <CardDescription className="text-xs">
                {entitlements?.is_active
                  ? `${entitlements.days_remaining} day(s) remaining${sub?.provider ? ` · via ${formatProviderLabel(sub.provider)}` : ""}`
                  : "Abhi aap Limited Mode par hain — neeche se 7-day trial ya paid plan select karein."}
              </CardDescription>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {billingStatus?.trial_eligible && (
                <Button
                  size="sm"
                  disabled={submittingAction === "trial"}
                  onClick={() => void handleStartTrial()}
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  {submittingAction === "trial" ? "Activating..." : "Start 7-Day Free Trial"}
                </Button>
              )}
              {sub && entitlements?.is_active && (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={submittingAction === "cancel"}
                  onClick={() => void handleCancelSubscription()}
                >
                  {submittingAction === "cancel" ? "Cancelling..." : "Cancel Plan"}
                </Button>
              )}
            </div>
          </div>
        </CardHeader>

        {entitlements && (
          <CardContent className="space-y-3">
            {entitlements.renewal_due_soon && (
              <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-xs text-amber-900">
                <AlertTriangle className="h-4 w-4 shrink-0 text-amber-700" />
                <span>
                  Aap ka plan {entitlements.days_remaining} din mein expire ho raha hai — early
                  renewal par aap ke baki din extend ho jayenge!
                </span>
              </div>
            )}

            <div className="flex flex-wrap gap-2">
              {[
                {
                  label:
                    entitlements.daily_chat_limit === null
                      ? "AI Chat: Unlimited"
                      : `AI Chat: ${entitlements.daily_chat_limit}/day`,
                  enabled: entitlements.can_use_ai_chat,
                },
                {
                  label: "Meal Photo Scanner",
                  enabled: entitlements.can_use_photo_scanner,
                },
                {
                  label: "Workouts & Face Yoga",
                  enabled: entitlements.can_use_workouts_face_yoga,
                },
                {
                  label: "Weekly Meal Plan",
                  enabled: entitlements.can_use_weekly_meal_plan,
                },
                {
                  label: "WhatsApp Reminders",
                  enabled: entitlements.can_use_whatsapp_reminders,
                },
              ].map((chip) => (
                <Badge key={chip.label} variant={chip.enabled ? "teal" : "outline"}>
                  {chip.enabled ? (
                    <Check className="h-3 w-3" />
                  ) : (
                    <Lock className="h-3 w-3 text-slate-400" />
                  )}
                  {chip.label}
                </Badge>
              ))}
            </div>
          </CardContent>
        )}
      </Card>

      {/* Sandbox Checkout Completion Banner */}
      {activeCheckout && (
        <Card className="border-[#0f766e]/30 bg-[#f0f7f4]/70">
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle className="text-base text-[#115e59]">
                  Checkout Ready: {formatProviderLabel(activeCheckout.transaction.provider)}
                </CardTitle>
                <CardDescription className="text-xs text-[#115e59]/80">
                  Order ID:{" "}
                  <span className="font-mono font-semibold">
                    {activeCheckout.transaction.provider_order_id}
                  </span>{" "}
                  · Amount:{" "}
                  {activeCheckout.transaction.currency === "USD"
                    ? `$${activeCheckout.transaction.amount.toFixed(2)}`
                    : `Rs. ${activeCheckout.transaction.amount.toLocaleString("en-US")}`}
                </CardDescription>
              </div>
              <Badge variant="amber">
                {activeCheckout.sandbox_mode ? "Sandbox Mode" : "Live Gateway"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 text-xs">
            <p className="text-slate-700">{activeCheckout.instructions}</p>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="truncate font-mono text-[11px] text-slate-500">
                Checkout URL: {activeCheckout.checkout_url}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  disabled={submittingAction === "confirm"}
                  onClick={() => void handleConfirmSandboxPayment()}
                >
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  {submittingAction === "confirm"
                    ? "Verifying..."
                    : "Complete Sandbox Payment (Webhook)"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setActiveCheckout(null)}
                >
                  Dismiss
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Paid Plans Grid */}
      <div className="grid gap-4 md:grid-cols-2">
        {paidPlans.map((plan) => {
          const selectedProvider =
            selectedProviders[plan.id] ?? plan.supported_providers[0] ?? "safepay";
          const isCurrentPlan =
            sub?.plan === plan.id && Boolean(entitlements?.is_active);
          return (
            <Card
              key={plan.id}
              className={plan.is_popular ? "border-[#0f766e] shadow-sm" : undefined}
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <CardTitle className="text-base">{plan.name}</CardTitle>
                      {plan.is_popular && (
                        <Badge variant="teal">
                          <Crown className="h-3 w-3" />
                          Popular
                        </Badge>
                      )}
                      {isCurrentPlan && <Badge variant="amber">Current</Badge>}
                    </div>
                    <CardDescription className="mt-1 text-xs">{plan.tagline}</CardDescription>
                  </div>
                  <p className="text-sm font-bold text-[#0f766e] shrink-0">
                    {formatPlanPrice(plan.price_amount, plan.currency, plan.duration_days)}
                  </p>
                </div>
              </CardHeader>

              <CardContent className="space-y-4">
                <ul className="space-y-1.5 text-xs text-slate-700">
                  {plan.features.map((feat) => (
                    <li key={feat} className="flex items-start gap-2">
                      <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#0f766e]" />
                      <span>{feat}</span>
                    </li>
                  ))}
                </ul>

                <div className="space-y-2 border-t border-slate-100 pt-3">
                  <div>
                    <Label htmlFor={`provider-${plan.id}`} className="text-xs">
                      Payment Method
                    </Label>
                    <Select
                      id={`provider-${plan.id}`}
                      value={selectedProvider}
                      onChange={(e) =>
                        setSelectedProviders((prev) => ({
                          ...prev,
                          [plan.id]: e.target.value as PaymentProvider,
                        }))
                      }
                    >
                      {plan.supported_providers.map((prov) => (
                        <option key={prov} value={prov}>
                          {formatProviderLabel(prov)}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <Button
                    type="button"
                    variant={plan.is_popular ? "primary" : "outline"}
                    size="sm"
                    className="w-full"
                    disabled={submittingAction === `checkout:${plan.id}`}
                    onClick={() => void handleCreateCheckout(plan.id)}
                  >
                    <CreditCard className="h-3.5 w-3.5" />
                    {submittingAction === `checkout:${plan.id}`
                      ? "Creating Checkout..."
                      : isCurrentPlan
                        ? "Extend / Renew Plan"
                        : `Subscribe with ${formatProviderLabel(selectedProvider)}`}
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Payment History List */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-base">Payment History</CardTitle>
            <Badge variant="outline">{transactions.length} order(s)</Badge>
          </div>
          <CardDescription className="text-xs">
            Safepay, PayFast, JazzCash, Easypaisa, aur LemonSqueezy checkout transactions.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {transactions.length === 0 ? (
            <p className="rounded-xl bg-slate-50 p-4 text-xs text-slate-600">
              Abhi tak koi payment transaction nahi hui — 7-day trial ya upar koi plan choose karein.
            </p>
          ) : (
            <div className="space-y-2">
              {transactions.map((tx) => {
                const statusBadge = formatTransactionStatus(tx.status);
                return (
                  <div
                    key={tx.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/70 px-3.5 py-2.5 text-xs"
                  >
                    <div className="min-w-0 space-y-0.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-slate-900">
                          {resolvePlanDisplayName(tx.plan, plans)}
                        </span>
                        <Badge variant="outline">{formatProviderLabel(tx.provider)}</Badge>
                        <Badge variant={statusBadge.variant}>{statusBadge.label}</Badge>
                      </div>
                      <p className="text-[11px] text-slate-500">
                        Order: <span className="font-mono">{tx.provider_order_id}</span> ·{" "}
                        {tx.currency === "USD"
                          ? `$${tx.amount.toFixed(2)}`
                          : `Rs. ${tx.amount.toLocaleString("en-US")}`}
                      </p>
                    </div>
                    <span className="text-[11px] text-slate-500 shrink-0">
                      {formatMessageTime(tx.created_at)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          <div className="mt-4 flex items-center gap-2 rounded-xl border border-[#0f766e]/15 bg-[#f0f7f4]/60 px-3.5 py-2.5 text-[11px] text-[#115e59]">
            <ShieldCheck className="h-4 w-4 shrink-0" />
            <span>
              Plan expiration se 3 din pehle WhatsApp renewal reminder bheja jata hai (Settings{" "}
              <Link href="/notifications" className="underline font-semibold">
                Reminders
              </Link>{" "}
              par manage karein).
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
