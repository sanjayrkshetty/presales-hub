"use client";

import { Suspense, useEffect, type ReactNode } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/lib/auth/session";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { CommandPalette } from "./CommandPalette";
import { KeyboardShortcutsOverlay } from "./KeyboardShortcutsOverlay";
import { WebSocketProvider } from "@/components/realtime/WebSocketProvider";
import { ToastStack } from "@/components/ui/ToastStack";
import { OfflineBanner } from "@/components/ui/OfflineBanner";
import { DemoModeProvider } from "@/providers/DemoModeProvider";
import { DemoResetButton } from "@/components/ui/DemoResetButton";

function DemoBanner() {
  const params  = useSearchParams();
  const isDemo  = params.get("demo") === "1" || process.env.NEXT_PUBLIC_DEMO_MODE === "true";
  if (!isDemo) return null;
  return (
    <div className="flex items-center justify-center gap-2 px-3 py-1 text-[10px] font-medium"
         style={{ background: "rgba(59,130,246,0.12)", borderBottom: "1px solid rgba(59,130,246,0.25)", color: "#93c5fd" }}>
      <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse inline-block" />
      DEMO MODE — simulated live activity active ·
      <a href="/" className="underline underline-offset-2">exit demo</a>
    </div>
  );
}

interface Props {
  children: ReactNode;
}

const PUBLIC_PREFIXES = ["/login"];

function FullScreenLoader() {
  return (
    <div className="h-screen w-screen flex items-center justify-center bg-bg-primary">
      <span className="text-[12px]" style={{ color: "var(--text-secondary)" }}>Loading…</span>
    </div>
  );
}

export function AppShell({ children }: Props) {
  const pathname  = usePathname();
  const isPublic  = !!pathname && PUBLIC_PREFIXES.some((p) => pathname.startsWith(p));
  const user      = useAuthStore((s) => s.user);
  const isLoading = useAuthStore((s) => s.isLoading);
  const router    = useRouter();

  useEffect(() => {
    if (!isPublic && !isLoading && !user) router.replace("/login");
  }, [isPublic, isLoading, user, router]);

  // Public routes (login) render bare — no shell, no WebSockets, no auth gate.
  if (isPublic) return <>{children}</>;

  // Protected routes: hold until the session bootstrap resolves, so data queries
  // don't fire before the access token exists (a 401 during boot would hard-redirect
  // to /login — the cause of the full-reload login bounce, ITEM-15).
  if (isLoading || !user) return <FullScreenLoader />;

  return (
    <Suspense>
      <DemoModeProvider>
        <div className="flex flex-col h-screen w-screen overflow-hidden bg-bg-primary">
          <WebSocketProvider />
          <DemoBanner />
          <OfflineBanner />
          <div className="flex flex-1 min-h-0 overflow-hidden">
            <Sidebar />
            <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
              <TopBar apiUrl="http://localhost:8003/docs" />
              <main className="flex-1 overflow-auto">
                {children}
              </main>
            </div>
          </div>
          <CommandPalette />
          <KeyboardShortcutsOverlay />
          <ToastStack />
          <div className="fixed bottom-3 left-14 z-40">
            <DemoResetButton />
          </div>
        </div>
      </DemoModeProvider>
    </Suspense>
  );
}
