import { apiFetch } from "./client";
import type { PipelineAnalytics, SlaAnalytics, SmeLoad } from "../types/api";

export const analyticsApi = {
  pipeline: () => apiFetch<PipelineAnalytics>("/api/analytics/pipeline"),
  sla:      () => apiFetch<SlaAnalytics>("/api/analytics/sla"),
  smeLoad:  () => apiFetch<SmeLoad[]>("/api/analytics/sme-load"),
};
