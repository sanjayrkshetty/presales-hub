"use client";
import { cn } from "@/lib/utils";

interface Props {
  score: number;
  flags?: string[];
}

export function ConfidenceBar({ score, flags = [] }: Props) {
  const pct = Math.round(score * 100);
  const color = score >= 0.8 ? "bg-success" : score >= 0.5 ? "bg-warn" : "bg-danger";
  const label = score >= 0.8 ? "High" : score >= 0.5 ? "Medium" : "Low";

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <p className="text-2xs uppercase tracking-widest text-text-muted font-sans font-semibold">Confidence</p>
        <span className={cn("text-2xs font-mono font-bold",
          score >= 0.8 ? "text-success" : score >= 0.5 ? "text-warn" : "text-danger"
        )}>{label} · {pct}%</span>
      </div>
      <div className="health-bar">
        <div className={cn("health-bar-fill", color)} style={{ width: `${pct}%` }} />
      </div>
      {flags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-0.5">
          {flags.map((f) => (
            <span key={f} className="px-1.5 py-0.5 rounded text-2xs font-sans bg-warn/10 text-warn border border-warn/20">
              {f}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
