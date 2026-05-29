"use client";
import { Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/lib/api/analytics";
import { MetricCard } from "@/components/ui/MetricCard";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { ChartSkeleton } from "@/components/ui/ChartSkeleton";
import { ROIDashboard } from "@/components/analytics/ROIDashboard";
import { ExportButton } from "@/components/analytics/ExportButton";
import { SlaBreachTrend } from "@/components/analytics/SlaBreachTrend";
import { FunnelChart } from "@/components/analytics/FunnelChart";
import { SmeHeatmap } from "@/components/analytics/SmeHeatmap";
import { formatHours } from "@/lib/utils";
import Link from "next/link";
import { BarChart3, TrendingUp, Clock, Users } from "lucide-react";

export default function AnalyticsPage() {
  const { data: pipeline, isLoading: pL } = useQuery({
    queryKey: ["analytics", "pipeline"],
    queryFn:  analyticsApi.pipeline,
    staleTime: 30_000,
  });

  const { data: sla, isLoading: sL } = useQuery({
    queryKey: ["analytics", "sla"],
    queryFn:  analyticsApi.sla,
    staleTime: 10_000,
  });

  const { data: smes = [], isLoading: smeL } = useQuery({
    queryKey: ["analytics", "sme-load"],
    queryFn:  analyticsApi.smeLoad,
    staleTime: 30_000,
  });

  const apiBase = process.env.NEXT_PUBLIC_HUB_API_URL ?? "http://localhost:8003";

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <SectionHeader title="Analytics" />
        <ExportButton
          url={`${apiBase}/api/analytics/export/pipeline.csv`}
          filename="presales_pipeline.csv"
        />
      </div>

      {/* ROI Summary */}
      <ROIDashboard />

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {(pL || sL) ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 rounded bg-bg-tertiary animate-pulse" />
          ))
        ) : (
          <>
            <MetricCard
              label="Total Opportunities"
              value={pipeline?.total_opportunities ?? "—"}
              sub={`ACV: ₹${pipeline?.acv_cr?.toFixed(1) ?? "—"}Cr`}
              icon={<BarChart3 size={13} />}
              accent
            />
            <MetricCard
              label="Win Rate"
              value={pipeline ? `${(pipeline.win_rate * 100).toFixed(1)}%` : "—"}
              sub={`Avg cycle ${pipeline?.avg_cycle_days?.toFixed(0) ?? "—"}d`}
              icon={<TrendingUp size={13} />}
            />
            <MetricCard
              label="SLA Breached"
              value={sla?.breached_count ?? 0}
              sub={`${sla?.warning_count ?? 0} at risk · ${sla?.total_active ?? 0} total`}
              icon={<Clock size={13} />}
              danger={!!sla?.breached_count}
              warn={!sla?.breached_count && !!sla?.warning_count}
            />
            <MetricCard
              label="SMEs Active"
              value={smes.length}
              sub={`${smes.filter((s) => s.utilization_pct >= 80).length} near capacity`}
              icon={<Users size={13} />}
            />
          </>
        )}
      </div>

      {/* Main charts row */}
      <div className="grid grid-cols-12 gap-4">
        {/* Pipeline funnel — enhanced with Recharts */}
        <div className="col-span-12 lg:col-span-7 panel p-4">
          <SectionHeader title="Pipeline Funnel" count={pipeline?.total_opportunities} />
          {pL ? (
            <ChartSkeleton height={220} />
          ) : !pipeline?.funnel?.length ? (
            <p className="text-xs text-text-muted mt-4">No funnel data available.</p>
          ) : (
            <div className="mt-3">
              <Suspense fallback={<ChartSkeleton height={220} />}>
                <FunnelChart stages={pipeline.funnel} />
              </Suspense>
            </div>
          )}
        </div>

        {/* SLA breach by stage */}
        <div className="col-span-12 lg:col-span-5 panel p-4">
          <SectionHeader title="SLA Breaches by Stage" />
          {sL ? (
            <ChartSkeleton height={180} />
          ) : sla ? (
            <div className="mt-3">
              <Suspense fallback={<ChartSkeleton height={180} />}>
                <SlaBreachTrend sla={sla} />
              </Suspense>
            </div>
          ) : (
            <p className="text-xs text-text-muted mt-4">No SLA data available.</p>
          )}
        </div>

        {/* SME Heatmap */}
        <div className="col-span-12 panel p-4">
          <SectionHeader
            title="SME Utilization Heatmap"
            count={smes.length}
            actions={
              <div className="flex items-center gap-3 text-2xs text-text-muted font-sans">
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-success/40 inline-block" /> &lt;50%</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-accent/60 inline-block" /> 50-70%</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-warn/80 inline-block" /> 70-90%</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-danger inline-block" /> &gt;90%</span>
              </div>
            }
          />
          <div className="mt-3">
            <SmeHeatmap data={smes} isLoading={smeL} />
          </div>
        </div>

        {/* SLA breach list */}
        {sla && sla.breached.length > 0 && (
          <div className="col-span-12 lg:col-span-6 panel p-4">
            <SectionHeader title="Breached SLAs" count={sla.breached_count} />
            <div className="mt-2 flex flex-col gap-1">
              {sla.breached.slice(0, 8).map((opp) => (
                <div key={opp.opportunity_id} className="flex items-center justify-between text-xs font-sans py-1 border-b border-border/30 last:border-0">
                  <Link
                    href={`/proposals/${opp.proposal_id ?? opp.opportunity_id}`}
                    className="text-danger hover:text-danger/80 transition-colors truncate"
                  >
                    {opp.title}
                  </Link>
                  <span className="font-mono text-text-muted flex-shrink-0 ml-2">
                    {formatHours(opp.hours_remaining)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* At-risk SLA list */}
        {sla && sla.warning.length > 0 && (
          <div className="col-span-12 lg:col-span-6 panel p-4">
            <SectionHeader title="At-Risk SLAs" count={sla.warning_count} />
            <div className="mt-2 flex flex-col gap-1">
              {sla.warning.slice(0, 8).map((opp) => (
                <div key={opp.opportunity_id} className="flex items-center justify-between text-xs font-sans py-1 border-b border-border/30 last:border-0">
                  <Link
                    href={`/proposals/${opp.proposal_id ?? opp.opportunity_id}`}
                    className="text-warn hover:text-warn/80 transition-colors truncate"
                  >
                    {opp.title}
                  </Link>
                  <span className="font-mono text-text-muted flex-shrink-0 ml-2">
                    {formatHours(opp.hours_remaining)} left
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
