import { apiFetch } from "./client";
import type { AgentTask, AgentType } from "../types/api";

export const agentsApi = {
  submit: (agent_type: string, input_data: Record<string, unknown>, proposal_id?: string, opportunity_id?: string) =>
    apiFetch<{ task_id: string; status: string }>("/api/agents/tasks", {
      method: "POST",
      body: JSON.stringify({ agent_type, input_data, proposal_id, opportunity_id }),
    }),
  submitTask: (agent_type: string, input_data: Record<string, unknown>) =>
    apiFetch<{ task_id: string; status: string }>("/api/agents/tasks", {
      method: "POST",
      body: JSON.stringify({ agent_type, input_data }),
    }),
  listTasks: () => apiFetch<{ tasks: AgentTask[] }>("/api/agents/tasks"),
  getTask:   (task_id: string) => apiFetch<AgentTask>(`/api/agents/tasks/${task_id}`),
  listTypes: async () => {
    const r = await apiFetch<{ agents: AgentType[] }>("/api/agents/registry");
    return r.agents ?? [];
  },
  approve:  (task_id: string) => apiFetch<{ approved: boolean }>(`/api/agents/tasks/${task_id}/approve`, { method: "POST" }),
  reject:   (task_id: string, reason?: string) => apiFetch<{ rejected: boolean }>(`/api/agents/tasks/${task_id}/reject`, { method: "POST", body: JSON.stringify({ reason }) }),
  humanOverride: (task_id: string, decision: "approved" | "rejected", reason?: string) =>
    decision === "approved"
      ? apiFetch<{ approved: boolean }>(`/api/agents/tasks/${task_id}/approve`, { method: "POST" })
      : apiFetch<{ rejected: boolean }>(`/api/agents/tasks/${task_id}/reject`, { method: "POST", body: JSON.stringify({ reason }) }),
  registry: () => apiFetch<{ agents: AgentType[] }>("/api/agents/registry"),
  health:   () => apiFetch<{ status: string; agents_registered: number; plans_available: string[] }>("/api/agents/health"),
};
