"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BellRing,
  CreditCard,
  Dumbbell,
  HeartPulse,
  Home,
  LogIn,
  LogOut,
  MessageCircleHeart,
  UserCheck,
  Utensils,
} from "lucide-react";
import type { ReactNode } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Home", icon: Home },
  { href: "/chat", label: "Coach", icon: MessageCircleHeart },
  { href: "/plan", label: "Meals", icon: Utensils },
  { href: "/workouts", label: "Workouts", icon: Dumbbell },
  { href: "/onboarding", label: "Profile", icon: UserCheck },
];

const DESKTOP_EXTRA_NAV = [
  { href: "/notifications", label: "Reminders", icon: BellRing },
  { href: "/billing", label: "Billing", icon: CreditCard },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, signOut } = useAuth();

  if (pathname === "/login") {
    return (
      <div className="min-h-screen bg-[#fafaf7] text-slate-900">
        {children}
      </div>
    );
  }

  const handleSignOut = async () => {
    await signOut();
    router.push("/login");
  };

  return (
    <div className="flex min-h-screen bg-[#fafaf7] text-slate-900">
      {/* Desktop Sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200/80 bg-white md:flex">
        <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0f766e] text-white shadow-sm">
            <HeartPulse className="h-5 w-5" />
          </div>
          <div>
            <p className="text-base font-bold tracking-tight text-slate-900">FitSoul AI</p>
            <p className="text-xs text-slate-500">Nutrition & Wellness</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {[...NAV_ITEMS, ...DESKTOP_EXTRA_NAV].map(({ href, label, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-[#f0f7f4] text-[#0f766e] font-semibold"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-slate-100 p-4 space-y-3">
          {user ? (
            <div className="rounded-xl bg-slate-50 p-3 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-sm font-semibold text-slate-900">{user.fullName}</p>
                <Badge variant="teal">{user.mode === "supabase" ? "Auth" : "Local"}</Badge>
              </div>
              <p className="truncate text-xs text-slate-500">{user.email}</p>
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={handleSignOut}
              >
                <LogOut className="h-3.5 w-3.5" />
                Sign out
              </Button>
            </div>
          ) : (
            <Link href="/login" className="block">
              <Button variant="primary" size="sm" className="w-full">
                <LogIn className="h-4 w-4" />
                Sign in
              </Button>
            </Link>
          )}
          <p className="text-[11px] leading-relaxed text-slate-400">
            Wellness guidance only — not a substitute for professional medical advice.
          </p>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile Top Bar */}
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200/80 bg-white/95 px-4 py-3 backdrop-blur md:hidden">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#0f766e] text-white">
              <HeartPulse className="h-4 w-4" />
            </div>
            <span className="text-base font-bold text-slate-900">FitSoul AI</span>
          </Link>

          <div className="flex items-center gap-1.5">
            <Link
              href="/notifications"
              aria-label="WhatsApp Reminders"
              className={cn(
                "flex h-9 w-9 items-center justify-center rounded-lg transition-colors",
                pathname === "/notifications"
                  ? "bg-[#f0f7f4] text-[#0f766e]"
                  : "text-slate-600 hover:bg-slate-100",
              )}
            >
              <BellRing className="h-4 w-4" />
            </Link>
            <Link
              href="/billing"
              aria-label="Subscription and Billing"
              className={cn(
                "flex h-9 w-9 items-center justify-center rounded-lg transition-colors",
                pathname === "/billing"
                  ? "bg-[#f0f7f4] text-[#0f766e]"
                  : "text-slate-600 hover:bg-slate-100",
              )}
            >
              <CreditCard className="h-4 w-4" />
            </Link>
            {user ? (
              <Button variant="ghost" size="sm" onClick={handleSignOut}>
                <LogOut className="h-4 w-4" />
                <span className="sr-only sm:not-sr-only">Sign out</span>
              </Button>
            ) : (
              <Link href="/login">
                <Button variant="secondary" size="sm">
                  <LogIn className="h-4 w-4" />
                  Sign in
                </Button>
              </Link>
            )}
          </div>
        </header>

        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6 pb-24 md:px-8 md:py-8 md:pb-8">
          {children}
        </main>
      </div>

      {/* Mobile Bottom Tab Navigation */}
      <nav className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-slate-200 bg-white/95 backdrop-blur md:hidden">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex flex-col items-center justify-center gap-1 py-2.5 text-[11px] font-medium transition-colors",
                active ? "text-[#0f766e] font-semibold" : "text-slate-500 hover:text-slate-800",
              )}
            >
              <Icon className={cn("h-5 w-5", active && "stroke-[2.25]")} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
