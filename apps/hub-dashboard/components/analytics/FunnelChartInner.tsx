"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, LabelList,
} from "recharts";
import type { FunnelStage } from "@/lib/types/api";

const STAGE_LABEL: Record<string, string> = {
  intake:              "Intake",
  discovery:           "Discovery",
  technical_review:    "Tech Rev.",
  commercial_review:   "Comml.",
  legal_review:        "Legal",
  awaiting_approval:   "Approval",
  submitted:           "Submitted",
};

const STAGE_ORDER = [
  "intake","discovery","technical_review","commercial_review",
  "legal_review","awaiting_approval","submitted",
];

const GRADIENT = ["#00d4aa", "#00c49a", "#00b48a", "#00a47a", "#00946a", "#22c55e", "#16a34a"];

interface Props { stages: FunnelStage[]; }

export function FunnelChartInner({ stages }: Props) {
  const sorted = [...stages]
    .sort((a, b) => STAGE_ORDER.indexOf(a.stage) - STAGE_ORDER.indexOf(b.stage));

  const data = sorted.map((s, i) => {
    const prev = i > 0 ? sorted[i - 1].count : null;
    return {
      name:       STAGE_LABEL[s.stage] ?? s.stage,
      count:      s.count,
      conversion: prev && prev > 0 ? Math.round((s.count / prev) * 100) : null,
    };
  });

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart layout="vertical" data={data} margin={{ top: 4, right: 40, left: 0, bottom: 0 }}>
        <CartesianGrid horizontal={false} stroke="#1e2330" strokeDasharray="3 3" />
        <XAxis
          type="number"
          tick={{ fontSize: 10, fill: "#64748b", fontFamily: "var(--font-mono)" }}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
        />
        <YAxis
          type="category"
          dataKey="name"
          tick={{ fontSize: 10, fill: "#94a3b8", fontFamily: "var(--font-inter)" }}
          axisLine={false}
          tickLine={false}
          width={72}
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
          formatter={(v: any, _: any, item: any) => {
            const count = Number(v);
            const suffix = item?.payload?.conversion != null
              ? ` (${item.payload.conversion}% conv.)`
              : "";
            return [`${count}${suffix}`, "Opportunities"];
          }}
        />
        <Bar dataKey="count" radius={[0, 3, 3, 0]} maxBarSize={24}>
          {data.map((_, i) => (
            <Cell key={i} fill={GRADIENT[i % GRADIENT.length]} fillOpacity={0.75} />
          ))}
          <LabelList
            dataKey="count"
            position="right"
            style={{ fill: "#94a3b8", fontSize: 10, fontFamily: "var(--font-mono)" }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
