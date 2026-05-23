"use client";
import { create } from "zustand";
import type { ConnectionState, DomainEvent } from "../types/events";

const MAX_LOG = 200;

interface RealtimeStore {
  connectionState: ConnectionState;
  lastEvent:       DomainEvent | null;
  eventLog:        DomainEvent[];
  lastConnectedAt: string | null;

  setConnectionState: (state: ConnectionState) => void;
  pushEvent:          (event: DomainEvent) => void;
  clearLog:           () => void;
}

export const useRealtimeStore = create<RealtimeStore>((set) => ({
  connectionState: "disconnected",
  lastEvent:       null,
  eventLog:        [],
  lastConnectedAt: null,

  setConnectionState: (state) =>
    set((s) => ({
      connectionState: state,
      lastConnectedAt: state === "connected" ? new Date().toISOString() : s.lastConnectedAt,
    })),

  pushEvent: (event) =>
    set((s) => ({
      lastEvent: event,
      eventLog:  [event, ...s.eventLog].slice(0, MAX_LOG),
    })),

  clearLog: () => set({ eventLog: [], lastEvent: null }),
}));
