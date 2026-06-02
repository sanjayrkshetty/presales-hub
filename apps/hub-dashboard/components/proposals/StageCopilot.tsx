"use client";
import Link from "next/link";
import { DraftAssist } from "@/components/copilot/DraftAssist";
import { RiskExplainer } from "@/components/copilot/RiskExplainer";
import { SMERecommender } from "@/components/copilot/SMERecommender";
import { RFPAnalysis } from "@/components/copilot/RFPAnalysis";

const REVIEW_STAGES = new Set([
  "technical_review", "security_review", "delivery_review",
  "finance_review", "legal_review", "approval",
]);

interface Props { stage: string; proposalId: string; }

// Surfaces the existing copilot assistant most relevant to the current stage.
// Pure composition of existing components — no new agents, no learning loop.
export function StageCopilot({ stage, proposalId }: Props) {
  if (stage === "drafting") return <DraftAssist initialProposalId={proposalId} />;
  if (stage === "sme_assignment") return <SMERecommender initialProposalId={proposalId} />;
  if (stage === "intake" || stage === "qualification") return <RFPAnalysis />;
  if (REVIEW_STAGES.has(stage)) return <RiskExplainer initialProposalId={proposalId} />;

  return (
    <p className="text-xs text-text-muted font-sans">
      No stage-specific assistant for this stage. Open the{" "}
      <Link href="/copilot" className="text-purple hover:text-purple/80">full Copilot workspace</Link>.
    </p>
  );
}
