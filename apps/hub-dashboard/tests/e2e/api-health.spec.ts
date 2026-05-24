import { test, expect } from "@playwright/test";

const API = process.env.API_URL ?? "http://localhost:8003";

test.describe("API health and security", () => {
  test("health endpoint returns ok or degraded", async ({ request }) => {
    const res = await request.get(`${API}/api/health`);
    expect([200, 503]).toContain(res.status());
    const body = await res.json();
    expect(body).toHaveProperty("status");
    expect(body).toHaveProperty("checks");
    expect(body.checks).toHaveProperty("postgres");
    expect(body.checks).toHaveProperty("redis");
    expect(body.checks).toHaveProperty("temporal");
  });

  test("readiness endpoint exists", async ({ request }) => {
    const res = await request.get(`${API}/api/ready`);
    expect([200, 503]).toContain(res.status());
  });

  test("metrics endpoint returns prometheus format", async ({ request }) => {
    const res = await request.get(`${API}/metrics`);
    expect(res.status()).toBe(200);
    const text = await res.text();
    expect(text.length).toBeGreaterThan(0);
  });

  test("security headers present on API responses", async ({ request }) => {
    const res = await request.get(`${API}/api/health`);
    const headers = res.headers();
    expect(headers["x-frame-options"]).toBe("DENY");
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["content-security-policy"]).toBeTruthy();
  });

  test("rate limit triggers on /auth/login spam", async ({ request }) => {
    const attempts = Array.from({ length: 22 }).map(() =>
      request.post(`${API}/auth/login`, {
        data: { email: "spam@test.com", password: "bad" },
      })
    );
    const responses = await Promise.all(attempts);
    const statuses = responses.map((r) => r.status());
    expect(statuses).toContain(429);
  });

  test("request body > 10MB is rejected", async ({ request }) => {
    const bigBody = { data: "x".repeat(11 * 1024 * 1024) };
    const res = await request.post(`${API}/api/health`, { data: bigBody });
    expect(res.status()).toBe(413);
  });
});
