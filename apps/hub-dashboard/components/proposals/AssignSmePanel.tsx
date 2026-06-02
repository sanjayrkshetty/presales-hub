"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { proposalsApi } from "@/lib/api/proposals";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Spinner } from "@/components/ui/Spinner";
import { UserPlus, CheckCircle } from "lucide-react";

interface Props { proposalId: string; rfpType: string; }

interface AssignResult {
  assigned: { id: string; name: string; bu: string } | null;
  alternatives: Array<{ id: string; name: string; workload: number }>;
}

export function AssignSmePanel({ proposalId, rfpType }: Props) {
  const qc = useQueryClient();

  const assign = useMutation({
    mutationFn: () => proposalsApi.assignSme(proposalId, rfpType) as Promise<AssignResult>,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["proposals", proposalId] });
      qc.invalidateQueries({ queryKey: ["opportunities", proposalId] });
    },
  });

  const result = assign.data;

  return (
    <div className="panel">
      <SectionHeader title="SME Assignment" icon={<UserPlus size={11} />} />
      <div className="p-3 flex flex-col gap-3">
        <button onClick={() => assign.mutate()}
          disabled={assign.isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-sans font-semibold bg-accent/10 text-accent border border-accent/30 hover:bg-accent/20 transition-colors disabled:opacity-50 self-start">
          {assign.isPending ? <Spinner size="sm" /> : <UserPlus size={12} />} Auto-assign SME
        </button>

        {assign.isError && (
          <p className="text-2xs text-danger font-sans">
            {(assign.error as Error)?.message ?? "Assignment failed"}
          </p>
        )}

        {result?.assigned && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 text-xs font-sans">
              <CheckCircle size={12} className="text-success" />
              <span className="text-text-primary font-semibold">{result.assigned.name}</span>
              <span className="text-2xs text-text-muted">{result.assigned.bu}</span>
            </div>
            {result.alternatives?.length > 0 && (
              <div className="flex flex-col gap-1">
                <span className="text-2xs uppercase tracking-widest text-text-muted font-sans font-semibold">Alternatives</span>
                {result.alternatives.map((a) => (
                  <div key={a.id} className="flex items-center gap-2 text-2xs font-sans text-text-secondary">
                    <span>{a.name}</span>
                    <span className="text-text-muted">· workload {a.workload}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
