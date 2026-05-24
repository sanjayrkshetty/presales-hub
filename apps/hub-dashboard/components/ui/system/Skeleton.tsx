import { cn } from "@/lib/utils";
import type { CSSProperties } from "react";

interface SkeletonProps {
  variant?:   "line" | "block" | "circle";
  width?:     string | number;
  height?:    string | number;
  className?: string;
}

export function Skeleton({ variant = "block", width, height, className }: SkeletonProps) {
  const style: CSSProperties = {};
  if (width)  style.width  = typeof width  === "number" ? `${width}px`  : width;
  if (height) style.height = typeof height === "number" ? `${height}px` : height;

  return (
    <div
      className={cn(
        "animate-pulse bg-bg-tertiary",
        variant === "line"   && "h-3 rounded",
        variant === "block"  && "rounded",
        variant === "circle" && "rounded-full",
        className
      )}
      style={style}
      aria-hidden="true"
    />
  );
}

interface GroupProps {
  count?:      number;
  className?:  string;
  itemClass?:  string;
}

export function SkeletonGroup({ count = 3, className, itemClass }: GroupProps) {
  return (
    <div className={cn("flex flex-col gap-2", className)} aria-hidden="true">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton
          key={i}
          variant="line"
          className={cn(i === count - 1 && "w-2/3", itemClass)}
        />
      ))}
    </div>
  );
}
