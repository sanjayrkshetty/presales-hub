"use client";
import { usePathname } from "next/navigation";
import { Bell, Search, ExternalLink } from "lucide-react";
import { useUIStore } from "@/lib/store/ui";
import { useNotificationStore } from "@/lib/store/notifications";
import { RealtimeIndicator } from "@/components/realtime/RealtimeIndicator";
import { cn } from "@/lib/utils";

const BREADCRUMBS: Record<string, string> = {
  "/ops":          "Operations Console",
  "/proposals":    "Proposals",
  "/approvals":    "Approval Center",
  "/sla":          "SLA Command Center",
  "/copilot":      "AI Copilot",
  "/agents":       "Agent Monitor",
  "/intelligence": "Intelligence Cockpit",
  "/workflows":    "Workflow Timelines",
  "/analytics":    "Analytics",
  "/stakeholders": "Stakeholders",
  "/integrations": "Integration Health",
  "/platform":     "Platform Admin",
};

interface Props { apiUrl?: string; }

export function TopBar({ apiUrl }: Props) {
  const pathname    = usePathname();
  const { setCommandPaletteOpen } = useUIStore();
  const { unreadCount, markAllRead, notifications } = useNotificationStore();

  const crumb = BREADCRUMBS[pathname] ?? pathname.split("/").filter(Boolean).join(" / ");

  return (
    <header className="h-11 flex items-center px-4 gap-3 border-b border-border bg-bg-secondary flex-shrink-0">
      {/* Breadcrumb */}
      <span className="text-xs font-sans font-medium text-text-secondary truncate flex-1">
        {crumb}
      </span>

      {/* Search / command palette trigger */}
      <button
        onClick={() => setCommandPaletteOpen(true)}
        className="flex items-center gap-2 px-3 py-1 rounded border border-border bg-bg-tertiary text-text-muted hover:border-border-subtle hover:text-text-secondary transition-colors text-xs font-sans"
      >
        <Search size={11} />
        <span className="hidden sm:inline">Search or jump to…</span>
        <kbd className="hidden sm:inline text-2xs bg-bg-primary px-1 rounded">⌘K</kbd>
      </button>

      <RealtimeIndicator />

      {/* Notifications */}
      <div className="relative">
        <button
          onClick={markAllRead}
          className="relative p-1.5 rounded hover:bg-white/4 transition-colors text-text-muted hover:text-text-primary"
          title="Notifications"
        >
          <Bell size={14} />
          {unreadCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-3.5 flex items-center justify-center rounded-full bg-danger text-white text-2xs font-mono font-bold px-0.5">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </button>
      </div>

      {/* API link */}
      {apiUrl && (
        <a href={apiUrl} target="_blank" rel="noopener" className="text-text-muted hover:text-text-primary transition-colors" title="API Docs">
          <ExternalLink size={12} />
        </a>
      )}
    </header>
  );
}
