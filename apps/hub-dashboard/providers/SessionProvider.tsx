"use client";

import { useEffect, useRef } from "react";
import { useAuthStore } from "@/lib/auth/session";
import { initApiAuth, apiFetch } from "@/lib/api/client";
import type { AuthUser } from "@/lib/auth/session";

type TokenResp = { access_token: string };

// Wires the auth token from the Zustand store into the API client.
// Also attempts a silent token refresh on first mount so the user stays
// logged in across page reloads (refresh cookie is HttpOnly — persists).
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const { setSession, clearSession, setLoading } = useAuthStore();
  const initialised = useRef(false);

  useEffect(() => {
    // Register the token getter once — subsequent apiFetch calls will inject it
    initApiAuth(() => useAuthStore.getState().accessToken);

    if (initialised.current) return;
    initialised.current = true;

    // Silent refresh — if the refresh cookie exists the server will return a new access token.
    // If it fails (no cookie / expired) we stay logged out.
    (async () => {
      try {
        const data = await apiFetch<TokenResp>("/auth/refresh", {
          method:      "POST",
          credentials: "include",
        });
        const me = await apiFetch<AuthUser>("/auth/me", {
          headers: { Authorization: `Bearer ${data.access_token}` },
        });
        setSession(me, data.access_token);
      } catch {
        clearSession();
      }
    })();
  }, [setSession, clearSession, setLoading]);

  return <>{children}</>;
}
