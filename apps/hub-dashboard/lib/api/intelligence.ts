import { apiFetch } from "./client";
import type { HealthScore, SlaRisk, Bottleneck, Anomaly, IntelligenceDashboard, SmeCandidateResult } from "../types/api";

export const intelligenceApi = {
  proposalHealth: (id: string) => apiFetch<HealthScore>(`/api/intelligence/proposals/${id}/health`),
  recomputeHealth: (id: string, use_llm = false) =>
    apiFetch<HealthScore>(`/api/intelligence/proposals/${id}/health/recompute`, {
      method: "POST",
      params: { use_llm },
    }),
  slaRisk:      (id: string) => apiFetch<SlaRisk>(`/api/intelligence/proposals/${id}/sla-risk`),
  smeCandidates:(id: string) => apiFetch<{ results: SmeCandidateResult[] }>(`/api/intelligence/proposals/${id}/sme-candidates`),
  bottlenecks:  () => apiFetch<{ bottlenecks: Bottleneck[] }>("/api/intelligence/bottlenecks"),
  anomalies:    (acknowledged?: boolean) => apiFetch<{ anomalies: Anomaly[] }>("/api/intelligence/anomalies", { params: { acknowledged } }),
  acknowledgeAnomaly: (id: string) =>
    apiFetch<{ acknowledged: boolean }>(`/api/intelligence/anomalies/${id}/acknowledge`, { method: "POST" }),
  dashboard:    () => apiFetch<IntelligenceDashboard>("/api/intelligence/dashboard"),
};
