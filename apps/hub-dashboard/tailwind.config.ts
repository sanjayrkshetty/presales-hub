import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary:   "#0a0b0d",
          secondary: "#111318",
          tertiary:  "#161a21",
        },
        border: {
          DEFAULT: "#1e2128",
          subtle:  "#262b35",
        },
        accent: {
          DEFAULT:  "#00d4aa",
          dim:      "#00d4aa22",
          hover:    "#00f0c0",
        },
        warn: "#f59e0b",
        danger: "#ef4444",
        success: "#22c55e",
        muted: "#64748b",
        text: {
          primary:   "#e2e8f0",
          secondary: "#94a3b8",
          muted:     "#64748b",
        },
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "Consolas", "monospace"],
      },
      borderRadius: {
        sm: "3px",
        DEFAULT: "4px",
        md: "6px",
        lg: "8px",
      },
    },
  },
  plugins: [],
};

export default config;
