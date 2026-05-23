"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { copilotApi } from "@/lib/api/copilot";
import { GroundingCitations } from "./GroundingCitations";
import { ConfidenceBar } from "./ConfidenceBar";
import { Spinner } from "@/components/ui/Spinner";
import { Lightbulb } from "lucide-react";

function resultText(result: Record<string, unknown>): string {
  if (typeof result.solution === "string") return result.solution;
  if (typeof result.content === "string") return result.content;
  if (typeof result.suggestion === "string") return result.suggestion;
  return JSON.stringify(result, null, 2);
}

export function SolutionSuggest() {
  const [proposalId, setProposalId] = useState("");
  const [requirements, setRequirements] = useState("");

  const suggest = useMutation({
    mutationFn: () => copilotApi.suggestSolution(proposalId, requirements),
  });

  const result = suggest.data;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <div className="flex flex-col gap-1">
          <label className="text-2xs text-text-muted font-sans uppercase tracking-widest">Proposal ID (optional)</label>
          <input
            value={proposalId}
            onChange={(e) => setProposalId(e.target.value)}
            placeholder="opp_…"
            className="bg-bg-tertiary border border-border rounded px-2 py-1.5 text-xs font-mono text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50 transition-colors"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-2xs text-text-muted font-sans uppercase tracking-widest">Requirements</label>
          <textarea
            value={requirements}
            onChange={(e) => setRequirements(e.target.value)}
            placeholder="Describe client requirements…"
            rows={3}
            className="bg-bg-tertiary border border-border rounded px-2 py-1.5 text-xs font-sans text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50 transition-colors resize-none"
          />
        </div>
        <button
          onClick={() => suggest.mutate()}
          disabled={!requirements.trim() || suggest.isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-blue/10 border border-blue/30 text-blue text-xs font-sans font-semibold hover:bg-blue/20 transition-colors disabled:opacity-50 self-start"
        >
          {suggest.isPending ? <Spinner size="sm" /> : <Lightbulb size={12} />}
          Suggest Solution
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
