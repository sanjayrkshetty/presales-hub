"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { agentsApi } from "@/lib/api/agents";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ConfidenceBar } from "@/components/copilot/ConfidenceBar";
import { Spinner } from "@/components/ui/Spinner";
import { timeAgo } from "@/lib/utils";
import { CheckCircle, XCircle } from "lucide-react";
import type { AgentTask } from "@/lib/types/api";

interface Props { taskId: string; }

export function AgentTaskCard({ taskId }: Props) {
  const qc = useQueryClient();

  const { data: task } = useQuery<AgentTask>({
    queryKey: ["agents", "tasks", taskId],
    queryFn: () => agentsApi.getTask(taskId),
    refetchInterval: (q) => {
      const data = q.state.data as AgentTask | undefined;
      return data?.status === "running" || data?.status === "pending" ? 3000 : false;
    },
  });

  const override = useMutation({
    mutationFn: ({ decision, reason }: { decision: "approved" | "rejected"; reason?: string }) =>
      agentsApi.humanOverride(taskId, decision, reason) as Promise<{ approved: boolean }>,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agents", "tasks", taskId] }),
  });

  if (!task) return <div className="panel-sm p-3"><Spinner /></div>;

  return (
    <div className="panel-sm p-3 flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-0.5 min-w-0">
          <span className="text-xs font-mono text-text-primary truncate">{task.task_id}</span>
          <span className="text-2xs font-sans text-text-muted">{task.agent_type?.replace(/_/g, " ")}</span>
        </div>
        <StatusBadge status={task.status} />
      </div>

      {task.confidence != null && (
        <ConfidenceBar score={task.confidence} />
      )}

      {task.output_summary && (
        <div className="bg-bg-primary rounded p-2">
          <p className="text-2xs font-sans text-text-secondary line-clamp-3">{task.output_summary}</p>
        </div>
      )}

      <div className="flex items-center justify-between">
        <span className="text-2xs font-sans text-text-muted">{timeAgo(task.created_at)}</span>
        {task.status === "awaiting_approval" && (
          <div className="flex gap-1.5">
            <button
              onClick={() => override.mutate({ decision: "approved" })}
              disabled={override.isPending}
              className="flex items-center gap-1 px-2 py-0.5 rounded bg-success/10 text-success border border-success/30 text-2xs font-sans hover:bg-success/20 transition-colors"
            >
              <CheckCircle size={10} /> Approve
            </button>
            <button
              onClick={() => override.mutate({ decision: "rejected" })}
              disabled={override.isPending}
              className="flex items-center gap-1 px-2 py-0.5 rounded bg-danger/10 text-danger border border-danger/30 text-2xs font-sans hover:bg-danger/20 transition-colors"
            >
              <XCircle size={10} /> Reject
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
