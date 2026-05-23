"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { copilotApi } from "@/lib/api/copilot";
import { ConfidenceBar } from "./ConfidenceBar";
import { GroundingCitations } from "./GroundingCitations";
import { Spinner } from "@/components/ui/Spinner";
import { FileText } from "lucide-react";

export function RFPAnalysis() {
  const [rfpText, setRfpText] = useState("");

  const analyze = useMutation({
    mutationFn: () => copilotApi.analyzeRfp(rfpText),
  });

  const result = analyze.data;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <label className="text-2xs text-text-muted font-sans uppercase tracking-widest">RFP Text</label>
        <textarea
          value={rfpText}
          onChange={(e) => setRfpText(e.target.value)}
          placeholder="Paste RFP content here…"
          rows={6}
          className="bg-bg-tertiary border border-border rounded px-2 py-1.5 text-xs font-sans text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50 transition-colors resize-none"
        />
        <button
          onClick={() => analyze.mutate()}
          disabled={!rfpText.trim() || analyze.isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-accent/10 border border-accent/30 text-accent text-xs font-sans font-semibold hover:bg-accent/20 transition-colors disabled:opacity-50 self-start"
        >
          {analyze.isPending ? <Spinner size="sm" /> : <FileText size={12} />}
          Analyze RFP
        </button>
      </div>

      {result && (
        <div className="flex flex-col gap-3">
          <ConfidenceBar score={result.evaluation_score ?? 0} flags={result.safety_flags} />
          <div className="flex flex-col gap-2">
            {Object.entries(result.result).map(([key, value]) => (
              <div key={key} className="panel-sm p-2">
                <p className="text-2xs uppercase tracking-widest text-text-muted font-sans font-semibold mb-1">
                  {key.replace(/_/g, " ")}
                </p>
                <p className="text-xs font-sans text-text-primary">
                  {Array.isArray(value) ? (value as string[]).join(", ") : String(value)}
                </p>
              </div>
            ))}
          </div>
          <GroundingCitations sources={result.grounding_metadata ?? []} />
        </div>
      )}
    </div>
  );
}
