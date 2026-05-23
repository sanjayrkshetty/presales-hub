"use client";
import { create } from "zustand";
import type { ConnectionState, DomainEvent } from "../types/events";
import { getEventId } from "../types/events";

const MAX_LOG  = 200;
const MAX_SEEN = 500;

// Out-of-store dedup set — avoids serialising a Set into Zustand state
const _seen = new Set<string>();
function isDuplicate(event: DomainEvent): boolean {
  const id = getEventId(event);
  if (!id) return false;
  if (_seen.has(id)) return true;
  _seen.add(id);
  if (_seen.size > MAX_SEEN) _seen.delete(_seen.values().next().value!);
  return false;
}

interface RealtimeStore {
  connectionState:  ConnectionState;
  channelStates:    Record<string, "connecting" | "open" | "closed" | "error">;
  lastEvent:        DomainEvent | null;
  eventLog:         DomainEvent[];
  lastConnectedAt:  string | null;

  setChannelState:    (channel: string, state: "connecting" | "open" | "closed" | "error") => void;
  setConnectionState: (state: ConnectionState) => void;
  pushEvent:          (event: DomainEvent) => void;
  clearLog:           () => void;
}

function computeAggregate(
  channelStates: Record<string, "connecting" | "open" | "closed" | "error">
): ConnectionState {
  const states = Object.values(channelStates);
  if (states.length === 0)          return "disconnected";
  if (states.every((s) => s === "open"))    return "connected";
  if (states.some((s) => s === "error"))    return "error";
  if (states.some((s) => s === "connecting")) return "connecting";
  if (states.some((s) => s === "open"))     return "degraded";
  return "disconnected";
}

export const useRealtimeStore = create<RealtimeStore>((set) => ({
  connectionState:  "disconnected",
  channelStates:    {},
  lastEvent:        null,
  eventLog:         [],
  lastConnectedAt:  null,

  setChannelState: (channel, state) =>
    set((s) => {
      const channelStates = { ...s.channelStates, [channel]: state };
      const connectionState = computeAggregate(channelStates);
      return {
        channelStates,
        connectionState,
        lastConnectedAt:
          connectionState === "connected" ? new Date().toISOString() : s.lastConnectedAt,
      };
    }),

  // Direct override for cases where aggregate doesn't apply (e.g., pre-init)
  setConnectionState: (state) =>
    set((s) => ({
      connectionState: state,
      lastConnectedAt:
        state === "connected" ? new Date().toISOString() : s.lastConnectedAt,
    })),

  pushEvent: (event) =>
    set((s) => {
      if (isDuplicate(event)) return s;
      return {
        lastEvent: event,
        eventLog:  [event, ...s.eventLog].slice(0, MAX_LOG),
      };
    }),

  clearLog: () => {
    _seen.clear();
    set({ eventLog: [], lastEvent: null });
  },
}));
