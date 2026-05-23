import { apiFetch } from "./client";
import type { CopilotResult } from "../types/api";

export const copilotApi = {
  analyzeRfp: (rfp_text: string, session_id?: string) =>
    apiFetch<CopilotResult>("/api/copilot/rfp/analyze", {
      method: "POST",
      body: JSON.stringify({ rfp_text, session_id }),
    }),
  draftSection: (id: string, section: string, user_query?: string, session_id?: string) =>
    apiFetch<CopilotResult>(`/api/copilot/proposals/${id}/draft-section`, {
      method: "POST",
      body: JSON.stringify({ section, user_query, session_id }),
    }),
  brief:          (id: string) => apiFetch<CopilotResult>(`/api/copilot/proposals/${id}/brief`, { method: "POST", body: "{}" }),
  risks:          (id: string) => apiFetch<CopilotResult>(`/api/copilot/proposals/${id}/risks`, { method: "POST", body: "{}" }),
  complianceGap:  (id: string, rfp_requirements: string) =>
    apiFetch<CopilotResult>(`/api/copilot/proposals/${id}/compliance-gap`, {
      method: "POST",
      body: JSON.stringify({ rfp_requirements }),
    }),
  smeRecommend:   (id: string, user_query: string, top_k = 5) =>
    apiFetch<CopilotResult>(`/api/copilot/proposals/${id}/sme-recommend`, {
      method: "POST",
      body: JSON.stringify({ user_query, top_k }),
    }),
  solutionSuggest: (requirements: string, rfp_type?: string) =>
    apiFetch<CopilotResult>("/api/copilot/solutions/suggest", {
      method: "POST",
      body: JSON.stringify({ requirements, rfp_type }),
    }),
  // Convenience aliases matching component names
  draft:          (id: string, section: string) =>
    apiFetch<CopilotResult>(`/api/copilot/proposals/${id}/draft-section`, {
      method: "POST",
      body: JSON.stringify({ section }),
    }),
  explainRisk:    (id: string) => apiFetch<CopilotResult>(`/api/copilot/proposals/${id}/risks`, { method: "POST", body: "{}" }),
  recommendSme:   (id: string) => apiFetch<CopilotResult>(`/api/copilot/proposals/${id}/sme-recommend`, {
      method: "POST",
      body: JSON.stringify({ user_query: "recommend top SMEs for this proposal" }),
    }),
  suggestSolution: (proposalId: string, requirements: string) =>
    apiFetch<CopilotResult>("/api/copilot/solutions/suggest", {
      method: "POST",
      body: JSON.stringify({ requirements }),
    }),
  status:  () => apiFetch<{ provider: string; prompts_registered: number; active_sessions: number }>("/api/copilot/status"),
};
