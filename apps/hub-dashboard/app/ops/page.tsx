"use client";
import { Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/lib/api/analytics";
import { MetricCard } from "@/components/ui/MetricCard";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { ChartSkeleton } from "@/components/ui/ChartSkeleton";
import { LiveProposalTable } from "@/components/ops/LiveProposalTable";
import { AnomalyBanner } from "@/components/ops/AnomalyBanner";
import { BottleneckPanel } from "@/components/ops/BottleneckPanel";
import { SLABreachList } from "@/components/ops/SLABreachList";
import { ActivityFeed } from "@/components/ActivityFeed";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { BarChart3, TrendingUp, AlertTriangle, Clock } from "lucide-react";

export default function OpsPage() {
  const { data: pipeline, isLoading: pipelineLoading } = useQuery({
    queryKey: ["analytics", "pipeline"],
    queryFn:  analyticsApi.pipeline,
    staleTime: 30_000,
  });
  const { data: sla, isLoading: slaLoading } = useQuery({
    queryKey: ["analytics", "sla"],
    queryFn:  analyticsApi.sla,
    staleTime: 10_000,
  });

  const loading = pipelineLoading || slaLoading;

  return (
    <div className="p-4 flex flex-col gap-4 h-full">
      {/* KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 rounded bg-bg-tertiary animate-pulse" />
          ))
        ) : (
          <>
            <MetricCard
              label="Active Pipeline"
              value={pipeline ? formatCurrency(pipeline.active_pipeline_cr) : "—"}
              sub={`${pipeline?.total_opportunities ?? 0} opportunities`}
              icon={<BarChart3 size={13} />}
              accent
            />
            <MetricCard
              label="Win Rate"
              value={pipeline ? formatPercent(pipeline.win_rate) : "—"}
              sub={`Avg cycle: ${pipeline?.avg_cycle_days?.toFixed(0) ?? "—"}d`}
              icon={<TrendingUp size={13} />}
            />
            <MetricCard
              label="SLA Breached"
              value={sla?.breached_count ?? 0}
              sub={`${sla?.warning_count ?? 0} at risk`}
              icon={<Clock size={13} />}
              danger={!!sla?.breached_count}
              warn={!sla?.breached_count && !!sla?.warning_count}
            />
            <MetricCard
              label="ACV"
              value={pipeline ? formatCurrency(pipeline.acv_cr) : "—"}
              sub="Annual contract value"
              icon={<AlertTriangle size={13} />}
            />
          </>
        )}
      </div>

      {/* Main 3-column layout */}
      <div className="grid grid-cols-12 gap-4 flex-1 min-h-0">
        {/* Left: Bottlenecks + Anomalies */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-3">
          <Suspense fallback={<ChartSkeleton />}>
            <AnomalyBanner />
            <BottleneckPanel />
            <SLABreachList />
          </Suspense>
        </div>

        {/* Center: Live proposals */}
        <div className="col-span-12 lg:col-span-6 panel overflow-hidden flex flex-col">
          <SectionHeader title="Active Proposals" count={pipeline?.total_opportunities} />
          <div className="flex-1 overflow-auto">
            <Suspense fallback={<ChartSkeleton />}>
              <LiveProposalTable />
            </Suspense>
          </div>
        </div>

        {/* Right: Activity feed */}
        <div className="col-span-12 lg:col-span-3 panel overflow-hidden flex flex-col">
          <SectionHeader title="Live Activity" />
          <div className="flex-1 overflow-auto">
            <Suspense fallback={<ChartSkeleton />}>
              <ActivityFeed />
            </Suspense>
          </div>
        </div>
      </div>
    </div>
  );
}
