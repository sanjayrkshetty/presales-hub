"use client";

import { useRealtimeStore } from "@/lib/store/realtime";
import { WifiOff, RefreshCw } from "lucide-react";

export function OfflineBanner() {
  const state = useRealtimeStore((s) => s.connectionState);

  if (state === "connected" || state === "degraded") return null;

  const isReconnecting = state === "reconnecting";

  return (
    <div
      className="flex items-center justify-center gap-2 px-3 py-1.5 text-xs font-sans z-40"
      style={{
        background: isReconnecting ? "rgba(234,179,8,0.12)" : "rgba(239,68,68,0.12)",
        borderBottom: `1px solid ${isReconnecting ? "rgba(234,179,8,0.3)" : "rgba(239,68,68,0.3)"}`,
        color: isReconnecting ? "#fde047" : "#fca5a5",
      }}
    >
      {isReconnecting ? (
        <RefreshCw size={11} className="animate-spin flex-shrink-0" />
      ) : (
        <WifiOff size={11} className="flex-shrink-0" />
      )}
      <span>
        {isReconnecting
          ? "Reconnecting to realtime stream…"
          : "Realtime connection lost — live data paused"}
      </span>
    </div>
  );
}
