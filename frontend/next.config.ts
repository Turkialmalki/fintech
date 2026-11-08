import type { NextConfig } from "next";

const API_ORIGIN = process.env.API_ORIGIN ?? "http://localhost:8000";
// On Vercel, /api/* is routed to the FastAPI service by vercel.json (Services); no proxying needed here.
const ON_VERCEL = !!process.env.VERCEL;

const nextConfig: NextConfig = {
  ...(ON_VERCEL ? {} : { output: "standalone" as const }),
  poweredByHeader: false,
  reactStrictMode: true,
  // The browser talks to the API through the same origin (no CORS, cookies-free bearer auth).
  async rewrites() {
    return ON_VERCEL ? [] : [{ source: "/api/v1/:path*", destination: `${API_ORIGIN}/api/v1/:path*` }];
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      ],
    }];
  },
};

export default nextConfig;
