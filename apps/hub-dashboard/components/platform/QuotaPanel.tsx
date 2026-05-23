"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { platformApi } from "@/lib/api/platform";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/utils";
import { useState } from "react";
import type { TenantQuota } from "@/lib/types/api";

interface Props { tenantId: string; }

export function QuotaPanel({ tenantId }: Props) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const [newLimit, setNewLimit] = useState("");

  const { data: resp, isLoading } = useQuery<{ tenant_id: string; quotas: TenantQuota[] }>({
    queryKey: ["platform", "tenants", tenantId, "quotas"],
    queryFn:  () => platformApi.getQuotas(tenantId),
    staleTime: 30_000,
    enabled: !!tenantId,
  });

  const update = useMutation({
    mutationFn: ({ resource, limit }: { resource: string; limit: number }) =>
      platformApi.updateQuota(tenantId, resource, limit),
    onSuccess: () => {
      setEditing(null);
      setNewLimit("");
      qc.invalidateQueries({ queryKey: ["platform", "tenants", tenantId, "quotas"] });
    },
  });

  const quotas = resp?.quotas ?? [];

  return (
    <div className="panel">
      <SectionHeader title="Quotas" />
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : (
        <div className="p-3 flex flex-col gap-2">
          {quotas.map((q) => {
            const color = q.percent_used >= 90 ? "bg-danger" : q.percent_used >= 70 ? "bg-warn" : "bg-success";
            return (
              <div key={q.resource} className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-sans text-text-primary">{q.resource.replace(/_/g, " ")}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-2xs font-mono text-text-muted">{q.used}/{q.limit}</span>
                    <button
                      onClick={() => { setEditing(q.resource); setNewLimit(String(q.limit)); }}
                      className="text-2xs text-accent hover:text-accent-hover font-sans transition-colors"
                    >
                      Edit
                    </button>
                  </div>
                </div>
                <div className="health-bar">
                  <div className={cn("health-bar-fill", color)} style={{ width: `${Math.min(100, q.percent_used)}%` }} />
                </div>
                {editing === q.resource && (
                  <div className="flex items-center gap-2 mt-1">
                    <input
                      type="number"
                      value={newLimit}
                      onChange={(e) => setNewLimit(e.target.value)}
                      className="w-20 bg-bg-tertiary border border-border rounded px-2 py-0.5 text-xs font-mono text-text-primary outline-none focus:border-accent/50"
                    />
                    <button
                      onClick={() => update.mutate({ resource: q.resource, limit: Number(newLimit) })}
                      disabled={update.isPending || !newLimit}
                      className="px-2 py-0.5 rounded text-2xs font-sans bg-accent/10 text-accent border border-accent/30 hover:bg-accent/20 transition-colors disabled:opacity-50"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setEditing(null)}
                      className="text-2xs text-text-muted hover:text-text-primary font-sans transition-colors"
                    >
                      cancel
                    </button>
                  </div>
                )}
              </div>
            );
          })}
          {quotas.length === 0 && (
            <p className="text-xs text-text-muted font-sans text-center py-4">No quota data</p>
          )}
        </div>
      )}
    </div>
  );
}
