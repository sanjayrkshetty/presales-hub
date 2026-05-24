"use client";

import { useEffect, useState, useTransition } from "react";
import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useUIStore } from "@/lib/store/ui";
import { apiFetch } from "@/lib/api/client";
import {
  LayoutDashboard, FileText, CheckSquare, Clock, Zap, Bot,
  TrendingUp, GitBranch, BarChart3, Users, Plug, Settings,
  Search, User, Briefcase,
} from "lucide-react";

const NAV_ACTIONS = [
  { label: "Operations Console",   href: "/ops",            icon: LayoutDashboard },
  { label: "Proposals",            href: "/proposals",      icon: FileText        },
  { label: "Approval Center",      href: "/approvals",      icon: CheckSquare     },
  { label: "SLA Command Center",   href: "/sla",            icon: Clock           },
  { label: "AI Copilot",           href: "/copilot",        icon: Zap             },
  { label: "Agent Monitor",        href: "/agents",         icon: Bot             },
  { label: "Intelligence Cockpit", href: "/intelligence",   icon: TrendingUp      },
  { label: "Workflow Timelines",   href: "/workflows",      icon: GitBranch       },
  { label: "Analytics",            href: "/analytics",      icon: BarChart3       },
  { label: "AI Governance",        href: "/ai-governance",  icon: Brain           },
  { label: "Stakeholders",         href: "/stakeholders",   icon: Users           },
  { label: "Integration Health",   href: "/integrations",   icon: Plug            },
  { label: "Platform Admin",       href: "/platform",       icon: Settings        },
];

// Dynamically imported to avoid tree-shaking Brain from lucide
import { Brain } from "lucide-react";

interface EntityResult {
  id: string;
  label: string;
  sub: string;
  href: string;
  icon: typeof FileText;
}

// 0 = exact, 1 = starts-with, 2 = contains — lower score sorts first
function relevanceScore(label: string, term: string): number {
  const l = label.toLowerCase();
  if (l === term) return 0;
  if (l.startsWith(term)) return 1;
  return 2;
}

function rankByRelevance<T extends { label: string }>(items: T[], term: string): T[] {
  return [...items].sort((a, b) => relevanceScore(a.label, term) - relevanceScore(b.label, term));
}

async function searchEntities(q: string): Promise<EntityResult[]> {
  if (q.length < 2) return [];
  const term = q.toLowerCase();
  const results: EntityResult[] = [];

  try {
    const opps = await apiFetch<Array<{ id: string; title: string; stage: string }>>("/api/opportunities");
    const matched = opps.filter(
      (o) => o.title.toLowerCase().includes(term) || o.id.toLowerCase().includes(term)
    );
    rankByRelevance(matched.map((o) => ({ ...o, label: o.title })), term)
      .slice(0, 4)
      .forEach((o) => results.push({ id: o.id, label: o.title, sub: o.stage, href: `/proposals?opp=${o.id}`, icon: Briefcase }));
  } catch {}

  try {
    const stks = await apiFetch<Array<{ id: string; name: string; role: string; bu: string }>>("/api/stakeholders");
    const matched = stks.filter(
      (s) => s.name.toLowerCase().includes(term) || s.role.toLowerCase().includes(term)
    );
    rankByRelevance(matched.map((s) => ({ ...s, label: s.name })), term)
      .slice(0, 3)
      .forEach((s) => results.push({ id: s.id, label: s.name, sub: `${s.role} · ${s.bu}`, href: `/stakeholders`, icon: User }));
  } catch {}

  return results;
}

