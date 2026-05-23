import { describe, it, expect } from "vitest";
import {
  parseDomainEvent,
  assertNever,
  getEventId,
  KNOWN_EVENT_TYPES,
  type DomainEvent,
  type ActivityEvent,
  type SlaBreachEvent,
} from "@/lib/types/events";

describe("parseDomainEvent", () => {
  it("returns null for non-objects", () => {
    expect(parseDomainEvent(null)).toBeNull();
    expect(parseDomainEvent("string")).toBeNull();
    expect(parseDomainEvent(42)).toBeNull();
    expect(parseDomainEvent(undefined)).toBeNull();
  });

  it("returns null for objects missing event_type", () => {
    expect(parseDomainEvent({ foo: "bar" })).toBeNull();
    expect(parseDomainEvent({})).toBeNull();
  });

  it("returns null for non-string event_type", () => {
    expect(parseDomainEvent({ event_type: 123 })).toBeNull();
  });

  it("returns null for unknown event types", () => {
    expect(parseDomainEvent({ event_type: "tenant.suspended" })).toBeNull();
    expect(parseDomainEvent({ event_type: "unknown.event" })).toBeNull();
    expect(parseDomainEvent({ event_type: "" })).toBeNull();
  });

  it("returns a valid DomainEvent for all known types", () => {
    for (const et of KNOWN_EVENT_TYPES) {
      const result = parseDomainEvent({ event_type: et, id: "x", proposal_id: "p1" });
      expect(result).not.toBeNull();
      expect(result?.event_type).toBe(et);
    }
  });

  it("preserves all fields from the raw object", () => {
    const raw = { event_type: "activity", id: "abc-123", proposal_id: "p1", actor_name: "Alice", action_type: "created", description: "test", is_alert: false, created_at: "2025-01-01T00:00:00Z" };
    const result = parseDomainEvent(raw) as ActivityEvent;
    expect(result).not.toBeNull();
    expect(result.id).toBe("abc-123");
    expect(result.actor_name).toBe("Alice");
  });
});

describe("assertNever", () => {
  it("throws with the event_type in the message", () => {
    const badEvent = { event_type: "unhandled.type" } as unknown as never;
    expect(() => assertNever(badEvent)).toThrow("unhandled.type");
  });
});

describe("getEventId", () => {
  it("returns null for ping events", () => {
    expect(getEventId({ event_type: "ping" })).toBeNull();
  });

  it("returns id from ActivityEvent", () => {
    const ev: DomainEvent = {
      event_type: "activity",
      id: "act-1",
      proposal_id: "p1",
      actor_name: "A",
      action_type: "created",
      description: "d",
      is_alert: false,
      created_at: "2025-01-01T00:00:00Z",
    };
    expect(getEventId(ev)).toBe("act-1");
  });

  it("returns anomaly_id for AnomalyDetectedEvent", () => {
    const ev: DomainEvent = {
      event_type: "anomaly.detected",
      anomaly_id: "anom-99",
      proposal_id: "p1",
      anomaly_type: "price_spike",
      severity: "high",
      timestamp: "2025-01-01T00:00:00Z",
    };
    expect(getEventId(ev)).toBe("anom-99");
  });

  it("returns null if no id fields present on SlaBreachEvent", () => {
    const ev: SlaBreachEvent = {
      event_type: "sla.breach",
      proposal_id: "p1",
      opportunity_id: "o1",
      stage: "scoping",
      hours_overdue: 5,
      timestamp: "2025-01-01T00:00:00Z",
    };
    expect(getEventId(ev)).toBeNull();
  });
});

// Type-level exhaustiveness — this test verifies DomainEvent has no BaseEvent catch-all
// by ensuring a switch with all known cases has no TS error when calling assertNever on default
describe("DomainEvent exhaustive switch (type-level)", () => {
  function handleEvent(event: DomainEvent): string {
    switch (event.event_type) {
      case "ping":                 return "ping";
      case "activity":
      case "activity.backfill":    return "activity";
      case "proposal.transitioned": return "transitioned";
      case "sla.breach":           return "breach";
      case "sme.assigned":         return "sme";
      case "approval.decision":    return "approval";
      case "anomaly.detected":     return "anomaly";
      default:                     return assertNever(event);
    }
  }

  it("handles all known event types without reaching default", () => {
    const ev = parseDomainEvent({ event_type: "activity", id: "1", proposal_id: "p", actor_name: "A", action_type: "c", description: "d", is_alert: false, created_at: "2025" });
    expect(handleEvent(ev!)).toBe("activity");
  });
});
