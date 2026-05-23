import { describe, it, expect } from "vitest";
import { ApiError, isApiError } from "@/lib/errors";

// Mirrors the retry predicate in QueryProvider — test the logic directly
function shouldRetry(failureCount: number, error: unknown): boolean {
  if (isApiError(error) && error.isClientError) return false;
  return failureCount < 2;
}

describe("QueryClient retry policy", () => {
  it("does not retry 4xx errors", () => {
    const err = new ApiError(400, "Bad Request", "/api");
    expect(shouldRetry(0, err)).toBe(false);
    expect(shouldRetry(1, err)).toBe(false);
  });

  it("does not retry 401", () => {
    expect(shouldRetry(0, new ApiError(401, "Unauthorized", "/api"))).toBe(false);
  });

  it("does not retry 404", () => {
    expect(shouldRetry(0, new ApiError(404, "Not Found", "/api"))).toBe(false);
  });

  it("retries 5xx up to 2 times", () => {
    const err = new ApiError(500, "Internal Server Error", "/api");
    expect(shouldRetry(0, err)).toBe(true);
    expect(shouldRetry(1, err)).toBe(true);
    expect(shouldRetry(2, err)).toBe(false);
  });

  it("retries network errors (non-ApiError) up to 2 times", () => {
    const networkErr = new Error("Network failure");
    expect(shouldRetry(0, networkErr)).toBe(true);
    expect(shouldRetry(1, networkErr)).toBe(true);
    expect(shouldRetry(2, networkErr)).toBe(false);
  });
});
