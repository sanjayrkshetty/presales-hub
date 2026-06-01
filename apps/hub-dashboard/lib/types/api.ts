// ── Core domain types ────────────────────────────────────────────────────────

export interface SlaStatus {
  status: "ok" | "warning" | "breached";
  hours_remaining: number;
  hours_allowed: number;
}

export interface Client {
  id: string;
  name: string;
  sector: string;
  tier: string;
}

export interface Opportunity {
  id: string;
  title: string;
  rfp_type: string;
  stage: string;
  deal_value_cr: number;
  win_probability: number;
  deadline: string;
  created_at: string;
  updated_at: string;
  client: Client;
  proposal_id: string | null;
  health_score: number;
  sla: SlaStatus;
}

export interface Stakeholder {
  id: string;
  name: string;
  role: string;
  bu: string;
  expertise: string[];
  current_workload: number;
  email: string;
  active_proposals: number;
}

export interface Approval {
  id: string;
  stage: string;
  order_index: number;
  parallel_group: number | null;
  status: string;
  decision_note: string | null;
  decided_at: string | null;
  due_at: string | null;
  approver: { id: string; name: string; role: string };
}

export interface ActivityItem {
  id: string;
  proposal_id: string;
  actor_name: string;
  action_type: string;
  description: string;
  is_alert: boolean;
  created_at: string;
}

// ── Analytics ────────────────────────────────────────────────────────────────

export interface FunnelStage {
  stage: string;
  count: number;
  value_cr: number;
}

export interface PipelineAnalytics {
  total_opportunities: number;
  win_rate: number | null;
  acv_cr: number;
  avg_cycle_days: number | null;
  active_pipeline_cr: number | null;
  funnel: FunnelStage[];
}

export interface SlaAlertItem {
  opportunity_id: string;
  proposal_id: string | null;
  client_name: string | null;
  title: string;
  stage: string;
  hours_remaining: number;
  hours_allowed: number;
  deal_value_cr: number;
}

export interface SlaAnalytics {
  total_active: number;
  breached_count: number;
  warning_count: number;
  breached: SlaAlertItem[];
  warning: SlaAlertItem[];
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

// ── Decision Intelligence ────────────────────────────────────────────────────

export interface HealthScore {
  proposal_id: string;
  overall_score: number;
  readiness_classification: string;
  breakdown: Record<string, unknown>;
  risk_factors: string[];
  missing_requirements: string[];
  explanation: string;
  model_version: string;
  scored_at: string;
  cached: boolean;
}

export interface SlaRisk {
  breach_probability: number;
  predicted_hours_to_breach: number;
  risk_level: string;
  factors: string[];
}

export interface Bottleneck {
  stage: string;
  severity: string;
  affected_count: number;
  estimated_delay_hours: number;
  factors: string[];
}

export interface Anomaly {
  id: string;
  proposal_id: string;
  approval_id: string;
  anomaly_type: string;
  severity: string;
  details: Record<string, unknown>;
  acknowledged: boolean;
  detected_at: string;
}

export interface IntelligenceDashboard {
  anomalies: Anomaly[];
  bottlenecks: Bottleneck[];
  score_distribution: { green: number; yellow: number; orange: number; red: number };
  critical_sla_risks: SlaRisk[];
}

export interface SmeCandidateResult {
  score: number;
  expertise_overlap: string[];
  workload: number;
  stakeholder: Stakeholder;
}

// ── Workflows ────────────────────────────────────────────────────────────────

export interface WorkflowTransition {
  from_stage: string;
  to_stage: string;
  actor_id: string;
  note: string;
  timestamp: string;
}

export interface WorkflowStatus {
  workflow_id: string;
  stage: string;
  is_active: boolean;
  transition_history: WorkflowTransition[];
}

// ── Strategy ─────────────────────────────────────────────────────────────────

export interface Forecast {
  period_label: string;
  weighted_forecast_cr: number;
  forecast_low_cr: number;
  forecast_high_cr: number;
  win_rate_trend: number;
}

export interface CapacityReport {
  sme_saturation: Record<string, number>;
  approval_bottlenecks: string[];
  burnout_signals: string[];
  advisory: string;
}

export interface Recommendation {
  id: string;
  category: string;
  priority: "critical" | "high" | "medium" | "low";
  title: string;
  description: string;
  action: string;
  affected_entity_id?: string;
}

export interface EscalationSignal {
  proposal_id: string;
  risk_level: string;
  signals: string[];
}

export interface DependencyGraph {
  node_count: number;
  edge_count: number;
  chokepoints: string[];
  blocked_proposals: string[];
  cross_bu_dependencies: Array<{ from: string; to: string; weight: number }>;
  high_risk_stakeholders: string[];
}

// ── Copilot ──────────────────────────────────────────────────────────────────

export interface GroundingSource {
  source_id: string;
  title?: string;
  score: number;
  excerpt?: string;
}

export interface ReasoningStep {
  section_id?: string;
  content: string;
}

export interface CopilotResult {
  result: Record<string, unknown>;
  grounding_metadata: Array<{ source: string; score: number; content: string }>;
  evaluation_score: number;
  safety_flags: string[];
}

export interface MemorySearchResult {
  content: string;
  score: number;
  source_id: string;
  metadata: Record<string, unknown>;
}

// ── Agents ───────────────────────────────────────────────────────────────────

export interface AgentTask {
  task_id: string;
  agent_type: string;
  status: "pending" | "running" | "completed" | "failed" | "awaiting_approval";
  confidence: number;
  grounding_score: number;
  output_summary: string;
  created_at: string;
  output?: Record<string, unknown>;
}

export interface AgentType {
  agent_type: string;
  description: string;
  input_schema: Record<string, unknown>;
}

// ── Integration ──────────────────────────────────────────────────────────────

export interface ConnectorHealth {
  platform: string;
  healthy: boolean;
  latency_ms: number;
  message: string;
  last_checked: string;
}

export interface SyncRecord {
  id: string;
  tenant_id: string;
  platform: string;
  status: string;
  last_synced_at: string;
  checksum: string;
}

export interface RetryJob {
  id: string;
  tenant_id: string;
  platform: string;
  job_type: string;
  status: string;
  attempt_count: number;
  max_attempts: number;
  next_retry_at: string;
  error_message: string;
}

export interface WebhookSubscription {
  id: string;
  tenant_id: string;
  target_url: string;
  event_types: string[];
  active: boolean;
  created_at: string;
}

export interface IntegrationDashboard {
  connector_status: Record<string, string>;
  sync_health: { total: number; synced: number; conflict: number; failed: number };
  webhook_delivery: { total: number; delivered: number; failed: number; dlq: number };
  rate_limit_status: Record<string, unknown>;
  dlq_summary: Record<string, unknown>;
  failed_jobs: number;
}

// ── Platform ─────────────────────────────────────────────────────────────────

export interface Tenant {
  id: string;
  org_name: string;
  tier: string;
  status: string;
  region: string;
  admin_email: string;
  billing_plan: string;
  feature_flags: Record<string, boolean>;
  quotas: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface TenantQuota {
  resource: string;
  limit: number;
  used: number;
  remaining: number;
  exhausted: boolean;
  percent_used: number;
}

export interface AuditEntry {
  action: string;
  actor_id: string;
  resource_type: string;
  resource_id: string;
  status: string;
  occurred_at: string;
}

export interface PlatformHealth {
  status: string;
  environment: string;
  deployment_mode: string;
  tenant_count: number;
  active_tenant_count: number;
  warnings: string[];
}
