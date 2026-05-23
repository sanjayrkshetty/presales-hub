"use client";

import { useEffect, useRef } from "react";
import { X, Bell, AlertTriangle, Info, CheckCircle, AlertCircle } from "lucide-react";
import { useNotificationStore, type Notification } from "@/lib/store/notifications";

const TYPE_ICON = {
  danger:  <AlertCircle  size={11} style={{ color: "var(--danger)" }} />,
  warn:    <AlertTriangle size={11} style={{ color: "#f59e0b" }} />,
  success: <CheckCircle  size={11} style={{ color: "var(--success)" }} />,
  info:    <Info         size={11} style={{ color: "var(--accent)" }} />,
};

function timeAgo(iso: string) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60)  return `${Math.round(s)}s ago`;
  if (s < 3600) return `${Math.round(s/60)}m ago`;
  return `${Math.round(s/3600)}h ago`;
}

interface Props {
  open:    boolean;
  onClose: () => void;
}

export function NotificationPanel({ open, onClose }: Props) {
  const { notifications, markRead, dismiss, markAllRead } = useNotificationStore();
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      ref={panelRef}
      className="absolute top-11 right-0 z-50 w-80 max-h-[480px] flex flex-col rounded shadow-xl overflow-hidden"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b flex-shrink-0"
           style={{ borderColor: "var(--border)" }}>
        <div className="flex items-center gap-1.5">
          <Bell size={11} style={{ color: "var(--accent)" }} />
          <span className="text-[11px] font-semibold" style={{ color: "var(--text-primary)" }}>
            Notifications
          </span>
          {notifications.filter(n => !n.read).length > 0 && (
            <span className="text-[9px] bg-danger text-white rounded-full px-1.5 py-0.5 font-mono font-bold">
              {notifications.filter(n => !n.read).length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button onClick={markAllRead}
                  className="text-[10px] transition-colors hover:opacity-80"
                  style={{ color: "var(--accent)" }}>
            Mark all read
          </button>
          <button onClick={onClose} className="ml-1 opacity-50 hover:opacity-100">
            <X size={11} />
          </button>
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {notifications.length === 0 ? (
          <div className="px-4 py-8 text-center text-[11px]" style={{ color: "var(--text-muted)" }}>
            No notifications
          </div>
        ) : (
          notifications.map((n) => (
            <NotificationRow key={n.id} n={n} onRead={markRead} onDismiss={dismiss} />
          ))
        )}
      </div>
    </div>
  );
}

function NotificationRow({ n, onRead, onDismiss }: {
  n: Notification;
  onRead: (id: string) => void;
  onDismiss: (id: string) => void;
}) {
  return (
    <div
      onClick={() => onRead(n.id)}
      className="px-3 py-2.5 border-b flex gap-2 cursor-pointer hover:bg-white/[0.03] transition-colors"
      style={{
        borderColor: "var(--border)",
        background: !n.read ? "rgba(59,130,246,0.03)" : undefined,
      }}
    >
      <div className="mt-0.5 shrink-0">{TYPE_ICON[n.type]}</div>
      <div className="flex-1 min-w-0">
        <div className={`text-[11px] font-medium truncate ${!n.read ? "" : "opacity-70"}`}
             style={{ color: "var(--text-primary)" }}>
          {n.title}
        </div>
        <div className="text-[10px] mt-0.5 line-clamp-2" style={{ color: "var(--text-secondary)" }}>
          {n.message}
        </div>
        <div className="text-[9px] mt-1" style={{ color: "var(--text-muted)" }}>
          {timeAgo(n.created_at)}
        </div>
      </div>
      {!n.read && (
        <div className="mt-1 w-1.5 h-1.5 rounded-full shrink-0" style={{ background: "var(--accent)" }} />
      )}
      <button onClick={(e) => { e.stopPropagation(); onDismiss(n.id); }}
              className="shrink-0 opacity-0 group-hover:opacity-50 hover:opacity-100 transition-opacity self-start mt-0.5">
        <X size={10} />
      </button>
    </div>
  );
}
