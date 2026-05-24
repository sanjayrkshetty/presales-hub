"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRealtimeStore } from "@/lib/store/realtime";
import { healthApi } from "@/lib/api/health";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Spinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/utils";
import {
  Database, Radio, GitBranch, RefreshCw, Zap, Wifi,
  CheckCircle2, XCircle, AlertTriangle, Clock, Activity,
  Brain, Server,
} from "lucide-react";
import type { CircuitBreakerStatus } from "@/lib/api/health";

const REFRESH_MS = 10_000;

function ServiceRow({
  icon, label, status, detail, latency,
}: {
  icon:     React.ReactNode;
  label:    string;
  status:   "ok" | "error" | "unknown";
  detail?:  string;
  latency?: number;
}) {
  const isOk  = status === "ok";
  const isErr = status === "error";
  return (
    <div className="flex items-center gap-3 py-2.5 border-b border-border/40 last:border-0">
      <span className={cn("text-text-muted", isOk && "text-success", isErr && "text-danger")}>
        {icon}
      </span>
      <span className="text-xs font-sans font-medium text-text-primary flex-1">{label}</span>
      {detail && <span className="text-2xs text-text-muted font-mono truncate max-w-[160px]">{detail}</span>}
      {latency !== undefined && (
        <span className="text-2xs font-mono text-text-muted w-16 text-right">{latency}ms</span>
      )}
      <span>
        {isOk  ? <CheckCircle2 size={14} className="text-success" /> :
         isErr  ? <XCircle size={14} className="text-danger" /> :
                  <AlertTriangle size={14} className="text-warn" />}
      </span>
    </div>
  );
}

const STATE_STYLES: Record<string, string> = {
  closed:    "border-success/40 bg-success/5",
  half_open: "border-warn/40 bg-warn/5",
  open:      "border-danger/40 bg-danger/5",
};

const STATE_ICON: Record<string, React.ReactNode> = {
  closed:    <CheckCircle2 size={14} className="text-success" />,
  half_open: <AlertTriangle size={14} className="text-warn" />,
  open:      <XCircle size={14} className="text-danger" />,
};

const CB_LABEL: Record<string, string> = {
  anthropic: "Anthropic Claude",
  openai:    "OpenAI",
  groq:      "Groq",
  temporal:  "Temporal",
};

function BreakerCard({ breaker }: { breaker: CircuitBreakerStatus }) {
  const state = breaker.state;
  return (
    <div className={cn("panel p-3 flex flex-col gap-2 border", STATE_STYLES[state] ?? "border-border")}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-sans font-medium text-text-primary">
          {CB_LABEL[breaker.name] ?? breaker.name}
        </span>
        {STATE_ICON[state]}
      </div>
      <div className="flex items-center justify-between text-2xs text-text-muted font-mono">
        <span className="uppercase">{state.replace("_", " ")}</span>
        <span>{breaker.failures}/{breaker.failure_threshold} failures</span>
      </div>
      <div className="h-1 rounded bg-bg-tertiary overflow-hidden">
        <div
          className={cn(
            "h-full rounded transition-all",
            state === "closed"    && "bg-success",
            state === "half_open" && "bg-warn",
            state === "open"      && "bg-danger",
          )}
          style={{ width: `${Math.min((breaker.failures / breaker.failure_threshold) * 100, 100)}%` }}
        />
      </div>
    </div>
  );
}

