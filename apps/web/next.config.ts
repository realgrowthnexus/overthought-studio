import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

// Supabase project origin (REST, auth, storage signed URLs, realtime websocket). NEXT_PUBLIC_* is fixed at build time.
const sbUrl = (() => {
  try {
    return new URL(process.env.NEXT_PUBLIC_SUPABASE_URL ?? "");
  } catch {
    return null;
  }
})();
const secure = !sbUrl || sbUrl.protocol === "https:";
const sbHttp = sbUrl ? `${sbUrl.protocol}//${sbUrl.host}` : "https://*.supabase.co";
const sbWs = sbUrl ? `${secure ? "wss" : "ws"}://${sbUrl.host}` : "wss://*.supabase.co";
const tiktokImg = "https://*.tiktokcdn.com https://*.tiktokcdn-us.com";

// 'unsafe-inline' scripts are needed for Next's inline bootstrap + next-themes without per-request nonces.
// Everything else is locked to our origin and the Supabase project.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' data: blob: ${sbHttp} ${tiktokImg}`,
  `media-src 'self' blob: ${sbHttp}`,
  "font-src 'self' data:",
  `connect-src 'self' ${sbHttp} ${sbWs}${isDev ? " ws:" : ""}`,
  "frame-src 'none'",
  "frame-ancestors 'none'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "worker-src 'self' blob:",
  "manifest-src 'self'",
].join("; ");

const nextConfig: NextConfig = {
  // Self-contained server bundle for the Docker image on the VPS (`node server.js`); `next start` still works.
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  images: {
    // All remote images (TikTok avatars) are rendered `unoptimized`, so the optimizer never fetches remote hosts:
    // keeps /_next/image from being an unauthenticated image proxy.
    remotePatterns: [],
  },
  experimental: {
    // CSV/XLSX import is capped at 20 MB in lib/actions.ts.
    serverActions: { bodySizeLimit: "21mb" },
    optimizePackageImports: ["lucide-react", "recharts", "motion"],
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()",
          },
        ],
      },
      {
        // OAuth endpoints and auth pages must never be cached by the proxy or the browser.
        source: "/(api|auth|login|setup)/:path*",
        headers: [{ key: "Cache-Control", value: "no-store" }],
      },
    ];
  },
};

export default nextConfig;
