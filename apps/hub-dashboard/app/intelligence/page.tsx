"use client";
import { useQuery } from "@tanstack/react-query";
import { intelligenceApi } from "@/lib/api/intelligence";
import { analyticsApi } from "@/lib/api/analytics";
import { ForecastPanel } from "@/components/intelligence/ForecastPanel";
import { CapacityReport } from "@/components/intelligence/CapacityReport";
import { RecommendationFeed } from "@/components/intelligence/RecommendationFeed";
import { DependencyGraph } from "@/components/intelligence/DependencyGraph";
import { MetricCard } from "@/components/ui/MetricCard";
import { AnomalyBanner } from "@/components/ops/AnomalyBanner";
import { formatCurrency, formatPercent } from "@/lib/utils";
import type { PipelineAnalytics } from "@/lib/types/api";

export default function IntelligencePage() {
  const { data: pipeline } = useQuery<PipelineAnalytics>({
    queryKey: ["analytics", "pipeline"],
    queryFn:  analyticsApi.pipeline,
    staleTime: 30_000,
  });

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Win Rate"       value={pipeline ? formatPercent(pipeline.win_rate) : "—"} />
        <MetricCard label="Pipeline"       value={pipeline ? formatCurrency(pipeline.active_pipeline_cr) : "—"} accent />
        <MetricCard label="Avg Cycle"      value={pipeline ? `${pipeline.avg_cycle_days?.toFixed(0)}d` : "—"} />
        <MetricCard label="Total Active"   value={pipeline?.total_opportunities ?? "—"} />
      </div>

      <AnomalyBanner />

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-8">
          <ForecastPanel />
        </div>
        <div className="col-span-12 lg:col-span-4">
          <RecommendationFeed />
        </div>
        <div className="col-span-12 lg:col-span-6">
          <CapacityReport />
        </div>
        <div className="col-span-12 lg:col-span-6">
          <DependencyGraph />
        </div>
      </div>
    </div>
  );
}
