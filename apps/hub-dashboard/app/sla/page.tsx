"use client";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/lib/api/analytics";
import { MetricCard } from "@/components/ui/MetricCard";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { formatHours, slaColor, cn } from "@/lib/utils";
import { Clock, AlertTriangle } from "lucide-react";
import Link from "next/link";

export default function SLACommandPage() {
  const { data: sla } = useQuery({
    queryKey: ["analytics", "sla"],
    queryFn:  analyticsApi.sla,
    staleTime: 10_000,
    refetchInterval: 30_000,
  });

  const breached = sla?.breached ?? [];
  const warning  = sla?.warning  ?? [];
  const byStage  = sla?.breach_by_stage ?? {};

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="grid grid-cols-3 gap-3">
        <MetricCard label="Total Active"  value={sla?.total_active ?? "—"} />
        <MetricCard label="Breached"      value={sla?.breached_count ?? "—"} danger={!!sla?.breached_count} icon={<AlertTriangle size={13} />} />
        <MetricCard label="At Risk"       value={sla?.warning_count  ?? "—"} warn={!!sla?.warning_count} icon={<Clock size={13} />} />
      </div>

      {/* Breach countdown — top critical items */}
      {breached.length > 0 && (
        <div className="panel">
          <SectionHeader title="Breach Countdowns" icon={<AlertTriangle size={11} />} />
          <div className="p-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {breached.slice(0, 6).map((opp) => (
              <Link key={opp.id} href={`/proposals/${opp.proposal_id ?? opp.id}`}
                className="panel-sm p-3 flex flex-col gap-1.5 hover:border-danger/50 transition-colors border-danger/20">
                <span className="text-xs font-sans font-medium text-text-primary truncate">{opp.title}</span>
                <span className="text-2xs text-text-muted font-sans">{opp.client?.name} · {opp.stage.replace(/_/g, " ")}</span>
                <span className="font-mono text-2xl font-bold text-danger leading-none">
                  {formatHours(opp.sla.hours_remaining)}
                </span>
                <div className="health-bar mt-1">
                  <div className="health-bar-fill bg-danger" style={{ width: `${Math.min(100, Math.abs(opp.sla.hours_remaining) / opp.sla.hours_allowed * 100)}%` }} />
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* At-risk */}
      {warning.length > 0 && (
        <div className="panel">
          <SectionHeader title="At Risk" count={warning.length} icon={<Clock size={11} />} />
          <table className="data-table">
            <thead><tr><th>Proposal</th><th>Stage</th><th>Time Remaining</th><th>Used</th></tr></thead>
            <tbody>
              {warning.map((opp) => {
                const pctUsed = Math.round((1 - opp.sla.hours_remaining / opp.sla.hours_allowed) * 100);
                return (
                  <tr key={opp.id}>
                    <td>
                      <Link href={`/proposals/${opp.proposal_id ?? opp.id}`}
                        className="text-xs font-sans text-warn hover:text-yellow-400 transition-colors">
                        {opp.title}
                      </Link>
                    </td>
                    <td><span className="text-xs font-mono text-text-secondary">{opp.stage.replace(/_/g, " ")}</span></td>
                    <td><span className="font-mono text-xs text-warn">{formatHours(opp.sla.hours_remaining)}</span></td>
                    <td>
                      <div className="flex items-center gap-2">
                        <div className="health-bar w-16 flex-shrink-0">
                          <div className="health-bar-fill bg-warn" style={{ width: `${pctUsed}%` }} />
                        </div>
                        <span className="font-mono text-2xs text-warn">{pctUsed}%</span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Breach by stage heatmap */}
      {Object.keys(byStage).length > 0 && (
        <div className="panel">
          <SectionHeader title="Breach Heatmap by Stage" />
          <div className="p-3 grid grid-cols-2 md:grid-cols-4 gap-2">
            {Object.entries(byStage).sort((a, b) => b[1] - a[1]).map(([stage, count]) => (
              <div key={stage} className={cn("panel-sm p-2", count > 2 ? "border-danger/30" : "border-warn/20")}>
                <p className="text-2xs text-text-muted font-sans">{stage.replace(/_/g, " ")}</p>
                <p className={cn("font-mono text-lg font-bold", count > 2 ? "text-danger" : "text-warn")}>{count}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {sla?.top_bottleneck && (
        <p className="text-xs text-text-secondary font-sans">
          Top bottleneck: <span className="font-mono text-text-primary">{sla.top_bottleneck.replace(/_/g, " ")}</span>
        </p>
      )}
    </div>
  );
}
