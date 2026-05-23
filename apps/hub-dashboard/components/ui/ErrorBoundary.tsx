"use client";
import { ErrorBoundary as ReactErrorBoundary, type FallbackProps } from "react-error-boundary";
import type { ReactNode } from "react";
import { isApiError } from "@/lib/errors";
import { AlertTriangle, RefreshCw } from "lucide-react";

function DefaultFallback({ error, resetErrorBoundary }: FallbackProps) {
  const message = isApiError(error)
    ? `API error ${error.status} — ${error.body}`
    : (error as Error)?.message ?? "Something went wrong";

  return (
    <div className="panel p-6 flex flex-col items-center gap-3 text-center">
      <AlertTriangle size={20} className="text-warn" />
      <p className="text-sm font-sans text-text-secondary">{message}</p>
      <button
        onClick={resetErrorBoundary}
        className="flex items-center gap-1.5 px-3 py-1 rounded text-xs font-sans font-semibold
                   bg-blue/10 text-blue border border-blue/30 hover:bg-blue/20 transition-colors"
      >
        <RefreshCw size={11} /> Retry
      </button>
    </div>
  );
}

interface PageBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

export function PageErrorBoundary({ children, fallback }: PageBoundaryProps) {
  return (
    <ReactErrorBoundary
      FallbackComponent={fallback ? () => <>{fallback}</> : DefaultFallback}
      onError={(error, info) => {
        if (process.env.NODE_ENV === "development") {
          console.error("[ErrorBoundary]", error, info.componentStack);
        }
        // TODO: send to Sentry once configured (post-Phase 9)
      }}
    >
      {children}
    </ReactErrorBoundary>
  );
}

interface PanelBoundaryProps {
  children: ReactNode;
  title?: string;
}

export function PanelErrorBoundary({ children, title }: PanelBoundaryProps) {
  return (
    <ReactErrorBoundary
      FallbackComponent={({ error, resetErrorBoundary }) => (
        <div className="panel p-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <AlertTriangle size={14} className="text-warn shrink-0" />
            <span className="text-xs font-sans text-text-muted truncate">
              {title ? `${title} unavailable` : "Panel unavailable"}
              {" — "}
              <span className="font-mono">{(error as Error)?.message}</span>
            </span>
          </div>
          <button
            onClick={resetErrorBoundary}
            className="shrink-0 text-2xs text-blue hover:text-blue/70 font-sans transition-colors"
          >
            Retry
          </button>
        </div>
      )}
    >
      {children}
    </ReactErrorBoundary>
  );
}
