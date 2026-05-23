"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { agentsApi } from "@/lib/api/agents";
import { AgentRegistryList } from "@/components/agents/AgentRegistryList";
import { AgentTaskCard } from "@/components/agents/AgentTaskCard";
import { AgentGraph } from "@/components/agents/AgentGraph";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { MetricCard } from "@/components/ui/MetricCard";
import { Spinner } from "@/components/ui/Spinner";
import { Bot, Play } from "lucide-react";
import type { AgentTask } from "@/lib/types/api";

export default function AgentsPage() {
  const qc = useQueryClient();
  const [selectedType, setSelectedType] = useState("");
  const [inputData, setInputData] = useState("");
  const [inputError, setInputError] = useState("");
  const [taskIds, setTaskIds] = useState<string[]>([]);

  const { data: tasksResp, isLoading: tasksLoading } = useQuery<{ tasks: AgentTask[] }>({
    queryKey: ["agents", "tasks"],
    queryFn: agentsApi.listTasks,
    staleTime: 10_000,
    refetchInterval: 15_000,
  });

  const tasks = tasksResp?.tasks ?? [];

  const submit = useMutation({
    mutationFn: ({ agentType, inputData }: { agentType: string; inputData: Record<string, unknown> }) =>
      agentsApi.submitTask(agentType, inputData),
    onSuccess: (data) => {
      setTaskIds((ids) => [data.task_id, ...ids]);
      setInputData("");
      qc.invalidateQueries({ queryKey: ["agents", "tasks"] });
    },
  });

  function handleSubmit() {
    setInputError("");
    let parsed: Record<string, unknown> = {};
    if (inputData.trim()) {
      try {
        parsed = JSON.parse(inputData);
      } catch {
        setInputError("Invalid JSON");
        return;
      }
    }
    submit.mutate({ agentType: selectedType, inputData: parsed });
  }

  const running  = tasks.filter((t) => t.status === "running").length;
  const pending  = tasks.filter((t) => t.status === "pending").length;
  const awaiting = tasks.filter((t) => t.status === "awaiting_approval").length;

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Total Tasks"    value={tasks.length} />
        <MetricCard label="Running"        value={running} accent={running > 0} />
        <MetricCard label="Pending"        value={pending} />
        <MetricCard label="Awaiting Review" value={awaiting} warn={awaiting > 0} />
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* Registry + submit */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-4">
          <div className="panel">
            <SectionHeader title="Agent Registry" icon={<Bot size={11} />} />
            <div className="p-3">
              <AgentRegistryList onSelect={setSelectedType} selected={selectedType} />
            </div>
          </div>

          {selectedType && (
            <div className="panel">
              <SectionHeader title="Submit Task" />
              <div className="p-3 flex flex-col gap-2">
                <div className="flex flex-col gap-1">
                  <label className="text-2xs text-text-muted font-sans uppercase tracking-widest">Agent</label>
                  <span className="text-xs font-mono text-accent">{selectedType.replace(/_/g, " ")}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-2xs text-text-muted font-sans uppercase tracking-widest">Input JSON</label>
                  <textarea
                    value={inputData}
                    onChange={(e) => { setInputData(e.target.value); setInputError(""); }}
                    placeholder='{"proposal_id": "opp_…"}'
                    rows={4}
                    className="bg-bg-tertiary border border-border rounded px-2 py-1.5 text-xs font-mono text-text-primary placeholder:text-text-muted outline-none focus:border-accent/50 transition-colors resize-none"
                  />
                  {inputError && <p className="text-2xs text-danger font-sans">{inputError}</p>}
                </div>
                <button
                  onClick={handleSubmit}
                  disabled={!selectedType || submit.isPending}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-accent/10 border border-accent/30 text-accent text-xs font-sans font-semibold hover:bg-accent/20 transition-colors disabled:opacity-50 self-start"
                >
                  {submit.isPending ? <Spinner size="sm" /> : <Play size={11} />}
                  Run Task
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Task list + graph */}
        <div className="col-span-12 lg:col-span-8 flex flex-col gap-4">
          <div className="panel">
            <SectionHeader title="Task Graph" />
            <div className="p-3">
              <AgentGraph tasks={tasks} />
            </div>
          </div>

          {taskIds.length > 0 && (
            <div className="panel">
              <SectionHeader title="My Submitted Tasks" count={taskIds.length} />
              <div className="p-3 grid grid-cols-1 md:grid-cols-2 gap-2">
                {taskIds.map((id) => (
                  <AgentTaskCard key={id} taskId={id} />
                ))}
              </div>
            </div>
          )}

          <div className="panel">
            <SectionHeader title="All Tasks" count={tasks.length} />
            {tasksLoading ? (
              <div className="flex justify-center py-8"><Spinner /></div>
            ) : (
              <div className="p-3 grid grid-cols-1 md:grid-cols-2 gap-2">
                {tasks.slice(0, 20).map((t) => (
                  <AgentTaskCard key={t.task_id} taskId={t.task_id} />
                ))}
                {tasks.length === 0 && (
                  <p className="col-span-2 text-xs text-text-muted font-sans text-center py-4">No tasks yet</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
