import { cn } from "@/lib/utils";
import { Check } from "lucide-react";
import { STAGE_ORDER, stageLabel } from "@/lib/workflow/stages";

const STAGES = STAGE_ORDER;

interface Props { currentStage: string; }

export function StageProgressRail({ currentStage }: Props) {
  const idx = STAGES.indexOf(currentStage as typeof STAGES[number]);

  return (
    <div className="w-full overflow-x-auto pb-2">
      <div className="flex items-center min-w-max gap-0">
        {STAGES.map((stage, i) => {
          const done   = i < idx;
          const active = i === idx;
          const future = i > idx;
          return (
            <div key={stage} className="flex items-center">
              <div className="flex flex-col items-center gap-1">
                <div className={cn(
                  "w-6 h-6 rounded-full flex items-center justify-center border text-2xs font-mono transition-all",
                  done   && "bg-accent border-accent text-bg-primary",
                  active && "bg-accent/20 border-accent text-accent ring-2 ring-accent/30",
                  future && "bg-bg-tertiary border-border text-text-muted"
                )}>
                  {done ? <Check size={10} strokeWidth={3} /> : <span>{i + 1}</span>}
                </div>
                <span className={cn(
                  "text-2xs font-sans whitespace-nowrap",
                  active ? "text-accent font-semibold" : "text-text-muted"
                )}>
                  {stageLabel(stage)}
                </span>
              </div>
              {i < STAGES.length - 1 && (
                <div className={cn("h-px w-8 mx-1 mt-[-14px]", done ? "bg-accent" : "bg-border")} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
