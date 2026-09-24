import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { lintComponents } from "../../scripts/skin-lint.mjs";
import tokens from "../design/tokens.json";
import mapping from "./legacy-variables.json";

const legacy = readFileSync(join(process.cwd(), "../../legacy/npc-panel-18.6.6/app/ui_app.html"), "utf8");
const skin = readFileSync(join(process.cwd(), "public/skin/skin.css"), "utf8");
const components = readFileSync(join(process.cwd(), "src/skin/components.css"), "utf8");

describe("the variable layer accounts for every 18.6.6 variable", () => {
  const used = new Set([...legacy.matchAll(/var\((--[\w-]+)/g)].map((m) => m[1]));
  const defined = new Set([...legacy.matchAll(/(?<![\w-])(--[A-Za-z][\w-]*)\s*:/g)].map((m) => m[1]));
  const mapped = new Set(mapping.map.map((m) => m.var));
  const left = new Set(mapping.left.map((m) => m.var));

  it("maps or deliberately leaves each one, with a reason", () => {
    for (const v of new Set([...used, ...defined])) expect(mapped.has(v) || left.has(v), v).toBe(true);
    for (const e of [...mapping.map, ...mapping.left]) expect(e.why, e.var).toBeTruthy();
  });

  it("never maps and leaves the same variable", () => {
    for (const v of mapped) expect(left.has(v), v).toBe(false);
  });

  it("maps colours only to tokens that exist", () => {
    const names = new Set(tokens.color.tokens.map((t) => t.name));
    for (const m of mapping.map) if ("token" in m && m.token) expect(names.has(m.token), `${m.var} → ${m.token}`).toBe(true);
  });

  it("never uses the solid parked-on-you fill: that needs the viewer-actionability contract (OI-11)", () => {
    for (const m of mapping.map) expect("token" in m ? m.token : undefined, m.var).not.toBe("status-you");
  });
});

describe("skin.css", () => {
  it("declares each mapped 18.6.6 variable after the tokens", () => {
    const tokensAt = skin.indexOf("--aia-surface:");
    for (const m of mapping.map) {
      const at = skin.indexOf(`  ${m.var}: `);
      expect(at, m.var).toBeGreaterThan(tokensAt);
    }
  });

  it("prefixes every token, so it never collides with 18.6.6's own --ink or --space-*", () => {
    for (const t of tokens.color.tokens) expect(skin).toContain(`--aia-${t.name}:`);
    expect(skin).not.toMatch(/^\s+--ink:\s*#/m);
  });

  it("is light only, as 18.6.6 is", () => {
    expect(skin).toContain("color-scheme: light;");
    expect(skin).not.toContain("prefers-color-scheme");
  });

  it("loads the self-hosted faces from /skin/fonts/ and nothing from a CDN", () => {
    expect(skin).toContain('url("/skin/fonts/IBMPlexSans-Regular.woff2")');
    expect(skin).not.toMatch(/https?:\/\//);
  });
});

describe("lintComponents", () => {
  it("passes the committed component layer", () => {
    expect(lintComponents(components)).toEqual([]);
  });

  it.each([
    [".a { color: #fff; }", "hex"],
    [".a { background: rgba(0,0,0,.1); }", "colour function"],
    [".a { border-color: color-mix(in srgb, red, blue); }", "colour function"],
    [".a {\n  border-radius: 6px;\n}", "border-radius"],
    [".a {\n  font-family: Inter, sans-serif;\n}", "font-family"],
    [".a {\n  box-shadow: 0 1px 2px black;\n}", "box-shadow"],
  ])("refuses %s", (css, what) => {
    expect(lintComponents(css).join(" ")).toContain(what);
  });

  it("accepts tokens and the few literal forms that carry no visual decision", () => {
    const css = [
      ".a {",
      "  color: var(--aia-ink);",
      "  border-radius: 50%;",
      "  box-shadow: none;",
      "  font-family: inherit;",
      "  padding: 8px 12px;",
      "}",
      "/* #abcdef in a comment is fine */",
    ].join("\n");
    expect(lintComponents(css)).toEqual([]);
  });
});
