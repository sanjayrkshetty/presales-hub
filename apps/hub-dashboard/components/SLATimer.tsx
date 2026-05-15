"use client";

import { SlaStatus } from "@/lib/api";

interface Props {
  sla: SlaStatus;
  compact?: boolean;
}

export function SLATimer({ sla, compact }: Props) {
  const { status, hours_remaining, hours_allowed } = sla;

  const color =
    status === "breached" ? "var(--danger)" :
    status === "warning"  ? "var(--warn)" :
    "var(--success)";

  const label =
    status === "breached"
      ? `BREACHED ${Math.abs(hours_remaining ?? 0).toFixed(1)}h ago`
      : `${(hours_remaining ?? 0).toFixed(1)}h remaining`;

  const pct = hours_allowed
    ? Math.max(0, Math.min(100, ((hours_allowed - (hours_remaining ?? 0)) / hours_allowed) * 100))
    : 0;

  if (compact) {
    return (
      <span className="text-[10px] font-semibold" style={{ color }}>
        {status === "breached" ? "⚠ " : ""}{label}
      </span>
    );
  }

  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center">
        <span className="text-[10px] font-semibold" style={{ color }}>
          {status === "breached" ? "⚠ " : ""}SLA · {label}
        </span>
      </div>
      <div className="health-bar">
        <div
          className="health-bar-fill"
          style={{
            width: `${pct}%`,
            background: color,
            opacity: status === "breached" ? 1 : 0.85,
          }}
        />
      </div>
    </div>
  );
}
