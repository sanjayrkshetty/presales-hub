"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore, type AuthUser } from "@/lib/auth/session";
import { apiFetch } from "@/lib/api/client";

type LoginTokenResp = { access_token: string };

async function fetchMe(token: string): Promise<AuthUser> {
  return apiFetch<AuthUser>("/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function useAuth() {
  const { user, accessToken, isLoading, setSession, clearSession } = useAuthStore();
  const router = useRouter();

  const login = useCallback(async (email: string, password: string) => {
    const data = await apiFetch<LoginTokenResp>("/auth/login", {
      method:      "POST",
      body:        JSON.stringify({ email, password }),
      credentials: "include",
    });
    const me = await fetchMe(data.access_token);
    setSession(me, data.access_token);
    router.push("/");
  }, [setSession, router]);

  const logout = useCallback(async () => {
    await apiFetch("/auth/logout", { method: "POST", credentials: "include" }).catch(() => {});
    clearSession();
    router.push("/login");
  }, [clearSession, router]);

  const refreshSession = useCallback(async (): Promise<string | null> => {
    try {
      const data = await apiFetch<LoginTokenResp>("/auth/refresh", {
        method:      "POST",
        credentials: "include",
      });
      const me = await fetchMe(data.access_token);
      setSession(me, data.access_token);
      return data.access_token;
    } catch {
      clearSession();
      return null;
    }
  }, [setSession, clearSession]);

  return {
    user,
    accessToken,
    isLoading,
    isAuthenticated: !!user,
    login,
    logout,
    refreshSession,
  };
}
