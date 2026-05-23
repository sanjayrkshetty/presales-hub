"use client";

import { Suspense, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { CommandPalette } from "./CommandPalette";
import { WebSocketProvider } from "@/components/realtime/WebSocketProvider";
import { ToastStack } from "@/components/ui/ToastStack";
import { DemoModeProvider } from "@/providers/DemoModeProvider";

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

export function AppShell({ children }: Props) {
  return (
    <Suspense>
      <DemoModeProvider>
        <div className="flex flex-col h-screen w-screen overflow-hidden bg-bg-primary">
          <WebSocketProvider />
          <DemoBanner />
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
          <ToastStack />
        </div>
      </DemoModeProvider>
    </Suspense>
  );
}
