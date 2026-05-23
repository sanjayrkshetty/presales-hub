"use client";

import { X, CheckCircle, AlertTriangle, Info, AlertCircle } from "lucide-react";
import { useToastStore, type Toast } from "@/lib/store/toast";

const ICONS = {
  success: <CheckCircle  size={13} className="shrink-0" style={{ color: "var(--success)" }} />,
  warn:    <AlertTriangle size={13} className="shrink-0" style={{ color: "#f59e0b" }} />,
  danger:  <AlertCircle  size={13} className="shrink-0" style={{ color: "var(--danger)" }} />,
  info:    <Info         size={13} className="shrink-0" style={{ color: "var(--accent)" }} />,
};

const BORDER_COLORS = {
  success: "var(--success)",
  warn:    "#f59e0b",
  danger:  "var(--danger)",
  info:    "var(--accent)",
};

function ToastItem({ toast }: { toast: Toast }) {
  const remove = useToastStore((s) => s.remove);
  return (
    <div
      className="flex items-start gap-2.5 px-3 py-2.5 rounded shadow-lg text-[11px] min-w-[260px] max-w-[340px]"
      style={{
        background:  "var(--surface)",
        border:      `1px solid ${BORDER_COLORS[toast.type]}`,
        borderLeft:  `3px solid ${BORDER_COLORS[toast.type]}`,
        color:       "var(--text-primary)",
      }}
    >
      {ICONS[toast.type]}
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate">{toast.title}</div>
        {toast.message && (
          <div className="mt-0.5 text-[10px]" style={{ color: "var(--text-secondary)" }}>
            {toast.message}
          </div>
        )}
      </div>
      <button
        onClick={() => remove(toast.id)}
        className="shrink-0 opacity-50 hover:opacity-100 transition-opacity"
      >
        <X size={11} />
      </button>
    </div>
  );
}

export function ToastStack() {
  const toasts = useToastStore((s) => s.toasts);
  if (toasts.length === 0) return null;
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto">
          <ToastItem toast={t} />
        </div>
      ))}
    </div>
  );
}
