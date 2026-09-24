import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output traces the server's imports into .next/standalone so the
  // production image (apps/web/Dockerfile) ships the server and only the modules
  // it needs, not the whole node_modules tree. `next dev` is unaffected.
  output: "standalone",
  // Root the trace at this package. Without it, Next detects the repository's
  // root package-lock.json, treats the monorepo as the workspace, and emits
  // .next/standalone/apps/web/server.js -- a layout that differs between a
  // checkout (repository root present) and the image (apps/web alone).
  outputFileTracingRoot: path.join(__dirname),
  // `next dev` only: the rebuilt interface's rail keeps its footer link at the
  // bottom left, where the indicator would sit on top of it.
  devIndicators: { position: "bottom-right" },
};

export default nextConfig;
