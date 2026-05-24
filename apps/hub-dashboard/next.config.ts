import type { NextConfig } from "next";

const API_URL = process.env.NEXT_PUBLIC_HUB_API_URL ?? "http://localhost:8003";

// Derive WebSocket origin from API URL for CSP connect-src
const wsOrigin = API_URL.replace(/^http/, "ws");
const wssOrigin = API_URL.replace(/^http/, "wss");

// Frontend CSP: Next.js requires unsafe-inline for hydration styles.
// Script-src keeps unsafe-inline because Next.js injects inline scripts at build time.
// For production with nonces, configure generateBuildId + nonce in middleware.ts.
const cspHeader = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  `connect-src 'self' ${API_URL} ${wsOrigin} ${wssOrigin}`,
  "img-src 'self' data: blob:",
  "font-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const securityHeaders = [
  { key: "X-Frame-Options",            value: "DENY" },
  { key: "X-Content-Type-Options",     value: "nosniff" },
  { key: "X-XSS-Protection",           value: "1; mode=block" },
  { key: "Referrer-Policy",            value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy",         value: "geolocation=(), microphone=(), camera=()" },
  { key: "Content-Security-Policy",    value: cspHeader },
];

const nextConfig: NextConfig = {
  output: "standalone",

  experimental: {
    optimizePackageImports: [
      "lucide-react",
      "@radix-ui/react-dialog",
      "@radix-ui/react-progress",
      "@radix-ui/react-scroll-area",
      "@radix-ui/react-select",
      "@radix-ui/react-separator",
      "@radix-ui/react-tabs",
      "@radix-ui/react-tooltip",
    ],
  },

  env: {
    NEXT_PUBLIC_HUB_API_URL: API_URL,
  },

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