export function CommandPalette() {
  const { commandPaletteOpen, setCommandPaletteOpen } = useUIStore();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [entities, setEntities] = useState<EntityResult[]>([]);
  const [, startTransition] = useTransition();

  const filteredNavActions = query.length < 1
    ? NAV_ACTIONS
    : rankByRelevance(
        NAV_ACTIONS.filter((a) => a.label.toLowerCase().includes(query.toLowerCase())),
        query.toLowerCase()
      );

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCommandPaletteOpen(true);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, [setCommandPaletteOpen]);

  useEffect(() => {
    if (!commandPaletteOpen) { setQuery(""); setEntities([]); }
  }, [commandPaletteOpen]);

  useEffect(() => {
    if (!query) { setEntities([]); return; }
    const timer = setTimeout(() => {
      startTransition(() => {
        searchEntities(query).then(setEntities);
      });
    }, 250);
    return () => clearTimeout(timer);
  }, [query]);

  function navigate(href: string) {
    router.push(href);
    setCommandPaletteOpen(false);
  }

  if (!commandPaletteOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/60 backdrop-blur-sm"
      onClick={() => setCommandPaletteOpen(false)}
    >
      <div
        className="w-full max-w-lg mx-4 panel shadow-panel-lg animate-fade_in overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <Command
          className="w-full bg-transparent"
          onKeyDown={(e) => { if (e.key === "Escape") setCommandPaletteOpen(false); }}
          shouldFilter={false}
        >
          <div className="flex items-center gap-2 px-3 border-b border-border">
            <Search size={13} className="text-text-muted flex-shrink-0" />
            <Command.Input
              placeholder="Search proposals, stakeholders, or jump to…"
              className="flex-1 py-3 bg-transparent text-sm text-text-primary placeholder:text-text-muted outline-none font-sans"
              autoFocus
              value={query}
              onValueChange={setQuery}
            />
            <kbd className="text-2xs text-text-muted bg-bg-tertiary px-1.5 py-0.5 rounded">ESC</kbd>
          </div>
          <Command.List className="max-h-80 overflow-y-auto py-1">
            <Command.Empty className="py-6 text-center text-xs text-text-muted font-sans">
              No results for &ldquo;{query}&rdquo;
            </Command.Empty>

            {entities.length > 0 && (
              <Command.Group
                heading="Results"
                className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-2xs [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-widest [&_[cmdk-group-heading]]:text-text-muted [&_[cmdk-group-heading]]:font-sans [&_[cmdk-group-heading]]:font-semibold"
              >
                {entities.map(({ id, label, sub, href, icon: Icon }) => (
                  <Command.Item
                    key={id}
                    value={`entity-${id}-${label}`}
                    onSelect={() => navigate(href)}
                    className="flex items-center gap-2.5 px-3 py-2 text-sm cursor-pointer data-[selected=true]:bg-white/5 font-sans transition-colors"
                  >
                    <Icon size={13} className="text-accent flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-text-primary text-sm truncate">{label}</div>
                      <div className="text-text-muted text-2xs truncate">{sub}</div>
                    </div>
                  </Command.Item>
                ))}
              </Command.Group>
            )}

            <Command.Group
              heading="Navigation"
              className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-2xs [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-widest [&_[cmdk-group-heading]]:text-text-muted [&_[cmdk-group-heading]]:font-sans [&_[cmdk-group-heading]]:font-semibold"
            >
              {filteredNavActions.map(({ label, href, icon: Icon }) => (
                <Command.Item
                  key={href}
                  value={label}
                  onSelect={() => navigate(href)}
                  className="flex items-center gap-2.5 px-3 py-2 text-sm text-text-secondary hover:text-text-primary cursor-pointer data-[selected=true]:bg-white/5 data-[selected=true]:text-text-primary font-sans transition-colors"
                >
                  <Icon size={13} className="text-text-muted flex-shrink-0" />
                  {label}
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>
          <div className="px-3 py-1.5 border-t border-border flex items-center justify-between">
            <span className="text-2xs text-text-muted font-sans">
              Press <kbd className="px-1 rounded border border-border bg-bg-tertiary font-mono">?</kbd> for shortcuts
            </span>
            <span className="text-2xs text-text-muted font-sans">
              <kbd className="px-1 rounded border border-border bg-bg-tertiary font-mono">↑↓</kbd> navigate ·
              <kbd className="px-1 rounded border border-border bg-bg-tertiary font-mono ml-1">↵</kbd> open
            </span>
          </div>
        </Command>
      </div>
    </div>
  );
}
