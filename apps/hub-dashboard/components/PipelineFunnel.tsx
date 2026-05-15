"use client";

import { PipelineAnalytics } from "@/lib/api";

const ACTIVE_STAGES = [
  "intake", "qualification", "sme_assignment", "drafting",
  "technical_review", "security_review", "finance_review",
  "legal_review", "approval", "submission",
];

const STAGE_SHORT: Record<string, string> = {
  intake:           "Intake",
  qualification:    "Qual.",
  sme_assignment:   "SME",
  drafting:         "Draft",
  technical_review: "Tech Rev.",
  security_review:  "Sec Rev.",
  finance_review:   "Finance",
  legal_review:     "Legal",
  approval:         "Approval",
  submission:       "Submit",
};

interface Props {
  data: PipelineAnalytics;
}

export function PipelineFunnel({ data }: Props) {
  const active = data.funnel.filter(f => ACTIVE_STAGES.includes(f.stage));
  const maxCount = Math.max(...active.map(f => f.count), 1);

  return (
    <div className="space-y-1">
      {active.map((f) => {
        const pct = (f.count / maxCount) * 100;
        return (
          <div key={f.stage} className="flex items-center gap-2">
            <span className="text-[10px] w-16 shrink-0 text-right" style={{ color: "#64748b" }}>
              {STAGE_SHORT[f.stage]}
            </span>
            <div className="flex-1 health-bar">
              <div
                className="health-bar-fill"
                style={{ width: `${pct}%`, background: "var(--accent)", height: "6px" }}
              />
            </div>
            <span className="text-[11px] font-semibold w-4 text-right" style={{ color: "#e2e8f0" }}>
              {f.count}
            </span>
            {f.value_cr > 0 && (
              <span className="text-[10px] w-14 text-right" style={{ color: "#64748b" }}>
                ₹{f.value_cr.toFixed(1)}cr
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
