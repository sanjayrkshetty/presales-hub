import { apiFetch } from "./client";
import type { CapacityReport, Recommendation, DependencyGraph, EscalationSignal, Forecast } from "../types/api";

export const strategyApi = {
  forecast: (period_label = "current", rolling_window_days = 30) =>
    apiFetch<{ pipeline: Forecast; rolling: Forecast; advisory: string }>("/api/strategy/forecast", {
      method: "POST",
      body: JSON.stringify({ period_label, rolling_window_days, include_quarter_projection: true }),
    }),
  capacity:       () => apiFetch<{ report: CapacityReport; advisory: string }>("/api/strategy/capacity"),
  escalations:    () => apiFetch<{ signals: EscalationSignal[]; summary: string; high_risk: number; medium_risk: number }>("/api/strategy/escalations"),
  dependencies:   () => apiFetch<DependencyGraph>("/api/strategy/dependencies"),
  recommendations:() => apiFetch<{ recommendations: Recommendation[]; total: number; critical_count: number; high_count: number; summary: string }>("/api/strategy/recommendations"),
  executiveSummary:() => apiFetch<{ summary: Record<string, unknown>; advisory: string }>("/api/strategy/executive-summary"),
};
