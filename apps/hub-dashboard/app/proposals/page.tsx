"use client";
import { useQuery } from "@tanstack/react-query";
import { opportunitiesApi } from "@/lib/api/opportunities";
import { LiveProposalTable } from "@/components/ops/LiveProposalTable";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { MetricCard } from "@/components/ui/MetricCard";
import { analyticsApi } from "@/lib/api/analytics";
import { formatCurrency, formatPercent } from "@/lib/utils";

export default function ProposalsPage() {
  const { data: pipeline } = useQuery({ queryKey: ["analytics", "pipeline"], queryFn: analyticsApi.pipeline });
  const funnel = pipeline?.funnel ?? [];

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Total Active"     value={pipeline?.total_opportunities ?? "—"} />
        <MetricCard label="Win Rate"         value={pipeline ? formatPercent(pipeline.win_rate ?? 0) : "—"} />
        <MetricCard label="Active Pipeline"  value={pipeline ? formatCurrency(pipeline.active_pipeline_cr ?? 0) : "—"} accent />
        <MetricCard label="Avg Cycle"        value={pipeline ? `${pipeline.avg_cycle_days?.toFixed(0)}d` : "—"} />
      </div>

      {/* Funnel bar */}
      {funnel.length > 0 && (
        <div className="panel">
          <SectionHeader title="Pipeline Funnel" />
          <div className="p-3 overflow-x-auto">
            <div className="flex items-end gap-2 h-20 min-w-max">
              {funnel.map((s) => {
                const max = Math.max(...funnel.map((f) => f.count), 1);
                const h = Math.round((s.count / max) * 72);
                return (
                  <div key={s.stage} className="flex flex-col items-center gap-1">
                    <span className="text-2xs font-mono text-text-secondary">{s.count}</span>
                    <div className="w-12 bg-accent/70 rounded-sm" style={{ height: h }} title={`${s.stage}: ${s.count}`} />
                    <span className="text-2xs text-text-muted font-sans text-center leading-tight w-12">{s.stage.replace(/_/g, " ")}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <div className="panel">
        <SectionHeader title="All Proposals" />
        <LiveProposalTable />
      </div>
    </div>
  );
}
