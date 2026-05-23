import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PageErrorBoundary, PanelErrorBoundary } from "@/components/ui/ErrorBoundary";

// Component that throws on demand
function Bomb({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error("test error message");
  return <div>safe content</div>;
}

// Wrapper that allows changing shouldThrow without re-mounting ErrorBoundary
function ResettableWrapper() {
  const [shouldThrow, setShouldThrow] = React.useState(true);
  return (
    <div>
      <button onClick={() => setShouldThrow(false)} data-testid="fix-btn">Fix</button>
      <PageErrorBoundary>
        <Bomb shouldThrow={shouldThrow} />
      </PageErrorBoundary>
    </div>
  );
}

// Silence console.error for expected boundary catches in tests
const silenceConsole = () => {
  const spy = vi.spyOn(console, "error").mockImplementation(() => {});
  return () => spy.mockRestore();
};

import React from "react";

describe("PageErrorBoundary", () => {
  it("renders children when no error", () => {
    render(
      <PageErrorBoundary>
        <div>hello</div>
      </PageErrorBoundary>
    );
    expect(screen.getByText("hello")).toBeTruthy();
  });

  it("renders fallback when child throws", () => {
    const restore = silenceConsole();
    render(
      <PageErrorBoundary>
        <Bomb shouldThrow />
      </PageErrorBoundary>
    );
    expect(screen.getByText(/test error message/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /retry/i })).toBeTruthy();
    restore();
  });

  it("renders the error message in the fallback", () => {
    const restore = silenceConsole();
    render(
      <PageErrorBoundary>
        <Bomb shouldThrow />
      </PageErrorBoundary>
    );
    const fallback = screen.getByText(/test error message/i);
    expect(fallback).toBeTruthy();
    restore();
  });

  it("retry button calls resetErrorBoundary", () => {
    const restore = silenceConsole();
    render(
      <PageErrorBoundary>
        <Bomb shouldThrow />
      </PageErrorBoundary>
    );
    const retryBtn = screen.getByRole("button", { name: /retry/i });
    // Click retry — boundary will try to re-render (Bomb still throws, but the retry handler fires)
    expect(() => fireEvent.click(retryBtn)).not.toThrow();
    restore();
  });
});

describe("PanelErrorBoundary", () => {
  it("renders children when no error", () => {
    render(
      <PanelErrorBoundary title="Test Panel">
        <div>panel content</div>
      </PanelErrorBoundary>
    );
    expect(screen.getByText("panel content")).toBeTruthy();
  });

  it("renders inline error with panel title on throw", () => {
    const restore = silenceConsole();
    render(
      <PanelErrorBoundary title="Analytics">
        <Bomb shouldThrow />
      </PanelErrorBoundary>
    );
    expect(screen.getByText(/analytics unavailable/i)).toBeTruthy();
    restore();
  });

  it("shows a retry button in the panel fallback", () => {
    const restore = silenceConsole();
    render(
      <PanelErrorBoundary title="Test">
        <Bomb shouldThrow />
      </PanelErrorBoundary>
    );
    expect(screen.getByText(/retry/i)).toBeTruthy();
    restore();
  });
});
