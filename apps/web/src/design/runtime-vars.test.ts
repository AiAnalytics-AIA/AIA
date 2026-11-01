// A colour read at runtime through var(): Tailwind's `@theme inline` emits a --color-* variable only
// when a utility class uses it, so var(--color-…) in an inline style or arbitrary value can resolve to
// nothing (the Metodika cards' art and accents rendered blank or black: settings fidelity gap 2).
// Components read the runtime properties tokens.css always defines (--viz-stage, --hue-blue, --signal…).
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(__dirname, "..");
const files = (dir: string): string[] => readdirSync(dir).flatMap((name) => {
  const path = join(dir, name);
  if (statSync(path).isDirectory()) return name === "node_modules" ? [] : files(path);
  return /\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name) && name !== "tokens.ts" ? [path] : [];
});
const defined = new Set([...readFileSync(join(SRC, "app/tokens.css"), "utf8").matchAll(/^\s*(--[a-z0-9-]+):/gm)].map((m) => m[1]));

describe("colours read at runtime", () => {
  it("never reads a --color-* variable, which Tailwind may not emit", () => {
    const offenders = files(SRC).filter((f) => /var\(--color-/.test(readFileSync(f, "utf8"))).map((f) => f.slice(SRC.length + 1));
    expect(offenders).toEqual([]);
  });

  it("reads only runtime variables tokens.css defines in the Metodika art", () => {
    const art = readFileSync(join(SRC, "components/aia/settings/MethodologyArt.tsx"), "utf8");
    const named = [...art.matchAll(/v\("([a-z0-9-]+)"\)/g)].map((m) => `--${m[1]}`);
    const accents = [...art.matchAll(/"(hue-[a-z]+|border-strong)"/g)].map((m) => `--${m[1]}`);
    const terraces = Array.from({ length: 10 }, (_, i) => `--viz-terrace-${i + 1}`);
    for (const name of [...named, ...accents, ...terraces]) expect(defined.has(name), name).toBe(true);
  });
});
