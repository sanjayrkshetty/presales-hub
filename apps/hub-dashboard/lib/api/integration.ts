import { apiFetch } from "./client";
import type { ConnectorHealth, IntegrationDashboard, RetryJob, WebhookSubscription } from "../types/api";

export const integrationApi = {
  listConnectors:  (tenant_id = "default") => apiFetch<{ connectors: ConnectorHealth[] }>("/api/integration/connectors", { params: { tenant_id } }),
  connectorHealth: (platform: string) => apiFetch<ConnectorHealth>(`/api/integration/connectors/${platform}/health`),
  syncStatus:      (tenant_id = "default") => apiFetch<{ by_status: Record<string, number>; records: unknown[] }>("/api/integration/sync/status", { params: { tenant_id } }),
  runSync:         (channel: string, tenant_id = "default") =>
    apiFetch<{ channel: string; status: string }>("/api/integration/sync/run", {
      method: "POST",
      body: JSON.stringify({ channel, tenant_id }),
    }),
  listWebhooks:    (tenant_id = "default") => apiFetch<{ subscriptions: WebhookSubscription[] }>("/api/integration/webhooks", { params: { tenant_id } }),
  createWebhook:   (tenant_id: string, target_url: string, event_types: string[], secret?: string) =>
    apiFetch<WebhookSubscription>("/api/integration/webhooks", {
      method: "POST",
      body: JSON.stringify({ tenant_id, target_url, event_types, secret }),
    }),
  deleteWebhook:   (id: string) => apiFetch<{ deleted: boolean }>(`/api/integration/webhooks/${id}`, { method: "DELETE" }),
  retryQueue:      (tenant_id = "default") => apiFetch<{ jobs: RetryJob[] }>("/api/integration/retry/queue", { params: { tenant_id } }),
  dlq:             (tenant_id = "default") => apiFetch<{ jobs: RetryJob[] }>("/api/integration/retry/dlq", { params: { tenant_id } }),
  requeueDlq:      (job_id: string) => apiFetch<{ requeued: boolean }>(`/api/integration/retry/dlq/${job_id}/requeue`, { method: "POST" }),
  dashboard:       (tenant_id = "default") => apiFetch<IntegrationDashboard>("/api/integration/dashboard", { params: { tenant_id } }),
  rateLimits:      (tenant_id = "default") => apiFetch<Record<string, unknown>>("/api/integration/rate-limits", { params: { tenant_id } }),
};
