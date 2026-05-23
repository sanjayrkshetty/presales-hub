import { apiFetch } from "./client";
import type { Approval, WorkflowStatus } from "../types/api";

export const proposalsApi = {
  transition: (id: string, to_stage: string, actor_id?: string, note?: string) =>
    apiFetch<{ proposal_id: string; stage: string }>(`/api/proposals/${id}/transition`, {
      method: "POST",
      body: JSON.stringify({ to_stage, actor_id, note }),
    }),
  assignSme: (id: string, rfp_type: string, required_skills?: string[]) =>
    apiFetch<{ assigned: unknown; alternatives: unknown[] }>(`/api/proposals/${id}/assign-sme`, {
      method: "POST",
      body: JSON.stringify({ rfp_type, required_skills }),
    }),
  getApprovals: (id: string) => apiFetch<Approval[]>(`/api/proposals/${id}/approvals`),
  startWorkflow: (id: string) =>
    apiFetch<{ workflow_id: string; status: string }>(`/api/workflows/proposals/${id}/start`, {
      method: "POST",
      body: JSON.stringify({ proposal_id: id }),
    }),
  getWorkflowStatus: (id: string) => apiFetch<WorkflowStatus>(`/api/workflows/proposals/${id}/status`),
  cancelWorkflow: (id: string) =>
    apiFetch<{ cancelled: boolean }>(`/api/workflows/proposals/${id}/cancel`, { method: "POST" }),
  signalTransition: (id: string, to_stage: string, actor_id?: string, note?: string) =>
    apiFetch<{ signaled: boolean; to_stage: string }>(`/api/workflows/proposals/${id}/transition`, {
      method: "POST",
      body: JSON.stringify({ to_stage, actor_id, note }),
    }),
};
