"use client";
import { useSearchParams } from "next/navigation";
import { useDemoStore } from "@/lib/store/demo";
import { RotateCcw } from "lucide-react";

export function DemoResetButton() {
  const params   = useSearchParams();
  const isDemo   = params.get("demo") === "1" || process.env.NEXT_PUBLIC_DEMO_MODE === "true";
  const demoReset = useDemoStore((s) => s.demoReset);

  if (!isDemo) return null;

  return (
    <button
      onClick={demoReset}
      className="flex items-center gap-1.5 px-2 py-1.5 rounded text-2xs font-sans text-text-muted hover:text-text-primary hover:bg-white/4 transition-colors border border-transparent hover:border-border"
      title="Reset demo state — clears events and notifications"
      aria-label="Reset demo state"
    >
      <RotateCcw size={10} />
      Reset demo
    </button>
  );
}
