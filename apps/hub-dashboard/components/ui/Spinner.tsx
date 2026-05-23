import { cn } from "@/lib/utils";

interface Props { size?: "sm" | "md" | "lg"; className?: string; }

export function Spinner({ size = "md", className }: Props) {
  const sz = { sm: "w-3 h-3 border", md: "w-5 h-5 border-2", lg: "w-8 h-8 border-2" }[size];
  return (
    <div className={cn("rounded-full border-border border-t-accent animate-spin", sz, className)} />
  );
}
