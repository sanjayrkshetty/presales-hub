"use client";

import { useMemo, useState } from "react";
import { useRealtimeStore } from "@/lib/store/realtime";
import { ActivityDetailModal } from "@/components/activity/ActivityDetailModal";
import type { ActivityEvent } from "@/lib/types/events";
import type { ActivityItem } from "@/lib/types/api";

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

function toActivityItem(e: ActivityEvent): ActivityItem {
  return {
    id:          e.id,
    proposal_id: e.proposal_id,
    actor_name:  e.actor_name,
    action_type: e.action_type,
    description: e.description,
    is_alert:    e.is_alert,
    created_at:  e.created_at,
  };
}

interface Props {
  initialItems?: ActivityItem[];
}

export function ActivityFeed({ initialItems = [] }: Props) {
  const connectionState = useRealtimeStore((s) => s.connectionState);
  const connected       = connectionState === "connected" || connectionState === "degraded";
  const eventLog        = useRealtimeStore((s) => s.eventLog);
  const [selected, setSelected] = useState<ActivityItem | null>(null);

  const storeItems = useMemo(
    () =>
      eventLog
        .filter((e): e is ActivityEvent =>
          e.event_type === "activity" || e.event_type === "activity.backfill"
        )
        .slice(0, 50)
        .map(toActivityItem),
    [eventLog]
  );

  const items = storeItems.length > 0 ? storeItems : initialItems.slice(0, 50);

  return (
    <>
      <div className="flex flex-col h-full">
        <div className="panel-header">
          Activity Feed
          <span
            className="ml-auto flex items-center gap-1 text-[10px]"
            style={{ color: connected ? "var(--success)" : "#64748b" }}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full inline-block ${
                connected ? "bg-green-500 animate-pulse" : "bg-gray-600"
              }`}
            />
            {connected ? "Live" : connectionState === "reconnecting" ? "Reconnecting…" : "Offline"}
          </span>
        </div>
        <div className="flex-1 overflow-y-auto">
          {items.length === 0 && (
            <div className="p-4 text-center text-[11px]" style={{ color: "#64748b" }}>
              Waiting for activity…
            </div>
          )}
          {items.map((item) => (
            <button
              key={item.id}
              onClick={() => setSelected(item)}
              className="w-full text-left px-3 py-2 border-b flex gap-2 items-start hover:bg-white/[0.04] transition-colors cursor-pointer"
              style={{
                borderColor: "var(--border)",
                background: item.is_alert ? "rgba(239,68,68,0.04)" : undefined,
              }}
            >
              <span
                className="text-[11px] font-bold w-4 shrink-0 mt-0.5"
                style={{ color: item.is_alert ? "var(--danger)" : "var(--accent)" }}
              >
                {ACTION_ICONS[item.action_type] ?? "·"}
              </span>
              <div className="flex-1 min-w-0">
                <div
                  className="text-[11px] truncate"
                  style={{ color: item.is_alert ? "#fca5a5" : "#cbd5e1" }}
                >
                  {item.description}
                </div>
                <div className="text-[10px] mt-0.5" style={{ color: "#475569" }}>
                  {item.actor_name} · {timeAgo(item.created_at)}
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {selected && (
        <ActivityDetailModal item={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}
