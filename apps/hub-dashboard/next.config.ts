import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_HUB_API_URL: process.env.NEXT_PUBLIC_HUB_API_URL || "http://localhost:8003",
  },
};

export default nextConfig;
