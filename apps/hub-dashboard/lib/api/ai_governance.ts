import { apiFetch } from "./client";

export interface UsageSummary {
  period_days: number;
  since: string;
  tenants: Array<{
    tenant_id: string;
    tokens: number;
    api_calls: number;
    agent_executions: number;
    cost_usd: number;
  }>;
  totals: { tokens: number; api_calls: number; cost_usd: number };
}

export interface DailyUsage {
  day: string;
  tokens: number;
  calls: number;
}

export interface QuotaRecord {
  tenant_id: string;
  resource_type: string;
  limit: number;
  used: number;
  pct_used: number;
}

export const aiGovernanceApi = {
  summary: (days = 30) =>
    apiFetch<UsageSummary>(`/api/ai/usage/summary?days=${days}`),
  history: (days = 30, tenantId?: string) =>
    apiFetch<DailyUsage[]>(
      `/api/ai/usage/history?days=${days}${tenantId ? `&tenant_id=${tenantId}` : ""}`
    ),
  quotas: () => apiFetch<QuotaRecord[]>("/api/ai/quotas"),
};
