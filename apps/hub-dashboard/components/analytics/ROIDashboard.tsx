"use client";

import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/lib/api/analytics";
import { MetricCard } from "@/components/ui/MetricCard";
import { TrendingUp, Clock, CheckCircle, DollarSign } from "lucide-react";
import { formatCurrency, formatPercent } from "@/lib/utils";

export function ROIDashboard() {
  const { data: pipeline } = useQuery({
    queryKey: ["analytics", "pipeline"],
    queryFn:  analyticsApi.pipeline,
    staleTime: 60_000,
  });
  const { data: sla } = useQuery({
    queryKey: ["analytics", "sla"],
    queryFn:  analyticsApi.sla,
    staleTime: 60_000,
  });

  const slaCompliance = sla
    ? Math.max(
        0,
        Math.round(
          ((sla.total_active - sla.breached_count) / Math.max(sla.total_active, 1)) * 100
        )
      )
    : null;

  // Estimated AI time savings: assume avg 2h saved per opportunity vs manual workflow
  const timeSavedHours = (pipeline?.total_opportunities ?? 0) * 2;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <MetricCard
        label="Pipeline Value"
        value={pipeline ? formatCurrency(pipeline.active_pipeline_cr) : "—"}
        sub={`${pipeline?.total_opportunities ?? 0} active opportunities`}
        icon={<DollarSign size={13} />}
        accent
      />
      <MetricCard
        label="Win Rate"
        value={pipeline ? formatPercent(pipeline.win_rate) : "—"}
        sub={`Avg close: ${pipeline?.avg_cycle_days?.toFixed(0) ?? "—"}d`}
        icon={<TrendingUp size={13} />}
      />
      <MetricCard
        label="SLA Compliance"
        value={slaCompliance !== null ? `${slaCompliance}%` : "—"}
        sub={`${sla?.breached_count ?? 0} breaches`}
        icon={<CheckCircle size={13} />}
        danger={(slaCompliance ?? 100) < 70}
        warn={(slaCompliance ?? 100) >= 70 && (slaCompliance ?? 100) < 90}
      />
      <MetricCard
        label="AI Time Saved"
        value={`~${timeSavedHours}h`}
        sub="Est. vs. manual workflow"
        icon={<Clock size={13} />}
      />
    </div>
  );
}
