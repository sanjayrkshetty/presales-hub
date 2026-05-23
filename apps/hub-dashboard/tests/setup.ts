import "@testing-library/react";
import { afterEach, beforeAll, afterAll, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// Auto-cleanup after each test
afterEach(() => cleanup());

// Minimal WebSocket mock — avoids actual network connections in tests
class MockWebSocket extends EventTarget {
  static CONNECTING = 0;
  static OPEN       = 1;
  static CLOSING    = 2;
  static CLOSED     = 3;

  readyState = MockWebSocket.CONNECTING;
  url:        string;
  onopen:     ((e: Event) => void) | null  = null;
  onclose:    ((e: Event) => void) | null  = null;
  onmessage:  ((e: MessageEvent) => void) | null = null;
  onerror:    ((e: Event) => void) | null  = null;

  constructor(url: string) {
    super();
    this.url = url;
    // Simulate async open so tests can control timing
    MockWebSocket._instances.push(this);
  }

  send(_data: string) {}

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new Event("close"));
  }

  // Test helper: simulate the socket becoming open
  simulateOpen() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  simulateMessage(data: unknown) {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(data) }));
  }

  simulateError() {
    this.onerror?.(new Event("error"));
  }

  static _instances: MockWebSocket[] = [];
  static reset() { MockWebSocket._instances = []; }
}

beforeAll(() => {
  vi.stubGlobal("WebSocket", MockWebSocket);
});

afterAll(() => {
  vi.unstubAllGlobals();
});

afterEach(() => {
  MockWebSocket.reset();
});

export { MockWebSocket };
