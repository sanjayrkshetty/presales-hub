import { apiFetch } from "./client";

export interface ServiceCheck {
  status: "ok" | "error";
  detail?: string;
}

export interface CircuitBreakerStatus {
  name:               string;
  state:              "closed" | "open" | "half_open";
  failures:           number;
  failure_threshold:  number;
  recovery_timeout_s: number;
}

export interface HealthResponse {
  status:           "ok" | "degraded" | "critical";
  service:          string;
  version:          string;
  timestamp:        string;
  checks: {
    postgres:  ServiceCheck;
    redis:     ServiceCheck;
    temporal:  ServiceCheck;
  };
  circuit_breakers: CircuitBreakerStatus[];
  latency_ms:       number;
  dlq_pending?:     number;
}

export const healthApi = {
  get: () => apiFetch<HealthResponse>("/api/health"),
};
