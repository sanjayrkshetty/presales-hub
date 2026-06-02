"use client";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { opportunitiesApi } from "@/lib/api/opportunities";
import { intelligenceApi } from "@/lib/api/intelligence";
import { StageProgressRail } from "@/components/proposals/StageProgressRail";
import { WorkflowStatusPanel } from "@/components/proposals/WorkflowStatusPanel";
import { ProposalApprovalChain } from "@/components/proposals/ProposalApprovalChain";
import { AssignSmePanel } from "@/components/proposals/AssignSmePanel";
import { StageCopilot } from "@/components/proposals/StageCopilot";
import { MetricCard } from "@/components/ui/MetricCard";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Spinner } from "@/components/ui/Spinner";
import { formatCurrency, formatHours, slaColor } from "@/lib/utils";
import { ArrowLeft, Zap } from "lucide-react";
import Link from "next/link";
import { useUIStore } from "@/lib/store/ui";

export default function ProposalWarRoom() {
  const { id } = useParams<{ id: string }>();
  const { toggleCopilot, copilotOpen } = useUIStore();

  const { data: opp, isLoading } = useQuery({
    queryKey: ["opportunities", id],
    queryFn:  () => opportunitiesApi.get(id),
    staleTime: 15_000,
  });

  const { data: health } = useQuery({
    queryKey: ["proposals", id, "health"],
    queryFn:  () => intelligenceApi.proposalHealth(id),
    staleTime: 30_000,
    enabled: !!id,
  });

  if (isLoading) return <div className="flex justify-center items-center h-full"><Spinner size="lg" /></div>;
  if (!opp) return <div className="p-8 text-center text-xs text-text-muted font-sans">Opportunity not found</div>;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-bg-secondary flex-shrink-0">
        <Link href="/proposals" className="text-text-muted hover:text-text-primary transition-colors">
          <ArrowLeft size={14} />
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-md font-sans font-semibold text-text-primary truncate">{opp.title}</h1>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs text-text-muted font-sans">{opp.client?.name}</span>
            <span className="text-text-muted">·</span>
            <StatusBadge status={opp.sla.status} label={`${formatHours(opp.sla.hours_remaining)} SLA`} />
          </div>
        </div>
        <div className="flex items-center gap-3">
          <MetricCard label="Value" value={formatCurrency(opp.deal_value_cr)} className="py-1.5 px-3 min-w-0" />
          <ProgressRing score={opp.health_score} size={44} />
          <button onClick={toggleCopilot}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded border text-xs font-sans font-semibold transition-colors
              ${copilotOpen ? "bg-purple/20 border-purple/40 text-purple" : "bg-bg-tertiary border-border text-text-secondary hover:text-text-primary"}`}>
            <Zap size={12} /> Copilot
          </button>
        </div>
      </div>

      {/* Stage rail */}
      <div className="px-4 py-3 border-b border-border bg-bg-secondary flex-shrink-0">
        <StageProgressRail currentStage={opp.stage} />
      </div>

      {/* Body */}
      <div className="flex flex-1 min-h-0">
        <div className="flex-1 overflow-auto p-4">
          <div className="grid grid-cols-12 gap-4">
            {/* Health breakdown */}
            {health && (
              <div className="col-span-12 panel p-3">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-2xs uppercase tracking-widest text-text-muted font-sans font-semibold">AI Health Assessment</span>
                  <span className={`text-xs font-sans font-semibold ${health.overall_score >= 80 ? "text-success" : health.overall_score >= 50 ? "text-warn" : "text-danger"}`}>
                    {health.readiness_classification}
                  </span>
                  {health.risk_factors.length > 0 && (
                    <span className="text-xs text-text-muted font-sans">
                      Risks: {health.risk_factors.join(", ")}
                    </span>
                  )}
                  {health.explanation && (
                    <p className="w-full text-xs text-text-secondary font-sans mt-1">{health.explanation}</p>
                  )}
                </div>
              </div>
            )}

            {/* Left column */}
            <div className="col-span-12 lg:col-span-5 flex flex-col gap-4">
              <WorkflowStatusPanel proposalId={id} />
              {opp.stage === "sme_assignment" && (
                <AssignSmePanel proposalId={id} rfpType={opp.rfp_type} />
              )}
              <ProposalApprovalChain proposalId={id} />
            </div>

            {/* Right column */}
            <div className="col-span-12 lg:col-span-7 flex flex-col gap-4">
              <div className="panel">
                <div className="panel-header">Deal Details</div>
                <div className="p-3 grid grid-cols-2 gap-x-6 gap-y-2">
                  {[
                    ["RFP Type",   opp.rfp_type],
                    ["Stage",      opp.stage?.replace(/_/g, " ")],
                    ["Win Prob",   `${(opp.win_probability * 100).toFixed(0)}%`],
                    ["Deadline",   new Date(opp.deadline).toLocaleDateString()],
                    ["Client",     opp.client?.name],
                    ["Sector",     opp.client?.sector],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <p className="text-2xs text-text-muted font-sans uppercase tracking-widest">{k}</p>
                      <p className="text-xs font-mono text-text-primary mt-0.5">{v}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Copilot slide-in panel */}
        {copilotOpen && (
          <div className="w-80 border-l border-border bg-bg-secondary flex flex-col animate-slide_in flex-shrink-0">
            <div className="panel-header">
              <Zap size={11} className="text-purple" />
              <span>AI Copilot</span>
            </div>
            <div className="p-3 overflow-y-auto flex-1">
              <StageCopilot stage={opp.stage} proposalId={id} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
