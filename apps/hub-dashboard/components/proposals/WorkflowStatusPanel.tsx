"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { proposalsApi } from "@/lib/api/proposals";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Spinner } from "@/components/ui/Spinner";
import { timeAgo } from "@/lib/utils";
import { GitBranch, Play, X } from "lucide-react";

interface Props { proposalId: string; }

export function WorkflowStatusPanel({ proposalId }: Props) {
  const qc = useQueryClient();

  const { data: wf, isLoading } = useQuery({
    queryKey: ["proposals", proposalId, "workflow"],
    queryFn:  () => proposalsApi.getWorkflowStatus(proposalId),
    staleTime: 10_000,
    retry: false,
  });

  const start = useMutation({
    mutationFn: () => proposalsApi.startWorkflow(proposalId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["proposals", proposalId, "workflow"] }),
  });

  const cancel = useMutation({
    mutationFn: () => proposalsApi.cancelWorkflow(proposalId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["proposals", proposalId, "workflow"] }),
  });

  return (
    <div className="panel">
      <SectionHeader title="Temporal Workflow" icon={<GitBranch size={11} />}
        actions={
          <div className="flex gap-1">
            {(!wf || !wf.is_active) && (
              <button onClick={() => start.mutate()}
                disabled={start.isPending}
                className="flex items-center gap-1 px-2 py-0.5 rounded text-2xs font-sans font-semibold bg-accent/10 text-accent border border-accent/30 hover:bg-accent/20 transition-colors disabled:opacity-50">
                {start.isPending ? <Spinner size="sm" /> : <Play size={9} />} Start
              </button>
            )}
            {wf?.is_active && (
              <button onClick={() => cancel.mutate()}
                disabled={cancel.isPending}
                className="flex items-center gap-1 px-2 py-0.5 rounded text-2xs font-sans font-semibold bg-danger/10 text-danger border border-danger/30 hover:bg-danger/20 transition-colors disabled:opacity-50">
                {cancel.isPending ? <Spinner size="sm" /> : <X size={9} />} Cancel
              </button>
            )}
          </div>
        }
      />
      <div className="p-3">
        {isLoading && <div className="flex justify-center py-4"><Spinner /></div>}
        {!isLoading && !wf && (
          <p className="text-xs text-text-muted font-sans text-center py-2">No workflow started</p>
        )}
        {wf && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <StatusBadge status={wf.is_active ? "active" : "pending"} label={wf.is_active ? "Running" : "Stopped"} />
              <span className="text-xs font-mono text-text-secondary">Stage: {wf.stage?.replace(/_/g, " ")}</span>
            </div>
            {wf.transition_history?.length > 0 && (
              <div className="flex flex-col gap-1">
                <span className="text-2xs uppercase tracking-widest text-text-muted font-sans font-semibold">Transition History</span>
                <div className="max-h-40 overflow-y-auto flex flex-col gap-1">
                  {[...wf.transition_history].reverse().map((t, i) => (
                    <div key={i} className="flex items-center gap-2 text-2xs font-sans">
                      <span className="font-mono text-text-muted">{timeAgo(t.timestamp)}</span>
                      <span className="text-text-muted">→</span>
                      <span className="text-text-secondary">{t.to_stage?.replace(/_/g, " ")}</span>
                      {t.actor_id && <span className="text-text-muted">by {t.actor_id}</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
