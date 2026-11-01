// The editor's pure part against the API's own document (fixtures/methodology.json): every
// field the object map's preset declares is editable and present in its specification, a value
// keeps its type, a field the base lacks is never invented, and the domain's problems land on
// the field they name.
import { describe, expect, it } from "vitest";

import type { MethodModuleDetail } from "./api";
import fixture from "./fixtures/methodology.json";
import {
  boundUnder,
  boundWords,
  changedPaths,
  editableSteps,
  fromInput,
  outsideBound,
  problemsFor,
  readPath,
  toInput,
  unplacedProblems,
  withPath,
} from "./methodology-edit";

type Doc = { details: Record<string, Record<string, MethodModuleDetail>>; presets: Record<string, Record<string, Record<string, unknown>>> };
const doc = fixture as unknown as Doc;
const detail = doc.details.sociomap["aia-sociomap-3"];
const spec = doc.presets.sociomap["aia-sociomap-3"];

describe("the fields an edit offers", () => {
  it("are every specification value the preset has, each one present in its specification", () => {
    const fields = editableSteps(detail).flatMap((s) => s.fields.map((f) => f.reference));
    expect(fields).toContain("relation.n_min");
    expect(fields).toContain("terrain.sigma");
    expect(new Set(fields).size).toBe(fields.length);
    for (const ref of fields) expect(readPath(spec, ref), ref).not.toBeUndefined();
  });

  it("include each formula slot in its step, and leave out a step with neither", () => {
    const steps = editableSteps(detail);
    expect(steps.flatMap((s) => s.step.formulas.map((f) => f.slot_id))).toContain("f12.kernel");
    expect(steps.every((s) => s.fields.length > 0 || s.step.formulas.length > 0)).toBe(true);
    expect(steps.length).toBeLessThan(detail.step_details.length);
  });

  it("do not offer a part the other preset omits", () => {
    const other = editableSteps(doc.details.sociomap["aia-sociomap-2"]).flatMap((s) => s.fields.map((f) => f.reference));
    const omitted = doc.details.sociomap["aia-sociomap-2"].step_details.flatMap((s) => s.values).filter((v) => v.absent).map((v) => v.reference);
    expect(omitted.length).toBeGreaterThan(0);
    for (const ref of omitted) expect(other).not.toContain(ref);
  });
});

describe("a value typed in", () => {
  it("keeps its type, a number taking a Czech decimal comma", () => {
    expect(fromInput(0.25, "0,3")).toEqual({ ok: true, value: 0.3 });
    expect(fromInput(30, " 40 ")).toEqual({ ok: true, value: 40 });
    expect(fromInput(30, "čtyřicet")).toEqual({ ok: false, reason: "number" });
    expect(fromInput(30, "")).toEqual({ ok: false, reason: "number" });
    expect(fromInput(50, "null")).toEqual({ ok: true, value: null }); // a line no longer checked
    expect(fromInput("kish_effective_n", "40")).toEqual({ ok: true, value: "40" });
    expect(fromInput(true, "false")).toEqual({ ok: true, value: false });
    expect(fromInput(true, "ne")).toEqual({ ok: false, reason: "boolean" });
    expect(fromInput([0.025, 0.975], "[0.05, 0.95]")).toEqual({ ok: true, value: [0.05, 0.95] });
    expect(fromInput({ a: 1 }, "{a: 1}")).toEqual({ ok: false, reason: "json" });
    expect(fromInput(null, "null")).toEqual({ ok: true, value: null });
  });

  it("round-trips every value of the preset unchanged", () => {
    for (const { fields } of editableSteps(detail)) {
      for (const f of fields) {
        const original = readPath(spec, f.reference);
        expect(fromInput(original, toInput(original)), f.reference).toEqual({ ok: true, value: original });
      }
    }
  });
});

