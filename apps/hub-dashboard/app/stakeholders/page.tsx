"use client";
import { useQuery } from "@tanstack/react-query";
import { opportunitiesApi } from "@/lib/api/opportunities";
import { analyticsApi } from "@/lib/api/analytics";
import { MetricCard } from "@/components/ui/MetricCard";
import { SectionHeader } from "@/components/ui/SectionHeader";

const ROLE_COLOR: Record<string, string> = {
  presales_lead:      "text-accent border-accent/20 bg-accent/5",
  solution_architect: "text-purple border-purple/20 bg-purple/5",
  sme:                "text-warn border-warn/20 bg-warn/5",
  security_reviewer:  "text-danger border-danger/20 bg-danger/5",
  finance:            "text-success border-success/20 bg-success/5",
  legal:              "text-text-muted border-border",
  delivery:           "text-blue border-blue/20 bg-blue/5",
};

export default function StakeholdersPage() {
  const { data: stakeholders = [] } = useQuery({
    queryKey: ["stakeholders"],
    queryFn:  opportunitiesApi.stakeholders,
    staleTime: 30_000,
  });

  const { data: smes = [] } = useQuery({
    queryKey: ["analytics", "sme-load"],
    queryFn:  analyticsApi.smeLoad,
    staleTime: 30_000,
  });

  const smeMap = new Map(smes.map((s) => [s.id, s]));

  const roles = [...new Set(stakeholders.map((s) => s.role))];
  const roleCount = roles.length;

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="grid grid-cols-3 gap-3">
        <MetricCard label="Total Stakeholders" value={stakeholders.length} />
        <MetricCard label="Roles"              value={roleCount} />
        <MetricCard label="Avg Active"         value={stakeholders.length ? (stakeholders.reduce((a, s) => a + (s.active_proposals ?? 0), 0) / stakeholders.length).toFixed(1) : "—"} />
      </div>

      <div className="panel">
        <SectionHeader title="Stakeholders & Expertise" count={stakeholders.length} />
        <div className="p-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {stakeholders.map((s) => {
            const load = smeMap.get(s.id);
            const pct = load?.utilization_pct ?? Math.min(100, (s.current_workload ?? 0) * 25);
            const barColor = pct >= 90 ? "bg-danger" : pct >= 60 ? "bg-warn" : "bg-success";
            const textColor = pct >= 90 ? "text-danger" : pct >= 60 ? "text-warn" : "text-success";
            const roleClass = ROLE_COLOR[s.role] ?? ROLE_COLOR.legal;

            return (
              <div key={s.id} className="panel-sm p-3 flex flex-col gap-2">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-xs font-sans font-semibold text-text-primary">{s.name}</p>
                    <p className="text-2xs font-sans text-text-muted">{s.email ?? s.bu}</p>
                  </div>
                  <span className={`px-1.5 py-0.5 rounded text-2xs font-sans border flex-shrink-0 ${roleClass}`}>
                    {s.role.replace(/_/g, " ")}
                  </span>
                </div>

                <div className="flex flex-col gap-1">
                  <div className="flex justify-between">
                    <span className="text-2xs text-text-muted font-sans">Workload</span>
                    <span className={`text-2xs font-mono ${textColor}`}>
                      {s.current_workload ?? 0} active
                    </span>
                  </div>
                  <div className="health-bar">
                    <div className={`health-bar-fill ${barColor}`} style={{ width: `${pct}%` }} />
                  </div>
                </div>

                <div className="flex flex-wrap gap-1">
                  {s.expertise.map((e) => (
                    <span key={e} className="px-1 py-0.5 rounded text-2xs font-sans bg-bg-primary text-text-secondary border border-border">
                      {e}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
          {stakeholders.length === 0 && (
            <p className="col-span-3 text-xs text-text-muted font-sans text-center py-8">No stakeholders found</p>
          )}
        </div>
      </div>
    </div>
  );
}
