"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { ApiError, getProfile, type ProfileRecord } from "@/lib/api";
import {
  clearLocalSession,
  deriveLocalUserId,
  getSupabaseClient,
  isSupabaseConfigured,
  loadLocalSession,
  saveLocalSession,
  type AuthMode,
  type AuthUser,
} from "@/lib/auth";

interface AuthContextValue {
  user: AuthUser | null;
  profileRecord: ProfileRecord | null;
  isLoading: boolean;
  isProfileLoading: boolean;
  authMode: AuthMode;
  signInLocal: (email: string, fullName: string) => Promise<ProfileRecord | null>;
  sendSupabaseMagicLink: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshProfile: (overrideUserId?: string) => Promise<ProfileRecord | null>;
  setProfileRecord: (record: ProfileRecord | null) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [profileRecord, setProfileRecord] = useState<ProfileRecord | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isProfileLoading, setIsProfileLoading] = useState(false);

  const authMode: AuthMode = isSupabaseConfigured() ? "supabase" : "local";

  const refreshProfile = useCallback(
    async (overrideUserId?: string): Promise<ProfileRecord | null> => {
      const targetId = overrideUserId ?? user?.id;
      if (!targetId) {
        setProfileRecord(null);
        return null;
      }

      setIsProfileLoading(true);
      try {
        const fetched = await getProfile(targetId);
        setProfileRecord(fetched);
        return fetched;
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setProfileRecord(null);
          return null;
        }
        return null;
      } finally {
        setIsProfileLoading(false);
      }
    },
    [user?.id],
  );

  useEffect(() => {
    const supabase = getSupabaseClient();
    if (!supabase) {
      const localUser = loadLocalSession();
      setUser(localUser);
      if (localUser) {
        void refreshProfile(localUser.id).finally(() => setIsLoading(false));
      } else {
        setIsLoading(false);
      }
      return;
    }

    let mounted = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) {
        return;
      }
      const supaUser = data.session?.user;
      if (supaUser) {
        const mapped: AuthUser = {
          id: supaUser.id,
          email: supaUser.email ?? "",
          fullName:
            (typeof supaUser.user_metadata?.full_name === "string"
              ? supaUser.user_metadata.full_name
              : supaUser.email?.split("@")[0]) ?? "Member",
          mode: "supabase",
        };
        setUser(mapped);
        void refreshProfile(mapped.id).finally(() => {
          if (mounted) {
            setIsLoading(false);
          }
        });
      } else {
        setUser(null);
        setProfileRecord(null);
        setIsLoading(false);
      }
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      const supaUser = session?.user;
      if (supaUser) {
        const mapped: AuthUser = {
          id: supaUser.id,
          email: supaUser.email ?? "",
          fullName:
            (typeof supaUser.user_metadata?.full_name === "string"
              ? supaUser.user_metadata.full_name
              : supaUser.email?.split("@")[0]) ?? "Member",
          mode: "supabase",
        };
        setUser(mapped);
        void refreshProfile(mapped.id);
      } else {
        setUser(null);
        setProfileRecord(null);
      }
    });

    return () => {
      mounted = false;
      listener.subscription.unsubscribe();
    };
  }, [refreshProfile]);

  const signInLocal = useCallback(
    async (email: string, fullName: string): Promise<ProfileRecord | null> => {
      const cleanEmail = email.trim().toLowerCase();
      const cleanName = fullName.trim() || cleanEmail.split("@")[0] || "FitSoul Member";
      const localUser: AuthUser = {
        id: deriveLocalUserId(cleanEmail),
        email: cleanEmail,
        fullName: cleanName,
        mode: "local",
      };
      saveLocalSession(localUser);
      setUser(localUser);
      return refreshProfile(localUser.id);
    },
    [refreshProfile],
  );

  const sendSupabaseMagicLink = useCallback(async (email: string): Promise<void> => {
    const supabase = getSupabaseClient();
    if (!supabase) {
      throw new Error("Supabase is not configured");
    }
    const redirectTo =
      typeof window !== "undefined" ? `${window.location.origin}/onboarding` : undefined;
    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { emailRedirectTo: redirectTo },
    });
    if (error) {
      throw new Error(error.message);
    }
  }, []);

  const signOut = useCallback(async (): Promise<void> => {
    const supabase = getSupabaseClient();
    if (supabase) {
      await supabase.auth.signOut();
    }
    clearLocalSession();
    setUser(null);
    setProfileRecord(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        profileRecord,
        isLoading,
        isProfileLoading,
        authMode,
        signInLocal,
        sendSupabaseMagicLink,
        signOut,
        refreshProfile,
        setProfileRecord,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside an AuthProvider");
  }
  return ctx;
}
