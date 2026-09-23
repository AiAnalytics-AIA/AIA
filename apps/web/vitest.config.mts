import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// No @vitejs/plugin-react: its current release pulls a different Vite from the
// one Vitest runs on. esbuild's automatic JSX runtime is all the tests need.
export default defineConfig({
  esbuild: { jsx: "automatic" },
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
