"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { platformApi } from "@/lib/api/platform";
import { TenantTable } from "@/components/platform/TenantTable";
import { QuotaPanel } from "@/components/platform/QuotaPanel";
import { FeatureFlagTable } from "@/components/platform/FeatureFlagTable";
import { MetricCard } from "@/components/ui/MetricCard";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatusDot } from "@/components/ui/StatusDot";
import { timeAgo } from "@/lib/utils";
import { Shield } from "lucide-react";
import type { Tenant, PlatformHealth, AuditEntry } from "@/lib/types/api";

export default function PlatformPage() {
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null);

  const { data: health } = useQuery<PlatformHealth>({
    queryKey: ["platform", "health"],
    queryFn:  platformApi.health,
    staleTime: 30_000,
  });

  const { data: metrics } = useQuery<{ tenants_by_tier: Record<string, number>; total_usage_records: number; total_billing_events: number }>({
    queryKey: ["platform", "metrics"],
    queryFn:  platformApi.metrics,
    staleTime: 60_000,
  });

  const { data: auditResp } = useQuery<{ entries: AuditEntry[] }>({
    queryKey: ["platform", "tenants", selectedTenant?.id, "audit"],
    queryFn:  () => platformApi.getAudit(selectedTenant!.id),
    staleTime: 30_000,
    enabled: !!selectedTenant,
  });

  const tierCounts = Object.entries(metrics?.tenants_by_tier ?? {});

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Total Tenants"  value={health?.tenant_count ?? "—"} />
        <MetricCard label="Active"         value={health?.active_tenant_count ?? "—"} accent />
        <MetricCard label="Usage Records"  value={metrics?.total_usage_records ?? "—"} />
        <MetricCard label="Billing Events" value={metrics?.total_billing_events ?? "—"} />
      </div>

      {tierCounts.length > 0 && (
        <div className="panel">
          <SectionHeader title="Tenants by Tier" />
          <div className="p-3 flex gap-4">
            {tierCounts.map(([tier, count]) => (
              <div key={tier} className="panel-sm p-3 text-center min-w-24">
                <p className="text-lg font-mono font-bold text-text-primary">{count}</p>
                <p className="text-2xs font-sans text-text-muted capitalize">{tier}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {health?.warnings && health.warnings.length > 0 && (
        <div className="panel p-3 border-warn/20">
          <p className="text-xs text-warn font-sans">
            Platform warnings: {health.warnings.join(" · ")}
          </p>
        </div>
      )}

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-6">
          <TenantTable onSelect={setSelectedTenant} selected={selectedTenant?.id} />
        </div>

        <div className="col-span-12 lg:col-span-6 flex flex-col gap-4">
          {selectedTenant ? (
            <>
              <div className="panel p-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-sans font-semibold text-text-primary">{selectedTenant.org_name}</p>
                  <p className="text-xs font-mono text-text-muted">{selectedTenant.id} · {selectedTenant.tier} · {selectedTenant.region}</p>
                </div>
                <StatusDot status={selectedTenant.status === "active" ? "active" : "error"} pulse />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <QuotaPanel tenantId={selectedTenant.id} />
                <FeatureFlagTable tenantId={selectedTenant.id} />
              </div>
              {auditResp?.entries && auditResp.entries.length > 0 && (
                <div className="panel">
                  <SectionHeader title="Audit Trail" count={auditResp.entries.length} icon={<Shield size={11} />} />
                  <div className="p-3 flex flex-col gap-1 max-h-48 overflow-y-auto">
                    {auditResp.entries.map((e, i) => (
                      <div key={i} className="flex items-center gap-2 text-2xs font-sans">
                        <span className="font-mono text-text-muted">{timeAgo(e.occurred_at)}</span>
                        <span className="font-mono text-text-secondary">{e.action}</span>
                        <span className="text-text-muted">{e.resource_type}/{e.resource_id}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="panel flex items-center justify-center h-48">
              <p className="text-xs text-text-muted font-sans">Select a tenant to manage</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
