"use client";

import { X, ExternalLink } from "lucide-react";
import { useRouter } from "next/navigation";
import type { ActivityItem } from "@/lib/types/api";

const ACTION_LABELS: Record<string, string> = {
  stage_transition:  "Stage Transition",
  sme_assigned:      "SME Assigned",
  approval_decision: "Approval Decision",
  sla_breach:        "SLA Breach",
  created:           "Created",
};

function fmt(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(iso));
}

interface Props {
  item: ActivityItem | null;
  onClose: () => void;
}

export function ActivityDetailModal({ item, onClose }: Props) {
  const router = useRouter();
  if (!item) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm mx-4 panel shadow-panel-lg animate-fade_in overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <span
            className="text-xs font-mono font-semibold uppercase tracking-widest"
            style={{ color: item.is_alert ? "var(--danger)" : "var(--accent)" }}
          >
            {ACTION_LABELS[item.action_type] ?? item.action_type}
          </span>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary transition-colors">
            <X size={14} />
          </button>
        </div>

        <div className="px-4 py-4 flex flex-col gap-3">
          <p className="text-sm text-text-primary font-sans leading-relaxed">
            {item.description}
          </p>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <p className="text-2xs text-text-muted mb-0.5">Actor</p>
              <p className="text-xs text-text-secondary font-mono">{item.actor_name}</p>
            </div>
            <div>
              <p className="text-2xs text-text-muted mb-0.5">Time</p>
              <p className="text-xs text-text-secondary font-mono">{fmt(item.created_at)}</p>
            </div>
            {item.proposal_id && (
              <div className="col-span-2">
                <p className="text-2xs text-text-muted mb-0.5">Proposal ID</p>
                <p className="text-xs text-text-secondary font-mono truncate">{item.proposal_id}</p>
              </div>
            )}
          </div>
        </div>

        {item.proposal_id && (
          <div className="px-4 pb-4">
            <button
              onClick={() => { router.push(`/proposals?id=${item.proposal_id}`); onClose(); }}
              className="w-full flex items-center justify-center gap-2 py-2 rounded border border-border text-xs text-text-secondary hover:text-text-primary hover:border-border-subtle transition-colors font-sans"
            >
              <ExternalLink size={12} />
              View Proposal
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
