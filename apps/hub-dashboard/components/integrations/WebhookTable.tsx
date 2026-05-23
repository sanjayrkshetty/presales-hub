"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { integrationApi } from "@/lib/api/integration";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatusDot } from "@/components/ui/StatusDot";
import { Spinner } from "@/components/ui/Spinner";
import { timeAgo } from "@/lib/utils";
import { Trash2 } from "lucide-react";
import type { WebhookSubscription } from "@/lib/types/api";

export function WebhookTable() {
  const qc = useQueryClient();

  const { data: resp, isLoading } = useQuery<{ subscriptions: WebhookSubscription[] }>({
    queryKey: ["integration", "webhooks"],
    queryFn:  () => integrationApi.listWebhooks(),
    staleTime: 30_000,
  });

  const del = useMutation({
    mutationFn: (id: string) => integrationApi.deleteWebhook(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["integration", "webhooks"] }),
  });

  const subs = resp?.subscriptions ?? [];

  return (
    <div className="panel">
      <SectionHeader title="Webhook Subscriptions" count={subs.length} />
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : (
        <table className="data-table">
          <thead>
            <tr><th>URL</th><th>Events</th><th>Status</th><th>Created</th><th></th></tr>
          </thead>
          <tbody>
            {subs.map((sub) => (
              <tr key={sub.id}>
                <td>
                  <span className="text-xs font-mono text-text-secondary truncate max-w-48 block">{sub.target_url}</span>
                </td>
                <td>
                  <div className="flex flex-wrap gap-1">
                    {sub.event_types.slice(0, 3).map((e) => (
                      <span key={e} className="px-1 py-0.5 rounded text-2xs font-mono bg-blue/10 text-blue border border-blue/20">
                        {e}
                      </span>
                    ))}
                    {sub.event_types.length > 3 && (
                      <span className="text-2xs text-text-muted font-sans">+{sub.event_types.length - 3}</span>
                    )}
                  </div>
                </td>
                <td>
                  <StatusDot status={sub.active ? "active" : "error"} pulse={sub.active} />
                </td>
                <td><span className="text-xs font-mono text-text-muted">{timeAgo(sub.created_at)}</span></td>
                <td>
                  <button
                    onClick={() => del.mutate(sub.id)}
                    disabled={del.isPending}
                    className="p-1 rounded text-text-muted hover:text-danger transition-colors"
                  >
                    <Trash2 size={11} />
                  </button>
                </td>
              </tr>
            ))}
            {subs.length === 0 && (
              <tr><td colSpan={5} className="text-center py-6 text-xs text-text-muted font-sans">No webhooks configured</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
