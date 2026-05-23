"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/lib/api/analytics";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { formatHours } from "@/lib/utils";
import { Clock } from "lucide-react";

export function SLABreachList() {
  const { data } = useQuery({
    queryKey: ["analytics", "sla"],
    queryFn:  analyticsApi.sla,
    staleTime: 10_000,
    refetchInterval: 30_000,
  });

  const breached = data?.breached ?? [];
  const warning  = data?.warning  ?? [];

  return (
    <div className="panel">
      <SectionHeader title="SLA Alerts" icon={<Clock size={11} />}
        count={(breached.length + warning.length)} />
      <div className="divide-y divide-border">
        {breached.slice(0, 5).map((opp) => (
          <div key={opp.id} className="px-3 py-2 flex items-center justify-between gap-2">
            <Link href={`/proposals/${opp.proposal_id ?? opp.id}`}
              className="text-xs font-sans text-danger hover:text-red-400 truncate flex-1">
              {opp.title}
            </Link>
            <span className="text-2xs font-mono text-danger flex-shrink-0">
              {formatHours(opp.sla.hours_remaining)}
            </span>
          </div>
        ))}
        {warning.slice(0, 3).map((opp) => (
          <div key={opp.id} className="px-3 py-2 flex items-center justify-between gap-2">
            <Link href={`/proposals/${opp.proposal_id ?? opp.id}`}
              className="text-xs font-sans text-warn hover:text-yellow-400 truncate flex-1">
              {opp.title}
            </Link>
            <span className="text-2xs font-mono text-warn flex-shrink-0">
              {formatHours(opp.sla.hours_remaining)}
            </span>
          </div>
        ))}
        {breached.length === 0 && warning.length === 0 && (
          <p className="text-xs text-text-muted text-center py-4 font-sans">All SLAs healthy</p>
        )}
      </div>
    </div>
  );
}
