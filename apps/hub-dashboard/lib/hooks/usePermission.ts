"use client";

import { useAuthStore } from "@/lib/auth/session";

export function usePermission(permission: string): boolean {
  return useAuthStore((s) => s.user?.permissions.includes(permission) ?? false);
}

export function useHasAnyPermission(permissions: string[]): boolean {
  const userPerms = useAuthStore((s) => s.user?.permissions ?? []);
  return permissions.some((p) => userPerms.includes(p));
}

export function useHasRole(role: string): boolean {
  return useAuthStore((s) => s.user?.roles.includes(role) ?? false);
}
