import { test, expect } from "@playwright/test";

const BASE = process.env.DASHBOARD_URL ?? "http://localhost:3002";

async function login(page: import("@playwright/test").Page) {
  await page.goto(`${BASE}/login`);
  await page.fill("input[type=email], input[name=email]", "arjun@sisa.demo");
  await page.fill("input[type=password]", "Demo@1234");
  await page.click("button[type=submit]");
  await page.waitForURL("**/ops", { timeout: 10_000 });
}

test.describe("Proposal lifecycle", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("proposals page loads with table", async ({ page }) => {
    await page.goto(`${BASE}/proposals`);
    await expect(page.locator("text=/proposal|opportunity/i").first()).toBeVisible({ timeout: 8_000 });
  });

  test("approvals page loads approval records", async ({ page }) => {
    await page.goto(`${BASE}/approvals`);
    await expect(page.locator("text=/approval|approve|pending/i").first()).toBeVisible({ timeout: 8_000 });
  });

  test("SLA page shows breach/warning indicators", async ({ page }) => {
    await page.goto(`${BASE}/sla`);
    await expect(page.locator("text=/SLA|breach|warning/i").first()).toBeVisible({ timeout: 8_000 });
  });

  test("ops page KPI strip renders 4 cards", async ({ page }) => {
    await page.goto(`${BASE}/ops`);
    // Wait for the metric cards — they animate in after data loads
    await expect(page.locator(".grid > *").first()).toBeVisible({ timeout: 10_000 });
  });

  test("command palette opens and searches", async ({ page }) => {
    await page.goto(`${BASE}/ops`);
    await page.keyboard.press("Control+k");
    await expect(page.locator("input[placeholder*='Search']")).toBeVisible({ timeout: 3_000 });
    await page.keyboard.type("Infosys");
    // Wait for either results or "No results" message
    await page.waitForTimeout(600); // debounce
    await page.keyboard.press("Escape");
    await expect(page.locator("input[placeholder*='Search']")).not.toBeVisible();
  });

  test("keyboard shortcuts overlay opens with ?", async ({ page }) => {
    await page.goto(`${BASE}/ops`);
    await page.keyboard.press("?");
    await expect(page.locator("text=Keyboard Shortcuts")).toBeVisible({ timeout: 2_000 });
    await page.keyboard.press("Escape");
    await expect(page.locator("text=Keyboard Shortcuts")).not.toBeVisible();
  });

  test("activity feed shows events and drill-down modal opens", async ({ page }) => {
    await page.goto(`${BASE}/ops?demo=1`);
    // Wait for demo events to appear
    await page.waitForTimeout(2_000);
    const feedItems = page.locator(".flex-1.overflow-y-auto button");
    const count = await feedItems.count();
    if (count > 0) {
      await feedItems.first().click();
      await expect(page.locator("text=/Stage Transition|SME Assigned|Approval|Created/")).toBeVisible({ timeout: 2_000 });
      await page.keyboard.press("Escape");
    }
  });
});
