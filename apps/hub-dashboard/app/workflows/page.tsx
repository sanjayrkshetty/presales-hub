"use client";
import { useQuery } from "@tanstack/react-query";
import { opportunitiesApi } from "@/lib/api/opportunities";
import { MetricCard } from "@/components/ui/MetricCard";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Spinner } from "@/components/ui/Spinner";
import { WorkflowStatusPanel } from "@/components/proposals/WorkflowStatusPanel";
import { formatHours, slaColor } from "@/lib/utils";
import { GitBranch } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import type { Opportunity } from "@/lib/types/api";

export default function WorkflowsPage() {
  const [selected, setSelected] = useState<string | null>(null);

  const { data: opps = [], isLoading } = useQuery<Opportunity[]>({
    queryKey: ["opportunities"],
    queryFn:  opportunitiesApi.list,
    staleTime: 20_000,
  });

  const active    = opps.filter((o) => o.stage !== "closed_won" && o.stage !== "closed_lost");
  const breached  = opps.filter((o) => o.sla.status === "breached").length;
  const atRisk    = opps.filter((o) => o.sla.status === "warning").length;

  const selectedOpp = opps.find((o) => (o.proposal_id ?? o.id) === selected);

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="grid grid-cols-3 gap-3">
        <MetricCard label="Active Workflows" value={active.length} icon={<GitBranch size={13} />} />
        <MetricCard label="SLA Breached"     value={breached} danger={breached > 0} />
        <MetricCard label="At Risk"          value={atRisk} warn={atRisk > 0} />
      </div>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-5">
          <div className="panel">
            <SectionHeader title="Active Proposals" count={active.length} icon={<GitBranch size={11} />} />
            {isLoading ? (
              <div className="flex justify-center py-8"><Spinner /></div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr><th>Proposal</th><th>Stage</th><th>SLA</th><th></th></tr>
                </thead>
                <tbody>
                  {active.map((opp) => {
                    const pid = opp.proposal_id ?? opp.id;
                    return (
                      <tr
                        key={opp.id}
                        onClick={() => setSelected(pid)}
                        className={`cursor-pointer transition-colors ${selected === pid ? "bg-accent/5" : "hover:bg-bg-tertiary"}`}
                      >
                        <td>
                          <div className="flex flex-col gap-0.5">
                            <span className="text-xs font-sans text-text-primary">{opp.title}</span>
                            <span className="text-2xs text-text-muted font-sans">{opp.client?.name}</span>
                          </div>
                        </td>
                        <td>
                          <span className="text-xs font-mono text-text-secondary">{opp.stage.replace(/_/g, " ")}</span>
                        </td>
                        <td>
                          <span className="text-xs font-mono" style={{ color: slaColor(opp.sla.status) }}>
                            {formatHours(opp.sla.hours_remaining)}
                          </span>
                        </td>
                        <td>
                          <Link
                            href={`/proposals/${pid}`}
                            onClick={(e) => e.stopPropagation()}
                            className="text-2xs text-accent hover:text-accent-hover font-sans transition-colors"
                          >
                            War Room →
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                  {active.length === 0 && (
                    <tr><td colSpan={4} className="text-center py-8 text-xs text-text-muted font-sans">No active proposals</td></tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div className="col-span-12 lg:col-span-7">
          {selected ? (
            <div className="flex flex-col gap-4">
              {selectedOpp && (
                <div className="panel p-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-sans font-semibold text-text-primary">{selectedOpp.title}</p>
                      <p className="text-xs text-text-muted font-sans mt-0.5">{selectedOpp.client?.name} · {selectedOpp.stage.replace(/_/g, " ")}</p>
                    </div>
                    <StatusBadge status={selectedOpp.sla.status} label={formatHours(selectedOpp.sla.hours_remaining)} />
                  </div>
                </div>
              )}
              <WorkflowStatusPanel proposalId={selected} />
            </div>
          ) : (
            <div className="panel flex items-center justify-center h-48">
              <p className="text-xs text-text-muted font-sans">Select a proposal to view its workflow</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
