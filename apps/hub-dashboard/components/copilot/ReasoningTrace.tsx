"use client";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface Props {
  steps?: Array<{ section_id?: string; content: string }>;
}

export function ReasoningTrace({ steps }: Props) {
  const [open, setOpen] = useState(false);
  if (!steps?.length) return null;

  return (
    <div className="flex flex-col gap-1">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-2xs text-text-muted hover:text-text-primary font-sans transition-colors self-start"
      >
        {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        Reasoning trace ({steps.length} steps)
      </button>
      {open && (
        <div className="ml-3 flex flex-col gap-1 border-l border-border pl-3">
          {steps.map((step, i) => (
            <div key={i} className="flex flex-col gap-0.5">
              <p className="text-2xs font-mono text-text-secondary">
                {String(i + 1).padStart(2, "0")} {step.section_id ?? `step_${i + 1}`}
              </p>
              <p className="text-2xs font-sans text-text-muted">{step.content}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
