"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/store/ui";
import {
  LayoutDashboard, FileText, CheckSquare, Clock, Bot, GitBranch,
  Cpu, TrendingUp, Plug, Settings, BarChart3, Users, ChevronLeft, ChevronRight,
  Zap,
} from "lucide-react";

const NAV = [
  {
    group: "Operations",
    items: [
      { href: "/ops",       icon: LayoutDashboard, label: "Operations Console" },
      { href: "/proposals", icon: FileText,         label: "Proposals"          },
      { href: "/approvals", icon: CheckSquare,       label: "Approvals"          },
      { href: "/sla",       icon: Clock,             label: "SLA Command"        },
    ],
  },
  {
    group: "Intelligence",
    items: [
      { href: "/copilot",       icon: Zap,         label: "AI Copilot"      },
      { href: "/agents",        icon: Bot,          label: "Agent Monitor"   },
      { href: "/intelligence",  icon: TrendingUp,   label: "Intelligence"    },
      { href: "/workflows",     icon: GitBranch,    label: "Workflows"       },
    ],
  },
  {
    group: "Data",
    items: [
      { href: "/analytics",   icon: BarChart3, label: "Analytics"   },
      { href: "/stakeholders",icon: Users,      label: "Stakeholders" },
    ],
  },
  {
    group: "Platform",
    items: [
      { href: "/integrations", icon: Plug,     label: "Integrations" },
      { href: "/platform",     icon: Settings, label: "Platform"     },
    ],
  },
];

export function Sidebar() {
  const pathname   = usePathname();
  const { sidebarCollapsed, toggleSidebar } = useUIStore();

  return (
    <aside className={cn(
      "flex flex-col h-full bg-bg-secondary border-r border-border transition-all duration-200 flex-shrink-0",
      sidebarCollapsed ? "w-12" : "w-48"
    )}>
      {/* Logo */}
      <div className="h-11 flex items-center px-3 border-b border-border gap-2 flex-shrink-0">
        <span className="w-6 h-6 rounded bg-accent/20 border border-accent/40 flex items-center justify-center flex-shrink-0">
          <Cpu size={12} className="text-accent" />
        </span>
        {!sidebarCollapsed && (
          <span className="text-xs font-sans font-bold text-text-primary tracking-tight truncate">PRESALES HUB</span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-2">
        {NAV.map((section) => (
          <div key={section.group} className="mb-1">
            {!sidebarCollapsed && (
              <div className="px-3 pt-3 pb-1 text-2xs uppercase tracking-widest text-text-muted font-sans font-semibold">
                {section.group}
              </div>
            )}
            {section.items.map(({ href, icon: Icon, label }) => {
              const active = pathname === href || (href !== "/" && pathname.startsWith(href));
              return (
                <Link
                  key={href}
                  href={href}
                  title={sidebarCollapsed ? label : undefined}
                  className={cn(
                    "flex items-center gap-2.5 px-3 py-1.5 mx-1 rounded text-xs font-sans transition-colors",
                    active
                      ? "bg-accent/10 text-accent"
                      : "text-text-secondary hover:text-text-primary hover:bg-white/4"
                  )}
                >
                  <Icon size={13} className="flex-shrink-0" />
                  {!sidebarCollapsed && <span className="truncate">{label}</span>}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={toggleSidebar}
        className="h-9 flex items-center justify-center border-t border-border text-text-muted hover:text-text-primary hover:bg-white/4 transition-colors"
        aria-label="Toggle sidebar"
      >
        {sidebarCollapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
      </button>
    </aside>
  );
}
