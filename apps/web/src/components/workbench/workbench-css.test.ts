// The workbench stylesheet must not override a screen's Tailwind utilities on form controls:
// unlayered CSS beats every @layer, so the prototype's element rules live in @layer base
// (a pressed object-map pill's text-[var(--viz-stage)] computed to its own background).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const CSS = readFileSync(join(process.cwd(), "src/components/workbench/workbench.css"), "utf8");

/** The CSS outside every @layer block, braces matched; comments dropped first, so an "@layer" in
 * a comment is not taken for a block, and a statement (`@layer a, b;`) opens none. */
function unlayered(source: string): string {
  const css = source.replace(/\/\*[\s\S]*?\*\//g, "");
  let out = "";
  let i = 0;
  while (i < css.length) {
    const at = css.indexOf("@layer", i);
    if (at < 0) return out + css.slice(i);
    out += css.slice(i, at);
    const open = css.indexOf("{", at);
    const end = css.indexOf(";", at);
    if (open < 0 || (end >= 0 && end < open)) {
      i = end < 0 ? css.length : end + 1;
      continue;
    }
    let depth = 0;
    let j = open;
    for (; j < css.length; j++) {
      if (css[j] === "{") depth++;
      else if (css[j] === "}" && --depth === 0) break;
    }
    i = j + 1;
  }
  return out;
}

describe("workbench.css", () => {
  it("sets a form control's colour only inside @layer base, never unlayered", () => {
    expect(CSS).toMatch(/@layer base \{[\s\S]*button, input, textarea, select \{ font: inherit; color: inherit; \}/);
    expect(unlayered(CSS)).not.toMatch(/(^|[\s,{])(button|input|textarea|select)\s*[,{][^}]*color:/);
  });

  it("draws the Lead chat at the product's radii, from the tokens: bubbles and cards 10, the composer 12, chips 6 (UI-3)", () => {
    const radius = (selector: string) => {
      const rule = new RegExp(`(^|\\n)${selector.replace(/[.]/g, "\\.")} \\{[^}]*border-radius: ([^;]+);`).exec(CSS);
      return rule?.[2];
    };
    for (const card of [".bubble", ".act", ".act__row", ".dec", ".ret", ".queue", ".autopilot", ".mention"]) {
      expect(radius(card), card).toBe("var(--radius-panel)");
    }
    expect(radius(".composer")).toBe("var(--radius-composer)");
    for (const chip of [".linkchip", ".srcchip", ".refchip"]) expect(radius(chip), chip).toBe("var(--radius-control)");
    const tokens = readFileSync(join(process.cwd(), "src/app/tokens.css"), "utf8");
    expect(tokens).toContain("--radius-panel: 10px;");
    expect(tokens).toContain("--radius-composer: 12px;");
  });

  it("reads only real @layer blocks as layered: a comment or a statement naming @layer hides no rule", () => {
    const css = "/* rules go in @layer base */\nbutton { color: red; }\n@layer a, b;\ninput { color: blue; }\n@layer base { select { color: green; } }\n.x { margin: 0; }";
    const left = unlayered(css);
    expect(left).toContain("button { color: red; }");
    expect(left).toContain("input { color: blue; }");
    expect(left).not.toContain("select");
    expect(left).toContain(".x { margin: 0; }");
  });
});
