import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment:  "happy-dom",
    globals:      true,
    setupFiles:   ["./tests/setup.ts"],
    include:      ["tests/unit/**/*.{test,spec}.{ts,tsx}"],
    exclude:      ["tests/e2e/**"],
    coverage: {
      provider:   "v8",
      reporter:   ["text", "lcov"],
      include:    ["lib/**", "components/**", "providers/**"],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
