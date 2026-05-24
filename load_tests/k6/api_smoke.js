/**
 * Presales Hub — k6 API Smoke Test
 *
 * Baseline read-path verification: health, analytics, opportunities.
 * Designed to run after every deployment to catch regressions fast.
 *
 * Usage:
 *   k6 run load_tests/k6/api_smoke.js
 *   k6 run --env BASE_URL=https://api.presaleshub.io load_tests/k6/api_smoke.js
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8003";
const EMAIL = __ENV.DEMO_EMAIL || "arjun@sisa.demo";
const PASSWORD = __ENV.DEMO_PASSWORD || "Demo@1234";

const errorRate = new Rate("errors");
const apiLatency = new Trend("api_latency_ms", true);

export const options = {
  stages: [
    { duration: "10s", target: 5 },   // ramp up
    { duration: "30s", target: 5 },   // steady state
    { duration: "10s", target: 0 },   // ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<500"],  // 95th percentile under 500ms
    errors: ["rate<0.01"],             // < 1% error rate
    http_req_failed: ["rate<0.01"],
  },
};

let token = null;

export function setup() {
  const res = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email: EMAIL, password: PASSWORD }),
    { headers: { "Content-Type": "application/json" } },
  );
  if (res.status !== 200) {
    console.error(`Login failed: HTTP ${res.status} — ${res.body}`);
    return { token: null };
  }
  const body = JSON.parse(res.body);
  return { token: body.access_token };
}

export default function (data) {
  const headers = data.token
    ? { Authorization: `Bearer ${data.token}`, "Content-Type": "application/json" }
    : { "Content-Type": "application/json" };

  // Health check
  const health = http.get(`${BASE_URL}/api/health`);
  check(health, {
    "health: status 200": (r) => r.status === 200,
    "health: status ok/degraded": (r) => {
      try {
        const body = JSON.parse(r.body);
        return ["ok", "degraded"].includes(body.status);
      } catch {
        return false;
      }
    },
  });
  apiLatency.add(health.timings.duration, { endpoint: "health" });
  errorRate.add(health.status !== 200);

  // Metrics endpoint
  const metrics = http.get(`${BASE_URL}/metrics`);
  check(metrics, { "metrics: status 200": (r) => r.status === 200 });
  errorRate.add(metrics.status !== 200);

  // Pipeline analytics
  const pipeline = http.get(`${BASE_URL}/api/analytics/pipeline`, { headers });
  check(pipeline, { "analytics/pipeline: status 200": (r) => r.status === 200 });
  apiLatency.add(pipeline.timings.duration, { endpoint: "analytics_pipeline" });
  errorRate.add(pipeline.status !== 200);

  // SLA analytics
  const sla = http.get(`${BASE_URL}/api/analytics/sla`, { headers });
  check(sla, { "analytics/sla: status 200": (r) => r.status === 200 });
  apiLatency.add(sla.timings.duration, { endpoint: "analytics_sla" });
  errorRate.add(sla.status !== 200);

  // Opportunities list
  const opps = http.get(`${BASE_URL}/api/opportunities`, { headers });
  check(opps, { "opportunities: status 200": (r) => r.status === 200 });
  apiLatency.add(opps.timings.duration, { endpoint: "opportunities" });
  errorRate.add(opps.status !== 200);

  sleep(1);
}
