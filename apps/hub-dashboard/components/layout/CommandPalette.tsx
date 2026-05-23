"use client";
import { useEffect } from "react";
import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useUIStore } from "@/lib/store/ui";
import {
  LayoutDashboard, FileText, CheckSquare, Clock, Zap, Bot,
  TrendingUp, GitBranch, BarChart3, Users, Plug, Settings,
} from "lucide-react";

const ACTIONS = [
  { label: "Operations Console",   href: "/ops",          icon: LayoutDashboard },
  { label: "Proposals",            href: "/proposals",    icon: FileText        },
  { label: "Approval Center",      href: "/approvals",    icon: CheckSquare     },
  { label: "SLA Command Center",   href: "/sla",          icon: Clock           },
  { label: "AI Copilot",           href: "/copilot",      icon: Zap             },
  { label: "Agent Monitor",        href: "/agents",       icon: Bot             },
  { label: "Intelligence Cockpit", href: "/intelligence", icon: TrendingUp      },
  { label: "Workflow Timelines",   href: "/workflows",    icon: GitBranch       },
  { label: "Analytics",            href: "/analytics",    icon: BarChart3       },
  { label: "Stakeholders",         href: "/stakeholders", icon: Users           },
  { label: "Integration Health",   href: "/integrations", icon: Plug            },
  { label: "Platform Admin",       href: "/platform",     icon: Settings        },
];

export function CommandPalette() {
  const { commandPaletteOpen, setCommandPaletteOpen } = useUIStore();
  const router = useRouter();

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
        >
          <div className="flex items-center gap-2 px-3 border-b border-border">
            <span className="text-text-muted text-sm">⌘</span>
            <Command.Input
              placeholder="Jump to… or search"
              className="flex-1 py-3 bg-transparent text-sm text-text-primary placeholder:text-text-muted outline-none font-sans"
              autoFocus
            />
            <kbd className="text-2xs text-text-muted bg-bg-tertiary px-1.5 py-0.5 rounded">ESC</kbd>
          </div>
          <Command.List className="max-h-72 overflow-y-auto py-1">
            <Command.Empty className="py-6 text-center text-xs text-text-muted font-sans">
              No results
            </Command.Empty>
            <Command.Group heading="Navigation" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-2xs [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-widest [&_[cmdk-group-heading]]:text-text-muted [&_[cmdk-group-heading]]:font-sans [&_[cmdk-group-heading]]:font-semibold">
              {ACTIONS.map(({ label, href, icon: Icon }) => (
                <Command.Item
                  key={href}
                  value={label}
                  onSelect={() => { router.push(href); setCommandPaletteOpen(false); }}
                  className="flex items-center gap-2.5 px-3 py-2 text-sm text-text-secondary hover:text-text-primary cursor-pointer data-[selected=true]:bg-white/5 data-[selected=true]:text-text-primary font-sans transition-colors"
                >
                  <Icon size={13} className="text-text-muted flex-shrink-0" />
                  {label}
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
