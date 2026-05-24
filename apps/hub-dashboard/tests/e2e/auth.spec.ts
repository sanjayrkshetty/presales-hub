import { test, expect } from "@playwright/test";

const BASE = process.env.DASHBOARD_URL ?? "http://localhost:3002";
const API  = process.env.API_URL        ?? "http://localhost:8003";

test.describe("Authentication flow", () => {
  test("login page renders and accepts credentials", async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await expect(page.locator("input[type=email], input[name=email]")).toBeVisible();
    await expect(page.locator("input[type=password]")).toBeVisible();
  });

  test("invalid credentials shows error", async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.fill("input[type=email], input[name=email]", "wrong@sisa.demo");
    await page.fill("input[type=password]", "BadPassword!");
    await page.click("button[type=submit]");
    await expect(page.locator("text=/invalid|credentials|error/i")).toBeVisible({ timeout: 5000 });
  });

  test("valid login redirects to dashboard", async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.fill("input[type=email], input[name=email]", "arjun@sisa.demo");
    await page.fill("input[type=password]", "Demo@1234");
    await page.click("button[type=submit]");
    await page.waitForURL("**/ops", { timeout: 10_000 });
    await expect(page).toHaveURL(/\/ops/);
  });

  test("logout clears session and returns to login", async ({ page }) => {
    await page.goto(`${BASE}/login`);
    await page.fill("input[type=email], input[name=email]", "arjun@sisa.demo");
    await page.fill("input[type=password]", "Demo@1234");
    await page.click("button[type=submit]");
    await page.waitForURL("**/ops", { timeout: 10_000 });

    // Open profile menu and click sign out
    const profileBtn = page.locator("button[title]").filter({ hasText: /[A-Z]{1,2}/ }).last();
    await profileBtn.click();
    await page.click("text=Sign out");
    await page.waitForURL("**/login", { timeout: 5_000 });
  });

  test("protected route without auth redirects to login", async ({ page }) => {
    await page.context().clearCookies();
    await page.goto(`${BASE}/ops`);
    await expect(page).toHaveURL(/\/login/, { timeout: 8_000 });
  });
});
