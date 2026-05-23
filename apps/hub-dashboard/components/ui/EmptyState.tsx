import type { ReactNode } from "react";

interface Props {
  icon?:    ReactNode;
  title:    string;
  message?: string;
  action?:  ReactNode;
}

export function EmptyState({ icon, title, message, action }: Props) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      {icon && <div className="text-text-muted opacity-40 text-3xl">{icon}</div>}
      <div>
        <p className="text-sm font-sans font-medium text-text-secondary">{title}</p>
        {message && <p className="text-xs text-text-muted mt-1 font-sans">{message}</p>}
      </div>
      {action}
    </div>
  );
}
