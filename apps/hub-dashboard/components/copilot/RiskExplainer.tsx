"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { copilotApi } from "@/lib/api/copilot";
import { GroundingCitations } from "./GroundingCitations";
import { ConfidenceBar } from "./ConfidenceBar";
import { Spinner } from "@/components/ui/Spinner";
import { AlertTriangle } from "lucide-react";

function resultText(result: Record<string, unknown>): string {
  if (typeof result.content === "string") return result.content;
  if (typeof result.risks === "string") return result.risks;
  if (Array.isArray(result.risks)) return (result.risks as string[]).join("\n\n");
  return JSON.stringify(result, null, 2);
}

export function RiskExplainer({ initialProposalId = "" }: { initialProposalId?: string } = {}) {
  const [proposalId, setProposalId] = useState(initialProposalId);

  const explain = useMutation({
    mutationFn: () => copilotApi.explainRisk(proposalId),
  });

  const result = explain.data;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <label className="text-2xs text-text-muted font-sans uppercase tracking-widest">Proposal ID</label>
        <input
          value={proposalId}
          onChange={(e) => setProposalId(e.target.value)}
          placeholder="opp_…"
          className="bg-bg-tertiary border border-border rounded px-2 py-1.5 text-xs font-mono text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50 transition-colors"
        />
        <button
          onClick={() => explain.mutate()}
          disabled={!proposalId || explain.isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-danger/10 border border-danger/30 text-danger text-xs font-sans font-semibold hover:bg-danger/20 transition-colors disabled:opacity-50 self-start"
        >
          {explain.isPending ? <Spinner size="sm" /> : <AlertTriangle size={12} />}
          Explain Risks
        </button>
      </div>

      {result && (
        <div className="flex flex-col gap-3">
          <ConfidenceBar score={result.evaluation_score ?? 0} flags={result.safety_flags} />
          <div className="panel-sm p-3">
            <p className="text-xs font-sans text-text-primary leading-relaxed whitespace-pre-wrap">
              {resultText(result.result)}
            </p>
          </div>
          <GroundingCitations sources={result.grounding_metadata ?? []} />
        </div>
      )}
    </div>
  );
}
