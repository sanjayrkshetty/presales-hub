import { describe, it, expect, beforeEach } from "vitest";
import { useRealtimeStore } from "@/lib/store/realtime";
import type { ActivityEvent, SlaBreachEvent, DomainEvent } from "@/lib/types/events";

function makeActivity(id: string): ActivityEvent {
  return {
    event_type:  "activity",
    id,
    proposal_id: "p1",
    actor_name:  "Alice",
    action_type: "created",
    description: "test",
    is_alert:    false,
    created_at:  new Date().toISOString(),
  };
}

function makeBreach(proposalId: string): SlaBreachEvent {
  return {
    event_type:     "sla.breach",
    proposal_id:    proposalId,
    opportunity_id: "o1",
    stage:          "scoping",
    hours_overdue:  3,
    timestamp:      new Date().toISOString(),
  };
}

describe("RealtimeStore", () => {
  beforeEach(() => {
    // Reset store state before each test
    useRealtimeStore.getState().clearLog();
    useRealtimeStore.setState({ channelStates: {}, connectionState: "disconnected" });
  });

  describe("pushEvent — deduplication", () => {
    it("stores an event with a unique id", () => {
      const ev = makeActivity("act-1");
      useRealtimeStore.getState().pushEvent(ev);
      expect(useRealtimeStore.getState().eventLog).toHaveLength(1);
      expect(useRealtimeStore.getState().lastEvent).toEqual(ev);
    });

    it("ignores a duplicate event with the same id", () => {
      const ev = makeActivity("act-dup");
      useRealtimeStore.getState().pushEvent(ev);
      useRealtimeStore.getState().pushEvent(ev);
      expect(useRealtimeStore.getState().eventLog).toHaveLength(1);
    });

    it("stores events with different ids", () => {
      useRealtimeStore.getState().pushEvent(makeActivity("id-1"));
      useRealtimeStore.getState().pushEvent(makeActivity("id-2"));
      useRealtimeStore.getState().pushEvent(makeActivity("id-3"));
      expect(useRealtimeStore.getState().eventLog).toHaveLength(3);
    });

    it("allows events without ids (e.g. SlaBreachEvent) through", () => {
      const b1 = makeBreach("p1");
      const b2 = makeBreach("p2");
      useRealtimeStore.getState().pushEvent(b1);
      useRealtimeStore.getState().pushEvent(b2);
      // Both should be stored since no ID to dedup on
      expect(useRealtimeStore.getState().eventLog.length).toBeGreaterThanOrEqual(2);
    });

    it("updates lastEvent to the most recent push", () => {
      useRealtimeStore.getState().pushEvent(makeActivity("id-a"));
      const second = makeActivity("id-b");
      useRealtimeStore.getState().pushEvent(second);
      expect(useRealtimeStore.getState().lastEvent).toEqual(second);
    });
  });

  describe("connection state aggregation via setChannelState", () => {
    it("connected when all 3 channels are open", () => {
      const { setChannelState } = useRealtimeStore.getState();
      setChannelState("/ws/events",     "open");
      setChannelState("/ws/sla-alerts", "open");
      setChannelState("/ws/activity",   "open");
      expect(useRealtimeStore.getState().connectionState).toBe("connected");
    });

    it("degraded when some channels open, not all", () => {
      const { setChannelState } = useRealtimeStore.getState();
      setChannelState("/ws/events",     "open");
      setChannelState("/ws/sla-alerts", "closed");
      setChannelState("/ws/activity",   "open");
      expect(useRealtimeStore.getState().connectionState).toBe("degraded");
    });

    it("connecting when any channel is still connecting", () => {
      const { setChannelState } = useRealtimeStore.getState();
      setChannelState("/ws/events",     "connecting");
      setChannelState("/ws/sla-alerts", "closed");
      setChannelState("/ws/activity",   "closed");
      expect(useRealtimeStore.getState().connectionState).toBe("connecting");
    });

    it("error when any channel errors", () => {
      const { setChannelState } = useRealtimeStore.getState();
      setChannelState("/ws/events",     "error");
      setChannelState("/ws/sla-alerts", "open");
      setChannelState("/ws/activity",   "open");
      expect(useRealtimeStore.getState().connectionState).toBe("error");
    });

    it("disconnected when all channels closed", () => {
      const { setChannelState } = useRealtimeStore.getState();
      setChannelState("/ws/events",     "closed");
      setChannelState("/ws/sla-alerts", "closed");
      setChannelState("/ws/activity",   "closed");
      expect(useRealtimeStore.getState().connectionState).toBe("disconnected");
    });

    it("records lastConnectedAt when transitioning to connected", () => {
      const before = Date.now();
      const { setChannelState } = useRealtimeStore.getState();
      setChannelState("/ws/events",     "open");
      setChannelState("/ws/sla-alerts", "open");
      setChannelState("/ws/activity",   "open");
      const ts = useRealtimeStore.getState().lastConnectedAt;
      expect(ts).not.toBeNull();
      expect(new Date(ts!).getTime()).toBeGreaterThanOrEqual(before);
    });
  });

  describe("clearLog", () => {
    it("resets eventLog and lastEvent", () => {
      useRealtimeStore.getState().pushEvent(makeActivity("cl-1"));
      useRealtimeStore.getState().clearLog();
      expect(useRealtimeStore.getState().eventLog).toHaveLength(0);
      expect(useRealtimeStore.getState().lastEvent).toBeNull();
    });
  });
});
