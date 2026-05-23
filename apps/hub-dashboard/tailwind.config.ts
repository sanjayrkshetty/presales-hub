import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
    "./providers/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary:   "#08090b",
          secondary: "#0f1117",
          tertiary:  "#151820",
          elevated:  "#1a1e2a",
        },
        border: {
          DEFAULT: "#1e2330",
          subtle:  "#252a38",
        },
        accent: {
          DEFAULT:  "#00d4aa",
          dim:      "#00d4aa18",
          muted:    "#00d4aa66",
          hover:    "#00f0c0",
        },
        blue:    "#3b82f6",
        purple:  "#8b5cf6",
        warn:    "#f59e0b",
        danger:  "#ef4444",
        success: "#22c55e",
        muted:   "#64748b",
        text: {
          primary:   "#e2e8f0",
          secondary: "#94a3b8",
          muted:     "#64748b",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "'JetBrains Mono'", "Consolas", "monospace"],
      },
      fontSize: {
        "2xs": ["10px", { lineHeight: "14px", letterSpacing: "0.06em" }],
        xs:   ["11px", { lineHeight: "16px" }],
        sm:   ["12px", { lineHeight: "18px" }],
        base: ["13px", { lineHeight: "20px" }],
        md:   ["14px", { lineHeight: "20px" }],
        lg:   ["16px", { lineHeight: "24px" }],
        xl:   ["18px", { lineHeight: "28px" }],
        "2xl":["22px", { lineHeight: "32px" }],
        "3xl":["28px", { lineHeight: "36px" }],
      },
      borderRadius: {
        sm:      "2px",
        DEFAULT: "4px",
        md:      "6px",
        lg:      "8px",
        xl:      "12px",
      },
      boxShadow: {
        panel:    "0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(30,35,48,0.8)",
        "panel-lg": "0 4px 16px rgba(0,0,0,0.6), 0 0 0 1px rgba(30,35,48,0.8)",
        accent:   "0 0 12px rgba(0,212,170,0.15)",
      },
      keyframes: {
        pulse_dot: {
          "0%, 100%": { opacity: "1" },
          "50%":      { opacity: "0.4" },
        },
        slide_in: {
          from: { transform: "translateX(100%)", opacity: "0" },
          to:   { transform: "translateX(0)",    opacity: "1" },
        },
        fade_in: {
          from: { opacity: "0", transform: "translateY(4px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        pulse_dot: "pulse_dot 1.8s ease-in-out infinite",
        slide_in:  "slide_in 0.2s ease-out",
        fade_in:   "fade_in 0.15s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
