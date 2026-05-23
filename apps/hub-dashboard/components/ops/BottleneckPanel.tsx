"use client";
import { useQuery } from "@tanstack/react-query";
import { intelligenceApi } from "@/lib/api/intelligence";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { AlertOctagon } from "lucide-react";

export function BottleneckPanel() {
  const { data } = useQuery({
    queryKey: ["intelligence", "bottlenecks"],
    queryFn:  intelligenceApi.bottlenecks,
    staleTime: 20_000,
  });

  const items = data?.bottlenecks ?? [];

  return (
    <div className="panel">
      <SectionHeader title="Stage Bottlenecks" count={items.length} icon={<AlertOctagon size={11} />} />
      <div className="divide-y divide-border">
        {items.length === 0 && (
          <p className="text-xs text-text-muted text-center py-4 font-sans">No bottlenecks detected</p>
        )}
        {items.map((b, i) => (
          <div key={i} className="px-3 py-2 flex items-center justify-between gap-2">
            <div className="flex flex-col gap-0.5 min-w-0">
              <span className="text-xs font-mono text-text-primary truncate">{b.stage.replace(/_/g, " ")}</span>
              <span className="text-2xs text-text-muted font-sans">{b.affected_count} proposals · {b.estimated_delay_hours.toFixed(0)}h avg delay</span>
            </div>
            <StatusBadge status={b.severity} />
          </div>
        ))}
      </div>
    </div>
  );
}
