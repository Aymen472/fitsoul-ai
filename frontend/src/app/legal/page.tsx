"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FileText,
  Lock,
  ShieldCheck,
  Stethoscope,
  Trash2,
} from "lucide-react";
import { useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { summarizeDeletionCount } from "@/lib/admin-helpers";
import { ApiError, deleteUserAccountData, type UserDeletionSummary } from "@/lib/api";

export default function LegalPage() {
  const { user, signOut } = useAuth();
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletionSummary, setDeletionSummary] = useState<UserDeletionSummary | null>(null);

  const handleDeleteAccount = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!user) {
      return;
    }
    if (confirmText.trim().toUpperCase() !== "DELETE") {
      setError("Confirmation ke liye exact 'DELETE' type karein.");
      return;
    }

    setDeleting(true);
    setError(null);
    try {
      const summary = await deleteUserAccountData(user.id);
      setDeletionSummary(summary);
      setConfirmText("");
      await signOut();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : "Account data delete nahi ho saka — FastAPI backend check karein.",
      );
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0f766e] text-white shadow-sm">
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              Legal, Privacy &amp; Medical Disclaimer
            </h1>
            <p className="text-xs text-slate-600">
              Clinical safety boundaries, privacy commitments, terms of use, aur data deletion
            </p>
          </div>
        </div>
        <Badge variant="teal">FitSoul AI Trust Center</Badge>
      </div>

      {/* 1. Medical Disclaimer */}
      <Card className="border-amber-200 bg-amber-50/30">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Stethoscope className="h-4 w-4 text-amber-700" />
            <CardTitle className="text-base">1. Medical &amp; Clinical Safety Disclaimer</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-2 text-xs leading-relaxed text-slate-700">
          <p>
            FitSoul AI provides general nutrition, lifestyle coaching, home fitness, and face yoga
            posture guidance. It is <strong>not a licensed medical service</strong> and does not
            diagnose, treat, cure, or prescribe medication.
          </p>
          <ul className="list-disc space-y-1 pl-5">
            <li>
              Strict deterministic calorie safety floors (female &ge; 1200 kcal, male &ge; 1500
              kcal) are enforced regardless of user prompts.
            </li>
            <li>
              High-risk users (Type-1 Diabetes, kidney/liver disease, pregnancy, or regular
              prescription medication) operate in limited doctor-supervised mode with supplement
              suggestions disabled.
            </li>
            <li>
              Always consult a qualified physician or registered dietitian before making major
              dietary or exercise changes.
            </li>
          </ul>
        </CardContent>
      </Card>

      {/* 2 & 3: Privacy & Terms */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Lock className="h-4 w-4 text-[#0f766e]" />
              <CardTitle className="text-base">2. Privacy Policy</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-2 text-xs leading-relaxed text-slate-700">
            <p>
              We store only the health profile, food/water/weight/workout logs, coach chat
              messages, and notification preferences needed to personalize your plan.
            </p>
            <ul className="list-disc space-y-1 pl-5">
              <li>
                Supabase Postgres enforces Row-Level Security (RLS) so each authenticated user can
                access only their own rows.
              </li>
              <li>
                We never sell personal health data or share chat logs with third-party advertisers.
              </li>
              <li>
                WhatsApp notifications require explicit opt-in and pause immediately on{" "}
                <span className="font-mono font-semibold">STOP</span>.
              </li>
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-[#0f766e]" />
              <CardTitle className="text-base">3. Terms of Service</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-2 text-xs leading-relaxed text-slate-700">
            <p>
              FitSoul AI is intended for adults aged 18 and above. You agree to provide accurate
              health disclosures during onboarding.
            </p>
            <ul className="list-disc space-y-1 pl-5">
              <li>
                Every new account is eligible once for a 7-day Free Trial before selecting Basic,
                Pro, Transformation, or Overseas billing tiers.
              </li>
              <li>
                You can cancel your active subscription at any time from{" "}
                <Link href="/billing" className="font-semibold text-[#0f766e] underline">
                  Billing
                </Link>
                , transitioning to limited free mode without surprise charges.
              </li>
            </ul>
          </CardContent>
        </Card>
      </div>

      {/* 4. Data Deletion Request */}
      <Card className="border-rose-200">
        <CardHeader className="pb-3">
          <div className="flex items-center gap-2">
            <Trash2 className="h-4 w-4 text-rose-600" />
            <CardTitle className="text-base text-rose-900">
              4. Account &amp; Data Deletion Request
            </CardTitle>
          </div>
          <CardDescription className="text-xs">
            Apna profile, meal/water/weight logs, workouts, coach chats, memories, notification
            logs, aur billing records hamesha ke liye delete karein.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-xs">
          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-rose-800">
              {error}
            </div>
          )}

          {deletionSummary && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3.5 text-emerald-900 space-y-1.5">
              <div className="flex items-center gap-2 font-semibold">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>
                  Account {deletionSummary.user_id} permanently wiped (
                  {summarizeDeletionCount(deletionSummary.records_removed)} total records removed).
                </span>
              </div>
              <p className="text-[11px] text-emerald-800">
                Aap ka local session bhi sign out kar diya gaya hai.
              </p>
            </div>
          )}

          {user ? (
            <form onSubmit={handleDeleteAccount} className="space-y-3">
              <div className="flex items-start gap-2 rounded-xl bg-rose-50/70 p-3 text-rose-900">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
                <span>
                  Signed in as <strong>{user.email}</strong> (ID:{" "}
                  <span className="font-mono">{user.id}</span>). Yeh action undo nahi ho sakta.
                </span>
              </div>

              <div className="max-w-sm">
                <Label htmlFor="delete-confirm" className="text-xs">
                  Type <span className="font-mono font-bold">DELETE</span> to confirm
                </Label>
                <Input
                  id="delete-confirm"
                  placeholder="DELETE"
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                />
              </div>

              <Button
                type="submit"
                size="sm"
                className="bg-rose-600 text-white hover:bg-rose-700"
                disabled={deleting || confirmText.trim().toUpperCase() !== "DELETE"}
              >
                <Trash2 className="h-3.5 w-3.5" />
                {deleting ? "Deleting All Data..." : "Permanently Delete My Data"}
              </Button>
            </form>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-3.5">
              <p className="text-slate-600">
                Self-service data deletion chalane ke liye apna account sign in hona zaroori hai.
              </p>
              <Link href="/login">
                <Button variant="outline" size="sm">
                  Sign In
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
