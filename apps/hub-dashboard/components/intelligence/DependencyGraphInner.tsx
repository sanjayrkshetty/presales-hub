"use client";
import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  type Node,
  type Edge,
} from "reactflow";
import "reactflow/dist/style.css";
import type { DependencyGraph as DependencyGraphType } from "@/lib/types/api";

interface Props { graph: DependencyGraphType; }

export function DependencyGraphInner({ graph }: Props) {
  const { nodes, edges } = useMemo(() => {
    const nodeIds = new Set<string>();
    (graph.cross_bu_dependencies ?? []).forEach((dep) => { nodeIds.add(dep.from); nodeIds.add(dep.to); });
    (graph.chokepoints ?? []).forEach((id) => nodeIds.add(id));
    (graph.blocked_proposals ?? []).forEach((id) => nodeIds.add(id));

    const idArr  = Array.from(nodeIds);
    const nodes: Node[] = idArr.map((id, i) => ({
      id,
      position: { x: (i % 4) * 220, y: Math.floor(i / 4) * 120 },
      data: {
        label: (
          <div className="flex flex-col gap-0.5 p-1">
            <span className="text-2xs font-sans leading-tight truncate max-w-[140px]">{id}</span>
          </div>
        ),
      },
      style: {
        background:   graph.chokepoints?.includes(id) ? "#ef444420" : "#1a1e2a",
        border:       `1px solid ${graph.chokepoints?.includes(id) ? "#ef4444" : "#1e2330"}`,
        borderRadius: 4,
        color:        "#e2e8f0",
        fontSize:     11,
        width:        170,
      },
    }));

    const edges: Edge[] = (graph.cross_bu_dependencies ?? []).map((dep, i) => ({
      id:         `e${i}`,
      source:     dep.from,
      target:     dep.to,
      label:      dep.weight > 1 ? String(dep.weight) : undefined,
      style:      { stroke: "#252a38", strokeWidth: 1 },
      labelStyle: { fill: "#64748b", fontSize: 10 },
    }));

    return { nodes, edges };
  }, [graph]);

  return (
    <div style={{ height: 320 }} className="rounded border border-border overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background color="#1e2330" gap={16} />
        <Controls showInteractive={false} style={{ background: "#0f1117", border: "1px solid #1e2330" }} />
      </ReactFlow>
    </div>
  );
}
