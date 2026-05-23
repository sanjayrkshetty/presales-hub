"use client";
import { useQuery } from "@tanstack/react-query";
import { agentsApi } from "@/lib/api/agents";
import { StatusDot } from "@/components/ui/StatusDot";
import { Spinner } from "@/components/ui/Spinner";
import type { AgentType } from "@/lib/types/api";

interface Props {
  onSelect?: (agentType: string) => void;
  selected?: string;
}

export function AgentRegistryList({ onSelect, selected }: Props) {
  const { data: registry = [], isLoading } = useQuery<AgentType[]>({
    queryKey: ["agents", "registry"],
    queryFn: agentsApi.listTypes,
    staleTime: 60_000,
  });

  if (isLoading) return <Spinner />;

  return (
    <div className="flex flex-col gap-1">
      {registry.map((agent) => (
        <button
          key={agent.agent_type}
          onClick={() => onSelect?.(agent.agent_type)}
          className={`flex items-start gap-2 p-2 rounded text-left transition-colors
            ${selected === agent.agent_type
              ? "bg-accent/10 border border-accent/30"
              : "hover:bg-bg-tertiary border border-transparent"
            }`}
        >
          <StatusDot status="active" className="mt-0.5 flex-shrink-0" />
          <div className="flex flex-col gap-0.5 min-w-0">
            <span className="text-xs font-mono text-text-primary">{agent.agent_type.replace(/_/g, " ")}</span>
            {agent.description && (
              <span className="text-2xs font-sans text-text-muted line-clamp-2">{agent.description}</span>
            )}
          </div>
        </button>
      ))}
      {registry.length === 0 && (
        <p className="text-xs text-text-muted font-sans text-center py-4">No agents registered</p>
      )}
    </div>
  );
}
