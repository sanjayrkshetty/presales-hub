import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface Props {
  label:      string;
  value:      string | number;
  sub?:       string;
  delta?:     number;
  icon?:      ReactNode;
  accent?:    boolean;
  danger?:    boolean;
  warn?:      boolean;
  className?: string;
}

export function MetricCard({ label, value, sub, delta, icon, accent, danger, warn, className }: Props) {
  const borderColor = danger ? "border-danger/40" : warn ? "border-warn/40" : accent ? "border-accent/30" : "border-border";
  return (
    <div className={cn("panel p-3 flex flex-col gap-1", borderColor, className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-2xs uppercase tracking-widest text-text-muted font-sans font-semibold">{label}</span>
        {icon && <span className="text-text-muted">{icon}</span>}
      </div>
      <div className="flex items-end gap-2">
        <span className={cn("font-mono text-2xl font-semibold leading-none",
          danger ? "text-danger" : warn ? "text-warn" : accent ? "text-accent" : "text-text-primary"
        )}>
          {value}
        </span>
        {delta !== undefined && (
          <span className={cn("text-xs font-mono mb-0.5", delta >= 0 ? "text-success" : "text-danger")}>
            {delta >= 0 ? "+" : ""}{delta.toFixed(1)}%
          </span>
        )}
      </div>
      {sub && <span className="text-xs text-text-muted font-sans">{sub}</span>}
    </div>
  );
}
