"use client";

import { useState, useRef, useEffect } from "react";
import { User, LogOut, Settings } from "lucide-react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/auth/session";
import { apiFetch } from "@/lib/api/client";

export function ProfileMenu() {
  const { user, clearSession } = useAuthStore();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  async function handleLogout() {
    try {
      await apiFetch("/auth/logout", { method: "POST", credentials: "include" });
    } catch {}
    clearSession();
    router.push("/login");
  }

  if (!user) return null;

  const initials = user.full_name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 px-2 py-1 rounded hover:bg-white/4 transition-colors"
        title={user.full_name}
      >
        <span className="w-6 h-6 rounded-full bg-accent/20 text-accent flex items-center justify-center text-2xs font-mono font-bold">
          {initials}
        </span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-52 rounded border border-border bg-bg-secondary shadow-lg z-50">
          <div className="px-3 py-2.5 border-b border-border">
            <p className="text-xs font-sans font-medium text-text-primary truncate">{user.full_name}</p>
            <p className="text-2xs text-text-muted truncate">{user.email}</p>
            {user.roles.length > 0 && (
              <p className="text-2xs text-accent mt-0.5">{user.roles[0]}</p>
            )}
          </div>

          <div className="py-1">
            <button
              onClick={() => { setOpen(false); router.push("/settings"); }}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary hover:bg-white/4 transition-colors text-left"
            >
              <Settings size={12} />
              Settings
            </button>
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-danger hover:bg-danger/10 transition-colors text-left"
            >
              <LogOut size={12} />
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
