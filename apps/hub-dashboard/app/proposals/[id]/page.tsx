import { notFound } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { ApprovalChain } from "@/components/ApprovalChain";
import { SLATimer } from "@/components/SLATimer";

export const revalidate = 30;

interface Props {
  params: Promise<{ id: string }>;
}

const STAGE_ORDER = [
  "intake", "qualification", "sme_assignment", "drafting",
  "technical_review", "security_review", "delivery_review",
  "finance_review", "legal_review", "approval",
  "submission", "client_followup",
];

function healthColor(score: number): string {
  if (score >= 80) return "#22c55e";
  if (score >= 60) return "#f59e0b";
  return "#ef4444";
}

export default async function ProposalDetailPage({ params }: Props) {
  const { id } = await params;

  let opp: Awaited<ReturnType<typeof api.opportunity>> | null = null;
  try {
    opp = await api.opportunity(id);
  } catch {
    notFound();
  }

  if (!opp) notFound();

  const proposal = (opp as any).proposal;
  const currentStageIdx = STAGE_ORDER.indexOf(opp.stage);

  return (
    <div className="space-y-4 max-w-5xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-[10px]" style={{ color: "#64748b" }}>
        <Link href="/" className="hover:text-accent transition-colors">Pipeline</Link>
        <span>/</span>
        <span style={{ color: "#94a3b8" }}>{opp.title}</span>
      </div>

      {/* Header */}
      <div className="panel p-4">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-[18px] font-bold" style={{ color: "#e2e8f0" }}>{opp.title}</h1>
            <div className="text-[12px] mt-1" style={{ color: "#64748b" }}>
              {opp.client?.name ?? "—"} · {opp.client?.sector ?? "—"} · {opp.rfp_type ?? "—"}
            </div>
          </div>
          <div className="text-right space-y-1">
            <div className="text-[22px] font-bold" style={{ color: "var(--accent)" }}>
              ₹{opp.deal_value_cr?.toFixed(2)}cr
            </div>
            {proposal?.health_score !== null && proposal?.health_score !== undefined && (
              <div className="text-[12px] font-semibold" style={{ color: healthColor(proposal.health_score) }}>
                Health: {proposal.health_score}/100
              </div>
            )}
          </div>
        </div>

        {/* Stage progress */}
        <div className="mt-4 flex gap-1 overflow-x-auto pb-1">
          {STAGE_ORDER.map((s, i) => (
            <div key={s}
              className="flex flex-col items-center gap-1 min-w-0 shrink-0"
              style={{ opacity: i > currentStageIdx ? 0.3 : 1 }}>
              <div className="w-2 h-2 rounded-full"
                style={{
                  background: i < currentStageIdx ? "var(--accent)" :
                              i === currentStageIdx ? "#e2e8f0" : "#1e2128",
                  border: i === currentStageIdx ? "2px solid var(--accent)" : "none",
                }} />
              <span className="text-[9px] whitespace-nowrap" style={{ color: i === currentStageIdx ? "var(--accent)" : "#475569" }}>
                {s.replace(/_/g, " ")}
              </span>
            </div>
          ))}
        </div>

        {opp.sla.hours_allowed && (
          <div className="mt-3">
            <SLATimer sla={opp.sla} />
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        {/* Deal info */}
        <div className="panel">
          <div className="panel-header">Deal Information</div>
          <div className="p-4 space-y-2">
            {[
              ["Client",         opp.client?.name ?? "—"],
              ["Sector",         opp.client?.sector ?? "—"],
              ["Tier",           opp.client?.tier ?? "—"],
              ["RFP Type",       opp.rfp_type ?? "—"],
              ["Win Probability",`${opp.win_probability}%`],
              ["Deadline",       opp.deadline ? new Date(opp.deadline).toLocaleDateString("en-IN") : "—"],
              ["Created",        new Date(opp.created_at).toLocaleDateString("en-IN")],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between items-center py-1 border-b last:border-0"
                style={{ borderColor: "var(--border)" }}>
                <span className="text-[10px]" style={{ color: "#64748b" }}>{k}</span>
                <span className="text-[11px] font-medium" style={{ color: "#e2e8f0" }}>{v}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Approval chain */}
        <div className="panel">
          <div className="panel-header">Approval Chain</div>
          <div className="p-4">
            <ApprovalChain approvals={proposal?.approvals ?? []} />
          </div>
        </div>
      </div>

      {/* Assignments */}
      {proposal?.assignments?.length > 0 && (
        <div className="panel">
          <div className="panel-header">Assignments ({proposal.assignments.length})</div>
          <div className="divide-y" style={{ borderColor: "var(--border)" }}>
            {proposal.assignments.map((a: any) => (
              <div key={a.id} className="p-3 flex justify-between items-center">
                <div>
                  <span className="text-[11px] font-medium" style={{ color: "#e2e8f0" }}>{a.role ?? "—"}</span>
                  <span className="ml-2 text-[10px]" style={{ color: "#64748b" }}>{a.bu ?? ""}</span>
                </div>
                <span className="badge text-[9px]"
                  style={{
                    background: a.status === "completed" ? "#22c55e22" : "#00d4aa15",
                    color: a.status === "completed" ? "#22c55e" : "#00d4aa",
                    border: `1px solid ${a.status === "completed" ? "#22c55e44" : "#00d4aa33"}`,
                  }}>
                  {a.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent activity */}
      {proposal?.recent_activity?.length > 0 && (
        <div className="panel">
          <div className="panel-header">Recent Activity</div>
          <div className="divide-y" style={{ borderColor: "var(--border)" }}>
            {proposal.recent_activity.map((act: any) => (
              <div key={act.id} className="p-3 flex gap-3 items-start"
                style={{ background: act.is_alert ? "rgba(239,68,68,0.04)" : undefined }}>
                <span className="text-[10px] font-mono" style={{ color: "#475569" }}>
                  {new Date(act.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                </span>
                <div>
                  <span className="text-[11px]" style={{ color: act.is_alert ? "#fca5a5" : "#cbd5e1" }}>
                    {act.description}
                  </span>
                  <span className="ml-2 text-[10px]" style={{ color: "#475569" }}>· {act.actor_name}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
