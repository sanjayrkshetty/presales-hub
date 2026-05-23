"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { platformApi } from "@/lib/api/platform";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Spinner } from "@/components/ui/Spinner";

interface Props { tenantId: string; }

export function FeatureFlagTable({ tenantId }: Props) {
  const qc = useQueryClient();

  const { data: resp, isLoading } = useQuery<{ flags: Record<string, boolean> }>({
    queryKey: ["platform", "tenants", tenantId, "flags"],
    queryFn:  () => platformApi.getFeatureFlags(tenantId),
    staleTime: 30_000,
    enabled: !!tenantId,
  });

  const toggle = useMutation({
    mutationFn: ({ flag, enabled }: { flag: string; enabled: boolean }) =>
      platformApi.setFeatureFlag(flag, enabled, tenantId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["platform", "tenants", tenantId, "flags"] }),
  });

  const flags = Object.entries(resp?.flags ?? {});

  return (
    <div className="panel">
      <SectionHeader title="Feature Flags" count={flags.length} />
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : (
        <div className="p-3 flex flex-col gap-1">
          {flags.map(([flag, enabled]) => (
            <div key={flag} className="flex items-center justify-between py-1 border-b border-border/50 last:border-0">
              <span className="text-xs font-mono text-text-primary">{flag.replace(/_/g, " ")}</span>
              <button
                onClick={() => toggle.mutate({ flag, enabled: !enabled })}
                disabled={toggle.isPending}
                className={`relative w-9 h-4.5 rounded-full transition-colors flex-shrink-0 ${enabled ? "bg-accent" : "bg-bg-tertiary border border-border"}`}
                style={{ height: "18px" }}
              >
                <span
                  className={`absolute top-0.5 w-3 h-3 rounded-full bg-white shadow transition-transform ${enabled ? "translate-x-[18px]" : "translate-x-0.5"}`}
                />
              </button>
            </div>
          ))}
          {flags.length === 0 && (
            <p className="text-xs text-text-muted font-sans text-center py-4">No feature flags</p>
          )}
        </div>
      )}
    </div>
  );
}