export default function SystemPage() {
  const [lastRefresh, setLastRefresh] = useState(() => new Date());

  const { data: health, isLoading, refetch } = useQuery({
    queryKey:        ["system", "health"],
    queryFn:         healthApi.get,
    staleTime:       REFRESH_MS,
    refetchInterval: REFRESH_MS,
    retry:           false,
  });

  const { channelStates, connectionState } = useRealtimeStore();

  function handleRefresh() {
    refetch();
    setLastRefresh(new Date());
  }

  const overallOk  = health?.status === "ok";
  const overallDeg = health?.status === "degraded";

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <SectionHeader title="System Health Center" />
        <div className="flex items-center gap-3">
          <span className="text-2xs text-text-muted font-sans">
            Last: {lastRefresh.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
          </span>
          <button
            onClick={handleRefresh}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded border border-border text-2xs font-sans text-text-muted hover:text-text-primary hover:border-border-subtle transition-colors"
            aria-label="Refresh health"
          >
            <RefreshCw size={11} className={isLoading ? "animate-spin" : ""} />
            Refresh
          </button>
        </div>
      </div>

      {/* Overall status banner */}
      {!isLoading && health && (
        <div className={cn(
          "flex items-center gap-3 px-4 py-3 rounded border",
          overallOk  ? "bg-success/5 border-success/30" :
          overallDeg ? "bg-warn/5 border-warn/30"       :
                       "bg-danger/5 border-danger/30"
        )}>
          {overallOk  ? <CheckCircle2 size={16} className="text-success" /> :
           overallDeg ? <AlertTriangle size={16} className="text-warn" /> :
                        <XCircle size={16} className="text-danger" />}
          <div className="flex flex-col gap-0">
            <span className={cn("text-sm font-sans font-semibold",
              overallOk ? "text-success" : overallDeg ? "text-warn" : "text-danger"
            )}>
              System {health.status.toUpperCase()}
            </span>
            <span className="text-2xs text-text-muted">
              {health.service} v{health.version} · latency {health.latency_ms}ms ·{" "}
              {new Date(health.timestamp).toLocaleTimeString()}
            </span>
          </div>
          {health.dlq_pending !== undefined && health.dlq_pending > 0 && (
            <span className="ml-auto badge badge-warn">
              {health.dlq_pending} DLQ events pending
            </span>
          )}
        </div>
      )}

      <div className="grid grid-cols-12 gap-4">
        {/* Service health matrix */}
        <div className="col-span-12 lg:col-span-4 panel p-4">
          <SectionHeader title="Dependency Health" icon={<Server size={13} />} />
          {isLoading ? (
            <div className="flex items-center justify-center py-6"><Spinner size="md" /></div>
          ) : health ? (
            <div className="mt-2">
              <ServiceRow
                icon={<Database size={14} />}
                label="PostgreSQL"
                status={health.checks.postgres.status}
                detail={health.checks.postgres.detail}
                latency={health.latency_ms}
              />
              <ServiceRow
                icon={<Radio size={14} />}
                label="Redis"
                status={health.checks.redis.status}
                detail={health.checks.redis.detail}
              />
              <ServiceRow
                icon={<GitBranch size={14} />}
                label="Temporal"
                status={health.checks.temporal.status}
                detail={health.checks.temporal.detail}
              />
            </div>
          ) : (
            <p className="text-xs text-text-muted mt-4">Unable to reach health endpoint.</p>
          )}
        </div>

        {/* Circuit breakers */}
        <div className="col-span-12 lg:col-span-8 panel p-4">
          <SectionHeader title="AI Provider Circuit Breakers" icon={<Zap size={13} />} />
          {isLoading ? (
            <div className="grid grid-cols-2 gap-3 mt-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-20 rounded bg-bg-tertiary animate-pulse" />
              ))}
            </div>
          ) : health?.circuit_breakers?.length ? (
            <div className="grid grid-cols-2 gap-3 mt-3">
              {health.circuit_breakers.map((cb) => (
                <BreakerCard key={cb.name} breaker={cb} />
              ))}
            </div>
          ) : (
            <p className="text-xs text-text-muted mt-4">No circuit breaker data available.</p>
          )}
        </div>

        {/* WebSocket connection health */}
        <div className="col-span-12 lg:col-span-5 panel p-4">
          <SectionHeader title="WebSocket Channels" icon={<Wifi size={13} />} />
          <div className="mt-3 flex flex-col gap-1">
            {/* Aggregate connection state */}
            <div className="flex items-center gap-3 py-2 border-b border-border/40">
              <Activity size={13} className="text-text-muted" />
              <span className="text-xs font-sans text-text-primary flex-1">Overall Connection</span>
              <span className={cn("badge text-2xs",
                connectionState === "connected"    && "badge-success",
                connectionState === "degraded"     && "badge-warn",
                connectionState === "reconnecting" && "badge-warn",
                connectionState === "error"        && "badge-danger",
                connectionState === "disconnected" && "badge-muted",
                connectionState === "connecting"   && "badge-blue",
              )}>
                {connectionState}
              </span>
            </div>
            {Object.entries(channelStates).length === 0 ? (
              <p className="text-xs text-text-muted py-2">No WebSocket channels initialised.</p>
            ) : (
              Object.entries(channelStates).map(([ch, state]) => (
                <div key={ch} className="flex items-center gap-3 py-1.5 border-b border-border/20 last:border-0">
                  <Wifi size={12} className="text-text-muted" />
                  <span className="text-xs font-mono text-text-secondary flex-1">{ch}</span>
                  <span className={cn("badge text-2xs",
                    state === "open"       && "badge-success",
                    state === "connecting" && "badge-blue",
                    state === "closed"     && "badge-muted",
                    state === "error"      && "badge-danger",
                  )}>
                    {state}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* AI provider status summary */}
        <div className="col-span-12 lg:col-span-7 panel p-4">
          <SectionHeader title="AI Provider Status" icon={<Brain size={13} />} />
          {isLoading ? (
            <div className="flex items-center justify-center py-6"><Spinner size="md" /></div>
          ) : (
            <div className="mt-3 flex flex-col gap-2">
              {(health?.circuit_breakers ?? []).filter((cb) => cb.name !== "temporal").map((cb) => {
                const pct = (cb.failures / cb.failure_threshold) * 100;
                return (
                  <div key={cb.name} className="flex flex-col gap-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-sans text-text-secondary">{CB_LABEL[cb.name] ?? cb.name}</span>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-text-muted text-2xs">
                          {cb.failures}/{cb.failure_threshold} failures
                        </span>
                        <span className={cn("badge text-2xs",
                          cb.state === "closed"    && "badge-success",
                          cb.state === "half_open" && "badge-warn",
                          cb.state === "open"      && "badge-danger",
                        )}>
                          {cb.state.replace("_", " ")}
                        </span>
                      </div>
                    </div>
                    <div className="h-1.5 rounded bg-bg-tertiary overflow-hidden">
                      <div
                        className={cn("h-full rounded transition-all",
                          cb.state === "closed"    && "bg-success/60",
                          cb.state === "half_open" && "bg-warn",
                          cb.state === "open"      && "bg-danger",
                        )}
                        style={{ width: `${Math.min(pct, 100)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
              {!health?.circuit_breakers?.length && (
                <p className="text-xs text-text-muted">No AI provider data.</p>
              )}
              <div className="mt-2 pt-2 border-t border-border/40">
                <div className="flex items-center justify-between text-2xs text-text-muted font-sans">
                  <span>Circuit breakers recover after {health?.circuit_breakers?.[0]?.recovery_timeout_s ?? 60}s</span>
                  <div className="flex items-center gap-1">
                    <Clock size={10} />
                    <span>Auto-refreshes every {REFRESH_MS / 1000}s</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
