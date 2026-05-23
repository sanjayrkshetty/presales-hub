import { cn } from "@/lib/utils";

const colorMap: Record<string, string> = {
  connected:    "bg-success",
  active:       "bg-success",
  ok:           "bg-success",
  approved:     "bg-success",
  warning:      "bg-warn",
  breached:     "bg-danger",
  error:        "bg-danger",
  danger:       "bg-danger",
  disconnected: "bg-muted",
  pending:      "bg-muted",
  archived:     "bg-muted",
};

interface Props {
  status: string;
  pulse?: boolean;
  size?: "sm" | "md";
  className?: string;
}

export function StatusDot({ status, pulse = false, size = "sm", className }: Props) {
  const color = colorMap[status] ?? "bg-muted";
  const sz    = size === "sm" ? "w-1.5 h-1.5" : "w-2 h-2";
  return (
    <span className={cn("rounded-full inline-block flex-shrink-0", sz, color, pulse && "animate-pulse_dot", className)} />
  );
}
