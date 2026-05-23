import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiFetch } from "@/lib/api/client";
import { ApiError, isApiError } from "@/lib/errors";

function mockFetch(status: number, body: string | object) {
  return vi.fn().mockResolvedValue({
    ok:         status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json:       () => Promise.resolve(typeof body === "string" ? JSON.parse(body) : body),
    text:       () => Promise.resolve(typeof body === "string" ? body : JSON.stringify(body)),
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch(200, { ok: true }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiFetch", () => {
  it("returns parsed JSON on 2xx", async () => {
    vi.stubGlobal("fetch", mockFetch(200, { id: "123", name: "test" }));
    const result = await apiFetch<{ id: string; name: string }>("/api/test");
    expect(result.id).toBe("123");
    expect(result.name).toBe("test");
  });

  it("throws ApiError on 4xx", async () => {
    vi.stubGlobal("fetch", mockFetch(404, "Not Found"));
    await expect(apiFetch("/api/missing")).rejects.toThrow(ApiError);
    await expect(apiFetch("/api/missing")).rejects.toMatchObject({ status: 404 });
  });

  it("throws ApiError on 500", async () => {
    vi.stubGlobal("fetch", mockFetch(500, "Internal Server Error"));
    await expect(apiFetch("/api/broken")).rejects.toThrow(ApiError);
    await expect(apiFetch("/api/broken")).rejects.toMatchObject({ status: 500 });
  });

  it("throws ApiError on 401", async () => {
    vi.stubGlobal("fetch", mockFetch(401, "Unauthorized"));
    try {
      await apiFetch("/api/auth");
    } catch (e) {
      expect(isApiError(e)).toBe(true);
      if (isApiError(e)) {
        expect(e.isUnauthorized).toBe(true);
        expect(e.isClientError).toBe(true);
        expect(e.isServerError).toBe(false);
      }
    }
  });

  it("builds query params into the URL", async () => {
    let capturedUrl = "";
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
      capturedUrl = url;
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) });
    }));
    await apiFetch("/api/test", { params: { tenant_id: "t1", limit: 10, active: true } });
    expect(capturedUrl).toContain("tenant_id=t1");
    expect(capturedUrl).toContain("limit=10");
    expect(capturedUrl).toContain("active=true");
  });

  it("skips undefined params", async () => {
    let capturedUrl = "";
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
      capturedUrl = url;
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) });
    }));
    await apiFetch("/api/test", { params: { id: "x", filter: undefined } });
    expect(capturedUrl).toContain("id=x");
    expect(capturedUrl).not.toContain("filter");
  });
});

describe("ApiError", () => {
  it("has correct error classification", () => {
    expect(new ApiError(400, "Bad Request", "/api").isClientError).toBe(true);
    expect(new ApiError(500, "Server Error", "/api").isServerError).toBe(true);
    expect(new ApiError(401, "Unauthorized", "/api").isUnauthorized).toBe(true);
    expect(new ApiError(403, "Forbidden", "/api").isForbidden).toBe(true);
    expect(new ApiError(404, "Not Found", "/api").isNotFound).toBe(true);
  });

  it("isApiError type guard works", () => {
    expect(isApiError(new ApiError(400, "", "/api"))).toBe(true);
    expect(isApiError(new Error("generic"))).toBe(false);
    expect(isApiError(null)).toBe(false);
    expect(isApiError("string")).toBe(false);
  });

  it("name is ApiError", () => {
    expect(new ApiError(500, "error", "/api").name).toBe("ApiError");
  });
});
