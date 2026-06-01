"use client";

import { useState, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/lib/api/analytics";
import {
  formatCurrency, formatPercent, cn,
} from "@/lib/utils";
import {
  Maximize2, Minimize2, Pause, Play, RefreshCw,
  TrendingUp, AlertTriangle, Clock, DollarSign,
  Activity, Cpu, ChevronRight,
} from "lucide-react";
import type { SlaAnalytics, PipelineAnalytics, SmeLoad } from "@/lib/types/api";

const REFRESH_MS = 15_000;

const STAGE_ORDER = ["intake", "discovery", "technical_review", "commercial_review", "legal_review", "awaiting_approval", "submitted"];
const STAGE_LABEL: Record<string, string> = {
  intake:              "Intake",
  discovery:           "Discovery",
  technical_review:    "Tech Review",
  commercial_review:   "Commercial",
  legal_review:        "Legal",
  awaiting_approval:   "Approval",
  submitted:           "Submitted",
};

function useTime() {
  const [time, setTime] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return time;
}

function revenueAtRisk(sla: SlaAnalytics): number {
  return sla.breached.reduce((sum, opp) => sum + (opp.deal_value_cr ?? 0), 0);
}

function aiHoursSaved(pipeline: PipelineAnalytics): number {
  return Math.round(pipeline.total_opportunities * 2.3);
}

function slaHealthPct(sla: SlaAnalytics): number {
  const total = sla.total_active;
  if (!total) return 100;
  return Math.round(((total - sla.breached_count - sla.warning_count) / total) * 100);
}

interface FunnelBarProps {
  label: string;
  count: number;
  max:   number;
  pct?:  number;
}

function FunnelBar({ label, count, max, pct }: FunnelBarProps) {
  const width = max > 0 ? (count / max) * 100 : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs font-sans text-text-muted w-24 shrink-0 text-right">{label}</span>
      <div className="flex-1 h-5 bg-bg-tertiary rounded overflow-hidden">
        <div
          className="h-full rounded bg-accent/70 transition-all duration-700 ease-out flex items-center justify-end pr-2"
          style={{ width: `${width}%` }}
        >
          {count > 0 && <span className="text-2xs font-mono text-bg-primary font-bold">{count}</span>}
        </div>
      </div>
      {pct !== undefined && (
        <span className="text-xs font-mono text-text-muted w-10 shrink-0">{pct}%</span>
      )}
    </div>
  );
}

