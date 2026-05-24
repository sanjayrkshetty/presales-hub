"use client";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

const badgeVariants = cva(
  "inline-flex items-center rounded px-1.5 py-0.5 font-sans font-medium",
  {
    variants: {
      variant: {
        success: "badge-success",
        warn:    "badge-warn",
        danger:  "badge-danger",
        info:    "badge-blue",
        accent:  "badge-accent",
        purple:  "badge-purple",
        muted:   "badge-muted",
      },
      size: {
        sm: "text-2xs",
        md: "text-xs",
      },
    },
    defaultVariants: {
      variant: "muted",
      size: "sm",
    },
  }
);

interface Props extends VariantProps<typeof badgeVariants> {
  children: ReactNode;
  className?: string;
}

export function Badge({ children, variant, size, className }: Props) {
  return (
    <span className={cn(badgeVariants({ variant, size }), className)}>
      {children}
    </span>
  );
}
