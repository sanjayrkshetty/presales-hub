"use client";
import { useQuery } from "@tanstack/react-query";
import { integrationApi } from "@/lib/api/integration";
import { ConnectorGrid } from "@/components/integrations/ConnectorGrid";
import { SyncStatusPanel } from "@/components/integrations/SyncStatusPanel";
import { DLQPanel } from "@/components/integrations/DLQPanel";
import { WebhookTable } from "@/components/integrations/WebhookTable";
import { MetricCard } from "@/components/ui/MetricCard";
import type { IntegrationDashboard } from "@/lib/types/api";

export default function IntegrationsPage() {
  const { data: dash } = useQuery<IntegrationDashboard>({
    queryKey: ["integration", "dashboard"],
    queryFn:  () => integrationApi.dashboard(),
    staleTime: 30_000,
  });

  const healthy  = Object.values(dash?.connector_status ?? {}).filter((s) => s === "healthy").length;
  const total    = Object.keys(dash?.connector_status ?? {}).length;
  const dlqCount = dash?.webhook_delivery?.dlq ?? 0;
  const failed   = dash?.failed_jobs ?? 0;

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Connectors OK"  value={`${healthy}/${total || "—"}`} accent={healthy === total && total > 0} />
        <MetricCard label="Sync Conflicts" value={dash?.sync_health?.conflict ?? "—"} warn={(dash?.sync_health?.conflict ?? 0) > 0} />
        <MetricCard label="Failed Jobs"    value={failed} danger={failed > 0} />
        <MetricCard label="DLQ"            value={dlqCount} warn={dlqCount > 0} />
      </div>

      <ConnectorGrid />

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-6">
          <SyncStatusPanel />
        </div>
        <div className="col-span-12 lg:col-span-6">
          <DLQPanel />
        </div>
        <div className="col-span-12">
          <WebhookTable />
        </div>
      </div>
    </div>
  );
}
