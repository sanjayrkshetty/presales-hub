interface Props {
  height?: number;
  className?: string;
}

export function ChartSkeleton({ height = 180, className }: Props) {
  return (
    <div
      className={`animate-pulse rounded bg-bg-tertiary border border-border ${className ?? ""}`}
      style={{ height }}
      aria-label="Loading chart…"
    />
  );
}

export function GraphSkeleton({ height = 320, className }: Props) {
  return (
    <div
      className={`animate-pulse rounded border border-border overflow-hidden ${className ?? ""}`}
      style={{ height }}
      aria-label="Loading graph…"
    >
      <div className="w-full h-full bg-bg-tertiary" />
    </div>
  );
}
