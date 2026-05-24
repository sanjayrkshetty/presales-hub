import { cn } from "@/lib/utils";
import type { SmeLoad } from "@/lib/types/api";
import { EmptyState } from "@/components/ui/EmptyState";

function utilizationColor(pct: number): string {
  if (pct >= 90) return "bg-danger text-white";
  if (pct >= 70) return "bg-warn/80 text-bg-primary";
  if (pct >= 50) return "bg-accent/60 text-bg-primary";
  return "bg-success/40 text-bg-primary";
}

interface Props {
  data:       SmeLoad[];
  isLoading?: boolean;
}

export function SmeHeatmap({ data, isLoading }: Props) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-4 gap-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-16 rounded bg-bg-tertiary animate-pulse" />
        ))}
      </div>
    );
  }

  if (!data.length) {
    return <EmptyState title="No SME data" message="No stakeholder utilization data available." />;
  }

  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 gap-2">
      {data.map((sme) => (
        <div
          key={sme.id}
          className={cn(
            "rounded p-2 flex flex-col gap-1 border border-transparent",
            utilizationColor(sme.utilization_pct)
          )}
          title={`${sme.name} — ${sme.utilization_pct}% utilized · ${sme.active_assignments} active`}
        >
          <span className="text-2xs font-sans font-semibold truncate">{sme.name.split(" ")[0]}</span>
          <span className="text-xs font-mono font-bold leading-none">{sme.utilization_pct}%</span>
          <span className="text-2xs opacity-75">{sme.active_assignments} active</span>
        </div>
      ))}
    </div>
  );
}
