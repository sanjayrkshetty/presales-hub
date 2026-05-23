"use client";
import { useEffect, useRef, useCallback } from "react";
import { useRealtimeStore } from "../store/realtime";
import { useNotificationStore } from "../store/notifications";
import { wsUrl } from "../api/client";
import { parseDomainEvent } from "../types/events";
import type { DomainEvent, SlaBreachEvent, AnomalyDetectedEvent } from "../types/events";

const CHANNELS = ["/ws/events", "/ws/sla-alerts", "/ws/activity"] as const;
type Channel  = typeof CHANNELS[number];

const BACKOFF     = [1000, 2000, 4000, 8000, 16_000, 30_000] as const;
const FLUSH_MS    = 16;   // ~60fps
const BATCH_SIZE  = 20;

export function useWebSocketManager() {
  const { setChannelState, pushEvent } = useRealtimeStore();
  const { addNotification }            = useNotificationStore();

  // Stable function refs — allows connect() to be called without stale closures
  const pushRef      = useRef(pushEvent);
  const notifyRef    = useRef(addNotification);
  const channelRef   = useRef(setChannelState);
  useEffect(() => { pushRef.current    = pushEvent;       }, [pushEvent]);
  useEffect(() => { notifyRef.current  = addNotification; }, [addNotification]);
  useEffect(() => { channelRef.current = setChannelState; }, [setChannelState]);

  const sockets  = useRef<Map<Channel, WebSocket>>(new Map());
  const retries  = useRef<Map<Channel, number>>(new Map());
  const timers   = useRef<Map<Channel, ReturnType<typeof setTimeout>>>(new Map());
  const mounted  = useRef(false);
  const queue    = useRef<DomainEvent[]>([]);

  const handleMessage = useCallback((raw: string) => {
    try {
      const parsed  = JSON.parse(raw) as unknown;
      const event   = parseDomainEvent(parsed);
      if (!event || event.event_type === "ping") return;
      queue.current.push(event);
    } catch { /* ignore parse errors */ }
  }, []);

  const handleSpecialNotifications = useCallback((event: DomainEvent) => {
    if (event.event_type === "sla.breach") {
      const e = event as SlaBreachEvent;
      notifyRef.current({
        type:        "danger",
        title:       "SLA Breach",
        message:     `Proposal ${e.proposal_id} breached SLA by ${e.hours_overdue?.toFixed(1)}h`,
        proposal_id: e.proposal_id,
      });
    }
    if (event.event_type === "anomaly.detected") {
      const e = event as AnomalyDetectedEvent;
      notifyRef.current({
        type:        "warn",
        title:       "Anomaly Detected",
        message:     e.anomaly_type ?? "Unknown anomaly",
        proposal_id: e.proposal_id,
      });
    }
  }, []);

  // connect uses refs only — no useCallback deps, safe to call from the mount effect
  const connect = useCallback((path: Channel) => {
    if (!mounted.current) return;

    channelRef.current(path, "connecting");
    const ws = new WebSocket(wsUrl(path));
    sockets.current.set(path, ws);

    ws.onopen = () => {
      if (!mounted.current) return;
      retries.current.set(path, 0);
      channelRef.current(path, "open");
    };

    ws.onmessage = (e) => handleMessage(e.data);

    ws.onclose = () => {
      if (!mounted.current) return;
      channelRef.current(path, "closed");
      const attempt = retries.current.get(path) ?? 0;
      const delay   = BACKOFF[Math.min(attempt, BACKOFF.length - 1)];
      retries.current.set(path, attempt + 1);
      const t = setTimeout(() => connect(path), delay);
      timers.current.set(path, t);
    };

    ws.onerror = () => {
      channelRef.current(path, "error");
    };
  }, [handleMessage]); // handleMessage is stable (no deps inside useCallback)

  useEffect(() => {
    mounted.current = true;

    // Flush queue ~60fps — prevents synchronous rerender flood on burst events
    const flushId = setInterval(() => {
      if (queue.current.length === 0) return;
      const batch = queue.current.splice(0, BATCH_SIZE);
      batch.forEach((ev) => {
        pushRef.current(ev);
        handleSpecialNotifications(ev);
      });
    }, FLUSH_MS);

    // Single mount — connect is stable via refs; empty deps prevents reconnect storm
    CHANNELS.forEach((ch) => connect(ch));

    return () => {
      mounted.current = false;
      clearInterval(flushId);
      timers.current.forEach((t) => clearTimeout(t));
      sockets.current.forEach((ws) => ws.close());
      sockets.current.clear();
      retries.current.clear();
      timers.current.clear();
      queue.current = [];
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
}

export function useRealtimeEvents<T extends DomainEvent>(
  eventType: string,
  callback: (event: T) => void
) {
  const lastEvent = useRealtimeStore((s) => s.lastEvent);
  const cbRef     = useRef(callback);
  cbRef.current   = callback;

  useEffect(() => {
    if (lastEvent && lastEvent.event_type === eventType) {
      cbRef.current(lastEvent as T);
    }
  }, [lastEvent, eventType]);
}
