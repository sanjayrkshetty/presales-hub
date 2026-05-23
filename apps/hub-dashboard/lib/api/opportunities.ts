import { apiFetch } from "./client";
import type { Opportunity, Stakeholder } from "../types/api";

export const opportunitiesApi = {
  list:        () => apiFetch<Opportunity[]>("/api/opportunities"),
  get:         (id: string) => apiFetch<Opportunity & { proposal?: unknown; assignments?: unknown[]; approvals?: unknown[]; recent_activity?: unknown[] }>(`/api/opportunities/${id}`),
  create:      (body: Record<string, unknown>) => apiFetch<Opportunity>("/api/opportunities", { method: "POST", body: JSON.stringify(body) }),
  stakeholders:() => apiFetch<Stakeholder[]>("/api/stakeholders"),
};
