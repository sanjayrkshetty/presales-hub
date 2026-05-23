"use client";
import { useQuery } from "@tanstack/react-query";
import { integrationApi } from "@/lib/api/integration";
import { StatusDot } from "@/components/ui/StatusDot";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Spinner } from "@/components/ui/Spinner";
import { timeAgo } from "@/lib/utils";
import type { ConnectorHealth } from "@/lib/types/api";

export function ConnectorGrid() {
  const { data: resp, isLoading } = useQuery<{ connectors: ConnectorHealth[] }>({
    queryKey: ["integration", "connectors"],
    queryFn:  () => integrationApi.listConnectors(),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  const connectors: ConnectorHealth[] = resp?.connectors ?? [];

  return (
    <div className="panel">
      <SectionHeader title="Integration Health" count={connectors.length} />
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : (
        <div className="p-3 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
          {connectors.map((c) => (
            <div key={c.platform} className="panel-sm p-3 flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-sans font-medium text-text-primary capitalize">{c.platform}</span>
                <StatusDot status={c.healthy ? "active" : "error"} pulse={c.healthy} />
              </div>
              <p className="text-2xs font-sans text-text-muted line-clamp-2">{c.message}</p>
              <div className="flex items-center justify-between mt-auto">
                <span className="text-2xs font-mono text-text-muted">{c.latency_ms}ms</span>
                <span className="text-2xs font-sans text-text-muted">{timeAgo(c.last_checked)}</span>
              </div>
            </div>
          ))}
          {connectors.length === 0 && (
            <p className="col-span-4 text-xs text-text-muted font-sans text-center py-4">No connectors registered</p>
          )}
        </div>
      )}
    </div>
  );
}
