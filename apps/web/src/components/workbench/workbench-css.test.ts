// The workbench stylesheet must not override a screen's Tailwind utilities on form controls:
// unlayered CSS beats every @layer, so the prototype's element rules live in @layer base
// (a pressed object-map pill's text-[var(--viz-stage)] computed to its own background).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const CSS = readFileSync(join(process.cwd(), "src/components/workbench/workbench.css"), "utf8");

/** The CSS outside every @layer block, braces matched. */
function unlayered(css: string): string {
  let out = "";
  let i = 0;
  while (i < css.length) {
    const at = css.indexOf("@layer", i);
    if (at < 0) return out + css.slice(i);
    out += css.slice(i, at);
    let depth = 0;
    let j = css.indexOf("{", at);
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
});
