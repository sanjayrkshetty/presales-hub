"use client";
import { useState } from "react";
import { DraftAssist } from "@/components/copilot/DraftAssist";
import { RFPAnalysis } from "@/components/copilot/RFPAnalysis";
import { RiskExplainer } from "@/components/copilot/RiskExplainer";
import { SMERecommender } from "@/components/copilot/SMERecommender";
import { SolutionSuggest } from "@/components/copilot/SolutionSuggest";
import { Zap } from "lucide-react";

const TABS = [
  { id: "draft",     label: "Draft Assist",     component: DraftAssist },
  { id: "rfp",       label: "RFP Analyzer",     component: RFPAnalysis },
  { id: "risk",      label: "Risk Explainer",   component: RiskExplainer },
  { id: "sme",       label: "SME Recommender",  component: SMERecommender },
  { id: "solution",  label: "Solution Suggest", component: SolutionSuggest },
] as const;

type TabId = typeof TABS[number]["id"];

export default function CopilotPage() {
  const [active, setActive] = useState<TabId>("draft");
  const ActiveTab = TABS.find((t) => t.id === active)!.component;

  return (
    <div className="p-4 flex flex-col gap-4 h-full">
      <div className="flex items-center gap-2">
        <Zap size={14} className="text-purple" />
        <h1 className="text-sm font-sans font-semibold text-text-primary">AI Copilot Workspace</h1>
        <span className="text-2xs font-mono text-text-muted ml-auto">claude-sonnet-4-6 · RAG-grounded</span>
      </div>

      <div className="flex gap-1 border-b border-border pb-0">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            className={`px-3 py-2 text-xs font-sans font-medium transition-colors border-b-2 -mb-px
              ${active === tab.id
                ? "text-purple border-purple"
                : "text-text-muted border-transparent hover:text-text-primary"
              }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-auto">
        <div className="max-w-2xl">
          <ActiveTab />
        </div>
      </div>
    </div>
  );
}
