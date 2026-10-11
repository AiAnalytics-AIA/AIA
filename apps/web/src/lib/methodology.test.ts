// The Metodika tab's reading of the methodology (ADR 0023): every formula and symbol the API
// serves renders as MathML (a malformed one fails here, not on a page), a value the preset
// omits or declares null is said in words and never shown as 0, a tiny tolerance is not
// rounded away, and the steps sit under their groups in the module's order.
import { describe, expect, it } from "vitest";

import type { MethodModuleDetail, MethodValue } from "./api";
import fixture from "./fixtures/methodology.json";
import { formulaMathML, groupSteps, showNumber, showValue } from "./methodology";

type Document = { modules: { id: string }[]; details: Record<string, Record<string, MethodModuleDetail>> };
const doc = fixture as unknown as Document;
const details = Object.values(doc.details).flatMap((byPreset) => Object.values(byPreset));
const WORDS = { absent: "v této metodice není", none: "žádná (null)", yes: "ano", no: "ne" };
const value = (v: unknown, absent = false): MethodValue => ({
  reference: "x", label_cs: "x", unit: "", origin: "specification", value: v, absent,
});

describe("every formula the API serves", () => {
  const formulas = details.flatMap((d) =>
    d.step_details.flatMap((s) => [
      { where: `${d.id}/${s.id}`, latex: s.formula_latex },
      ...s.symbols.map((y) => ({ where: `${d.id}/${s.id}/${y.latex}`, latex: y.latex })),
      ...s.formulas.flatMap((f) => [
        { where: `${d.id}/${s.id}/${f.slot_id}`, latex: f.latex },
        ...f.variables.map((v) => ({ where: `${d.id}/${s.id}/${f.slot_id}/${v.name}`, latex: v.latex })),
      ]),
    ]),
  );

  it("is in the fixture at all, the editable formulas included", () => {
    expect(doc.modules.map((m) => m.id)).toContain("sociomap");
    expect(formulas.length).toBeGreaterThan(40);
    expect(formulas.filter((f) => f.where.includes("/f12.kernel")).length).toBeGreaterThan(0);
  });

  it.each(formulas)("renders as MathML: $where", ({ latex }) => {
    const mathml = formulaMathML(latex);
    expect(mathml).not.toBeNull();
    expect(mathml).toContain("<math");
    expect(mathml).not.toContain("merror");
  });

  it("never passes markup or a link through (the page inserts Temml's output as HTML)", () => {
    const text = formulaMathML(String.raw`\text{<script>alert(1)</script><img src=x onerror=alert(1)>}`) ?? "";
    expect(text).not.toMatch(/<script|<img/i);
    expect(text).toContain("&lt;script&gt;"); // shown as text, escaped
    expect(formulaMathML(String.raw`\href{javascript:alert(1)}{x}`)).toBeNull(); // trust off: refused
  });

  it("returns null rather than throwing on a malformed formula", () => {
    expect(formulaMathML(String.raw`\frac{1}{`)).toBeNull();
  });
});

describe("values", () => {
  it("say absent and null in words, never 0", () => {
    expect(showValue(value(null, true), WORDS)).toBe("v této metodice není");
    expect(showValue(value(null), WORDS)).toBe("žádná (null)");
    expect(showValue(value(0), WORDS)).toBe("0");
  });

  it("keep a tiny tolerance visible", () => {
    expect(showNumber(1e-12)).toBe("10⁻¹²");
    expect(showNumber(0.0005)).toBe("0,0005");
    expect(showNumber(5e-7)).toBe("5 × 10⁻⁷");
    expect(showNumber(20261007)).toBe("20 261 007".replace(/ /g, " "));
  });

  it("show a constant's tuple of pairs as pairs", () => {
    expect(showValue(value([[0.05, "good"], [0.1, "fair"]]), WORDS)).toBe("(0,05, good), (0,1, fair)");
    expect(showValue(value(false), WORDS)).toBe("ne");
  });

  it("show every value of the map in force as something", () => {
    const sociomap = doc.details.sociomap["aia-sociomap-3"];
    for (const step of sociomap.step_details) for (const v of step.values) expect(showValue(v, WORDS)).not.toBe("");
  });
});

describe("groups", () => {
  it("hold every step of the object map, in the audit's order", () => {
    const sociomap = doc.details.sociomap["aia-sociomap-3"];
    const grouped = groupSteps(sociomap);
    expect(grouped.map((g) => g.group?.id)).toEqual(sociomap.groups.map((g) => g.id));
    expect(grouped.flatMap((g) => g.steps.map((s) => s.id)).sort()).toEqual(sociomap.step_details.map((s) => s.id).sort());
    expect(grouped.find((g) => g.group?.id === "F14")?.steps).toEqual([]);
  });

  it("put a module without groups in one block", () => {
    const flat = { ...doc.details.sociomap["aia-sociomap-3"], groups: [] };
    expect(groupSteps(flat)).toEqual([{ group: null, steps: flat.step_details }]);
  });
});
