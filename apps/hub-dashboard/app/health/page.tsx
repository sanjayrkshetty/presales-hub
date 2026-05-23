"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { useRealtimeStore } from "@/lib/store/realtime";

interface HealthResp {
  status:    string;
  service:   string;
  timestamp: string;
  version:   string;
}

const SUBSYSTEMS = [
  { key: "api",       label: "Hub API",          url: "/api/health" },
  { key: "ws-act",    label: "WebSocket Activity",url: null },
  { key: "ws-sla",    label: "WebSocket SLA",     url: null },
  { key: "ws-events", label: "WebSocket Events",  url: null },
];

function StatusDot({ ok }: { ok: boolean | null }) {
  if (ok === null) {
    return <span className="w-2 h-2 rounded-full inline-block" style={{ background: "#64748b" }} />;
  }
  return (
    <span
      className={`w-2 h-2 rounded-full inline-block ${ok ? "animate-pulse" : ""}`}
      style={{ background: ok ? "var(--success)" : "var(--danger)" }}
    />
  );
}

export default function HealthPage() {
  const { connectionState, channelStates } = useRealtimeStore();

  const { data: apiHealth, isLoading, isError } = useQuery({
    queryKey: ["health"],
    queryFn:  () => apiFetch<HealthResp>("/api/health"),
    refetchInterval: 10_000,
    retry: 1,
  });

  const channels = Object.entries(channelStates);
  const wsOk = connectionState === "connected" || connectionState === "degraded";

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          System Health
        </h1>
        <p className="text-[11px] mt-1" style={{ color: "var(--text-secondary)" }}>
          Live status of all platform subsystems
        </p>
      </div>

      {/* API health */}
      <div className="panel p-4 space-y-3">
        <div className="text-[11px] font-semibold uppercase tracking-wide"
             style={{ color: "var(--text-muted)" }}>
          Backend Services
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <StatusDot ok={isLoading ? null : !isError} />
            <span className="text-[12px]" style={{ color: "var(--text-primary)" }}>Hub API</span>
          </div>
          <div className="text-right">
            {apiHealth && (
              <span className="text-[11px] font-mono" style={{ color: "var(--success)" }}>
                {apiHealth.status} · v{apiHealth.version}
              </span>
            )}
            {isError && (
              <span className="text-[11px]" style={{ color: "var(--danger)" }}>
                Unreachable
              </span>
            )}
            {isLoading && (
              <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>Checking…</span>
            )}
          </div>
        </div>
        {apiHealth?.timestamp && (
          <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>
            Last checked: {new Date(apiHealth.timestamp).toLocaleTimeString()}
          </div>
        )}
      </div>

      {/* WebSocket channels */}
      <div className="panel p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-[11px] font-semibold uppercase tracking-wide"
               style={{ color: "var(--text-muted)" }}>
            Realtime Channels
          </div>
          <span
            className={`text-[10px] font-medium px-2 py-0.5 rounded-full`}
            style={{
              background: wsOk ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.12)",
              color: wsOk ? "var(--success)" : "var(--danger)",
            }}
          >
            {connectionState}
          </span>
        </div>
        {channels.length === 0 ? (
          <div className="text-[11px]" style={{ color: "var(--text-muted)" }}>
            No channels registered
          </div>
        ) : (
          channels.map(([ch, state]) => (
            <div key={ch} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <StatusDot ok={state === "open"} />
                <span className="text-[12px] font-mono" style={{ color: "var(--text-primary)" }}>
                  {ch}
                </span>
              </div>
              <span className="text-[11px] font-mono"
                    style={{ color: state === "open" ? "var(--success)" : "var(--text-muted)" }}>
                {state}
              </span>
            </div>
          ))
        )}
      </div>

      {/* External links */}
      <div className="panel p-4 space-y-2">
        <div className="text-[11px] font-semibold uppercase tracking-wide"
             style={{ color: "var(--text-muted)" }}>
          Observability Links
        </div>
        {[
          { label: "Temporal Workflow UI", url: "http://localhost:8080" },
          { label: "Jaeger Trace Explorer", url: "http://localhost:16686" },
          { label: "API Interactive Docs",  url: "http://localhost:8003/docs" },
        ].map(({ label, url }) => (
          <div key={url} className="flex items-center justify-between">
            <span className="text-[12px]" style={{ color: "var(--text-secondary)" }}>{label}</span>
            <a href={url} target="_blank" rel="noopener"
               className="text-[11px] font-mono underline-offset-2 hover:underline"
               style={{ color: "var(--accent)" }}>
              {url}
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
