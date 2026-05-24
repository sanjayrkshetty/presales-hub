"use client";
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface Props {
  open:       boolean;
  onClose:    () => void;
  title?:     string;
  children:   ReactNode;
  size?:      "sm" | "md" | "lg" | "xl";
  className?: string;
}

const SIZE = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
};

export function Modal({ open, onClose, title, children, size = "md", className }: Props) {
  const firstFocusRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    firstFocusRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      prev?.focus();
    };
  }, [open, onClose]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-[fade_in_0.15s_ease]"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        className={cn(
          "relative w-full bg-bg-elevated border border-border rounded-lg shadow-2xl",
          "flex flex-col max-h-[90vh] animate-[slide_in_0.2s_ease]",
          SIZE[size],
          className
        )}
      >
        {title && (
          <div className="flex items-center justify-between px-4 py-3 border-b border-border flex-shrink-0">
            <span className="text-sm font-sans font-semibold text-text-primary">{title}</span>
            <button
              ref={firstFocusRef}
              onClick={onClose}
              className="p-1 rounded hover:bg-white/4 text-text-muted hover:text-text-primary transition-colors"
              aria-label="Close modal"
            >
              <X size={14} />
            </button>
          </div>
        )}
        <div className="flex-1 overflow-auto p-4">{children}</div>
      </div>
    </div>,
    document.body
  );
}
