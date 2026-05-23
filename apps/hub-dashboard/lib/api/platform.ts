import { apiFetch } from "./client";
import type { Tenant, TenantQuota, AuditEntry, PlatformHealth } from "../types/api";

const ADMIN_KEY = process.env.NEXT_PUBLIC_PLATFORM_ADMIN_KEY ?? "dev-admin-key";
const adminHeaders = { "X-Platform-Admin-Key": ADMIN_KEY };

export const platformApi = {
  listTenants:    (status?: string, tier?: string, limit = 100) =>
    apiFetch<{ total: number; tenants: Tenant[] }>("/api/platform/tenants", { headers: adminHeaders, params: { status, tier, limit } }),
  getTenant:      (id: string) => apiFetch<Tenant>(`/api/platform/tenants/${id}`, { headers: adminHeaders }),
  provisionTenant:(body: Record<string, unknown>) =>
    apiFetch<{ tenant_id: string; status: string }>("/api/platform/tenants", { method: "POST", headers: adminHeaders, body: JSON.stringify(body) }),
  updateStatus:   (id: string, status: string, actor_id?: string, reason?: string) =>
    apiFetch<{ tenant_id: string; status: string }>(`/api/platform/tenants/${id}/status`, {
      method: "PATCH", headers: adminHeaders, body: JSON.stringify({ status, actor_id, reason }),
    }),
  getQuotas:      (id: string) => apiFetch<{ tenant_id: string; quotas: TenantQuota[] }>(`/api/platform/tenants/${id}/quotas`, { headers: adminHeaders }),
  updateQuota:    (id: string, resource: string, new_limit: number) =>
    apiFetch<{ tenant_id: string; resource: string; new_limit: number }>(`/api/platform/tenants/${id}/quotas`, {
      method: "PATCH", headers: adminHeaders, body: JSON.stringify({ resource, new_limit }),
    }),
  getAudit:       (id: string, limit = 50) => apiFetch<{ entries: AuditEntry[] }>(`/api/platform/tenants/${id}/audit`, { headers: adminHeaders, params: { limit } }),
  getFeatureFlags:(id: string) => apiFetch<{ flags: Record<string, boolean> }>(`/api/platform/tenants/${id}/feature-flags`, { headers: adminHeaders }),
  setFeatureFlag: (flag_name: string, enabled: boolean, tenant_id?: string) =>
    apiFetch<{ flag_name: string; enabled: boolean }>("/api/platform/feature-flags", {
      method: "POST", headers: adminHeaders, body: JSON.stringify({ flag_name, enabled, tenant_id }),
    }),
  health:         () => apiFetch<PlatformHealth>("/api/platform/health", { headers: adminHeaders }),
  metrics:        () => apiFetch<{ tenants_by_tier: Record<string, number>; total_usage_records: number; total_billing_events: number }>("/api/platform/metrics", { headers: adminHeaders }),
  deployment:     () => apiFetch<Record<string, unknown>>("/api/platform/deployment", { headers: adminHeaders }),
};
