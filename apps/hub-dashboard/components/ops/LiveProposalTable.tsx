"use client";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { opportunitiesApi } from "@/lib/api/opportunities";
import { useRealtimeEvents } from "@/lib/hooks/useWebSocket";
import { formatCurrency, formatHours, slaColor, healthColor, cn } from "@/lib/utils";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { Spinner } from "@/components/ui/Spinner";
import type { ProposalTransitionedEvent, SlaBreachEvent } from "@/lib/types/events";
import { useState } from "react";
import { ArrowUpDown } from "lucide-react";
import type { Opportunity } from "@/lib/types/api";

type SortKey = "sla" | "health" | "value" | "stage";

export function LiveProposalTable() {
  const qc = useQueryClient();
  const [sort, setSort] = useState<SortKey>("sla");
  const [flashIds, setFlashIds] = useState<Set<string>>(new Set());

  const { data: opps = [], isLoading } = useQuery({
    queryKey: ["opportunities"],
    queryFn:  opportunitiesApi.list,
    staleTime: 15_000,
  });

  useRealtimeEvents<ProposalTransitionedEvent>("proposal.transitioned", () => {
    qc.invalidateQueries({ queryKey: ["opportunities"] });
  });

  useRealtimeEvents<SlaBreachEvent>("sla.breach", (e) => {
    const related = opps.find((o) => o.proposal_id === e.proposal_id || o.id === e.opportunity_id);
    if (related) {
      setFlashIds((s) => { const n = new Set(s); n.add(related.id); return n; });
      setTimeout(() => setFlashIds((s) => { const n = new Set(s); n.delete(related.id); return n; }), 1500);
      qc.invalidateQueries({ queryKey: ["opportunities"] });
    }
  });

  const sorted = [...opps].sort((a, b) => {
    if (sort === "sla")    return (a.sla.hours_remaining ?? Infinity) - (b.sla.hours_remaining ?? Infinity);
    if (sort === "health") return (a.health_score) - (b.health_score);
    if (sort === "value")  return (b.deal_value_cr) - (a.deal_value_cr);
    if (sort === "stage")  return a.stage.localeCompare(b.stage);
    return 0;
  });

  const colBtn = (key: SortKey, label: string) => (
    <button
      onClick={() => setSort(key)}
      className={cn("flex items-center gap-1 hover:text-text-primary transition-colors", sort === key && "text-accent")}
    >
      {label}<ArrowUpDown size={9} />
    </button>
  );

  if (isLoading) return <div className="flex justify-center py-8"><Spinner /></div>;

  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th>Opportunity</th>
            <th>{colBtn("stage", "Stage")}</th>
            <th>{colBtn("health", "Health")}</th>
            <th>{colBtn("sla", "SLA")}</th>
            <th>{colBtn("value", "Value")}</th>
            <th>Win %</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((opp) => (
            <tr key={opp.id} className={cn(flashIds.has(opp.id) && "row-flash")}>
              <td>
                <div className="flex flex-col gap-0.5">
                  <Link href={`/proposals/${opp.proposal_id ?? opp.id}`}
                    className="text-text-primary hover:text-accent transition-colors text-xs font-sans font-medium truncate max-w-48">
                    {opp.title}
                  </Link>
                  <span className="text-2xs text-text-muted font-sans">{opp.client?.name}</span>
                </div>
              </td>
              <td>
                <span className="text-xs text-text-secondary font-mono">
                  {opp.stage.replace(/_/g, " ")}
                </span>
              </td>
              <td>
                <ProgressRing score={opp.health_score} size={36} stroke={3} />
              </td>
              <td>
                <div className="flex flex-col gap-0.5">
                  <StatusBadge status={opp.sla.status} />
                  <span className="text-2xs font-mono" style={{ color: slaColor(opp.sla.status) }}>
                    {formatHours(opp.sla.hours_remaining)}
                  </span>
                </div>
              </td>
              <td className="font-mono text-xs text-text-primary">{formatCurrency(opp.deal_value_cr)}</td>
              <td>
                <span className="font-mono text-xs" style={{ color: healthColor(opp.win_probability * 100) }}>
                  {(opp.win_probability * 100).toFixed(0)}%
                </span>
              </td>
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr><td colSpan={6} className="text-center py-8 text-xs text-text-muted font-sans">No active opportunities</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
