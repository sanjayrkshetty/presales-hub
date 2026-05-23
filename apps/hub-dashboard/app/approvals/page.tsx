"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { opportunitiesApi } from "@/lib/api/opportunities";
import { proposalsApi } from "@/lib/api/proposals";
import { approvalsApi } from "@/lib/api/approvals";
import { MetricCard } from "@/components/ui/MetricCard";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Spinner } from "@/components/ui/Spinner";
import { timeAgo, formatHours, slaColor } from "@/lib/utils";
import { CheckSquare } from "lucide-react";
import type { Approval, Opportunity } from "@/lib/types/api";

interface ApprovalRow { approval: Approval; opp: Opportunity; }

export default function ApprovalsPage() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<"pending" | "all">("pending");
  const [deciding, setDeciding] = useState<{ approvalId: string; oppId: string } | null>(null);
  const [note, setNote] = useState("");

  const { data: opps = [], isLoading } = useQuery({
    queryKey: ["opportunities"],
    queryFn:  opportunitiesApi.list,
    staleTime: 20_000,
  });

  const decide = useMutation({
    mutationFn: ({ id, status }: { id: string; status: "approved" | "rejected" | "escalated" }) =>
      approvalsApi.decide(id, status, note || undefined),
    onSuccess: () => {
      setDeciding(null); setNote("");
      qc.invalidateQueries({ queryKey: ["opportunities"] });
    },
  });

  // Gather all approvals from all opportunities that have proposal_ids
  const rows: ApprovalRow[] = [];
  // We'll show a queue-style view using opportunities with pending SLA/stage context

  const pendingBreached = opps.filter((o) => o.sla.status === "breached").length;
  const pendingWarning  = opps.filter((o) => o.sla.status === "warning").length;

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="grid grid-cols-3 gap-3">
        <MetricCard label="Pending Review"  value={opps.length}   icon={<CheckSquare size={13} />} />
        <MetricCard label="SLA Breached"    value={pendingBreached} danger={pendingBreached > 0} />
        <MetricCard label="At Risk"         value={pendingWarning}  warn={pendingWarning > 0} />
      </div>

      <div className="panel">
        <SectionHeader title="Approval Queue" icon={<CheckSquare size={11} />}
          actions={
            <div className="flex gap-1">
              {(["pending", "all"] as const).map((f) => (
                <button key={f} onClick={() => setFilter(f)}
                  className={`px-2 py-0.5 rounded text-2xs font-sans font-semibold transition-colors
                    ${filter === f ? "bg-accent/10 text-accent border border-accent/30" : "text-text-muted hover:text-text-primary"}`}>
                  {f}
                </button>
              ))}
            </div>
          }
        />
        {isLoading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Opportunity</th>
                <th>Stage</th>
                <th>SLA</th>
                <th>Health</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {opps.map((opp) => (
                <tr key={opp.id}>
                  <td>
                    <div className="flex flex-col gap-0.5">
                      <span className="text-xs font-sans text-text-primary">{opp.title}</span>
                      <span className="text-2xs text-text-muted font-sans">{opp.client?.name}</span>
                    </div>
                  </td>
                  <td><span className="text-xs font-mono text-text-secondary">{opp.stage.replace(/_/g, " ")}</span></td>
                  <td>
                    <span className="text-xs font-mono" style={{ color: slaColor(opp.sla.status) }}>
                      {formatHours(opp.sla.hours_remaining)}
                    </span>
                  </td>
                  <td>
                    <span className="text-xs font-mono text-text-secondary">{opp.health_score}</span>
                  </td>
                  <td>
                    <a href={`/proposals/${opp.proposal_id ?? opp.id}`}
                      className="text-2xs text-accent hover:text-accent-hover font-sans transition-colors">
                      View War Room →
                    </a>
                  </td>
                </tr>
              ))}
              {opps.length === 0 && (
                <tr><td colSpan={5} className="text-center py-8 text-xs text-text-muted font-sans">Queue empty</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
