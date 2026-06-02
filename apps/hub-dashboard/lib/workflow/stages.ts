// Single source of truth for the proposal lifecycle.
// MUST mirror apps/hub-api/models/proposal.py (VALID_STAGES + TRANSITIONS).
// Do not maintain a divergent stage list anywhere else in the dashboard.

export const VALID_STAGES = [
  "intake", "qualification", "sme_assignment", "drafting",
  "technical_review", "security_review", "delivery_review",
  "finance_review", "legal_review", "approval",
  "submission", "client_followup", "closed_won", "closed_lost",
] as const;

export type Stage = (typeof VALID_STAGES)[number];

// Allowed forward transitions per stage — mirrors backend TRANSITIONS.
export const TRANSITIONS: Record<Stage, Stage[]> = {
  intake:           ["qualification"],
  qualification:    ["sme_assignment", "closed_lost"],
  sme_assignment:   ["drafting", "closed_lost"],
  drafting:         ["technical_review", "security_review", "delivery_review"],
  technical_review: ["finance_review", "drafting"],
  security_review:  ["finance_review", "drafting"],
  delivery_review:  ["finance_review", "drafting"],
  finance_review:   ["legal_review", "approval"],
  legal_review:     ["approval"],
  approval:         ["submission", "drafting"],
  submission:       ["client_followup"],
  client_followup:  ["closed_won", "closed_lost"],
  closed_won:       [],
  closed_lost:      [],
};

// The three reviews that run concurrently after drafting.
export const PARALLEL_REVIEW_GROUP: Stage[] = [
  "technical_review", "security_review", "delivery_review",
];

export const TERMINAL_STAGES: Stage[] = ["closed_won", "closed_lost"];

// Happy-path display order for the progress rail (closed_lost is an off-path
// terminal and is not shown on the linear rail).
export const STAGE_ORDER: Stage[] = [
  "intake", "qualification", "sme_assignment", "drafting",
  "technical_review", "security_review", "delivery_review",
  "finance_review", "legal_review", "approval",
  "submission", "client_followup", "closed_won",
];

export function isValidStage(stage: string): stage is Stage {
  return (VALID_STAGES as readonly string[]).includes(stage);
}

export function nextStages(stage: string): Stage[] {
  return isValidStage(stage) ? TRANSITIONS[stage] : [];
}

export function stageLabel(stage: string): string {
  return stage.replace(/_/g, " ");
}