describe("an edited specification", () => {
  it("changes only the field set, and never creates one the base lacks", () => {
    const next = withPath(spec, "terrain.sigma", 0.3);
    expect(readPath(next, "terrain.sigma")).toBe(0.3);
    expect(readPath(spec, "terrain.sigma")).toBe(0.25);
    expect(changedPaths(spec, next)).toEqual(["terrain.sigma"]);
    expect(() => withPath(spec, "terrain.invented", 1)).toThrow();
    expect(() => withPath(spec, "nothing.at_all", 1)).toThrow();
  });

  it("lists nothing when nothing changed", () => {
    expect(changedPaths(spec, structuredClone(spec))).toEqual([]);
  });
});

describe("the domain's problems", () => {
  const problems = {
    "spec.relation.n_min": "must be at least 5",
    "formula.f12.kernel.non_increasing_in:d2": "rises with distance",
    "formula.f12.kernel": "unknown_function: open",
    "base_preset": "no preset aia-sociomap-9",
  };
  it("land on the field or slot they name, a deeper one with its rest", () => {
    expect(problemsFor(problems, "spec.relation.n_min")).toEqual(["must be at least 5"]);
    expect(problemsFor(problems, "formula.f12.kernel")).toEqual(["non_increasing_in:d2: rises with distance", "unknown_function: open"]);
    expect(problemsFor(problems, "spec.relation")).toEqual(["n_min: must be at least 5"]);
    expect(problemsFor(problems, "spec.relation.n")).toEqual([]);
  });
  it("that no field shows are kept, never dropped", () => {
    expect(unplacedProblems(problems, ["spec.relation.n_min", "formula.f12.kernel"])).toEqual([["base_preset", "no preset aia-sociomap-9"]]);
  });
});

describe("a field's bound (settings-redesign F13)", () => {
  const fields = Object.fromEntries(editableSteps(doc.details.sociomap["aia-sociomap-5"]).flatMap((s) => s.fields).map((f) => [f.reference, f]));
  const draft = (values: Record<string, string>) => (path: string) => values[path];

  it("is the API's, read as the tightest limit on each side, and none where no check holds the field", () => {
    expect(boundWords(boundUnder(fields["terrain.grid_resolution"].bound!, draft({})))).toBe("mez 1–256");
    expect(boundWords(boundUnder(fields["terrain.sigma"].bound!, draft({})))).toBe("mez > 0");
    expect(boundWords(boundUnder(fields["terrain.frame_fill"].bound!, draft({})))).toBe("mez > 0 a ≤ 1");
    expect(boundWords(boundUnder(fields["layout.sparse_share"].bound!, draft({})))).toBe("mez ≥ 0 a < 1");
    // A strict limit on a whole number reads as the next whole one: > 3 is ≥ 4.
    expect(boundWords(boundUnder(fields["segments.min_ratings"].bound!, draft({})))).toBe("mez ≥ 4");
    // Held to one value under one preset, a range under another: no bound is declared.
    expect(fields["layout.min_objects"].bound).toBeNull();
    expect(fields["relation.estimator"].bound).toBeNull();
  });

  it("reads a limit from another field's draft value, and leaves out one whose draft is not a number", () => {
    const floor = fields["layout.layout_floor"].bound!;
    expect(boundWords(boundUnder(floor, draft({ "relation.n_min": "10" })))).toBe("mez 1–10");
    expect(boundWords(boundUnder(floor, draft({ "relation.n_min": "12" })))).toBe("mez 1–12");
    expect(boundWords(boundUnder(floor, draft({ "relation.n_min": "dvanáct" })))).toBe("mez ≥ 1");
  });

  it("says a number outside it, never text that is no number (the check's to refuse)", () => {
    const sides = boundUnder(fields["terrain.frame_fill"].bound!, draft({}));
    expect(outsideBound(sides, "0")).toBe(true);
    expect(outsideBound(sides, "0,7")).toBe(false);
    expect(outsideBound(sides, "1")).toBe(false);
    expect(outsideBound(sides, "1,01")).toBe(true);
    expect(outsideBound(sides, "")).toBe(false);
    expect(outsideBound(sides, "hodně")).toBe(false);
    expect(boundWords({ low: null, high: null })).toBe("");
  });
});
