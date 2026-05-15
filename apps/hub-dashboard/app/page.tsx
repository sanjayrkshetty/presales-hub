import { Suspense } from "react";
import { api } from "@/lib/api";
import { ProposalCard } from "@/components/ProposalCard";
import { ActivityFeed } from "@/components/ActivityFeed";
import { SmeWorkloadMap } from "@/components/SmeWorkloadMap";
import { PipelineFunnel } from "@/components/PipelineFunnel";

export const revalidate = 30;

export default async function PipelinePage() {
  const [opps, pipeline, sla, smes] = await Promise.all([
    api.opportunities().catch(() => []),
    api.pipeline().catch(() => null),
    api.sla().catch(() => null),
    api.smeLoad().catch(() => []),
  ]);

  const active = opps.filter(o => !["closed_won", "closed_lost"].includes(o.stage));
  const won    = opps.filter(o => o.stage === "closed_won");
  const lost   = opps.filter(o => o.stage === "closed_lost");

  const stageCounts: Record<string, number> = {};
  for (const o of active) {
    stageCounts[o.stage] = (stageCounts[o.stage] ?? 0) + 1;
  }

  return (
    <div className="grid grid-cols-[200px_1fr_260px] gap-3 h-[calc(100vh-56px)]">

      {/* LEFT — Pipeline summary */}
      <div className="flex flex-col gap-3 overflow-y-auto">
        <div className="panel">
          <div className="panel-header">Pipeline</div>
          <div className="p-3 space-y-1">
            {[
              ["Intake",         stageCounts.intake ?? 0],
              ["Qualification",  stageCounts.qualification ?? 0],
              ["SME Assignment", stageCounts.sme_assignment ?? 0],
              ["Drafting",       stageCounts.drafting ?? 0],
              ["In Review",      (stageCounts.technical_review ?? 0) + (stageCounts.security_review ?? 0) + (stageCounts.delivery_review ?? 0)],
              ["Finance/Legal",  (stageCounts.finance_review ?? 0) + (stageCounts.legal_review ?? 0)],
              ["Approval",       stageCounts.approval ?? 0],
              ["Submission",     stageCounts.submission ?? 0],
            ].map(([label, count]) => (
              <div key={String(label)} className="flex justify-between items-center py-0.5">
                <span className="text-[11px]" style={{ color: "#94a3b8" }}>{label}</span>
                <span className="text-[11px] font-semibold" style={{ color: Number(count) > 0 ? "#e2e8f0" : "#475569" }}>
                  {count}
                </span>
              </div>
            ))}
            <div className="border-t mt-2 pt-2 space-y-1" style={{ borderColor: "var(--border)" }}>
              <div className="flex justify-between">
                <span className="text-[11px]" style={{ color: "#22c55e" }}>Won</span>
                <span className="text-[11px] font-bold" style={{ color: "#22c55e" }}>{won.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[11px]" style={{ color: "#ef4444" }}>Lost</span>
                <span className="text-[11px] font-bold" style={{ color: "#ef4444" }}>{lost.length}</span>
              </div>
            </div>
          </div>
        </div>

        {/* KPIs */}
        {pipeline && (
          <div className="panel">
            <div className="panel-header">KPIs</div>
            <div className="p-3 space-y-2">
              {[
                ["Win Rate",    `${pipeline.win_rate}%`],
                ["Active ACV",  `₹${pipeline.active_pipeline_cr.toFixed(1)}cr`],
                ["Won ACV",     `₹${pipeline.acv_cr.toFixed(1)}cr`],
                ["Avg Cycle",   pipeline.avg_cycle_days ? `${pipeline.avg_cycle_days}d` : "—"],
              ].map(([k, v]) => (
                <div key={String(k)} className="flex justify-between">
                  <span className="text-[10px]" style={{ color: "#64748b" }}>{k}</span>
                  <span className="text-[11px] font-bold" style={{ color: "var(--accent)" }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* SLA alerts */}
        {sla && sla.breached_count > 0 && (
          <div className="panel" style={{ borderColor: "rgba(239,68,68,0.4)" }}>
            <div className="panel-header" style={{ color: "#ef4444" }}>
              ⚠ SLA Breaches ({sla.breached_count})
            </div>
            <div className="p-2 space-y-1">
              {sla.breached.map(b => (
                <div key={b.opportunity_id} className="text-[10px] py-1 border-b last:border-0"
                  style={{ borderColor: "var(--border)", color: "#fca5a5" }}>
                  {b.title}
                  <div style={{ color: "#64748b" }}>{b.stage.replace(/_/g, " ")} · {Math.abs(b.hours_remaining).toFixed(1)}h over</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Funnel */}
        {pipeline && (
          <div className="panel">
            <div className="panel-header">Stage Funnel</div>
            <div className="p-3">
              <PipelineFunnel data={pipeline} />
            </div>
          </div>
        )}
      </div>

      {/* CENTRE — Active proposals */}
      <div className="flex flex-col gap-3 overflow-y-auto">
        <div className="flex items-center gap-3 mb-1">
          <h2 className="text-[11px] font-semibold tracking-widest uppercase" style={{ color: "#64748b" }}>
            Active Proposals
          </h2>
          <span className="text-[10px] px-2 py-0.5 rounded"
            style={{ background: "#00d4aa15", color: "var(--accent)", border: "1px solid #00d4aa33" }}>
            {active.length} open
          </span>
        </div>
        <div className="space-y-2">
          {active
            .sort((a, b) => (a.sla.status === "breached" ? -1 : b.sla.status === "breached" ? 1 : 0))
            .map(opp => (
              <ProposalCard key={opp.id} opp={opp} />
            ))
          }
          {active.length === 0 && (
            <div className="panel p-8 text-center text-[11px]" style={{ color: "#64748b" }}>
              No active proposals. Run the seed script to populate demo data.
            </div>
          )}
        </div>
      </div>

      {/* RIGHT — Activity + SME workload */}
      <div className="flex flex-col gap-3 overflow-hidden">
        {/* Activity feed */}
        <div className="panel flex flex-col" style={{ minHeight: 0, flex: "1 1 0" }}>
          <Suspense fallback={<div className="panel-header">Activity Feed</div>}>
            <ActivityFeed />
          </Suspense>
        </div>

        {/* SME workload */}
        <div className="panel shrink-0">
          <div className="panel-header">SME Workload</div>
          <div className="p-3">
            <SmeWorkloadMap smes={smes} />
          </div>
        </div>
      </div>
    </div>
  );
}
