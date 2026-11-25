import { createClient, type SupabaseClient } from "@supabase/supabase-js";

export type AuthMode = "supabase" | "local";

export interface AuthUser {
  id: string;
  email: string;
  fullName: string;
  mode: AuthMode;
}

const LOCAL_SESSION_KEY = "fitsoul_local_session_v1";
let cachedSupabaseClient: SupabaseClient | null = null;

export function isSupabaseConfigured(): boolean {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() ?? "";
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim() ?? "";
  return Boolean(url && anonKey);
}

export function getSupabaseClient(): SupabaseClient | null {
  if (!isSupabaseConfigured()) {
    return null;
  }
  if (cachedSupabaseClient === null) {
    cachedSupabaseClient = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!.trim(),
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!.trim(),
    );
  }
  return cachedSupabaseClient;
}

export function deriveLocalUserId(email: string): string {
  const slug = email
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `local-${slug || "guest"}`;
}

export function loadLocalSession(): AuthUser | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(LOCAL_SESSION_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<AuthUser>;
    if (
      typeof parsed.id === "string" &&
      typeof parsed.email === "string" &&
      typeof parsed.fullName === "string"
    ) {
      return {
        id: parsed.id,
        email: parsed.email,
        fullName: parsed.fullName,
        mode: "local",
      };
    }
    return null;
  } catch {
    return null;
  }
}

export function saveLocalSession(user: AuthUser): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(LOCAL_SESSION_KEY, JSON.stringify(user));
  } catch {
    // Ignore storage quota or private browsing errors cleanly.
  }
}

export function clearLocalSession(): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.removeItem(LOCAL_SESSION_KEY);
  } catch {
    // Ignore storage removal errors cleanly.
  }
}
