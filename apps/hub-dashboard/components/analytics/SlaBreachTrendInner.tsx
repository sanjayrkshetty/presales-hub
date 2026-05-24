"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import type { SlaAnalytics } from "@/lib/types/api";

const STAGE_LABEL: Record<string, string> = {
  intake:              "Intake",
  discovery:           "Discovery",
  technical_review:    "Tech Review",
  commercial_review:   "Commercial",
  legal_review:        "Legal",
  awaiting_approval:   "Approval",
  submitted:           "Submitted",
};

interface Props {
  sla: SlaAnalytics;
}

export function SlaBreachTrendInner({ sla }: Props) {
  const data = Object.entries(sla.breach_by_stage)
    .filter(([, v]) => v > 0)
    .map(([stage, count]) => ({
      stage: STAGE_LABEL[stage] ?? stage,
      count,
    }))
    .sort((a, b) => b.count - a.count);

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-xs text-text-muted">
        No breach data by stage.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="#1e2330" strokeDasharray="3 3" />
        <XAxis
          dataKey="stage"
          tick={{ fontSize: 10, fill: "#64748b", fontFamily: "var(--font-inter)" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 10, fill: "#64748b", fontFamily: "var(--font-mono)" }}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
        />
        <Tooltip
          contentStyle={{
            background: "#0f1117",
            border: "1px solid #1e2330",
            borderRadius: 6,
            fontSize: 11,
            fontFamily: "var(--font-mono)",
            color: "#e2e8f0",
          }}
          cursor={{ fill: "rgba(255,255,255,0.03)" }}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          formatter={(v: any) => [Number(v), "Breaches"]}
        />
        <Bar dataKey="count" radius={[3, 3, 0, 0]} maxBarSize={40}>
          {data.map((_, i) => (
            <Cell
              key={i}
              fill={i === 0 ? "#ef4444" : i === 1 ? "#f59e0b" : "#00d4aa66"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
