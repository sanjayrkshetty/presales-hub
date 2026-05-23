"use client";
import { useQuery } from "@tanstack/react-query";
import { strategyApi } from "@/lib/api/strategy";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Spinner } from "@/components/ui/Spinner";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { formatCurrency } from "@/lib/utils";
import type { Forecast } from "@/lib/types/api";

function ForecastTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-bg-elevated border border-border rounded p-2 text-2xs font-sans">
      <p className="text-text-muted mb-1">{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.color }}>{p.name}: {formatCurrency(p.value)}</p>
      ))}
    </div>
  );
}

interface ForecastResponse {
  pipeline: Forecast;
  rolling: Forecast;
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
      period: rolling.period_label ?? "Rolling",
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
            {[
              ["Projected",    formatCurrency(pipeline.projected_revenue_cr)],
              ["Confidence ▼", formatCurrency(pipeline.confidence_low)],
              ["Confidence ▲", formatCurrency(pipeline.confidence_high)],
            ].map(([k, v]) => (
              <div key={k} className="panel-sm p-2">
                <p className="text-2xs text-text-muted font-sans">{k}</p>
                <p className="text-xs font-mono text-text-primary font-semibold mt-0.5">{v}</p>
              </div>
            ))}
          </div>

          {chartData.length > 0 && (
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradLow" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradBase" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00d4aa" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#00d4aa" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradHigh" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e2330" />
                <XAxis dataKey="period" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false}
                  tickFormatter={(v) => `${(v / 10_000_000).toFixed(0)}Cr`} />
                <Tooltip content={<ForecastTooltip />} />
                <Area type="monotone" dataKey="low"  stroke="#3b82f6" strokeWidth={1} fill="url(#gradLow)"  strokeDasharray="4 2" name="Low" />
                <Area type="monotone" dataKey="base" stroke="#00d4aa" strokeWidth={1.5} fill="url(#gradBase)" name="Base" />
                <Area type="monotone" dataKey="high" stroke="#8b5cf6" strokeWidth={1} fill="url(#gradHigh)" strokeDasharray="4 2" name="High" />
              </AreaChart>
            </ResponsiveContainer>
          )}

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
