/**
 * Auth setup — runs once before the E2E suite.
 * Logs in with demo credentials and saves the cookie state so
 * subsequent tests start authenticated.
 */
import { test as setup, expect } from "@playwright/test";
import path from "path";
import fs from "fs";

const AUTH_FILE = path.join(__dirname, ".auth", "user.json");
const BASE_URL  = process.env.E2E_BASE_URL ?? "http://localhost:3002";
const API_URL   = process.env.E2E_API_URL  ?? "http://localhost:8003";

setup("authenticate", async ({ page, request }) => {
  // Call the API login endpoint directly to get the refresh cookie
  const resp = await request.post(`${API_URL}/auth/login`, {
    data: {
      email:    process.env.E2E_EMAIL    ?? "arjun@sisa.demo",
      password: process.env.E2E_PASSWORD ?? "Demo@1234",
    },
  });

  expect(resp.ok()).toBeTruthy();

  // Navigate to dashboard — SessionProvider will pick up the refresh cookie
  await page.goto(`${BASE_URL}/?demo=1`);
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 10_000 });

  // Save storage state (cookies + localStorage)
  const dir = path.dirname(AUTH_FILE);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  await page.context().storageState({ path: AUTH_FILE });
});
