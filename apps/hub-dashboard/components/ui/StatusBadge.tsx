import { cn, statusBadgeClass } from "@/lib/utils";

interface Props {
  status: string;
  label?: string;
  className?: string;
}

export function StatusBadge({ status, label, className }: Props) {
  return (
    <span className={cn("badge", statusBadgeClass(status), className)}>
      {label ?? status}
    </span>
  );
}
