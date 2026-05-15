const BASE = process.env.NEXT_PUBLIC_HUB_API_URL ?? "http://localhost:8003";

export interface SlaStatus {
  status: "ok" | "warning" | "breached";
  hours_remaining: number | null;
  hours_allowed: number | null;
}

export interface Opportunity {
  id: string;
  title: string;
  rfp_type: string;
  stage: string;
  deal_value_cr: number | null;
  win_probability: number;
  deadline: string | null;
  created_at: string;
  updated_at: string;
  client: { id: string; name: string; sector: string; tier: string } | null;
  proposal_id: string | null;
  health_score: number | null;
  sla: SlaStatus;
}

export interface Stakeholder {
  id: string;
  name: string;
  role: string;
  bu: string;
  expertise: string[];
  current_workload: number;
  active_proposals: number;
  utilization_pct?: number;
}

export interface ActivityItem {
  id: string;
  proposal_id: string | null;
  actor_name: string;
  action_type: string;
  description: string;
  is_alert: boolean;
  created_at: string;
}

export interface PipelineAnalytics {
  total_opportunities: number;
  win_rate: number;
  acv_cr: number;
  avg_cycle_days: number | null;
  active_pipeline_cr: number;
  funnel: Array<{ stage: string; count: number; value_cr: number }>;
}

export interface SlaAnalytics {
  total_active: number;
  breached_count: number;
  warning_count: number;
  breached: Array<{ opportunity_id: string; title: string; stage: string; hours_remaining: number; hours_allowed: number }>;
  warning: Array<{ opportunity_id: string; title: string; stage: string; hours_remaining: number; hours_allowed: number }>;
  breach_by_stage: Record<string, number>;
  top_bottleneck: string | null;
}

export interface SmeLoad {
  id: string;
  name: string;
  bu: string;
  role: string;
  expertise: string[];
  current_workload: number;
  active_assignments: number;
  utilization_pct: number;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { next: { revalidate: 30 } });
  if (!res.ok) throw new Error(`API ${path} returned ${res.status}`);
  return res.json();
}

export const api = {
  opportunities: () => get<Opportunity[]>("/api/opportunities"),
  opportunity: (id: string) => get<Opportunity & { proposal?: unknown }>(`/api/opportunities/${id}`),
  stakeholders: () => get<Stakeholder[]>("/api/stakeholders"),
  pipeline: () => get<PipelineAnalytics>("/api/analytics/pipeline"),
  sla: () => get<SlaAnalytics>("/api/analytics/sla"),
  smeLoad: () => get<SmeLoad[]>("/api/analytics/sme-load"),
};

export function wsUrl(path: string): string {
  return `${BASE.replace("http", "ws")}${path}`;
}
