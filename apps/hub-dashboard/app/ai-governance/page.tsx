"use client";

import { useQuery } from "@tanstack/react-query";
import { aiGovernanceApi } from "@/lib/api/ai_governance";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { MetricCard } from "@/components/ui/MetricCard";
import { ChartSkeleton } from "@/components/ui/ChartSkeleton";
import { Badge } from "@/components/ui/system/Badge";
import { Brain, Zap, DollarSign, BarChart3, TrendingUp, AlertTriangle } from "lucide-react";

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Anthropic Claude",
  openai:    "OpenAI",
  groq:      "Groq",
  unknown:   "Mixed / Unknown",
};

function tokenEfficiency(tokens: number, calls: number): string {
  if (!calls) return "—";
  return Math.round(tokens / calls).toLocaleString();
}

function forecastDaysToLimit(used: number, limit: number, days: number): string {
  if (!used || !limit) return "—";
  const dailyRate = used / days;
  const remaining = limit - used;
  if (remaining <= 0) return "Exceeded";
  const daysLeft = Math.floor(remaining / dailyRate);
  if (daysLeft > 90) return ">90d";
  return `~${daysLeft}d`;
}

export default function AIGovernancePage() {
  const { data: summary, isLoading: sumLoading } = useQuery({
    queryKey: ["ai-governance", "summary"],
    queryFn:  () => aiGovernanceApi.summary(30),
    staleTime: 60_000,
  });
  const { data: history, isLoading: histLoading } = useQuery({
    queryKey: ["ai-governance", "history"],
    queryFn:  () => aiGovernanceApi.history(30),
    staleTime: 60_000,
  });
  const { data: quotas } = useQuery({
    queryKey: ["ai-governance", "quotas"],
    queryFn:  aiGovernanceApi.quotas,
    staleTime: 60_000,
  });

  const totalTokens = summary?.totals.tokens ?? 0;
  const totalCalls  = summary?.totals.api_calls ?? 0;
  const avgEfficiency = tokenEfficiency(totalTokens, totalCalls);

  // Identify dominant provider from tenant data (heuristic: all use same provider)
  const dominantProvider = "anthropic";

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <SectionHeader title="AI Governance" />
        <div className="flex items-center gap-2">
          <Badge variant="accent" size="sm">{PROVIDER_LABELS[dominantProvider]}</Badge>
          <Badge variant="muted" size="sm">30-day view</Badge>
        </div>
      </div>

      {/* KPI Strip */}
      {sumLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 rounded bg-bg-tertiary animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MetricCard
            label="Total Tokens (30d)"
            value={totalTokens.toLocaleString()}
            sub="All tenants combined"
            icon={<Brain size={13} />}
            accent
          />
          <MetricCard
            label="API Calls (30d)"
            value={totalCalls.toLocaleString()}
            sub={`~${avgEfficiency} tokens/call`}
            icon={<Zap size={13} />}
          />
          <MetricCard
            label="Est. Cost (30d)"
            value={`$${summary?.totals.cost_usd.toFixed(4) ?? "0.0000"}`}
            sub="Blended at $0.003/1K tokens"
            icon={<DollarSign size={13} />}
          />
          <MetricCard
            label="Active Tenants"
            value={summary?.tenants.length ?? 0}
            sub="With AI usage this period"
            icon={<BarChart3 size={13} />}
          />
        </div>
      )}

      <div className="grid grid-cols-12 gap-4">
        {/* Daily usage chart */}
        <div className="col-span-12 lg:col-span-8 panel p-4">
          <SectionHeader title="Daily Token Usage (30d)" />
          {histLoading ? (
            <ChartSkeleton />
          ) : !history?.length ? (
            <p className="text-xs text-text-muted mt-4">No token usage recorded in the last 30 days.</p>
          ) : (
            <div className="mt-3 flex items-end gap-1 h-32">
              {history.map((d) => {
                const max = Math.max(...history.map((x) => x.tokens), 1);
                const pct = Math.round((d.tokens / max) * 100);
                return (
                  <div key={d.day} className="flex-1 flex flex-col items-center gap-0.5 group relative">
                    <div
                      className="w-full rounded-t bg-accent/60 group-hover:bg-accent transition-colors"
                      style={{ height: `${pct}%`, minHeight: d.tokens > 0 ? "2px" : "0" }}
                    />
                    <span className="hidden group-hover:block absolute -top-7 text-2xs bg-bg-secondary border border-border rounded px-1 py-0.5 whitespace-nowrap z-10">
                      {d.day}: {d.tokens.toLocaleString()} tokens · {d.calls ?? 0} calls
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Token efficiency trend */}
          {history && history.length > 0 && (
            <div className="mt-4 pt-3 border-t border-border/40">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp size={12} className="text-text-muted" />
                <span className="text-2xs uppercase tracking-wider text-text-muted font-sans font-semibold">
                  Tokens per Call (efficiency)
                </span>
              </div>
              <div className="flex items-end gap-1 h-12">
                {history.map((d) => {
                  const eff = d.calls && d.calls > 0 ? d.tokens / d.calls : 0;
                  const maxEff = Math.max(...history.map((x) => (x.calls && x.calls > 0 ? x.tokens / x.calls : 0)), 1);
                  const pct = (eff / maxEff) * 100;
                  return (
                    <div key={d.day} className="flex-1 flex flex-col items-center gap-0 group relative">
                      <div
                        className="w-full rounded-t bg-blue/40 group-hover:bg-blue transition-colors"
                        style={{ height: `${pct}%`, minHeight: eff > 0 ? "2px" : "0" }}
                      />
                      <span className="hidden group-hover:block absolute -top-6 text-2xs bg-bg-secondary border border-border rounded px-1 py-0.5 whitespace-nowrap z-10">
                        {Math.round(eff).toLocaleString()} tok/call
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Quota bars */}
        <div className="col-span-12 lg:col-span-4 panel p-4">
          <SectionHeader title="Quota Utilization" />
          {!quotas?.length ? (
            <p className="text-xs text-text-muted mt-4">No quota records found.</p>
          ) : (
            <div className="mt-3 flex flex-col gap-3">
              {quotas.slice(0, 8).map((q, i) => {
                const isDanger  = q.pct_used >= 90;
                const isWarn    = q.pct_used >= 70;
                const forecast  = forecastDaysToLimit(q.used, q.limit, 30);
                return (
                  <div key={i} className="flex flex-col gap-1">
                    <div className="flex justify-between items-center text-2xs text-text-muted">
                      <span className="font-mono truncate max-w-[100px]">
                        {q.tenant_id.slice(0, 10)}… / {q.resource_type}
                      </span>
                      <div className="flex items-center gap-2">
                        {isDanger && <AlertTriangle size={9} className="text-danger" />}
                        <span className={isDanger ? "text-danger font-semibold" : isWarn ? "text-warn" : ""}>
                          {q.pct_used}%
                        </span>
                      </div>
                    </div>
                    <div className="h-1.5 rounded bg-bg-tertiary overflow-hidden">
                      <div
                        className={`h-full rounded transition-all ${
                          isDanger ? "bg-danger" : isWarn ? "bg-warn" : "bg-accent"
                        }`}
                        style={{ width: `${Math.min(q.pct_used, 100)}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-2xs text-text-muted/70">
                      <span>{q.used.toLocaleString()} / {q.limit.toLocaleString()}</span>
                      {forecast !== "—" && <span>Exhausts in {forecast}</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Per-tenant breakdown */}
      {summary && summary.tenants.length > 0 && (
        <div className="panel p-4">
          <SectionHeader title="Per-Tenant Breakdown" />
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-border text-text-muted">
                  <th className="text-left py-1.5 pr-4 font-sans text-2xs uppercase tracking-wider">Tenant</th>
                  <th className="text-right py-1.5 pr-4 font-sans text-2xs uppercase tracking-wider">Tokens</th>
                  <th className="text-right py-1.5 pr-4 font-sans text-2xs uppercase tracking-wider">API Calls</th>
                  <th className="text-right py-1.5 pr-4 font-sans text-2xs uppercase tracking-wider">Tok/Call</th>
                  <th className="text-right py-1.5 pr-4 font-sans text-2xs uppercase tracking-wider">Agent Runs</th>
                  <th className="text-right py-1.5 font-sans text-2xs uppercase tracking-wider">Est. Cost</th>
                </tr>
              </thead>
              <tbody>
                {summary.tenants.map((t) => (
                  <tr key={t.tenant_id} className="border-b border-border/50 hover:bg-white/2">
                    <td className="py-1.5 pr-4 text-text-secondary truncate max-w-[120px] font-sans">
                      {t.tenant_id}
                    </td>
                    <td className="py-1.5 pr-4 text-right text-text-primary">{t.tokens.toLocaleString()}</td>
                    <td className="py-1.5 pr-4 text-right">{t.api_calls.toLocaleString()}</td>
                    <td className="py-1.5 pr-4 text-right text-text-muted">
                      {tokenEfficiency(t.tokens, t.api_calls)}
                    </td>
                    <td className="py-1.5 pr-4 text-right">{t.agent_executions.toLocaleString()}</td>
                    <td className="py-1.5 text-right text-accent">${t.cost_usd.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
