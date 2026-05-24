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
  trend?:     number[];
  loading?:   boolean;
  className?: string;
}

export function KpiCard({
  label, value, sub, delta, icon, accent, danger, warn, trend, loading, className,
}: Props) {
  const borderColor = danger
    ? "border-danger/40"
    : warn
    ? "border-warn/40"
    : accent
    ? "border-accent/30"
    : "border-border";

  if (loading) {
    return <div className={cn("panel p-3 h-20 animate-pulse bg-bg-tertiary", className)} aria-hidden="true" />;
  }

  return (
    <div className={cn("panel p-3 flex flex-col gap-1", borderColor, className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-2xs uppercase tracking-widest text-text-muted font-sans font-semibold">
          {label}
        </span>
        {icon && <span className="text-text-muted" aria-hidden="true">{icon}</span>}
      </div>

      <div className="flex items-end gap-2">
        <span
          className={cn(
            "font-mono text-2xl font-semibold leading-none",
            danger ? "text-danger" : warn ? "text-warn" : accent ? "text-accent" : "text-text-primary"
          )}
        >
          {value}
        </span>
        {delta !== undefined && (
          <span className={cn("text-xs font-mono mb-0.5", delta >= 0 ? "text-success" : "text-danger")}>
            {delta >= 0 ? "+" : ""}{delta.toFixed(1)}%
          </span>
        )}
      </div>

      {sub && <span className="text-xs text-text-muted font-sans">{sub}</span>}

      {trend && trend.length > 1 && (
        <div className="flex items-end gap-px h-6 mt-1" aria-hidden="true">
          {trend.map((v, i) => {
            const max = Math.max(...trend, 1);
            const pct = (v / max) * 100;
            return (
              <div
                key={i}
                className={cn(
                  "flex-1 rounded-sm transition-all duration-300",
                  danger ? "bg-danger/40" : warn ? "bg-warn/40" : "bg-accent/30"
                )}
                style={{ height: `${Math.max(pct, 4)}%` }}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
