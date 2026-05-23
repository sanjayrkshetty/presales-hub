import { apiFetch } from "./client";

export const approvalsApi = {
  decide: (id: string, status: "approved" | "rejected" | "escalated" | "bypassed", decision_note?: string, actor_id?: string) =>
    apiFetch<{ approval_id: string; status: string }>(`/api/approvals/${id}/decide`, {
      method: "POST",
      body: JSON.stringify({ status, decision_note, actor_id }),
    }),
};
