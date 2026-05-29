import { apiFetch } from "./client";
import type { Opportunity, Stakeholder } from "../types/api";

const DEFAULT_SLA = { status: "ok" as const, hours_remaining: null, hours_allowed: null };
const normalizeSla = (o: Opportunity): Opportunity => ({ ...o, sla: o.sla ?? DEFAULT_SLA });

export const opportunitiesApi = {
  list:        () => apiFetch<Opportunity[]>("/api/opportunities").then(opps => opps.map(normalizeSla)),
  get:         (id: string) => apiFetch<Opportunity & { proposal?: unknown; assignments?: unknown[]; approvals?: unknown[]; recent_activity?: unknown[] }>(`/api/opportunities/${id}`).then(o => ({ ...normalizeSla(o), proposal: o.proposal, assignments: o.assignments, approvals: o.approvals, recent_activity: o.recent_activity })),
  create:      (body: Record<string, unknown>) => apiFetch<Opportunity>("/api/opportunities", { method: "POST", body: JSON.stringify(body) }),
  stakeholders:() => apiFetch<Stakeholder[]>("/api/stakeholders"),
};
