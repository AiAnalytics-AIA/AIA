// The look contract's primitives (prototypes/LOOK.md, 26 Oct 2026; prototype-build PBA6): the radii
// 6 / 8 / 10 with round kept for what is round by nature, and weights 400, 500 and 600 only.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

import tokensJson from "./tokens.json";

const SRC = join(process.cwd(), "src");

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return files(p);
    return /\.(tsx?|css|mjs)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [p] : [];
  });
}

const radius = (name: string) => tokensJson.radius.tokens.find((t) => t.name === name)?.value;

describe("the look contract's radii", () => {
  it("draws controls and chips at 6, cards at 8, dialogs and menus at 10", () => {
    expect(radius("radius-sm")).toBe("6px");
    expect(radius("radius-control")).toBe("6px");
    expect(radius("radius-md")).toBe("8px");
    expect(radius("radius-card")).toBe("8px");
    expect(radius("radius-panel")).toBe("10px");
    expect(radius("radius-0")).toBe("0px");
  });

  it("keeps round for what is round by nature, and nothing between 10 and round", () => {
    expect(radius("radius-pill")).toBe("999px");
    const px = tokensJson.radius.tokens.map((t) => Number.parseFloat(t.value)).filter((v) => v < 999);
    expect(Math.max(...px)).toBe(10);
  });

  it("generates the theme from the same values", () => {
    const theme = readFileSync(join(SRC, "app/tokens-theme.css"), "utf8");
    expect(theme).toContain("--radius-sm: 6px;");
    expect(theme).toContain("--radius-md: 8px;");
    expect(theme).toContain("--radius-panel: 10px;");
  });
});

describe("the look contract's weights", () => {
  // A heavy weight in any form the source writes one: a Tailwind class, CSS, an inline style or a
  // canvas font string.
  const HEAVY = [
    /\bfont-(bold|extrabold|black)\b/,
    /font-\[(700|800|900)\]/,
    /font-weight:\s*(700|800|900|bold|bolder)\b/,
    /fontWeight:\s*["']?(700|800|900|bold)\b/,
    /["'`](700|800|900|bold) \d+(\.\d+)?px /,
  ];

  it("uses no weight above 600 anywhere in apps/web/src", () => {
    const found: string[] = [];
    for (const f of files(SRC)) {
      if (f.endsWith("fonts.css")) continue; // @font-face declarations name the faces that exist, not a use
      // The Sociomap panel's canvas is a port of the approved object map's own drawing, pinned frame
      // for frame by object-map-panel.test.ts (draw66); its label weights change with that design.
      if (f.endsWith("lib/object-map-panel.ts")) continue;
      readFileSync(f, "utf8").split("\n").forEach((line, i) => {
        if (HEAVY.some((re) => re.test(line))) found.push(`${relative(SRC, f)}:${i + 1}`);
      });
    }
    expect(found).toEqual([]);
  });

  it("brings the browser's own bold (b, strong, th) down to the contract's weights", () => {
    const css = readFileSync(join(SRC, "app/globals.css"), "utf8");
    expect(css).toMatch(/b,\s*strong\s*{\s*font-weight:\s*600;/);
    expect(css).toMatch(/\bth\s*{\s*font-weight:\s*500;/);
  });

  it("sets a table header on the sunken surface", () => {
    const css = readFileSync(join(SRC, "app/globals.css"), "utf8");
    expect(css).toMatch(/thead th\s*{\s*background-color:\s*var\(--surface-sunken\);/);
  });
});
