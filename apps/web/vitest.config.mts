import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// Node by default (tokens, the injector, the unit client and its parity tests).
// A component test opts into jsdom with `// @vitest-environment jsdom`.
export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    // The time budgets, sized for a loaded machine (CLAUDE.md §7). The jsdom component
    // tests are CPU-bound (a profile of MethodologyVersions: jsdom, its selector engine and
    // React are ~70 % of the time; Temml under 1 %): its heaviest test takes 2.9 s alone and
    // 9.1 s when the suite shares the host's 4 cores, so vitest's 5 s default failed it under
    // load. 30 s is the size test-native-agents.ts already gives the research steps.
    testTimeout: 30_000,
    // Workers stay at vitest's default (cores - 1, 3 on CI's 4 vCPU): the contention measured
    // came from outside the suite, which fewer workers would not remove.
    // findBy* / waitFor: testing-library's 1 s default, raised in vitest.setup.ts.
    setupFiles: ["./vitest.setup.ts"],
  },
});
