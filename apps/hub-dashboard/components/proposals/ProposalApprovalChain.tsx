"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { proposalsApi } from "@/lib/api/proposals";
import { approvalsApi } from "@/lib/api/approvals";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Spinner } from "@/components/ui/Spinner";
import { timeAgo } from "@/lib/utils";
import { CheckSquare, CheckCircle, XCircle, AlertCircle } from "lucide-react";
import type { Approval } from "@/lib/types/api";

interface Props { proposalId: string; }

export function ProposalApprovalChain({ proposalId }: Props) {
  const qc = useQueryClient();
  const [deciding, setDeciding] = useState<string | null>(null);
  const [note, setNote] = useState("");

  const { data: approvals = [], isLoading } = useQuery({
    queryKey: ["proposals", proposalId, "approvals"],
    queryFn:  () => proposalsApi.getApprovals(proposalId),
    staleTime: 15_000,
  });

  const decide = useMutation({
    mutationFn: ({ id, status }: { id: string; status: "approved" | "rejected" | "escalated" }) =>
      approvalsApi.decide(id, status, note || undefined),
    onSuccess: () => {
      setDeciding(null); setNote("");
      qc.invalidateQueries({ queryKey: ["proposals", proposalId, "approvals"] });
    },
  });

  const statusIcon = (s: string) => {
    if (s === "approved") return <CheckCircle size={12} className="text-success" />;
    if (s === "rejected") return <XCircle size={12} className="text-danger" />;
    if (s === "escalated") return <AlertCircle size={12} className="text-warn" />;
    return <CheckCircle size={12} className="text-text-muted opacity-30" />;
  };

  const pending = approvals.filter((a) => a.status === "pending");

  return (
    <div className="panel">
      <SectionHeader title="Approval Chain" count={approvals.length} icon={<CheckSquare size={11} />} />
      <div className="p-3 flex flex-col gap-2">
        {isLoading && <Spinner />}
        {approvals.map((a: Approval) => (
          <div key={a.id} className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              {statusIcon(a.status)}
              <span className="text-xs font-sans text-text-primary flex-1">{a.approver.name}</span>
              <span className="text-2xs text-text-muted font-sans">{a.approver.role}</span>
              <StatusBadge status={a.status} />
            </div>
            <div className="ml-5 flex items-center gap-2 text-2xs text-text-muted font-sans">
              <span className="font-mono">{a.stage.replace(/_/g, " ")}</span>
              {a.decided_at && <span>· {timeAgo(a.decided_at)}</span>}
              {a.due_at && a.status === "pending" && (
                <span className="text-warn">due {timeAgo(a.due_at)}</span>
              )}
            </div>
            {a.decision_note && (
              <p className="ml-5 text-2xs text-text-secondary font-sans italic">"{a.decision_note}"</p>
            )}
            {a.status === "pending" && deciding === a.id && (
              <div className="ml-5 mt-1 flex flex-col gap-1.5 p-2 rounded border border-border bg-bg-tertiary">
                <input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Decision note (optional)…"
                  className="w-full bg-transparent text-xs text-text-primary placeholder:text-text-muted outline-none border-b border-border pb-1 font-sans"
                />
                <div className="flex gap-1.5">
                  {(["approved", "rejected", "escalated"] as const).map((s) => (
                    <button key={s} onClick={() => decide.mutate({ id: a.id, status: s })}
                      disabled={decide.isPending}
                      className={`px-2 py-0.5 rounded text-2xs font-sans font-semibold border transition-colors disabled:opacity-50
                        ${s === "approved"  ? "bg-success/10 text-success border-success/30 hover:bg-success/20" : ""}
                        ${s === "rejected"  ? "bg-danger/10 text-danger border-danger/30 hover:bg-danger/20" : ""}
                        ${s === "escalated" ? "bg-warn/10 text-warn border-warn/30 hover:bg-warn/20" : ""}
                      `}>
                      {decide.isPending ? <Spinner size="sm" /> : s}
                    </button>
                  ))}
                  <button onClick={() => setDeciding(null)}
                    className="px-2 py-0.5 rounded text-2xs text-text-muted hover:text-text-primary font-sans transition-colors">
                    cancel
                  </button>
                </div>
              </div>
            )}
            {a.status === "pending" && deciding !== a.id && (
              <button onClick={() => setDeciding(a.id)}
                className="ml-5 text-2xs text-accent hover:text-accent-hover font-sans transition-colors self-start">
                Record decision →
              </button>
            )}
          </div>
        ))}
        {!isLoading && approvals.length === 0 && (
          <p className="text-xs text-text-muted font-sans text-center py-2">No approvals configured</p>
        )}
      </div>
    </div>
  );
}
