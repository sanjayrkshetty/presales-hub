"use client";
import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { strategyApi } from "@/lib/api/strategy";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Spinner } from "@/components/ui/Spinner";
import { ChartSkeleton } from "@/components/ui/ChartSkeleton";
import { formatCurrency } from "@/lib/utils";
import type { Forecast } from "@/lib/types/api";

// Recharts is browser-only — lazy-load to prevent SSR hydration mismatch
const ForecastChartInner = dynamic(
  () => import("./ForecastChartInner").then((m) => ({ default: m.ForecastChartInner })),
  { ssr: false, loading: () => <ChartSkeleton height={180} /> }
);

interface ForecastResponse {
  pipeline: Forecast;
  rolling:  Forecast;
  advisory: string;
}

export function ForecastPanel() {
  const { data: resp, isLoading } = useQuery<ForecastResponse>({
    queryKey: ["strategy", "forecast"],
    queryFn:  () => strategyApi.forecast(),
    staleTime: 60_000,
  });

  const pipeline = resp?.pipeline;
  const rolling  = resp?.rolling;

  const chartData = pipeline && rolling ? [
    {
      period: rolling.period_label  ?? "Rolling",
      base:   rolling.projected_revenue_cr,
      low:    rolling.confidence_low,
      high:   rolling.confidence_high,
    },
    {
      period: pipeline.period_label ?? "Current",
      base:   pipeline.projected_revenue_cr,
      low:    pipeline.confidence_low,
      high:   pipeline.confidence_high,
    },
  ] : [];

  return (
    <div className="panel">
      <SectionHeader title="Pipeline Forecast" />
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : pipeline ? (
        <div className="p-3 flex flex-col gap-3">
          <div className="grid grid-cols-3 gap-2">
            {([
              ["Projected",    formatCurrency(pipeline.projected_revenue_cr)],
              ["Confidence ▼", formatCurrency(pipeline.confidence_low)],
              ["Confidence ▲", formatCurrency(pipeline.confidence_high)],
            ] as [string, string][]).map(([k, v]) => (
              <div key={k} className="panel-sm p-2">
                <p className="text-2xs text-text-muted font-sans">{k}</p>
                <p className="text-xs font-mono text-text-primary font-semibold mt-0.5">{v}</p>
              </div>
            ))}
          </div>

          {chartData.length > 0 && <ForecastChartInner data={chartData} />}

          {resp?.advisory && (
            <p className="text-2xs font-sans text-text-secondary italic">{resp.advisory}</p>
          )}
        </div>
      ) : (
        <p className="p-4 text-xs text-text-muted font-sans text-center">No forecast data</p>
      )}
    </div>
  );
}
