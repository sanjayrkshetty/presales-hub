"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { copilotApi } from "@/lib/api/copilot";
import { GroundingCitations } from "./GroundingCitations";
import { ConfidenceBar } from "./ConfidenceBar";
import { Spinner } from "@/components/ui/Spinner";
import { Zap } from "lucide-react";

function resultText(result: Record<string, unknown>): string {
  if (typeof result.content === "string") return result.content;
  if (typeof result.text === "string") return result.text;
  if (typeof result.draft === "string") return result.draft;
  return JSON.stringify(result, null, 2);
}

export function DraftAssist({ initialProposalId = "" }: { initialProposalId?: string } = {}) {
  const [proposalId, setProposalId] = useState(initialProposalId);
  const [section, setSection] = useState("executive_summary");

  const draft = useMutation({
    mutationFn: () => copilotApi.draft(proposalId, section),
  });

  const result = draft.data;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <div className="grid grid-cols-2 gap-2">
          <div className="flex flex-col gap-1">
            <label className="text-2xs text-text-muted font-sans uppercase tracking-widest">Proposal ID</label>
            <input
              value={proposalId}
              onChange={(e) => setProposalId(e.target.value)}
              placeholder="opp_…"
              className="bg-bg-tertiary border border-border rounded px-2 py-1.5 text-xs font-mono text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50 transition-colors"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-2xs text-text-muted font-sans uppercase tracking-widest">Section</label>
            <select
              value={section}
              onChange={(e) => setSection(e.target.value)}
              className="bg-bg-tertiary border border-border rounded px-2 py-1.5 text-xs font-sans text-text-primary outline-none focus:border-accent/50 transition-colors"
            >
              {["executive_summary", "technical_approach", "commercial_terms", "risk_mitigation", "team_credentials"].map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
              ))}
            </select>
          </div>
        </div>
        <button
          onClick={() => draft.mutate()}
          disabled={!proposalId || draft.isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-accent/10 border border-accent/30 text-accent text-xs font-sans font-semibold hover:bg-accent/20 transition-colors disabled:opacity-50 self-start"
        >
          {draft.isPending ? <Spinner size="sm" /> : <Zap size={12} />}
          Generate Draft
        </button>
      </div>

      {result && (
        <div className="flex flex-col gap-3">
          <ConfidenceBar score={result.evaluation_score ?? 0} flags={result.safety_flags} />
          <div className="panel-sm p-3">
            <p className="text-2xs uppercase tracking-widest text-text-muted font-sans font-semibold mb-2">Draft Output</p>
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
