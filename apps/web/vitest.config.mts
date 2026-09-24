import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// Node by default (tokens, the injector, the unit client and its parity tests).
// A component test opts into jsdom with `// @vitest-environment jsdom`.
export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
