"use client";

const STATUS_COLOR: Record<string, string> = {
  pending:   "#64748b",
  approved:  "#22c55e",
  rejected:  "#ef4444",
  escalated: "#f59e0b",
  bypassed:  "#475569",
};

const STATUS_ICON: Record<string, string> = {
  pending:   "○",
  approved:  "✓",
  rejected:  "✗",
  escalated: "⚠",
  bypassed:  "–",
};

interface ApprovalItem {
  id: string;
  stage: string | null;
  order_index: number;
  parallel_group: string | null;
  status: string;
  decision_note: string | null;
  decided_at: string | null;
  due_at: string | null;
  approver: { id: string; name: string; role: string } | null;
}

interface Props {
  approvals: ApprovalItem[];
}

export function ApprovalChain({ approvals }: Props) {
  if (approvals.length === 0) {
    return (
      <div className="text-[11px] py-4 text-center" style={{ color: "#64748b" }}>
        No approvals defined
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {approvals.map((a, idx) => (
        <div key={a.id} className="flex items-start gap-3">
          <div className="flex flex-col items-center">
            <span className="text-[14px] font-bold" style={{ color: STATUS_COLOR[a.status] ?? "#64748b" }}>
              {STATUS_ICON[a.status] ?? "○"}
            </span>
            {idx < approvals.length - 1 && (
              <div className="w-px flex-1 mt-1" style={{ background: "var(--border)", minHeight: 12 }} />
            )}
          </div>
          <div className="flex-1 pb-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium" style={{ color: "#e2e8f0" }}>
                {a.approver?.name ?? "Unassigned"}
              </span>
              <span className="badge text-[9px]"
                style={{
                  background: `${STATUS_COLOR[a.status]}22`,
                  color: STATUS_COLOR[a.status],
                  border: `1px solid ${STATUS_COLOR[a.status]}44`,
                }}>
                {a.status}
              </span>
            </div>
            <div className="text-[10px] mt-0.5" style={{ color: "#64748b" }}>
              {a.stage?.replace(/_/g, " ") ?? "—"}
              {a.parallel_group && <span className="ml-2 text-[9px]">parallel: {a.parallel_group}</span>}
            </div>
            {a.decision_note && (
              <div className="text-[10px] mt-1 italic" style={{ color: "#94a3b8" }}>
                "{a.decision_note}"
              </div>
            )}
            {a.due_at && a.status === "pending" && (
              <div className="text-[10px] mt-0.5"
                style={{ color: new Date(a.due_at) < new Date() ? "var(--danger)" : "#64748b" }}>
                Due: {new Date(a.due_at).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" })}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
