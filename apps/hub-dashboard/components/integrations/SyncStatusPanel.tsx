"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { integrationApi } from "@/lib/api/integration";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/utils";
import { RefreshCw } from "lucide-react";

const STATUS_COLOR: Record<string, string> = {
  synced:   "text-success",
  pending:  "text-text-muted",
  conflict: "text-warn",
  failed:   "text-danger",
};

interface SyncResp {
  by_status: Record<string, number>;
  records: Array<{ id: string; platform: string; status: string; last_synced_at: string; tenant_id: string }>;
}

export function SyncStatusPanel() {
  const qc = useQueryClient();

  const { data: resp, isLoading } = useQuery<SyncResp>({
    queryKey: ["integration", "sync"],
    queryFn:  () => integrationApi.syncStatus() as Promise<SyncResp>,
    staleTime: 30_000,
  });

  const runSync = useMutation({
    mutationFn: (channel: string) => integrationApi.runSync(channel),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["integration", "sync"] }),
  });

  const byStatus = resp?.by_status ?? {};
  const records  = (resp?.records ?? []) as Array<{ id: string; platform: string; status: string; last_synced_at: string }>;

  return (
    <div className="panel">
      <SectionHeader title="Sync Status"
        actions={
          <button
            onClick={() => runSync.mutate("all")}
            disabled={runSync.isPending}
            className="flex items-center gap-1 px-2 py-0.5 rounded text-2xs font-sans font-semibold bg-blue/10 text-blue border border-blue/30 hover:bg-blue/20 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={9} className={runSync.isPending ? "animate-spin" : ""} /> Sync All
          </button>
        }
      />
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : (
        <div className="p-3 flex flex-col gap-3">
          <div className="grid grid-cols-4 gap-2">
            {Object.entries(byStatus).map(([status, count]) => (
              <div key={status} className="panel-sm p-2 text-center">
                <p className={cn("text-sm font-mono font-bold", STATUS_COLOR[status] ?? "text-text-primary")}>{count}</p>
                <p className="text-2xs font-sans text-text-muted capitalize">{status}</p>
              </div>
            ))}
          </div>
          {records.length > 0 && (
            <table className="data-table">
              <thead><tr><th>Platform</th><th>Status</th><th>Last Synced</th></tr></thead>
              <tbody>
                {records.slice(0, 10).map((r) => (
                  <tr key={r.id}>
                    <td><span className="text-xs font-sans text-text-primary capitalize">{r.platform}</span></td>
                    <td><span className={cn("text-xs font-mono", STATUS_COLOR[r.status] ?? "")}>{r.status}</span></td>
                    <td><span className="text-xs font-mono text-text-muted">{r.last_synced_at ? new Date(r.last_synced_at).toLocaleString() : "—"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
