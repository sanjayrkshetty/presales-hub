"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { intelligenceApi } from "@/lib/api/intelligence";
import { AlertTriangle, X } from "lucide-react";

export function AnomalyBanner() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["intelligence", "anomalies", false],
    queryFn:  () => intelligenceApi.anomalies(false),
    staleTime: 10_000,
  });

  const ack = useMutation({
    mutationFn: (id: string) => intelligenceApi.acknowledgeAnomaly(id),
    onSuccess:  () => qc.invalidateQueries({ queryKey: ["intelligence", "anomalies"] }),
  });

  const anomalies = data?.anomalies?.filter((a) => !a.acknowledged) ?? [];
  if (anomalies.length === 0) return null;

  return (
    <div className="flex flex-col gap-1">
      {anomalies.slice(0, 3).map((a) => (
        <div key={a.id} className="flex items-start gap-2 px-3 py-2 rounded border border-warn/30 bg-warn/5">
          <AlertTriangle size={12} className="text-warn mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <span className="text-xs font-sans font-medium text-warn">{a.anomaly_type.replace(/_/g, " ")}</span>
            <span className="text-2xs text-text-muted font-sans ml-2">severity: {a.severity}</span>
          </div>
          <button
            onClick={() => ack.mutate(a.id)}
            className="text-text-muted hover:text-text-primary transition-colors flex-shrink-0"
          >
            <X size={11} />
          </button>
        </div>
      ))}
      {anomalies.length > 3 && (
        <p className="text-2xs text-text-muted font-sans px-1">+{anomalies.length - 3} more anomalies</p>
      )}
    </div>
  );
}
