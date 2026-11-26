"use client";

import Link from "next/link";
import {
  ArrowRight,
  BellRing,
  Camera,
  Check,
  Crown,
  Dumbbell,
  HeartPulse,
  MessageCircleHeart,
  ShieldCheck,
  Sparkles,
  Utensils,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const AUDIENCE_SEGMENTS = [
  {
    title: "PCOS & Hormonal Balance",
    desc: "Low-GI desi meal rules, high protein/fiber targets, aur hormone-friendly low-impact workouts.",
  },
  {
    title: "Brides & Grooms (90-Day)",
    desc: "Safe calorie roadmap + Face Yoga posture routines bina crash diet ke healthy glow ke liye.",
  },
  {
    title: "Busy Desk Professionals",
    desc: "Ghar ke khane (roti, daal, salan) ke exact portions aur 15-min zero-equipment home routines.",
  },
  {
    title: "Type-2 Diabetes & High BP",
    desc: "Per-meal carbohydrate caps, strict sodium limits, aur refined sugar guardrails built in.",
  },
  {
    title: "Overseas Pakistanis",
    desc: "Multi-timezone coaching (UK, UAE, KSA) + Pakistani + USDA foods aur global card checkout.",
  },
];

const FEATURE_PILLARS = [
  {
    icon: ShieldCheck,
    title: "Deterministic Clinical Math",
    desc: "Mifflin-St Jeor BMR/TDEE aur hard safety floors (female >= 1200 kcal, male >= 1500 kcal) Python code compute karta hai — AI kabhi calories nahi guess karta.",
  },
  {
    icon: Camera,
    title: "165+ Pakistani Food DB + Vision",
    desc: "Roti, daal, biryani, aur karahi se verified macro calculation aur Gemini Vision meal photo scanner with Roman Urdu item confirmation.",
  },
  {
    icon: MessageCircleHeart,
    title: "24/7 Empathetic AI Coach",
    desc: "Roman Urdu aur English mein bina guilt ke craving swaps, dawat strategies, long-term memory, aur emotional pattern nudges.",
  },
  {
    icon: Dumbbell,
    title: "Workouts & Face Yoga Studio",
    desc: "Knee-, back-, aur neck-friendly guided timer routines, voice cues, 'too hard' swap button, aur deterministic MET calorie burn.",
  },
  {
    icon: BellRing,
    title: "Proactive WhatsApp Reminders",
    desc: "Aap ke timezone aur sleep quiet hours ke mutabiq approved WhatsApp meal, water, workout & weekly report alerts with PWA deep links.",
  },
];

const PRICING_TIERS = [
  {
    name: "Free Trial",
    price: "Free / 7 days",
    highlight: false,
    bullets: ["Full Pro AI Coach & Photo Scanner", "7-Day Desi Meal Plan & Grocery List", "Workouts, Face Yoga & Reminders"],
  },
  {
    name: "Basic",
    price: "Rs. 1,499 / mo",
    highlight: false,
    bullets: ["7-Day Personalized Desi Meal Plan", "5 AI Coach turns/day + text logging", "WhatsApp meal & water reminders"],
  },
  {
    name: "Pro",
    price: "Rs. 2,999 / mo",
    highlight: true,
    bullets: ["Unlimited AI Coach + Photo Scanner", "Workouts & Face Yoga Timer Studio", "Weekly AI Report & Pattern Nudges"],
  },
  {
    name: "Transformation",
    price: "Rs. 6,999 / 3 mos",
    highlight: false,
    bullets: ["Full Pro locked for 90 days", "Goal-deadline milestone tracking", "Save Rs. 1,998 vs monthly"],
  },
  {
    name: "Overseas",
    price: "$9.99 / mo",
    highlight: false,
    bullets: ["Full Pro for international timezones", "Pakistani + USDA catalog", "LemonSqueezy / Card / Apple Pay"],
  },
];

export default function WelcomePage() {
  const [referralCode, setReferralCode] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ref = params.get("ref")?.trim();
    if (ref) {
      setReferralCode(ref);
    }
  }, []);

  return (
    <div className="min-h-screen bg-[#fafaf7] text-slate-900">
      {/* Top Navbar */}
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3.5 md:px-8">
          <Link href="/welcome" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#0f766e] text-white shadow-sm">
              <HeartPulse className="h-5 w-5" />
            </div>
            <div>
              <span className="text-base font-bold tracking-tight text-slate-900">FitSoul AI</span>
              <span className="hidden text-xs text-slate-500 sm:inline"> · South Asian Wellness</span>
            </div>
          </Link>

          <nav className="hidden items-center gap-6 text-sm font-medium text-slate-600 md:flex">
            <a href="#features" className="hover:text-[#0f766e]">
              Features
            </a>
            <a href="#pricing" className="hover:text-[#0f766e]">
              Pricing
            </a>
            <a href="#safety" className="hover:text-[#0f766e]">
              Clinical Safety
            </a>
          </nav>

          <div className="flex items-center gap-2">
            <Link href="/login">
              <Button variant="ghost" size="sm">
                Sign In
              </Button>
            </Link>
            <Link href="/login">
              <Button size="sm">
                Start 7-Day Free Trial
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-16 px-4 py-10 md:px-8 md:py-14">
        {/* Optional Referral Invite Banner */}
        {referralCode && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#0f766e]/25 bg-[#f0f7f4] px-5 py-3.5 text-sm text-[#115e59]">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 shrink-0" />
              <span>
                You were invited with referral code{" "}
                <strong className="font-mono">{referralCode}</strong> — start your{" "}
                <strong>7-Day Free Trial</strong> today!
              </span>
            </div>
            <Link href="/login">
              <Button size="sm">Claim Trial</Button>
            </Link>
          </div>
        )}

        {/* Hero Section */}
        <section className="rounded-3xl border border-[#0f766e]/15 bg-gradient-to-br from-white via-white to-[#f0f7f4] p-7 shadow-sm md:p-12">
          <div className="max-w-3xl space-y-5">
            <Badge variant="teal">
              <Sparkles className="h-3.5 w-3.5" />
              Pakistan&apos;s Culturally-Aware AI Nutrition &amp; Fitness Companion
            </Badge>
            <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-5xl sm:leading-tight">
              Apne ghar ke khane (roti, daal, sabzi) ke sath fit rahein — bina crash diet ke.
            </h1>
            <p className="text-base leading-relaxed text-slate-600 sm:text-lg">
              Clinical BMR/TDEE math, 165+ verified Pakistani foods, Roman Urdu &amp; English AI
              coaching, joint-safe workouts &amp; Face Yoga, aur proactive WhatsApp reminders —
              all inside one fast PWA.
            </p>
            <div className="flex flex-wrap items-center gap-3 pt-1">
              <Link href="/login">
                <Button size="lg">
                  Start Free 7-Day Trial
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link href="/">
                <Button variant="outline" size="lg">
                  <Utensils className="h-4 w-4" />
                  Open App Dashboard
                </Button>
              </Link>
            </div>
          </div>
        </section>

        {/* Built For Section */}
        <section className="space-y-5">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">
              Kis Ke Liye Banaya Gaya Hai?
            </h2>
            <p className="text-sm text-slate-600">
              Condition-aware rules engines har user ki body aur lifestyle ke mutabiq plan adapt
              karte hain.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {AUDIENCE_SEGMENTS.map((seg) => (
              <Card key={seg.title} className="h-full">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">{seg.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-xs leading-relaxed text-slate-600">{seg.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        {/* Feature Pillars */}
        <section id="features" className="space-y-5">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">
              5 Core FitSoul AI Pillars
            </h2>
            <p className="text-sm text-slate-600">
              AI creativity + Python clinical guardrails — zero hallucinated calories or unsafe
              prescriptions.
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {FEATURE_PILLARS.map(({ icon: Icon, title, desc }) => (
              <Card key={title} className="h-full">
                <CardHeader className="pb-2">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#f0f7f4] text-[#0f766e]">
                    <Icon className="h-5 w-5" />
                  </div>
                  <CardTitle className="pt-2 text-base">{title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-xs leading-relaxed text-slate-600">{desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        {/* Pricing Section */}
        <section id="pricing" className="space-y-5">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-slate-900">
                Simple Pakistani &amp; Overseas Pricing
              </h2>
              <p className="text-sm text-slate-600">
                Start with a 7-day Free Trial — upgrade via JazzCash, Easypaisa, Safepay, PayFast,
                or LemonSqueezy.
              </p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {["JazzCash", "Easypaisa", "Safepay", "PayFast", "LemonSqueezy"].map((gw) => (
                <Badge key={gw} variant="outline">
                  {gw}
                </Badge>
              ))}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-5">
            {PRICING_TIERS.map((tier) => (
              <Card
                key={tier.name}
                className={tier.highlight ? "border-[#0f766e] shadow-sm" : "h-full"}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-base">{tier.name}</CardTitle>
                    {tier.highlight && (
                      <Badge variant="teal">
                        <Crown className="h-3 w-3" />
                        Popular
                      </Badge>
                    )}
                  </div>
                  <CardDescription className="text-sm font-bold text-[#0f766e]">
                    {tier.price}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-xs text-slate-600">
                  {tier.bullets.map((b) => (
                    <div key={b} className="flex items-start gap-1.5">
                      <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#0f766e]" />
                      <span>{b}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        {/* Safety & Legal Trust Section */}
        <section
          id="safety"
          className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-amber-200 bg-amber-50/50 p-6"
        >
          <div className="max-w-2xl space-y-1">
            <h3 className="text-base font-bold text-slate-900">
              Clinical Safety &amp; Medical Disclaimer
            </h3>
            <p className="text-xs leading-relaxed text-slate-700">
              FitSoul AI enforces hard calorie floors (female &ge; 1200 kcal, male &ge; 1500 kcal),
              blocks prescription medicines, disables supplements for high-risk profiles, and is
              never a substitute for licensed medical care.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/legal">
              <Button variant="outline" size="sm">
                Privacy, Terms &amp; Data Delete
              </Button>
            </Link>
            <Link href="/billing">
              <Button size="sm">View Billing Plans</Button>
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}
