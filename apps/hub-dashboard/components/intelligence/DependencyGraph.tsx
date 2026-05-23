"use client";
import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { strategyApi } from "@/lib/api/strategy";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Spinner } from "@/components/ui/Spinner";
import { GraphSkeleton } from "@/components/ui/ChartSkeleton";
import type { DependencyGraph as DependencyGraphType } from "@/lib/types/api";

// ReactFlow is browser-only — lazy-load to prevent SSR hydration mismatch
const DependencyGraphInner = dynamic(
  () => import("./DependencyGraphInner").then((m) => ({ default: m.DependencyGraphInner })),
  { ssr: false, loading: () => <GraphSkeleton height={320} /> }
);

export function DependencyGraph() {
  const { data: graph, isLoading } = useQuery<DependencyGraphType>({
    queryKey: ["strategy", "dependencies"],
    queryFn:  () => strategyApi.dependencies(),
    staleTime: 120_000,
  });

  return (
    <div className="panel">
      <SectionHeader title="Cross-BU Dependency Graph" />
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : graph && (graph.cross_bu_dependencies?.length ?? 0) > 0 ? (
        <div className="p-3">
          <DependencyGraphInner graph={graph} />
          {graph.chokepoints && graph.chokepoints.length > 0 && (
            <p className="text-2xs text-text-muted font-sans mt-2">
              Chokepoints: <span className="text-danger font-mono">{graph.chokepoints.join(", ")}</span>
            </p>
          )}
        </div>
      ) : (
        <p className="p-4 text-xs text-text-muted font-sans text-center">No dependency data</p>
      )}
    </div>
  );
}
