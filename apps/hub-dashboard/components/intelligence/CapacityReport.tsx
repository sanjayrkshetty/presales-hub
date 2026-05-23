"use client";
import { useQuery } from "@tanstack/react-query";
import { strategyApi } from "@/lib/api/strategy";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/utils";
import type { CapacityReport as CapacityReportType } from "@/lib/types/api";

interface CapacityResponse {
  report: CapacityReportType;
  advisory: string;
}

export function CapacityReport() {
  const { data: resp, isLoading } = useQuery<CapacityResponse>({
    queryKey: ["strategy", "capacity"],
    queryFn: strategyApi.capacity,
    staleTime: 60_000,
  });

  const report = resp?.report;
  const saturation = Object.entries(report?.sme_saturation ?? {});

  return (
    <div className="panel">
      <SectionHeader title="SME Capacity" />
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : (
        <div className="p-3 flex flex-col gap-2">
          {report?.burnout_signals && report.burnout_signals.length > 0 && (
            <div className="panel-sm p-2 border-warn/20">
              <p className="text-2xs text-warn font-sans">
                Burnout signals: {report.burnout_signals.join(", ")}
              </p>
            </div>
          )}

          {saturation.map(([sme, pct]) => {
            const color = pct >= 90 ? "bg-danger" : pct >= 70 ? "bg-warn" : "bg-success";
            return (
              <div key={sme} className="flex items-center gap-3">
                <div className="w-32 flex-shrink-0">
                  <p className="text-xs font-sans text-text-primary truncate">{sme.replace(/_/g, " ")}</p>
                </div>
                <div className="flex-1 flex items-center gap-2">
                  <div className="health-bar flex-1">
                    <div className={cn("health-bar-fill", color)} style={{ width: `${Math.min(100, Math.round(pct))}%` }} />
                  </div>
                  <span className={cn("text-2xs font-mono w-8 text-right",
                    pct >= 90 ? "text-danger" : pct >= 70 ? "text-warn" : "text-success"
                  )}>{Math.round(pct)}%</span>
                </div>
              </div>
            );
          })}

          {saturation.length === 0 && (
            <p className="text-xs text-text-muted font-sans text-center py-4">No SME saturation data</p>
          )}

          {report?.approval_bottlenecks && report.approval_bottlenecks.length > 0 && (
            <p className="text-2xs font-sans text-text-muted mt-1">
              Bottlenecks: <span className="text-text-secondary">{report.approval_bottlenecks.join(", ")}</span>
            </p>
          )}

          {resp?.advisory && (
            <p className="text-2xs font-sans text-text-secondary italic mt-1">{resp.advisory}</p>
          )}
        </div>
      )}
    </div>
  );
}
