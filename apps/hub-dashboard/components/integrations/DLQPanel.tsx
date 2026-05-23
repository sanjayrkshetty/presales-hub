"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { integrationApi } from "@/lib/api/integration";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Spinner } from "@/components/ui/Spinner";
import { timeAgo } from "@/lib/utils";
import { RotateCcw } from "lucide-react";
import type { RetryJob } from "@/lib/types/api";

export function DLQPanel() {
  const qc = useQueryClient();

  const { data: resp, isLoading } = useQuery<{ jobs: RetryJob[] }>({
    queryKey: ["integration", "dlq"],
    queryFn:  () => integrationApi.dlq(),
    staleTime: 20_000,
  });

  const requeue = useMutation({
    mutationFn: (jobId: string) => integrationApi.requeueDlq(jobId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["integration", "dlq"] }),
  });

  const jobs: RetryJob[] = resp?.jobs ?? [];

  return (
    <div className="panel">
      <SectionHeader title="Dead Letter Queue" count={jobs.length} />
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : (
        <table className="data-table">
          <thead>
            <tr><th>Platform</th><th>Type</th><th>Attempts</th><th>Error</th><th>Next Retry</th><th></th></tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td><span className="text-xs font-sans text-text-primary capitalize">{job.platform}</span></td>
                <td><span className="text-xs font-mono text-text-secondary">{job.job_type}</span></td>
                <td><span className="text-xs font-mono text-warn">{job.attempt_count}/{job.max_attempts}</span></td>
                <td><span className="text-xs font-sans text-danger line-clamp-1">{job.error_message}</span></td>
                <td><span className="text-xs font-mono text-text-muted">{timeAgo(job.next_retry_at)}</span></td>
                <td>
                  <button
                    onClick={() => requeue.mutate(job.id)}
                    disabled={requeue.isPending}
                    className="flex items-center gap-1 px-1.5 py-0.5 rounded text-2xs font-sans bg-blue/10 text-blue border border-blue/20 hover:bg-blue/20 transition-colors"
                  >
                    <RotateCcw size={9} /> Requeue
                  </button>
                </td>
              </tr>
            ))}
            {jobs.length === 0 && (
              <tr><td colSpan={6} className="text-center py-6 text-xs text-text-muted font-sans">DLQ empty</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
