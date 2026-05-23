"use client";
import { useRealtimeStore } from "@/lib/store/realtime";
import { cn } from "@/lib/utils";

const labels: Record<string, string> = {
  connected:    "Live",
  connecting:   "Connecting",
  disconnected: "Offline",
  error:        "Error",
};

const dotColor: Record<string, string> = {
  connected:    "bg-success",
  connecting:   "bg-warn",
  disconnected: "bg-muted",
  error:        "bg-danger",
};

export function RealtimeIndicator() {
  const { connectionState } = useRealtimeStore();

  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-bg-tertiary border border-border">
      <span className={cn(
        "w-1.5 h-1.5 rounded-full flex-shrink-0",
        dotColor[connectionState],
        connectionState === "connected" && "animate-pulse_dot"
      )} />
      <span className="text-2xs font-sans uppercase tracking-widest text-text-muted">
        {labels[connectionState] ?? connectionState}
      </span>
    </div>
  );
}
