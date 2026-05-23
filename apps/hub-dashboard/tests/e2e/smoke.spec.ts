/**
 * Smoke tests — verify the critical user flows don't break.
 * These run against the full stack (make up-build first).
 */
import { test, expect } from "@playwright/test";

// ── Login smoke ───────────────────────────────────────────────────────────────
test("dashboard loads after auth", async ({ page }) => {
  await page.goto("/ops");
  await expect(page.locator("text=Operations Console")).toBeVisible({ timeout: 10_000 });
});

// ── Navigation ────────────────────────────────────────────────────────────────
test("can navigate to all main sections", async ({ page }) => {
  const routes = [
    { path: "/proposals",    text: "Proposals" },
    { path: "/approvals",    text: "Approval Center" },
    { path: "/sla",          text: "SLA Command Center" },
    { path: "/analytics",    text: "Analytics" },
    { path: "/stakeholders", text: "Stakeholders" },
    { path: "/intelligence", text: "Intelligence Cockpit" },
  ];
  for (const { path, text } of routes) {
    await page.goto(path);
    await expect(page.getByText(text)).toBeVisible({ timeout: 8_000 });
  }
});

// ── Command palette ───────────────────────────────────────────────────────────
test("command palette opens with keyboard shortcut", async ({ page }) => {
  await page.goto("/ops");
  await page.keyboard.press("Control+k");
  await expect(page.locator("[role=dialog]")).toBeVisible({ timeout: 3_000 });
  await page.keyboard.press("Escape");
  await expect(page.locator("[role=dialog]")).not.toBeVisible();
});

// ── Notification bell ─────────────────────────────────────────────────────────
test("notification panel opens on bell click", async ({ page }) => {
  await page.goto("/ops?demo=1");
  // Wait for demo notifications to inject
  await page.waitForTimeout(500);
  await page.locator('button[title="Notifications"]').click();
  await expect(page.getByText("Notifications")).toBeVisible({ timeout: 3_000 });
});

// ── Realtime indicator ────────────────────────────────────────────────────────
test("realtime indicator is visible in the header", async ({ page }) => {
  await page.goto("/ops");
  // Realtime indicator shows some connection state text
  const indicator = page.locator(".realtime-indicator, [data-testid=realtime], text=/Live|Offline|Reconnecting/");
  await expect(indicator.first()).toBeVisible({ timeout: 5_000 });
});

// ── Health page ───────────────────────────────────────────────────────────────
test("health page shows system status", async ({ page }) => {
  await page.goto("/health");
  await expect(page.getByText("System Health")).toBeVisible({ timeout: 5_000 });
  await expect(page.getByText("Hub API")).toBeVisible();
});
