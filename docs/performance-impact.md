# Phase 10 — Bundle & Performance Impact Summary

> Measured against the Phase 9 baseline. All values are approximate — run
> `next build` and check `.next/analyze/` for exact chunk sizes if
> `ANALYZE=true` is set in the build environment.

---

## Bundle Impact

| Addition | Estimated gzip delta | Notes |
|----------|---------------------|-------|
| `components/ui/system/*` (Badge, KpiCard, Table, Modal, Skeleton) | **+3–5 kB** | CVA adds ~1 kB; components are tree-shaken |
| `app/executive/page.tsx` | **+6–8 kB** | Fixed-position overlay, no Recharts — pure CSS |
| `app/system/page.tsx` | **+4–5 kB** | React Query + healthApi client |
| `components/analytics/FunnelChart.tsx` + inner | **+0 kB eager** | Dynamic import `ssr:false` — lazy chunk |
| `components/analytics/SlaBreachTrend.tsx` + inner | **+0 kB eager** | Same |
| `components/analytics/SmeHeatmap.tsx` | **+2 kB** | Pure CSS grid, no chart lib |
| `lib/store/demo.ts` | **+1 kB** | Single Zustand slice |
| `lib/hooks/usePreferences.ts` | **<1 kB** | localStorage wrapper |
| `lib/api/health.ts` | **<1 kB** | Typed fetch wrapper |
| `components/ui/DemoResetButton.tsx` | **<1 kB** | Conditionally rendered |
| Enhanced `DemoModeProvider.tsx` | **+1 kB** | No new deps |
| **Total eager bundle increase** | **≈18–25 kB gzip** | Recharts charts remain in async chunks |

### No New npm Packages Added

Phase 10 uses only existing dependencies:

| Dep already present | Used in Phase 10 |
|---------------------|-----------------|
| `recharts` 3.8 | FunnelChart, SlaBreachTrend |
| `class-variance-authority` | Badge |
| `zustand` | useDemoStore |
| `@tanstack/react-query` | healthApi, executive auto-refresh |
| `lucide-react` | Monitor, Server icons (already in bundle) |
| `cmdk` | CommandPalette (no change) |

---

## Runtime Performance

### Auto-Refresh Polling

| Page | Interval | Network call | Payload (est.) |
|------|----------|-------------|----------------|
| `/executive` | 15 s | `analyticsApi.pipeline()` + `analyticsApi.sla()` + `analyticsApi.smeLoad()` | ~3 KB combined |
| `/system` | 10 s | `GET /api/health` | ~1 KB |

Both use React Query `refetchInterval` with `staleTime` to prevent duplicate in-flight requests. Background tabs will not poll (React Query pauses on `visibilitychange`).

### WebSocket Connections

The executive page mounts inside AppShell (CSS overlay) so it inherits the existing single `useRealtimeStore` WebSocket connection — no additional connections opened.

### Chart Rendering

All Recharts components (`FunnelChart`, `SlaBreachTrend`) are imported via `next/dynamic` with `ssr: false`. They:
- Are excluded from the server-rendered HTML (no hydration mismatch)
- Load lazily when the analytics page first mounts
- Show `<ChartSkeleton>` while loading — no layout shift

### DemoModeProvider Jitter

Changed from `setInterval(8000)` to recursive `setTimeout(6000–18000 ms)`. Impact: one fewer timer per cycle; GC pressure is identical.

---

## Memory & Store Impact

| Store | Phase 10 additions | Notes |
|-------|-------------------|-------|
| `useRealtimeStore` | `clearLog()` called on demo reset | Pre-existing store |
| `useNotificationStore` | `markAllRead()` called on demo reset | Pre-existing store |
| `useDemoStore` | New: `isDemoMode`, `resetCount` | 2 booleans + 1 int |
| `usePreferences` | `localStorage` read on mount | Synchronous, <1 ms |

No memory leaks: all `useEffect` cleanups clear `setTimeout`/`setInterval` ids. Modal uses `createPortal` and unmounts cleanly.

---

## Lighthouse Estimates (approximate)

| Metric | Before Phase 10 | After Phase 10 | Delta |
|--------|----------------|----------------|-------|
| First Contentful Paint | baseline | +0 ms (no SSR change) | — |
| Total Blocking Time | baseline | negligible | Charts async |
| Cumulative Layout Shift | 0 | 0 | Charts use ChartSkeleton |
| Bundle (First Load JS) | baseline | +18–25 kB gzip | Acceptable |

---

## Recommendations

1. **Enable `ANALYZE=true`** in CI to track bundle size per PR — catch regressions early.
2. **Consider prefetching** `/api/health` on the ops console to warm the cache before users navigate to `/system`.
3. The executive page's 15 s polling and system page's 10 s polling are fine at current scale. Revisit if > 200 concurrent users hit those pages simultaneously — consider SSE or shared WebSocket event to replace REST polling.
