export type ConnectionState = "connecting" | "connected" | "disconnected" | "error";

export interface BaseEvent {
  event_type: string;
  [key: string]: unknown;
}

export interface PingEvent { event_type: "ping"; }

export interface ActivityEvent {
  event_type: "activity" | "activity.backfill";
  id: string;
  proposal_id: string;
  actor_name: string;
  action_type: string;
  description: string;
  is_alert: boolean;
  created_at: string;
}

export interface ProposalTransitionedEvent {
  event_type: "proposal.transitioned";
  proposal_id: string;
  from_stage: string;
  to_stage: string;
  actor_id: string;
  timestamp: string;
}

export interface SlaBreachEvent {
  event_type: "sla.breach";
  proposal_id: string;
  opportunity_id: string;
  stage: string;
  hours_overdue: number;
  timestamp: string;
}

export interface SmeAssignedEvent {
  event_type: "sme.assigned";
  proposal_id: string;
  stakeholder_id: string;
  stakeholder_name: string;
  timestamp: string;
}

export interface ApprovalDecisionEvent {
  event_type: "approval.decision";
  approval_id: string;
  proposal_id: string;
  stage: string;
  status: string;
  actor_id: string;
  timestamp: string;
}

export interface AnomalyDetectedEvent {
  event_type: "anomaly.detected";
  anomaly_id: string;
  proposal_id: string;
  anomaly_type: string;
  severity: string;
  timestamp: string;
}

export type DomainEvent =
  | PingEvent
  | ActivityEvent
  | ProposalTransitionedEvent
  | SlaBreachEvent
  | SmeAssignedEvent
  | ApprovalDecisionEvent
  | AnomalyDetectedEvent
  | BaseEvent;
