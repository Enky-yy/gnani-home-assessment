/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Same-origin via nginx in compose; local dev uses http://localhost:8000.
  async rewrites() {
    const backend = process.env.BACKEND_INTERNAL_URL || "http://localhost:8000";
    // Only used with `next dev` / `next start` directly (not behind nginx).
    // In compose, the browser hits same-origin /api/* via nginx.
    if (process.env.NEXT_PUBLIC_USE_REWRITE === "1") {
      return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
    }
    return [];
  },
};

export default nextConfig;
