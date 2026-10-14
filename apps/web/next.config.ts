import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  transpilePackages: ["@ledgic/db-types"],
  experimental: {
    optimizePackageImports: ["lucide-react"],
  },
};

export default nextConfig;
