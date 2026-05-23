import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { ActivityFeed } from "@/components/ActivityFeed";
import { useRealtimeStore } from "@/lib/store/realtime";
import { MockWebSocket } from "../setup";
import type { ActivityEvent } from "@/lib/types/events";

function makeActivityEvent(id: string, description: string): ActivityEvent {
  return {
    event_type:  "activity",
    id,
    proposal_id: "p1",
    actor_name:  "Alice",
    action_type: "created",
    description,
    is_alert:    false,
    created_at:  new Date(Date.now() - 5000).toISOString(),
  };
}

beforeEach(() => {
  useRealtimeStore.getState().clearLog();
  useRealtimeStore.setState({ channelStates: {}, connectionState: "disconnected" });
  MockWebSocket.reset();
});

describe("ActivityFeed", () => {
  it("renders 'Waiting for activity' when store is empty and no initial items", () => {
    render(<ActivityFeed />);
    expect(screen.getByText(/waiting for activity/i)).toBeTruthy();
  });

  it("renders activity events from the realtime store", () => {
    act(() => {
      useRealtimeStore.getState().pushEvent(makeActivityEvent("e1", "Proposal created for Acme"));
      useRealtimeStore.getState().pushEvent(makeActivityEvent("e2", "Stage moved to scoping"));
    });
    render(<ActivityFeed />);
    expect(screen.getByText("Proposal created for Acme")).toBeTruthy();
    expect(screen.getByText("Stage moved to scoping")).toBeTruthy();
  });

  it("deduplicates events — same id shown only once", () => {
    const ev = makeActivityEvent("dup-1", "Duplicate event");
    act(() => {
      useRealtimeStore.getState().pushEvent(ev);
      useRealtimeStore.getState().pushEvent(ev); // second push ignored by store
    });
    render(<ActivityFeed />);
    const items = screen.getAllByText("Duplicate event");
    expect(items).toHaveLength(1);
  });

  it("falls back to initialItems when store is empty", () => {
    render(
      <ActivityFeed
        initialItems={[
          {
            id:          "init-1",
            proposal_id: "p1",
            actor_name:  "Bob",
            action_type: "created",
            description: "Initial item from server",
            is_alert:    false,
            created_at:  new Date().toISOString(),
          },
        ]}
      />
    );
    expect(screen.getByText("Initial item from server")).toBeTruthy();
  });

  it("shows 'Offline' when connectionState is disconnected", () => {
    render(<ActivityFeed />);
    expect(screen.getByText("Offline")).toBeTruthy();
  });

  it("shows 'Live' when connectionState is connected", () => {
    act(() => { useRealtimeStore.setState({ connectionState: "connected" }); });
    render(<ActivityFeed />);
    expect(screen.getByText("Live")).toBeTruthy();
  });

  it("shows 'Reconnecting…' when connectionState is reconnecting", () => {
    act(() => { useRealtimeStore.setState({ connectionState: "reconnecting" }); });
    render(<ActivityFeed />);
    expect(screen.getByText("Reconnecting…")).toBeTruthy();
  });

  it("does not create WebSocket instances on render", () => {
    const countBefore = MockWebSocket._instances.length;
    render(<ActivityFeed />);
    expect(MockWebSocket._instances.length).toBe(countBefore);
  });

  it("limits rendered items to 50 even with more in store", () => {
    act(() => {
      for (let i = 0; i < 60; i++) {
        useRealtimeStore.getState().pushEvent(makeActivityEvent(`e-${i}`, `Event ${i}`));
      }
    });
    render(<ActivityFeed />);
    // Each item shows actor_name "Alice" inside "Alice · Xs ago" — use partial match
    const actors = screen.getAllByText(/^Alice/, { exact: false });
    expect(actors.length).toBeLessThanOrEqual(50);
    expect(actors.length).toBeGreaterThan(0);
  });
});
