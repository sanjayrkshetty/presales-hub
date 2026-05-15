"use client";

import { SmeLoad } from "@/lib/api";

function utilColor(pct: number): string {
  if (pct >= 90) return "var(--danger)";
  if (pct >= 60) return "var(--warn)";
  if (pct >= 30) return "var(--accent)";
  return "#22c55e";
}

interface Props {
  smes: SmeLoad[];
}

export function SmeWorkloadMap({ smes }: Props) {
  const displayed = smes.slice(0, 8);
  return (
    <div className="space-y-2">
      {displayed.map((s) => (
        <div key={s.id} className="space-y-1">
          <div className="flex justify-between items-center">
            <div>
              <span className="text-[11px] font-medium text-text-primary">{s.name}</span>
              <span className="ml-2 text-[10px]" style={{ color: "#64748b" }}>{s.bu}</span>
            </div>
            <span className="text-[10px] font-semibold" style={{ color: utilColor(s.utilization_pct) }}>
              {s.active_assignments} active
            </span>
          </div>
          <div className="health-bar">
            <div
              className="health-bar-fill"
              style={{ width: `${s.utilization_pct}%`, background: utilColor(s.utilization_pct) }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
