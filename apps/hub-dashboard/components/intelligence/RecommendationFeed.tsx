"use client";
import { useQuery } from "@tanstack/react-query";
import { strategyApi } from "@/lib/api/strategy";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/utils";
import { Lightbulb } from "lucide-react";
import type { Recommendation } from "@/lib/types/api";

const PRIORITY_COLOR: Record<string, string> = {
  critical: "text-danger border-danger/30 bg-danger/5",
  high:     "text-warn border-warn/30 bg-warn/5",
  medium:   "text-blue border-blue/30 bg-blue/5",
  low:      "text-text-muted border-border",
};

interface RecsResponse {
  recommendations: Recommendation[];
  total: number;
  critical_count: number;
  summary: string;
}

export function RecommendationFeed() {
  const { data: resp, isLoading } = useQuery<RecsResponse>({
    queryKey: ["strategy", "recommendations"],
    queryFn: strategyApi.recommendations,
    staleTime: 60_000,
  });

  const recs = resp?.recommendations ?? [];
  const sorted = [...recs].sort((a, b) => {
    const order = { critical: 0, high: 1, medium: 2, low: 3 };
    return (order[a.priority] ?? 4) - (order[b.priority] ?? 4);
  });

  return (
    <div className="panel">
      <SectionHeader title="Recommendations" count={recs.length} icon={<Lightbulb size={11} />} />
      {isLoading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : (
        <div className="p-3 flex flex-col gap-2">
          {sorted.map((rec) => (
            <div key={rec.id} className={cn("panel-sm p-3 border", PRIORITY_COLOR[rec.priority] ?? PRIORITY_COLOR.low)}>
              <div className="flex items-start justify-between gap-2 mb-1">
                <p className="text-xs font-sans text-text-primary">{rec.title}</p>
                <span className={cn("text-2xs font-mono font-semibold flex-shrink-0",
                  rec.priority === "critical" ? "text-danger" :
                  rec.priority === "high"     ? "text-warn" :
                  rec.priority === "medium"   ? "text-blue" : "text-text-muted"
                )}>{rec.priority}</span>
              </div>
              <p className="text-2xs font-sans text-text-muted">{rec.description}</p>
              {rec.action && (
                <p className="text-2xs font-sans text-accent mt-1">→ {rec.action}</p>
              )}
            </div>
          ))}
          {sorted.length === 0 && (
            <p className="text-xs text-text-muted font-sans text-center py-4">No recommendations</p>
          )}
        </div>
      )}
    </div>
  );
}
