import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(crores: number): string {
  if (crores >= 100) return `₹${(crores / 100).toFixed(1)}K Cr`;
  return `₹${crores.toFixed(1)} Cr`;
}

export function formatPercent(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatHours(hours: number): string {
  if (hours < 0) return "Overdue";
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${Math.floor(hours)}h ${Math.round((hours % 1) * 60)}m`;
  const days = Math.floor(hours / 24);
  const rem  = Math.floor(hours % 24);
  return rem > 0 ? `${days}d ${rem}h` : `${days}d`;
}

export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60)   return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60)   return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24)   return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function slaColor(status: string): string {
  if (status === "breached") return "#ef4444";
  if (status === "warning")  return "#f59e0b";
  return "#22c55e";
}

export function healthColor(score: number): string {
  if (score >= 80) return "#22c55e";
  if (score >= 50) return "#f59e0b";
  return "#ef4444";
}

export function tierBadgeClass(tier: string): string {
  const map: Record<string, string> = {
    enterprise:    "badge-purple",
    professional:  "badge-blue",
    starter:       "badge-accent",
    free:          "badge-muted",
  };
  return map[tier] ?? "badge-muted";
}

export function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    active:      "badge-accent",
    approved:    "badge-success",
    breached:    "badge-danger",
    warning:     "badge-warn",
    pending:     "badge-muted",
    rejected:    "badge-danger",
    escalated:   "badge-warn",
    suspended:   "badge-danger",
    archived:    "badge-muted",
    critical:    "badge-danger",
    high:        "badge-warn",
    medium:      "badge-blue",
    low:         "badge-muted",
  };
  return map[status.toLowerCase()] ?? "badge-muted";
}

export function truncate(str: string, max: number): string {
  return str.length <= max ? str : str.slice(0, max - 1) + "…";
}
