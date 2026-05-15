import { api } from "@/lib/api";
import { PipelineFunnel } from "@/components/PipelineFunnel";

export const revalidate = 30;

export default async function AnalyticsPage() {
  const [pipeline, sla, smes] = await Promise.all([
    api.pipeline().catch(() => null),
    api.sla().catch(() => null),
    api.smeLoad().catch(() => []),
  ]);

  return (
    <div className="space-y-4">
      <h1 className="text-[11px] font-semibold tracking-widest uppercase" style={{ color: "#64748b" }}>
        Analytics
      </h1>

      {/* KPI row */}
      {pipeline && (
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: "Total Opps",    value: String(pipeline.total_opportunities) },
            { label: "Win Rate",      value: `${pipeline.win_rate}%` },
            { label: "Active ACV",    value: `₹${pipeline.active_pipeline_cr.toFixed(2)}cr` },
            { label: "Avg Cycle",     value: pipeline.avg_cycle_days ? `${pipeline.avg_cycle_days}d` : "—" },
          ].map(({ label, value }) => (
            <div key={label} className="panel p-4">
              <div className="text-[10px] mb-1" style={{ color: "#64748b" }}>{label}</div>
              <div className="text-[22px] font-bold" style={{ color: "var(--accent)" }}>{value}</div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        {/* Pipeline funnel */}
        {pipeline && (
          <div className="panel">
            <div className="panel-header">Stage Funnel</div>
            <div className="p-4">
              <PipelineFunnel data={pipeline} />
            </div>
          </div>
        )}

        {/* SLA overview */}
        {sla && (
          <div className="panel">
            <div className="panel-header">SLA Health</div>
            <div className="p-4 space-y-4">
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: "Breached", value: sla.breached_count, color: "var(--danger)" },
                  { label: "Warning",  value: sla.warning_count,  color: "var(--warn)" },
                  { label: "Healthy",  value: sla.total_active - sla.breached_count - sla.warning_count, color: "var(--success)" },
                ].map(({ label, value, color }) => (
                  <div key={label} className="text-center">
                    <div className="text-[22px] font-bold" style={{ color }}>{value}</div>
                    <div className="text-[10px] mt-1" style={{ color: "#64748b" }}>{label}</div>
                  </div>
                ))}
              </div>
              {sla.top_bottleneck && (
                <div className="text-[11px] p-2 rounded" style={{ background: "rgba(239,68,68,0.08)", color: "#fca5a5" }}>
                  Top bottleneck: <strong>{sla.top_bottleneck.replace(/_/g, " ")}</strong>
                  {" "}({sla.breach_by_stage[sla.top_bottleneck]} breach{sla.breach_by_stage[sla.top_bottleneck] > 1 ? "es" : ""})
                </div>
              )}
              {sla.breached.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[10px] font-semibold tracking-wider" style={{ color: "#64748b" }}>BREACHED</div>
                  {sla.breached.map(b => (
                    <div key={b.opportunity_id} className="flex justify-between text-[11px] py-1 border-b last:border-0"
                      style={{ borderColor: "var(--border)" }}>
                      <span style={{ color: "#fca5a5" }}>{b.title}</span>
                      <span style={{ color: "#64748b" }}>{Math.abs(b.hours_remaining).toFixed(1)}h over</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* SME load heatmap */}
      {smes.length > 0 && (
        <div className="panel">
          <div className="panel-header">SME Workload Heatmap</div>
          <div className="p-4">
            <div className="grid grid-cols-4 gap-3">
              {smes.map(s => {
                const color =
                  s.utilization_pct >= 90 ? "var(--danger)" :
                  s.utilization_pct >= 60 ? "var(--warn)" :
                  "var(--accent)";
                return (
                  <div key={s.id} className="panel p-3 space-y-2">
                    <div className="flex justify-between">
                      <span className="text-[11px] font-medium" style={{ color: "#e2e8f0" }}>{s.name}</span>
                      <span className="text-[10px] font-bold" style={{ color }}>{s.utilization_pct}%</span>
                    </div>
                    <div className="text-[10px]" style={{ color: "#64748b" }}>{s.bu} · {s.role}</div>
                    <div className="health-bar">
                      <div className="health-bar-fill" style={{ width: `${s.utilization_pct}%`, background: color, height: "5px" }} />
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {s.expertise.slice(0, 3).map(e => (
                        <span key={e} className="badge text-[9px]"
                          style={{ background: "#00d4aa11", color: "#00d4aa", border: "1px solid #00d4aa22" }}>
                          {e}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