export default function ExecutivePage() {
  const now = useTime();
  const [paused, setPaused] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [presentMode, setPresentMode] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  const { data: pipeline, isLoading: pL, refetch: rPipeline } = useQuery({
    queryKey:        ["executive", "pipeline"],
    queryFn:         analyticsApi.pipeline,
    staleTime:       REFRESH_MS,
    refetchInterval: paused ? false : REFRESH_MS,
  });

  const { data: sla, isLoading: sL, refetch: rSla } = useQuery({
    queryKey:        ["executive", "sla"],
    queryFn:         analyticsApi.sla,
    staleTime:       REFRESH_MS,
    refetchInterval: paused ? false : REFRESH_MS,
  });

  const { data: smeLoad } = useQuery({
    queryKey:        ["executive", "sme"],
    queryFn:         analyticsApi.smeLoad,
    staleTime:       REFRESH_MS,
    refetchInterval: paused ? false : REFRESH_MS,
  });

  const loading = pL || sL;

  const handleRefresh = useCallback(() => {
    rPipeline();
    rSla();
  }, [rPipeline, rSla]);

  const toggleFullscreen = useCallback(async () => {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen?.();
      setFullscreen(true);
    } else {
      await document.exitFullscreen?.();
      setFullscreen(false);
    }
  }, []);

  useEffect(() => {
    const onFs = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "f" || e.key === "F") toggleFullscreen();
      if (e.key === "p" || e.key === "P") setPresentMode((v) => !v);
      if (e.key === " ") { e.preventDefault(); setPaused((v) => !v); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleFullscreen]);

  const sortedFunnel = [...(pipeline?.funnel ?? [])]
    .sort((a, b) => STAGE_ORDER.indexOf(a.stage) - STAGE_ORDER.indexOf(b.stage));
  const maxFunnelCount = Math.max(...sortedFunnel.map((s) => s.count), 1);

  const atRisk = sla ? [...sla.warning].sort((a, b) => a.hours_remaining - b.hours_remaining) : [];
  const breached = sla ? [...sla.breached].sort((a, b) => a.hours_remaining - b.hours_remaining) : [];
  const topDeals = [...breached, ...atRisk].slice(0, 5);

  const overCapacitySME = (smeLoad ?? []).filter((s) => s.utilization_pct >= 80).length;

  if (!mounted) return null;

  return (
    <div className="fixed inset-0 z-[100] bg-bg-primary overflow-auto flex flex-col">
      {/* Top bar */}
      <header className="flex-shrink-0 flex items-center justify-between px-6 py-3 border-b border-border bg-bg-secondary">
        <div className="flex items-center gap-3">
          <span className="w-7 h-7 rounded bg-accent/20 border border-accent/40 flex items-center justify-center">
            <Cpu size={14} className="text-accent" />
          </span>
          <div>
            <div className="text-xs font-bold text-text-primary font-sans tracking-tight">PRESALES HUB</div>
            <div className="text-2xs text-text-muted font-sans uppercase tracking-widest">Executive Wallboard</div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-text-muted tabular-nums">
            {now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            <span className="ml-2 text-text-muted/60">
              {now.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}
            </span>
          </span>
          {!paused && <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" aria-label="live" />}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setPaused((v) => !v)}
            className="flex items-center gap-1.5 px-2 py-1 rounded text-2xs font-sans text-text-muted hover:text-text-primary hover:bg-white/4 transition-colors"
            aria-label={paused ? "Resume auto-refresh" : "Pause auto-refresh"}
          >
            {paused ? <Play size={11} /> : <Pause size={11} />}
            {paused ? "Resume" : "Pause"}
          </button>
          <button
            onClick={handleRefresh}
            className="p-1.5 rounded text-text-muted hover:text-text-primary hover:bg-white/4 transition-colors"
            aria-label="Refresh now"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
          </button>
          <button
            onClick={() => setPresentMode((v) => !v)}
            className={cn(
              "px-2 py-1 rounded text-2xs font-sans transition-colors",
              presentMode
                ? "bg-accent/20 text-accent border border-accent/40"
                : "text-text-muted hover:text-text-primary hover:bg-white/4"
            )}
            aria-label="Toggle presentation mode"
          >
            {presentMode ? "Exit Présentation" : "Présentation"}
          </button>
          <button
            onClick={toggleFullscreen}
            className="p-1.5 rounded text-text-muted hover:text-text-primary hover:bg-white/4 transition-colors"
            aria-label={fullscreen ? "Exit fullscreen" : "Enter fullscreen"}
          >
            {fullscreen ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
          </button>
          <a
            href="/ops"
            className="flex items-center gap-1 px-2 py-1 rounded text-2xs font-sans text-text-muted hover:text-text-primary hover:bg-white/4 transition-colors"
          >
            Ops Console <ChevronRight size={10} />
          </a>
        </div>
      </header>

      <main className={cn("flex-1 p-6 flex flex-col gap-5", presentMode && "gap-6")}>
        {/* KPI Strip */}
        <div className={cn("grid gap-4", presentMode ? "grid-cols-2 lg:grid-cols-4" : "grid-cols-2 md:grid-cols-4")}>
          {loading ? (
            Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className={cn("panel p-4 animate-pulse bg-bg-tertiary", presentMode ? "h-36" : "h-24")} />
            ))
          ) : (
            <>
              <div className={cn("panel p-4 border-accent/30 flex flex-col gap-2", presentMode && "py-6")}>
                <div className="flex items-center justify-between">
                  <span className="text-2xs uppercase tracking-widest text-text-muted font-sans font-semibold">
                    Active Pipeline
                  </span>
                  <TrendingUp size={13} className="text-accent" />
                </div>
                <span className={cn("font-mono font-bold text-accent", presentMode ? "text-4xl" : "text-3xl")}>
                  {pipeline ? formatCurrency(pipeline.active_pipeline_cr ?? 0) : "—"}
                </span>
                <span className="text-xs text-text-muted">{pipeline?.total_opportunities ?? 0} active opportunities</span>
              </div>

              <div className={cn("panel p-4 flex flex-col gap-2", presentMode && "py-6")}>
                <div className="flex items-center justify-between">
                  <span className="text-2xs uppercase tracking-widest text-text-muted font-sans font-semibold">Win Rate</span>
                  <Activity size={13} className="text-text-muted" />
                </div>
                <span className={cn("font-mono font-bold text-text-primary", presentMode ? "text-4xl" : "text-3xl")}>
                  {pipeline ? formatPercent(pipeline.win_rate ?? 0) : "—"}
                </span>
                <span className="text-xs text-text-muted">Avg {pipeline?.avg_cycle_days?.toFixed(0) ?? "—"}d cycle time</span>
              </div>

              <div className={cn("panel p-4 flex flex-col gap-2",
                sla?.breached_count ? "border-danger/40" : sla?.warning_count ? "border-warn/40" : "",
                presentMode && "py-6"
              )}>
                <div className="flex items-center justify-between">
                  <span className="text-2xs uppercase tracking-widest text-text-muted font-sans font-semibold">SLA Health</span>
                  <Clock size={13} className={sla?.breached_count ? "text-danger" : sla?.warning_count ? "text-warn" : "text-success"} />
                </div>
                <span className={cn("font-mono font-bold",
                  sla ? (sla.breached_count > 0 ? "text-danger" : sla.warning_count > 0 ? "text-warn" : "text-success") : "text-text-primary",
                  presentMode ? "text-4xl" : "text-3xl"
                )}>
                  {sla ? `${slaHealthPct(sla)}%` : "—"}
                </span>
                <span className="text-xs text-text-muted">
                  {sla?.breached_count ?? 0} breached · {sla?.warning_count ?? 0} at risk
                </span>
              </div>

              <div className={cn("panel p-4 flex flex-col gap-2", presentMode && "py-6")}>
                <div className="flex items-center justify-between">
                  <span className="text-2xs uppercase tracking-widest text-text-muted font-sans font-semibold">AI Time Saved</span>
                  <DollarSign size={13} className="text-text-muted" />
                </div>
                <span className={cn("font-mono font-bold text-text-primary", presentMode ? "text-4xl" : "text-3xl")}>
                  {pipeline ? `~${aiHoursSaved(pipeline)}h` : "—"}
                </span>
                <span className="text-xs text-text-muted">Est. analyst hours automated</span>
              </div>
            </>
          )}
        </div>

        {/* Main panels */}
        <div className="grid grid-cols-12 gap-5 flex-1 min-h-0">
          {/* Pipeline Funnel */}
          <div className={cn("panel p-5 flex flex-col gap-4", presentMode ? "col-span-12 lg:col-span-5" : "col-span-12 lg:col-span-4")}>
            <div className="flex items-center justify-between">
              <span className="text-xs font-sans font-semibold text-text-primary uppercase tracking-widest">Pipeline Funnel</span>
              <span className="badge-accent text-2xs">{pipeline?.total_opportunities ?? 0} total</span>
            </div>
            <div className="flex flex-col gap-3 flex-1">
              {loading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="h-5 rounded bg-bg-tertiary animate-pulse" />
                ))
              ) : sortedFunnel.length === 0 ? (
                <p className="text-xs text-text-muted">No pipeline data.</p>
              ) : (
                sortedFunnel.map((stage, i) => {
                  const next = sortedFunnel[i + 1];
                  const convPct = next && stage.count > 0
                    ? Math.round((next.count / stage.count) * 100)
                    : undefined;
                  return (
                    <FunnelBar
                      key={stage.stage}
                      label={STAGE_LABEL[stage.stage] ?? stage.stage}
                      count={stage.count}
                      max={maxFunnelCount}
                      pct={convPct}
                    />
                  );
                })
              )}
            </div>
          </div>

          {/* Center: Revenue at risk + briefing */}
          <div className={cn("flex flex-col gap-4", presentMode ? "col-span-12 lg:col-span-4" : "col-span-12 lg:col-span-4")}>
            {/* Revenue at risk */}
            <div className="panel p-5 flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <AlertTriangle size={14} className="text-danger" />
                <span className="text-xs font-sans font-semibold text-text-primary uppercase tracking-widest">Revenue at Risk</span>
              </div>
              <div className="flex items-baseline gap-2">
                <span className={cn("font-mono font-bold text-danger", presentMode ? "text-4xl" : "text-3xl")}>
                  {sla ? formatCurrency(revenueAtRisk(sla)) : "—"}
                </span>
                <span className="text-xs text-text-muted">from {sla?.breached_count ?? 0} breached SLAs</span>
              </div>
              {overCapacitySME > 0 && (
                <div className="text-xs text-warn font-sans">
                  {overCapacitySME} SME{overCapacitySME > 1 ? "s" : ""} at capacity — assignment risk elevated
                </div>
              )}
            </div>

            {/* Today in Presales */}
            <div className="panel p-5 flex flex-col gap-3 flex-1">
              <span className="text-xs font-sans font-semibold text-text-primary uppercase tracking-widest">
                Today in Presales
              </span>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-0.5">
                  <span className={cn("font-mono font-bold text-text-primary", presentMode ? "text-2xl" : "text-xl")}>
                    {pipeline?.total_opportunities ?? 0}
                  </span>
                  <span className="text-2xs text-text-muted">Active deals</span>
                </div>
                <div className="flex flex-col gap-0.5">
                  <span className={cn("font-mono font-bold", sla?.breached_count ? "text-danger" : "text-text-primary", presentMode ? "text-2xl" : "text-xl")}>
                    {sla?.breached_count ?? 0}
                  </span>
                  <span className="text-2xs text-text-muted">SLA breaches</span>
                </div>
                <div className="flex flex-col gap-0.5">
                  <span className={cn("font-mono font-bold text-text-primary", presentMode ? "text-2xl" : "text-xl")}>
                    {sla?.warning_count ?? 0}
                  </span>
                  <span className="text-2xs text-text-muted">At risk</span>
                </div>
                <div className="flex flex-col gap-0.5">
                  <span className={cn("font-mono font-bold text-text-primary", presentMode ? "text-2xl" : "text-xl")}>
                    {smeLoad?.length ?? 0}
                  </span>
                  <span className="text-2xs text-text-muted">SMEs active</span>
                </div>
              </div>

              {sla?.top_bottleneck && (
                <div className="mt-2 p-2 rounded bg-warn/10 border border-warn/20">
                  <span className="text-2xs text-warn font-sans font-medium">Top bottleneck: </span>
                  <span className="text-2xs text-warn font-mono">{STAGE_LABEL[sla.top_bottleneck] ?? sla.top_bottleneck}</span>
                </div>
              )}
            </div>
          </div>

          {/* Right: At-risk deals */}
          <div className={cn("panel p-5 flex flex-col gap-3", presentMode ? "col-span-12 lg:col-span-3" : "col-span-12 lg:col-span-4")}>
            <span className="text-xs font-sans font-semibold text-text-primary uppercase tracking-widest">
              Deals Needing Attention
            </span>
            {loading ? (
              Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-14 rounded bg-bg-tertiary animate-pulse" />
              ))
            ) : topDeals.length === 0 ? (
              <p className="text-xs text-success font-sans mt-2">All SLAs on track.</p>
            ) : (
              <div className="flex flex-col gap-2 overflow-auto">
                {topDeals.map((opp) => {
                  const isBreached = opp.hours_remaining < 0;
                  return (
                    <div
                      key={opp.opportunity_id}
                      className={cn(
                        "p-3 rounded border flex flex-col gap-1",
                        isBreached ? "border-danger/30 bg-danger/5" : "border-warn/30 bg-warn/5"
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-sans font-medium text-text-primary truncate">
                          {opp.title}
                        </span>
                        <span className={cn("badge text-2xs shrink-0", isBreached ? "badge-danger" : "badge-warn")}>
                          {isBreached ? "Breached" : "At risk"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-2xs text-text-muted font-mono">
                        <span>{opp.client_name ?? "Unknown"}</span>
                        <span className={isBreached ? "text-danger" : "text-warn"}>
                          {isBreached
                            ? `${Math.abs(opp.hours_remaining ?? 0).toFixed(0)}h overdue`
                            : `${(opp.hours_remaining ?? 0).toFixed(0)}h left`}
                        </span>
                      </div>
                      <div className="text-2xs text-text-muted">
                        {opp.deal_value_cr ? formatCurrency(opp.deal_value_cr) : "—"} · {opp.stage}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      {!presentMode && (
        <footer className="flex-shrink-0 flex items-center justify-between px-6 py-2 border-t border-border bg-bg-secondary">
          <span className="text-2xs text-text-muted font-sans">
            Auto-refreshes every {REFRESH_MS / 1000}s ·{" "}
            <kbd className="text-2xs bg-bg-tertiary border border-border rounded px-1">F</kbd> fullscreen ·{" "}
            <kbd className="text-2xs bg-bg-tertiary border border-border rounded px-1">P</kbd> presentation ·{" "}
            <kbd className="text-2xs bg-bg-tertiary border border-border rounded px-1">Space</kbd> pause
          </span>
          <span className="text-2xs text-text-muted font-mono">
            {paused ? "⏸ PAUSED" : "● LIVE"}
          </span>
        </footer>
      )}
    </div>
  );
}
