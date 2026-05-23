import type { NextConfig } from "next";

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
    NEXT_PUBLIC_HUB_API_URL:
      process.env.NEXT_PUBLIC_HUB_API_URL ?? "http://localhost:8003",
  },
};

export default nextConfig;
