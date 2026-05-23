"use client";
import { useEffect, useRef, useCallback } from "react";
import { useRealtimeStore } from "../store/realtime";
import { useNotificationStore } from "../store/notifications";
import { wsUrl } from "../api/client";
import type { DomainEvent, SlaBreachEvent, AnomalyDetectedEvent } from "../types/events";

const CHANNELS = ["/ws/events", "/ws/sla-alerts", "/ws/activity"] as const;
const BACKOFF   = [1000, 2000, 4000, 8000, 16000, 30000];

export function useWebSocketManager() {
  const { setConnectionState, pushEvent } = useRealtimeStore();
  const { addNotification } = useNotificationStore();
  const sockets = useRef<Map<string, WebSocket>>(new Map());
  const retries  = useRef<Map<string, number>>(new Map());
  const timers   = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const mounted  = useRef(true);

  const handleMessage = useCallback((raw: string) => {
    try {
      const event = JSON.parse(raw) as DomainEvent;
      if (event.event_type === "ping") return;
      pushEvent(event);

      if (event.event_type === "sla.breach") {
        const e = event as SlaBreachEvent;
        addNotification({ type: "danger", title: "SLA Breach", message: `Proposal ${e.proposal_id} breached SLA by ${e.hours_overdue?.toFixed(1)}h`, proposal_id: e.proposal_id });
      }
      if (event.event_type === "anomaly.detected") {
        const e = event as AnomalyDetectedEvent;
        addNotification({ type: "warn", title: "Anomaly Detected", message: e.anomaly_type ?? "Unknown anomaly", proposal_id: e.proposal_id });
      }
    } catch { /* ignore parse errors */ }
  }, [pushEvent, addNotification]);

  const connect = useCallback((path: string) => {
    if (!mounted.current) return;
    const ws = new WebSocket(wsUrl(path));
    sockets.current.set(path, ws);
    setConnectionState("connecting");

    ws.onopen = () => {
      retries.current.set(path, 0);
      // Check if all channels are open
      const allOpen = CHANNELS.every((c) => sockets.current.get(c)?.readyState === WebSocket.OPEN);
      if (allOpen) setConnectionState("connected");
    };

    ws.onmessage = (e) => handleMessage(e.data);

    ws.onclose = () => {
      if (!mounted.current) return;
      const attempt = (retries.current.get(path) ?? 0);
      const delay   = BACKOFF[Math.min(attempt, BACKOFF.length - 1)];
      retries.current.set(path, attempt + 1);
      setConnectionState("disconnected");
      const t = setTimeout(() => connect(path), delay);
      timers.current.set(path, t);
    };

    ws.onerror = () => setConnectionState("error");
  }, [handleMessage, setConnectionState]);

  useEffect(() => {
    mounted.current = true;
    CHANNELS.forEach((ch) => connect(ch));
    return () => {
      mounted.current = false;
      timers.current.forEach((t) => clearTimeout(t));
      sockets.current.forEach((ws) => ws.close());
    };
  }, [connect]);
}

export function useRealtimeEvents<T extends DomainEvent>(
  eventType: string,
  callback: (event: T) => void
) {
  const lastEvent = useRealtimeStore((s) => s.lastEvent);
  const cbRef = useRef(callback);
  cbRef.current = callback;

  useEffect(() => {
    if (lastEvent && lastEvent.event_type === eventType) {
      cbRef.current(lastEvent as T);
    }
  }, [lastEvent, eventType]);
}
