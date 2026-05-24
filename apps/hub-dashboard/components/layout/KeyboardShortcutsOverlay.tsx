"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

const SHORTCUTS = [
  { group: "Navigation",  keys: ["⌘", "K"],           desc: "Open command palette"      },
  { group: "Navigation",  keys: ["?"],                  desc: "Show keyboard shortcuts"   },
  { group: "Navigation",  keys: ["G", "then", "O"],    desc: "Go to Operations"          },
  { group: "Navigation",  keys: ["G", "then", "P"],    desc: "Go to Proposals"           },
  { group: "Navigation",  keys: ["G", "then", "A"],    desc: "Go to Approvals"           },
  { group: "Navigation",  keys: ["G", "then", "S"],    desc: "Go to SLA Command Center"  },
  { group: "Navigation",  keys: ["G", "then", "C"],    desc: "Go to AI Copilot"          },
  { group: "Actions",     keys: ["Esc"],                desc: "Close dialog / panel"      },
  { group: "Actions",     keys: ["⌘", "Shift", "R"],   desc: "Refresh current data"      },
];

const grouped = SHORTCUTS.reduce<Record<string, typeof SHORTCUTS>>((acc, s) => {
  (acc[s.group] ??= []).push(s);
  return acc;
}, {});

export function KeyboardShortcutsOverlay() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "?") { e.preventDefault(); setOpen((o) => !o); }
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-md mx-4 panel shadow-panel-lg animate-fade_in overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <span className="text-xs font-mono font-semibold text-text-primary uppercase tracking-widest">
            Keyboard Shortcuts
          </span>
          <button onClick={() => setOpen(false)} className="text-text-muted hover:text-text-primary transition-colors">
            <X size={14} />
          </button>
        </div>
        <div className="overflow-y-auto max-h-96 py-2">
          {Object.entries(grouped).map(([group, items]) => (
            <div key={group} className="mb-3">
              <div className="px-4 py-1.5 text-2xs text-text-muted uppercase tracking-widest font-mono font-semibold">
                {group}
              </div>
              {items.map((s, i) => (
                <div key={i} className="flex items-center justify-between px-4 py-1.5 hover:bg-white/4">
                  <span className="text-xs text-text-secondary font-sans">{s.desc}</span>
                  <div className="flex items-center gap-1">
                    {s.keys.map((k, ki) => (
                      k === "then" ? (
                        <span key={ki} className="text-2xs text-text-muted">then</span>
                      ) : (
                        <kbd key={ki} className="px-1.5 py-0.5 rounded border border-border bg-bg-tertiary text-2xs font-mono text-text-secondary">
                          {k}
                        </kbd>
                      )
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
        <div className="px-4 py-2.5 border-t border-border text-2xs text-text-muted font-sans text-center">
          Press <kbd className="px-1 rounded border border-border bg-bg-tertiary font-mono">?</kbd> to toggle
        </div>
      </div>
    </div>
  );
}
