"use client";
import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  type Node,
  type Edge,
} from "reactflow";
import "reactflow/dist/style.css";
import type { AgentTask } from "@/lib/types/api";

const STATUS_COLOR: Record<string, string> = {
  completed:        "#22c55e",
  running:          "#00d4aa",
  pending:          "#64748b",
  failed:           "#ef4444",
  awaiting_approval:"#f59e0b",
};

interface Props { tasks: AgentTask[]; }

export function AgentGraph({ tasks }: Props) {
  const { nodes, edges } = useMemo(() => {
    const cols = 3;
    const nodes: Node[] = tasks.map((task, i) => ({
      id: task.task_id,
      position: { x: (i % cols) * 220, y: Math.floor(i / cols) * 120 },
      data: {
        label: (
          <div className="flex flex-col gap-0.5 p-1">
            <span className="text-2xs font-mono leading-tight">{task.agent_type?.replace(/_/g, " ")}</span>
            <span className="text-2xs font-sans opacity-60 truncate max-w-[140px]">{task.task_id}</span>
          </div>
        ),
      },
      style: {
        background: "#1a1e2a",
        border: `1px solid ${STATUS_COLOR[task.status] ?? "#1e2330"}`,
        borderRadius: 4,
        color: "#e2e8f0",
        fontSize: 11,
        width: 180,
      },
    }));

    const edges: Edge[] = [];

    return { nodes, edges };
  }, [tasks]);

  if (!tasks.length) return (
    <div className="flex items-center justify-center h-48 text-xs text-text-muted font-sans">
      No tasks to visualize
    </div>
  );

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
