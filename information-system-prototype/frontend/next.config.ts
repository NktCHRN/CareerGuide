import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Self-contained server output for a small production Docker image.
  output: "standalone",
  // Presigned photo / resume URLs point at the MinIO endpoint and rotate, so we
  // serve them with a plain <img> instead of next/image to avoid remotePatterns
  // churn. No image domains need to be whitelisted here.
  eslint: {
    // Lint is run explicitly via `npm run lint`; do not block production builds
    // of this prototype on style warnings.
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
