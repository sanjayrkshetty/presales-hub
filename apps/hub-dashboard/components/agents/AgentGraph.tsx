"use client";
import dynamic from "next/dynamic";
import type { AgentTask } from "@/lib/types/api";
import { GraphSkeleton } from "@/components/ui/ChartSkeleton";

// ReactFlow is browser-only — lazy-load to prevent SSR hydration mismatch
const AgentGraphInner = dynamic(
  () => import("./AgentGraphInner").then((m) => ({ default: m.AgentGraphInner })),
  { ssr: false, loading: () => <GraphSkeleton height={320} /> }
);

interface Props { tasks: AgentTask[]; }

export function AgentGraph({ tasks }: Props) {
  if (!tasks.length) {
    return (
      <div className="flex items-center justify-center h-48 text-xs text-text-muted font-sans">
        No tasks to visualize
      </div>
    );
  }
  return <AgentGraphInner tasks={tasks} />;
}
