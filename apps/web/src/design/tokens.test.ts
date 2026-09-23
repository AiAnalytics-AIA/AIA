import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { colors } from "./tokens";
import tokensJson from "./tokens.json";

describe("tokens — light and dark are both first-class", () => {
  it("resolves every colour in both themes", () => {
    for (const [name, v] of Object.entries(colors)) {
      expect(v.light, name).toMatch(/^#[0-9a-f]{6}$/);
      expect(v.dark, name).toMatch(/^#[0-9a-f]{6}$/);
    }
    expect(Object.keys(colors)).toHaveLength(tokensJson.color.tokens.length);
  });
  it("gives the dark theme its own surfaces and ink, not an inversion by accident", () => {
    expect(colors.surface.light).not.toBe(colors.surface.dark);
    expect(colors.ink.light).not.toBe(colors.ink.dark);
  });
  it("keeps the report paper light in both themes", () => {
    expect(colors["doc-paper"].light).toBe(colors["doc-paper"].dark);
  });
  it("declares every colour under data-theme=dark and under the system-dark media query", () => {
    const css = readFileSync(join(process.cwd(), "src/app/tokens.css"), "utf8");
    const dark = css.slice(css.indexOf('[data-theme="dark"]'), css.indexOf("@media"));
    const media = css.slice(css.indexOf("@media (prefers-color-scheme: dark)"));
    for (const name of Object.keys(colors)) {
      expect(dark, name).toContain(`--${name}:`);
      expect(media, name).toContain(`--${name}:`);
    }
  });
});
