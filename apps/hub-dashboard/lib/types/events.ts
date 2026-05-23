export type ConnectionState =
  | "connecting"    // initial attempt
  | "connected"     // all channels open
  | "reconnecting"  // lost connection, backoff retry in progress
  | "degraded"      // partial — some channels open, not all
  | "disconnected"  // cleanly closed, not retrying
  | "error";        // fatal error state

// BaseEvent is kept for type-guard utility only — NOT in DomainEvent union
export interface BaseEvent {
  event_type: string;
  [key: string]: unknown;
}

export interface UnknownEvent {
  event_type: string;
  raw?: unknown;
  [key: string]: unknown;
}

export type KnownEventType =
  | "ping"
  | "activity"
  | "activity.backfill"
  | "proposal.transitioned"
  | "sla.breach"
  | "sme.assigned"
  | "approval.decision"
  | "anomaly.detected";

export const KNOWN_EVENT_TYPES: ReadonlySet<KnownEventType> = new Set([
  "ping",
  "activity",
  "activity.backfill",
  "proposal.transitioned",
  "sla.breach",
  "sme.assigned",
  "approval.decision",
  "anomaly.detected",
]);

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
  id?: string;
  proposal_id: string;
  from_stage: string;
  to_stage: string;
  actor_id: string;
  timestamp: string;
}

export interface SlaBreachEvent {
  event_type: "sla.breach";
  id?: string;
  proposal_id: string;
  opportunity_id: string;
  stage: string;
  hours_overdue: number;
  timestamp: string;
}

export interface SmeAssignedEvent {
  event_type: "sme.assigned";
  id?: string;
  proposal_id: string;
  stakeholder_id: string;
  stakeholder_name: string;
  timestamp: string;
}

export interface ApprovalDecisionEvent {
  event_type: "approval.decision";
  id?: string;
  approval_id: string;
  proposal_id: string;
  stage: string;
  status: string;
  actor_id: string;
  timestamp: string;
}

export interface AnomalyDetectedEvent {
  event_type: "anomaly.detected";
  id?: string;
  anomaly_id: string;
  proposal_id: string;
  anomaly_type: string;
  severity: string;
  timestamp: string;
}

// DomainEvent has no BaseEvent catch-all — exhaustive narrowing is enforced
export type DomainEvent =
  | PingEvent
  | ActivityEvent
  | ProposalTransitionedEvent
  | SlaBreachEvent
  | SmeAssignedEvent
  | ApprovalDecisionEvent
  | AnomalyDetectedEvent;

// Type-level exhaustiveness guard — compile error if DomainEvent gains a new member
// that is not handled in a switch statement calling this.
export function assertNever(x: never): never {
  throw new Error(
    `Unhandled event type: ${String((x as { event_type?: string }).event_type)}`
  );
}

// Runtime guard: validates raw parsed JSON is a known DomainEvent
export function parseDomainEvent(raw: unknown): DomainEvent | null {
  if (typeof raw !== "object" || raw === null) return null;
  if (!("event_type" in raw)) return null;
  const et = (raw as { event_type: unknown }).event_type;
  if (typeof et !== "string") return null;
  if (!KNOWN_EVENT_TYPES.has(et as KnownEventType)) return null;
  return raw as DomainEvent;
}

// Extracts a stable dedup ID from any DomainEvent
export function getEventId(event: DomainEvent): string | null {
  if (event.event_type === "ping") return null; // pings are never stored
  const e = event as { id?: string; anomaly_id?: string; approval_id?: string; timestamp?: string; proposal_id?: string };
  return e.id ?? e.anomaly_id ?? e.approval_id ?? null;
}
