"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { copilotApi } from "@/lib/api/copilot";
import { ConfidenceBar } from "./ConfidenceBar";
import { GroundingCitations } from "./GroundingCitations";
import { Spinner } from "@/components/ui/Spinner";
import { Users } from "lucide-react";

function resultText(result: Record<string, unknown>): string {
  if (typeof result.recommendations === "string") return result.recommendations;
  if (typeof result.content === "string") return result.content;
  return JSON.stringify(result, null, 2);
}

export function SMERecommender() {
  const [proposalId, setProposalId] = useState("");

  const recommend = useMutation({
    mutationFn: () => copilotApi.recommendSme(proposalId),
  });

  const result = recommend.data;

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
          onClick={() => recommend.mutate()}
          disabled={!proposalId || recommend.isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-purple/10 border border-purple/30 text-purple text-xs font-sans font-semibold hover:bg-purple/20 transition-colors disabled:opacity-50 self-start"
        >
          {recommend.isPending ? <Spinner size="sm" /> : <Users size={12} />}
          Recommend SMEs
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
