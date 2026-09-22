import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { FIXTURE_CAPABILITIES, UNAVAILABLE_CAPABILITIES } from "./registry";

/** Every .ts/.tsx source file except tests and the registry itself. */
function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return sources(p);
    return /\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name) && !p.endsWith("registry.ts") ? [p] : [];
  });
}
const code = sources(join(process.cwd(), "src")).map((p) => readFileSync(p, "utf8")).join("\n");
const used = (re: RegExp) => new Set([...code.matchAll(re)].map((m) => m[1]));

describe("capability registry", () => {
  it("lists every fixture capability a screen marks", () => {
    const ids = FIXTURE_CAPABILITIES.map((c) => c.id);
    for (const id of used(/FixtureNotice capability="([^"]+)"/g)) expect(ids).toContain(id);
  });

  it("lists every unavailable capability a screen shows", () => {
    const ids = UNAVAILABLE_CAPABILITIES.map((c) => c.id);
    for (const id of used(/(?:Unavailable id|data-unavailable)="([^"]+)"/g)) expect(ids).toContain(id);
  });

  it("has no stale entries — each one is still shown somewhere", () => {
    const shown = new Set([...used(/FixtureNotice capability="([^"]+)"/g), ...used(/(?:Unavailable id|data-unavailable)="([^"]+)"/g)]);
    for (const c of [...FIXTURE_CAPABILITIES, ...UNAVAILABLE_CAPABILITIES]) expect(shown, c.id).toContain(c.id);
  });

  it("names an owner and, for backend gaps, a register entry", () => {
    for (const c of UNAVAILABLE_CAPABILITIES) expect(c.register, c.id).toMatch(/^OI-\d+$/);
  });
});
