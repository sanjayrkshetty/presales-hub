"use client";

import Link from "next/link";
import { Opportunity } from "@/lib/api";
import { SLATimer } from "./SLATimer";

const STAGE_LABELS: Record<string, string> = {
  intake:            "Intake",
  qualification:     "Qualification",
  sme_assignment:    "SME Assignment",
  drafting:          "Drafting",
  technical_review:  "Technical Review",
  security_review:   "Security Review",
  delivery_review:   "Delivery Review",
  finance_review:    "Finance Review",
  legal_review:      "Legal Review",
  approval:          "Approval",
  submission:        "Submission",
  client_followup:   "Client Follow-up",
  closed_won:        "Closed Won",
  closed_lost:       "Closed Lost",
};

function healthColor(score: number | null): string {
  if (!score) return "#64748b";
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#f59e0b";
  return "#ef4444";
}

interface Props {
  opp: Opportunity;
}

export function ProposalCard({ opp }: Props) {
  const isBreached = opp.sla.status === "breached";
  const isWon = opp.stage === "closed_won";
  const isLost = opp.stage === "closed_lost";

  return (
    <Link href={`/proposals/${opp.proposal_id ?? opp.id}`}
      className="block panel p-3 hover:border-accent/40 transition-colors group"
      style={{ borderColor: isBreached ? "rgba(239,68,68,0.4)" : undefined }}>

      {/* Title row */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div>
          <div className="font-semibold text-[13px] text-text-primary group-hover:text-accent transition-colors line-clamp-1">
            {opp.title}
          </div>
          <div className="text-[11px] mt-0.5" style={{ color: "#64748b" }}>
            {opp.client?.name ?? "—"} · {opp.client?.sector ?? "—"}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <span className="font-bold text-[13px]" style={{ color: "var(--accent)" }}>
            ₹{opp.deal_value_cr?.toFixed(1)}cr
          </span>
          {opp.health_score !== null && (
            <span className="text-[11px] font-semibold" style={{ color: healthColor(opp.health_score) }}>
              {opp.health_score}/100
            </span>
          )}
        </div>
      </div>

      {/* Stage badge */}
      <div className="flex items-center justify-between mb-2">
        <span className="badge text-[10px]"
          style={{
            background: isWon ? "#22c55e22" : isLost ? "#ef444422" : "#00d4aa15",
            color: isWon ? "#22c55e" : isLost ? "#ef4444" : "#00d4aa",
            border: `1px solid ${isWon ? "#22c55e44" : isLost ? "#ef444444" : "#00d4aa44"}`,
          }}>
          {STAGE_LABELS[opp.stage] ?? opp.stage}
        </span>
        <span className="text-[10px]" style={{ color: "#64748b" }}>
          {opp.win_probability}% win prob
        </span>
      </div>

      {/* Health bar */}
      {opp.health_score !== null && (
        <div className="mb-2">
          <div className="health-bar">
            <div
              className="health-bar-fill"
              style={{
                width: `${opp.health_score}%`,
                background: healthColor(opp.health_score),
              }}
            />
          </div>
        </div>
      )}

      {/* SLA */}
      {opp.sla.hours_allowed && !isWon && !isLost && (
        <SLATimer sla={opp.sla} />
      )}

      {/* Deadline */}
      {opp.deadline && (
        <div className="mt-1.5 text-[10px]" style={{ color: "#64748b" }}>
          Deadline: {new Date(opp.deadline).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}
        </div>
      )}
    </Link>
  );
}
