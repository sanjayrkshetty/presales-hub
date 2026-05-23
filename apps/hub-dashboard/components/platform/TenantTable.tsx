"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { platformApi } from "@/lib/api/platform";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatusDot } from "@/components/ui/StatusDot";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/utils";
import type { Tenant } from "@/lib/types/api";

const TIER_COLOR: Record<string, string> = {
  enterprise: "text-accent",
  professional: "text-blue",
  starter: "text-text-muted",
};

interface Props {
  onSelect?: (tenant: Tenant) => void;
  selected?: string;
}

export function TenantTable({ onSelect, selected }: Props) {
  const qc = useQueryClient();

  const { data: resp, isLoading } = useQuery<{ total: number; tenants: Tenant[] }>({
    queryKey: ["platform", "tenants"],
    queryFn:  () => platformApi.listTenants(),
    staleTime: 30_000,
  });

  const updateStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      platformApi.updateStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["platform", "tenants"] }),
  });

  const tenants = resp?.tenants ?? [];

  return (
    <div className="panel">
      <SectionHeader title="Tenants" count={tenants.length} />
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : (
        <table className="data-table">
          <thead>
            <tr><th>Organisation</th><th>Tier</th><th>Region</th><th>Status</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {tenants.map((t) => (
              <tr
                key={t.id}
                onClick={() => onSelect?.(t)}
                className={cn("cursor-pointer transition-colors",
                  selected === t.id ? "bg-accent/5" : "hover:bg-bg-tertiary"
                )}
              >
                <td>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-xs font-sans text-text-primary">{t.org_name}</span>
                    <span className="text-2xs text-text-muted font-sans">{t.admin_email}</span>
                  </div>
                </td>
                <td>
                  <span className={cn("text-xs font-mono font-semibold capitalize", TIER_COLOR[t.tier] ?? "text-text-secondary")}>
                    {t.tier}
                  </span>
                </td>
                <td><span className="text-xs font-mono text-text-secondary">{t.region}</span></td>
                <td>
                  <div className="flex items-center gap-1.5">
                    <StatusDot status={t.status === "active" ? "active" : t.status === "suspended" ? "error" : "pending"} />
                    <span className="text-xs font-sans text-text-secondary capitalize">{t.status}</span>
                  </div>
                </td>
                <td onClick={(e) => e.stopPropagation()}>
                  {t.status === "active" ? (
                    <button
                      onClick={() => updateStatus.mutate({ id: t.id, status: "suspended" })}
                      disabled={updateStatus.isPending}
                      className="text-2xs text-danger hover:text-danger/80 font-sans transition-colors"
                    >
                      Suspend
                    </button>
                  ) : (
                    <button
                      onClick={() => updateStatus.mutate({ id: t.id, status: "active" })}
                      disabled={updateStatus.isPending}
                      className="text-2xs text-success hover:text-success/80 font-sans transition-colors"
                    >
                      Activate
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {tenants.length === 0 && (
              <tr><td colSpan={5} className="text-center py-8 text-xs text-text-muted font-sans">No tenants</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
