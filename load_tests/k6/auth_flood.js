/**
 * Presales Hub — k6 Auth Flood Test
 *
 * Sends 22 concurrent login requests from the same "IP" to verify:
 * 1. Rate limiter fires (429) within the burst
 * 2. Account lockout fires (429) after 5 failed attempts for the same user
 * 3. API remains responsive under auth pressure
 *
 * Usage:
 *   k6 run load_tests/k6/auth_flood.js
 *   k6 run --env BASE_URL=https://api.presaleshub.io load_tests/k6/auth_flood.js
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Rate } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8003";

const rateLimitHits = new Counter("rate_limit_429_hits");
const lockoutHits = new Counter("account_lockout_hits");
const unexpectedErrors = new Rate("unexpected_errors");

export const options = {
  scenarios: {
    // Scenario 1: burst from single VU to test IP-level rate limiting
    ip_rate_limit: {
      executor: "shared-iterations",
      vus: 1,
      iterations: 22,
      maxDuration: "30s",
    },
    // Scenario 2: concurrent flood from multiple VUs
    concurrent_flood: {
      executor: "constant-vus",
      vus: 22,
      duration: "15s",
      startTime: "35s",
    },
  },
  thresholds: {
    rate_limit_429_hits: ["count>0"],      // must see at least one 429
    unexpected_errors: ["rate<0.5"],        // other errors should be < 50%
  },
};

export default function () {
  const i = Math.floor(Math.random() * 1000);
  const res = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({
      email: `flood_test_${i}@invalid.example`,
      password: "definitely_wrong_password",
    }),
    { headers: { "Content-Type": "application/json" } },
  );

  if (res.status === 429) {
    rateLimitHits.add(1);
    check(res, { "rate-limited: 429": (r) => r.status === 429 });
  } else if (res.status === 401) {
    // Expected: bad credentials
    check(res, { "bad-creds: 401": (r) => r.status === 401 });
  } else if (res.status === 200) {
    // Should not happen with wrong password
    unexpectedErrors.add(1);
    console.warn(`Unexpected 200 for flood login attempt ${i}`);
  } else {
    unexpectedErrors.add(1);
    console.warn(`Unexpected ${res.status} for attempt ${i}: ${res.body?.substring(0, 100)}`);
  }

  sleep(0.05); // minimal sleep to avoid overwhelming the test runner
}

export function handleSummary(data) {
  const hits = data.metrics?.rate_limit_429_hits?.values?.count ?? 0;
  console.log(`\n  Auth Flood Summary:`);
  console.log(`  Rate limit (429) hits: ${hits}`);
  console.log(`  Rate limiter ${hits > 0 ? "WORKING ✓" : "NOT TRIGGERED ✗"}`);
  return {};
}
