import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface Props {
  title:    string;
  count?:   number;
  actions?: ReactNode;
  icon?:    ReactNode;
  className?: string;
}

export function SectionHeader({ title, count, actions, icon, className }: Props) {
  return (
    <div className={cn("panel-header", className)}>
      {icon && <span>{icon}</span>}
      <span>{title}</span>
      {count !== undefined && (
        <span className="badge badge-muted ml-1 font-mono">{count}</span>
      )}
      {actions && <div className="ml-auto flex items-center gap-1">{actions}</div>}
    </div>
  );
}
