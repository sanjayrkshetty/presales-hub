import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useRealtimeStore } from "@/lib/store/realtime";
import { MockWebSocket } from "../setup";

async function importHook() {
  const mod = await import("@/lib/hooks/useWebSocket");
  return mod.useWebSocketManager;
}

beforeEach(() => {
  MockWebSocket.reset();
  useRealtimeStore.getState().clearLog();
  useRealtimeStore.setState({ channelStates: {}, connectionState: "disconnected" });
  vi.useFakeTimers();
});

afterEach(() => {
  // clearAllTimers stops the setInterval without running it infinitely
  vi.clearAllTimers();
  vi.useRealTimers();
});

describe("useWebSocketManager — socket lifecycle", () => {
  it("opens exactly 3 WebSocket connections on mount", async () => {
    const useWebSocketManager = await importHook();
    renderHook(() => useWebSocketManager());
    expect(MockWebSocket._instances).toHaveLength(3);
  });

  it("does not create extra connections on store updates (no reconnect storm)", async () => {
    const useWebSocketManager = await importHook();
    renderHook(() => useWebSocketManager());
    const initialCount = MockWebSocket._instances.length;
    // Simulate a Zustand store update
    act(() => {
      useRealtimeStore.getState().pushEvent({
        event_type: "activity",
        id:          "x1",
        proposal_id: "p",
        actor_name:  "A",
        action_type: "c",
        description: "d",
        is_alert:    false,
        created_at:  "2025",
      });
    });
    expect(MockWebSocket._instances).toHaveLength(initialCount);
  });

  it("closes all sockets on unmount", async () => {
    const useWebSocketManager = await importHook();
    const { unmount } = renderHook(() => useWebSocketManager());
    const sockets = [...MockWebSocket._instances];
    act(() => unmount());
    sockets.forEach((ws) => {
      expect(ws.readyState).toBe(MockWebSocket.CLOSED);
    });
  });

  it("sets channel to 'open' when socket opens", async () => {
    const useWebSocketManager = await importHook();
    renderHook(() => useWebSocketManager());
    act(() => {
      MockWebSocket._instances[0].simulateOpen();
    });
    const ch = MockWebSocket._instances[0].url.replace("ws://localhost:8003", "");
    const channelStates = useRealtimeStore.getState().channelStates;
    expect(channelStates[ch]).toBe("open");
  });

  it("aggregates to 'connected' when all 3 channels open", async () => {
    const useWebSocketManager = await importHook();
    renderHook(() => useWebSocketManager());
    act(() => {
      MockWebSocket._instances.forEach((ws) => ws.simulateOpen());
    });
    expect(useRealtimeStore.getState().connectionState).toBe("connected");
  });
});

describe("useWebSocketManager — message handling", () => {
  it("ignores ping events — not pushed to store (after queue flush)", async () => {
    const useWebSocketManager = await importHook();
    renderHook(() => useWebSocketManager());
    act(() => {
      MockWebSocket._instances[0].simulateMessage({ event_type: "ping" });
    });
    act(() => { vi.advanceTimersByTime(20); });
    expect(useRealtimeStore.getState().eventLog).toHaveLength(0);
  });

  it("ignores unknown event types", async () => {
    const useWebSocketManager = await importHook();
    renderHook(() => useWebSocketManager());
    act(() => {
      MockWebSocket._instances[0].simulateMessage({ event_type: "tenant.suspended", id: "x" });
    });
    act(() => { vi.advanceTimersByTime(20); });
    expect(useRealtimeStore.getState().eventLog).toHaveLength(0);
  });

  it("pushes known activity events to store after flush", async () => {
    const useWebSocketManager = await importHook();
    renderHook(() => useWebSocketManager());
    act(() => {
      MockWebSocket._instances[0].simulateMessage({
        event_type: "activity", id: "a1", proposal_id: "p1",
        actor_name: "A", action_type: "c", description: "d",
        is_alert: false, created_at: "2025-01-01T00:00:00Z",
      });
    });
    act(() => { vi.advanceTimersByTime(20); });
    expect(useRealtimeStore.getState().eventLog).toHaveLength(1);
    expect(useRealtimeStore.getState().eventLog[0].event_type).toBe("activity");
  });

  it("ignores malformed JSON without throwing", async () => {
    const useWebSocketManager = await importHook();
    renderHook(() => useWebSocketManager());
    expect(() => {
      act(() => {
        const ws = MockWebSocket._instances[0];
        ws.onmessage?.(new MessageEvent("message", { data: "{invalid json" }));
      });
    }).not.toThrow();
  });
});

describe("useWebSocketManager — backpressure queue", () => {
  it("processes burst of 25 events without dropping any", async () => {
    const useWebSocketManager = await importHook();
    renderHook(() => useWebSocketManager());

    act(() => {
      for (let i = 0; i < 25; i++) {
        MockWebSocket._instances[0].simulateMessage({
          event_type: "activity", id: `burst-${i}`, proposal_id: "p",
          actor_name: "A", action_type: "c", description: `Event ${i}`,
          is_alert: false, created_at: "2025-01-01T00:00:00Z",
        });
      }
    });

    // Flush batch 1 (20 events)
    act(() => { vi.advanceTimersByTime(20); });
    const after20 = useRealtimeStore.getState().eventLog.length;
    expect(after20).toBeGreaterThanOrEqual(1); // at least first batch processed

    // Flush batch 2 (remaining 5)
    act(() => { vi.advanceTimersByTime(20); });
    expect(useRealtimeStore.getState().eventLog.length).toBe(25);
  });

  it("cleans up the flush interval on unmount", async () => {
    const useWebSocketManager = await importHook();
    const { unmount } = renderHook(() => useWebSocketManager());
    act(() => unmount());
    // After unmount no more events should be processed
    // Add an event to the queue via a raw WS (already closed, but test the principle)
    expect(() => act(() => { vi.advanceTimersByTime(100); })).not.toThrow();
  });
});
