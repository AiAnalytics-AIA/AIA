import type { NextConfig } from "next";

/**
 * The demo's "/cases" routes and its "agents"/"templates" pages described a
 * superseded product. They redirect rather than 404, so old links still land.
 * Temporary (307), because nothing outside this repository is known to link here.
 */
const nextConfig: NextConfig = {
  async redirects() {
    return [
      { source: "/org/:orgSlug/cases/:path*", destination: "/org/:orgSlug/dashboard", permanent: false },
      { source: "/org/:orgSlug/agents", destination: "/org/:orgSlug/dashboard", permanent: false },
      { source: "/org/:orgSlug/templates", destination: "/org/:orgSlug/dashboard", permanent: false },
    ];
  },
};

export default nextConfig;
