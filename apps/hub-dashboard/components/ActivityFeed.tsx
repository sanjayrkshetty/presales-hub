"use client";

import { useEffect, useRef, useState } from "react";
import { wsUrl, ActivityItem } from "@/lib/api";

const ACTION_ICONS: Record<string, string> = {
  stage_transition:  "→",
  sme_assigned:      "⊕",
  approval_decision: "✓",
  sla_breach:        "⚠",
  created:           "+",
};

function timeAgo(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60)    return `${Math.round(diff)}s ago`;
  if (diff < 3600)  return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

interface Props {
  initialItems?: ActivityItem[];
}

export function ActivityFeed({ initialItems = [] }: Props) {
  const [items, setItems] = useState<ActivityItem[]>(initialItems);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(wsUrl("/ws/activity"));
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === "ping") return;
      setItems(prev => {
        const exists = prev.find(i => i.id === data.id);
        if (exists) return prev;
        return [data, ...prev].slice(0, 50);
      });
    };

    return () => ws.close();
  }, []);

  return (
    <div className="flex flex-col h-full">
      <div className="panel-header">
        Activity Feed
        <span className="ml-auto flex items-center gap-1 text-[10px]"
          style={{ color: connected ? "var(--success)" : "#64748b" }}>
          <span className={`w-1.5 h-1.5 rounded-full inline-block ${connected ? "bg-green-500 animate-pulse" : "bg-gray-600"}`} />
          {connected ? "Live" : "Offline"}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {items.length === 0 && (
          <div className="p-4 text-center text-[11px]" style={{ color: "#64748b" }}>
            Waiting for activity…
          </div>
        )}
        {items.map((item) => (
          <div key={item.id}
            className="px-3 py-2 border-b flex gap-2 items-start hover:bg-white/[0.02] transition-colors"
            style={{
              borderColor: "var(--border)",
              background: item.is_alert ? "rgba(239,68,68,0.04)" : undefined,
            }}>
            <span className="text-[11px] font-bold w-4 shrink-0 mt-0.5"
              style={{ color: item.is_alert ? "var(--danger)" : "var(--accent)" }}>
              {ACTION_ICONS[item.action_type] ?? "·"}
            </span>
            <div className="flex-1 min-w-0">
              <div className="text-[11px] truncate"
                style={{ color: item.is_alert ? "#fca5a5" : "#cbd5e1" }}>
                {item.description}
              </div>
              <div className="text-[10px] mt-0.5" style={{ color: "#475569" }}>
                {item.actor_name} · {timeAgo(item.created_at)}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
