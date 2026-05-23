"use client";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/lib/api/analytics";
import { MetricCard } from "@/components/ui/MetricCard";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { formatCurrency, formatPercent, formatHours, slaColor } from "@/lib/utils";
import Link from "next/link";

export default function AnalyticsPage() {
  const { data: pipeline } = useQuery({
    queryKey: ["analytics", "pipeline"],
    queryFn:  analyticsApi.pipeline,
    staleTime: 30_000,
  });

  const { data: sla } = useQuery({
    queryKey: ["analytics", "sla"],
    queryFn:  analyticsApi.sla,
    staleTime: 10_000,
  });

  const { data: smes = [] } = useQuery({
    queryKey: ["analytics", "sme-load"],
    queryFn:  analyticsApi.smeLoad,
    staleTime: 30_000,
  });

  const funnel = pipeline?.funnel ?? [];
  const maxCount = Math.max(...funnel.map((f) => f.count), 1);

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Total Active"   value={pipeline?.total_opportunities ?? "—"} />
        <MetricCard label="Win Rate"       value={pipeline ? formatPercent(pipeline.win_rate) : "—"} />
        <MetricCard label="Active Pipeline" value={pipeline ? formatCurrency(pipeline.active_pipeline_cr) : "—"} accent />
        <MetricCard label="Avg Cycle"      value={pipeline ? `${pipeline.avg_cycle_days?.toFixed(0)}d` : "—"} />
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* Funnel */}
        {funnel.length > 0 && (
          <div className="col-span-12 lg:col-span-7 panel">
            <SectionHeader title="Stage Funnel" />
            <div className="p-3 overflow-x-auto">
              <div className="flex items-end gap-2 h-28 min-w-max">
                {funnel.map((s) => {
                  const h = Math.round((s.count / maxCount) * 100);
                  return (
                    <div key={s.stage} className="flex flex-col items-center gap-1">
                      <span className="text-2xs font-mono text-text-secondary">{s.count}</span>
                      <div className="w-14 bg-accent/70 rounded-sm" style={{ height: h }} title={s.stage} />
                      <span className="text-2xs text-text-muted font-sans text-center leading-tight w-14">
                        {s.stage.replace(/_/g, " ")}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* SLA health */}
        {sla && (
          <div className="col-span-12 lg:col-span-5 panel">
            <SectionHeader title="SLA Health" />
            <div className="p-3 flex flex-col gap-3">
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label: "Breached", value: sla.breached_count, color: "text-danger" },
                  { label: "At Risk",  value: sla.warning_count,  color: "text-warn" },
                  { label: "Healthy",  value: sla.total_active - sla.breached_count - sla.warning_count, color: "text-success" },
                ].map(({ label, value, color }) => (
                  <div key={label} className="panel-sm p-2 text-center">
                    <p className={`text-xl font-mono font-bold ${color}`}>{value}</p>
                    <p className="text-2xs font-sans text-text-muted">{label}</p>
                  </div>
                ))}
              </div>
              {sla.breached.length > 0 && (
                <div className="flex flex-col gap-1">
                  <p className="text-2xs uppercase tracking-widest text-text-muted font-sans font-semibold">Breached</p>
                  {sla.breached.slice(0, 5).map((opp) => (
                    <div key={opp.id} className="flex items-center justify-between text-xs font-sans py-0.5">
                      <Link href={`/proposals/${opp.proposal_id ?? opp.id}`}
                        className="text-danger hover:text-danger/80 transition-colors truncate">{opp.title}</Link>
                      <span className="font-mono text-text-muted flex-shrink-0 ml-2">
                        {formatHours(opp.sla.hours_remaining)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* SME load */}
        {smes.length > 0 && (
          <div className="col-span-12 panel">
            <SectionHeader title="SME Workload" count={smes.length} />
            <div className="p-3 grid grid-cols-2 md:grid-cols-4 gap-2">
              {smes.map((s) => {
                const pct = s.utilization_pct;
                const barColor = pct >= 90 ? "bg-danger" : pct >= 60 ? "bg-warn" : "bg-success";
                const textColor = pct >= 90 ? "text-danger" : pct >= 60 ? "text-warn" : "text-success";
                return (
                  <div key={s.id} className="panel-sm p-3 flex flex-col gap-2">
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="text-xs font-sans text-text-primary">{s.name}</p>
                        <p className="text-2xs font-sans text-text-muted">{s.bu} · {s.role}</p>
                      </div>
                      <span className={`text-xs font-mono font-bold ${textColor}`}>{pct}%</span>
                    </div>
                    <div className="health-bar">
                      <div className={`health-bar-fill ${barColor}`} style={{ width: `${pct}%` }} />
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {s.expertise.slice(0, 3).map((e) => (
                        <span key={e} className="px-1 py-0.5 rounded text-2xs font-sans bg-accent/10 text-accent border border-accent/20">
                          {e}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
