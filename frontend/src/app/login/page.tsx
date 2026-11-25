"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, CheckCircle2, HeartPulse, Lock, Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";

export default function LoginPage() {
  const router = useRouter();
  const { authMode, signInLocal, sendSupabaseMagicLink } = useAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [magicLinkSent, setMagicLinkSent] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const trimmedEmail = email.trim();
    if (!trimmedEmail || !trimmedEmail.includes("@")) {
      setError("Please enter a valid email address (sahi email likhein).");
      return;
    }

    setSubmitting(true);
    try {
      if (authMode === "supabase") {
        await sendSupabaseMagicLink(trimmedEmail);
        setMagicLinkSent(true);
      } else {
        const profile = await signInLocal(trimmedEmail, fullName);
        router.push(profile ? "/" : "/onboarding");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in right now.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#0f766e] text-white shadow-sm">
            <HeartPulse className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Assalam o alaikum! Welcome to FitSoul AI
          </h1>
          <p className="text-sm text-slate-600">
            Aap ka 24/7 desi AI nutritionist, fitness coach, aur emotional wellness companion.
          </p>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-2">
              <CardTitle>Sign in to continue</CardTitle>
              <Badge variant={authMode === "supabase" ? "teal" : "amber"}>
                <Lock className="h-3 w-3" />
                {authMode === "supabase" ? "Supabase Auth" : "Local Dev Mode"}
              </Badge>
            </div>
            <CardDescription>
              {authMode === "supabase"
                ? "Enter your email to receive a passwordless magic link."
                : "Instant sign-in synced with your FastAPI backend profile."}
            </CardDescription>
          </CardHeader>

          <CardContent>
            {magicLinkSent ? (
              <div className="rounded-xl border border-[#0f766e]/20 bg-[#f0f7f4] p-4 text-sm text-[#115e59] space-y-2">
                <div className="flex items-center gap-2 font-semibold">
                  <CheckCircle2 className="h-4 w-4" />
                  <span>Magic link bhej diya gaya hai!</span>
                </div>
                <p>
                  Apne inbox (<strong>{email}</strong>) mein link par click kar ke FitSoul AI open
                  karein.
                </p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                {authMode === "local" && (
                  <div>
                    <Label htmlFor="full-name">Full Name</Label>
                    <Input
                      id="full-name"
                      type="text"
                      placeholder="e.g. Aymen"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      required
                    />
                  </div>
                )}

                <div>
                  <Label htmlFor="email">Email Address</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="aymen@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>

                {error && (
                  <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                    {error}
                  </p>
                )}

                <Button type="submit" size="lg" className="w-full" disabled={submitting}>
                  {submitting
                    ? "Connecting..."
                    : authMode === "supabase"
                      ? "Send Magic Link"
                      : "Continue to FitSoul AI"}
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </form>
            )}

            <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1">
                <Sparkles className="h-3.5 w-3.5 text-[#0f766e]" />
                History saved across devices
              </span>
              <Link href="/" className="font-medium text-[#0f766e] hover:underline">
                Back to overview
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
