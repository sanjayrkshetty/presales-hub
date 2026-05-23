"use client";
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

interface ChartEntry {
  period: string;
  base:   number;
  low:    number;
  high:   number;
}

interface TooltipProps { active?: boolean; payload?: Array<{ name: string; value: number; color: string }>; label?: string; }

function ForecastTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-bg-elevated border border-border rounded p-2 text-2xs font-sans">
      <p className="text-text-muted mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>{p.name}: {formatCurrency(p.value)}</p>
      ))}
    </div>
  );
}

interface Props { data: ChartEntry[]; }

export function ForecastChartInner({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={180}>
      <AreaChart data={data} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
        <defs>
          <linearGradient id="gradLow"  x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.15} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gradBase" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#00d4aa" stopOpacity={0.2} />
            <stop offset="95%" stopColor="#00d4aa" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gradHigh" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#8b5cf6" stopOpacity={0.15} />
            <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e2330" />
        <XAxis dataKey="period" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis
          tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false}
          tickFormatter={(v) => `${(v / 10_000_000).toFixed(0)}Cr`}
        />
        <Tooltip content={<ForecastTooltip />} />
        <Area type="monotone" dataKey="low"  stroke="#3b82f6" strokeWidth={1}   fill="url(#gradLow)"  strokeDasharray="4 2" name="Low" />
        <Area type="monotone" dataKey="base" stroke="#00d4aa" strokeWidth={1.5} fill="url(#gradBase)" name="Base" />
        <Area type="monotone" dataKey="high" stroke="#8b5cf6" strokeWidth={1}   fill="url(#gradHigh)" strokeDasharray="4 2" name="High" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
