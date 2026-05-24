"use client";

import { useAuthStore } from "@/lib/auth/session";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { User, Shield } from "lucide-react";

export default function SettingsPage() {
  const { user } = useAuthStore();

  if (!user) return null;

  return (
    <div className="p-6 max-w-2xl mx-auto flex flex-col gap-6">
      <SectionHeader title="Settings" />

      <div className="panel p-4 flex flex-col gap-4">
        <div className="flex items-center gap-2 text-xs font-mono text-text-muted uppercase tracking-widest">
          <User size={12} /> Profile
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <p className="text-2xs text-text-muted mb-1">Full name</p>
            <p className="text-xs text-text-primary font-mono">{user.full_name}</p>
          </div>
          <div>
            <p className="text-2xs text-text-muted mb-1">Email</p>
            <p className="text-xs text-text-primary font-mono">{user.email}</p>
          </div>
          <div>
            <p className="text-2xs text-text-muted mb-1">Tenant</p>
            <p className="text-xs text-text-primary font-mono">{user.tenant_id ?? "—"}</p>
          </div>
        </div>
      </div>

      <div className="panel p-4 flex flex-col gap-4">
        <div className="flex items-center gap-2 text-xs font-mono text-text-muted uppercase tracking-widest">
          <Shield size={12} /> Roles & Permissions
        </div>
        <div className="flex flex-wrap gap-1.5">
          {user.roles.map((r) => (
            <span key={r} className="px-2 py-0.5 rounded border border-accent/30 text-accent text-2xs font-mono">
              {r}
            </span>
          ))}
        </div>
        {user.permissions.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {user.permissions.map((p) => (
              <span key={p} className="px-1.5 py-0.5 rounded bg-bg-tertiary text-text-muted text-2xs font-mono">
                {p}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
