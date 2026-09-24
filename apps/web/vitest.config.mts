import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// Pure-function tests only (tokens, the interface injector). jsdom and Testing
// Library arrive with the first re-homed component, not before they are needed.
export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
