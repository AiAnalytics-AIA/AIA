// The live audience functions (panel-grounded-respondents 6e): AIA's catalogue, subpanels and
// preview as the step reads them, and the range filter that no longer stores OI-50's 0.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import type { AudienceCatalogue, AudiencePreview } from "@/lib/api";

import { applyPopulationSubpanel, factorRefusal, filterableFactors, liveCatalog, liveSubpanels, liveVerdict, setAudienceRange, setRange, filterCountLines, type Catalog, filterProblems, CATALOGUE_TOP_VALUES, matchingSubpanels } from "./audience";
import type { ResearchProject } from "./model";

const project = (audience: Record<string, unknown> = {}) => ({ audience, briefing: {}, ui_state: {} }) as unknown as ResearchProject;

export const CATALOGUE: AudienceCatalogue = {
  version_id: "DSV-1",
  version_label: "v17_4_0",
  catalogue_version: "aia-audience-catalogue-1",
  categories: [
    { id: "demography", label: "Demografie a životní fáze", description: "", count: 3, filterable_count: 3 },
    { id: "research_only", label: "Research-only / citlivé", description: "", count: 2, filterable_count: 0 },
  ],
  factors: [
    { id: "vek", column: "vek", label: "Věk", category: "demography", category_label: "Demografie a životní fáze", kind: "numeric", status: "PANEL_EXISTING", filterable: true, sensitive: false, source: "Panel v17", non_null: 100, min: 18, max: 89, p10: 22, p90: 80, policy_allowed: true, policy_reason: "allowed" },
    { id: "kraj", column: "kraj", label: "Kraj", category: "demography", category_label: "Demografie a životní fáze", kind: "category", status: "PANEL_EXISTING", filterable: true, sensitive: false, source: "Panel v17", non_null: 100, values: [{ value: "Hlavní město Praha", count: 60 }, { value: "Zlínský kraj", count: 40 }], policy_allowed: true, policy_reason: "allowed" },
    { id: "life_stage_derived", column: "life_stage_derived", label: "Životní fáze", category: "demography", category_label: "Demografie a životní fáze", kind: "category", status: "DERIVED_EXISTING_SIGNALS", filterable: true, sensitive: false, source: "Deterministický overlay", non_null: 100, values: [{ value: "Rodič", count: 30 }], policy_allowed: false, policy_reason: "unclassified_derived_field" },
  ],
  filterable_count: 3,
  factor_count: 5,
  logic: "OR uvnitř jedné dimenze, AND mezi dimenzemi",
  subpanels: [
    { key: "young_18_29", name: "Mladí 18–29", description: "Vestavěný pohled: Mladí 18–29.", filters: { vek: [18, 29] }, status: "ready", support_tier: "ROBUST", measured_by_18_6_6: { rows: 2785, weighted_population: 1.2, unique_core_donors: 900, effective_core_donors: 687.4, max_core_reuse: 8 }, usable: true, reason: null },
    { key: "students", name: "Studenti", description: "Studenti.", filters: { is_student: 1 }, status: "ready", support_tier: "GOOD", measured_by_18_6_6: { rows: 869, weighted_population: 0.4, unique_core_donors: 300, effective_core_donors: 240.1, max_core_reuse: 5 }, usable: false, reason: "audit_only" },
  ],
  subpanels_measured_on: "17.1.2",
  subpanel_note: "",
};

describe("AIA's catalogue", () => {
  it("is the factor editor's catalogue, a policy-refused factor listed and said", () => {
    const cat = liveCatalog(CATALOGUE);
    const { shown, total } = filterableFactors(cat, "demography", "");
    expect(total).toBe(3);
    expect(shown.map((f) => f.id)).toEqual(["vek", "kraj", "life_stage_derived"]);
    expect(factorRefusal(shown[0]!)).toBeNull();
    expect(factorRefusal(shown[2]!)).toContain("unclassified_derived_field");
    expect(shown[1]!.values).toEqual([{ value: "Hlavní město Praha", count: 60 }, { value: "Zlínský kraj", count: 40 }]);
  });

  it("gives a subpanel its filter and 18.6.6's counts, and choosing one sets exactly that filter", () => {
    const sub = liveSubpanels(CATALOGUE);
    const next = applyPopulationSubpanel(project({ filters: { kraj: ["Zlínský kraj"] } }), "young_18_29", sub);
    expect(next.audience).toMatchObject({ builtin_subpanel: "young_18_29", source_mode: "population", strategy: "filters", filters: { vek: [18, 29] } });
    expect((next.audience as Record<string, unknown>).support_summary).toMatchObject({ rows: 2785, unique_core_donors: 900 });
  });
});

describe("the range filter (OI-50 does not carry over)", () => {
  it("leaves an empty bound out, where the classic stored 0", () => {
    expect(setRange(project(), "vek", "25", "").project.audience.filters).toEqual({ vek: { min: 25 } });
    expect(setRange(project(), "vek", "", "40").project.audience.filters).toEqual({ vek: { max: 40 } });
    expect(setRange(project({ filters: { vek: { min: 1 } } }), "vek", " ", "").project.audience.filters).toEqual({});
    // The classic's, kept for parity: an empty bound becomes 0.
    expect(setAudienceRange(project(), "vek", "25", "").project.audience.filters).toEqual({ vek: { min: 25, max: 0 } });
  });
});

const PREVIEW: AudiencePreview = {
  version_id: "DSV-1",
  version_label: "v17_4_0",
  population_rows: 18766,
  selected_rows: 5120,
  selected_donors: 1400,
  filters_applied: { vek: { min: 30, max: 59 } },
  per_filter: { vek: 5120 },
  audience: { ok: true },
  n: 500,
  sample: { ok: true, status: "PASS", sample_donors: 380, effective_n: 470.2 },
  seed: 20261012,
};

describe("stored filters the population cannot honour (Findings F3)", () => {
  const cat = (factors = CATALOGUE.factors) => liveCatalog({ ...CATALOGUE, factors });
  const problems = (filters: Record<string, unknown>, factors = CATALOGUE.factors) => filterProblems(project({ filters }), cat(factors));

  it("names values a complete value list lacks, and whether any is left", () => {
    expect(problems({ kraj: ["Zlínský kraj", "Fiktivní kraj A"], vek: { min: 30 } })).toEqual([
      { id: "kraj", label: "Kraj", reason: "values", unknownValues: ["Fiktivní kraj A"], noneKnown: false },
    ]);
    expect(problems({ kraj: "Fiktivní kraj A" })[0]).toMatchObject({ reason: "values", noneKnown: true }); // a scalar is one value, as on the server
  });

  it("names a filter refused whole: a factor not offered, one the policy refuses, one with no value", () => {
    expect(problems({ prijem: ["Nad 60 000 Kč"] })).toEqual([{ id: "prijem", label: "prijem", reason: "factor", unknownValues: [], noneKnown: false }]);
    expect(problems({ life_stage_derived: ["Rodič"] })[0]).toMatchObject({ reason: "policy" }); // policy_allowed false
    expect(problems({ kraj: [] })[0]).toMatchObject({ reason: "empty" });
    expect(problems({ kraj: [null] })[0]).toMatchObject({ reason: "empty" });
  });

  it("holds a numeric filter to the server's interval rule, case by shared case (_interval)", () => {
    // packages/aia_core/tests/test_audience_interval_cases.py holds _interval to the same file.
    const { cases } = JSON.parse(readFileSync(join(process.cwd(), "../../packages/aia_core/tests/fixtures/audience_interval/cases.json"), "utf8")) as { cases: { value: unknown; refused: boolean }[] };
    expect(cases.length).toBeGreaterThan(10);
    for (const { value, refused } of cases) {
      expect(problems({ vek: value }), JSON.stringify(value)).toEqual(refused ? [{ id: "vek", label: "Věk", reason: "range", unknownValues: [], noneKnown: false }] : []);
    }
  });

  it("says nothing it cannot prove: a cut value list, a number, a boolean, no catalogue", () => {
    const cut = CATALOGUE.factors.map((f) => (f.id === "kraj" ? { ...f, values: Array.from({ length: CATALOGUE_TOP_VALUES }, (_, i) => ({ value: `K${i}`, count: 1 })) } : f));
    expect(problems({ kraj: ["Fiktivní kraj A"] }, cut)).toEqual([]);
    expect(problems({ kraj: [1] })).toEqual([]); // text the population keys may differ from JavaScript's (1.0)
    expect(problems({ kraj: [true] })).toEqual([]);
    expect(problems({ vek: { min: 200 } })).toEqual([]);
    expect(problems({ kraj: ["Zlínský kraj"] })).toEqual([]);
    expect(filterProblems(project({ filters: { kraj: ["Fiktivní kraj A"] } }), null)).toEqual([]);
  });
});

describe("the preview in words", () => {
  it("names each filter's own count beside the combined one, by the catalogue's label (AUD3)", () => {
    const two: AudiencePreview = { ...PREVIEW, selected_rows: 900, filters_applied: { vek: { min: 30, max: 59 }, kraj: { values: ["Zlínský kraj"] } }, per_filter: { vek: 5120, kraj: 1200 } };
    const cat = { factors: [{ id: "vek", label: "Věk" }, { id: "kraj", label: "Kraj" }] } as Catalog;
    expect(liveVerdict(two, cat).lines.slice(0, 3)).toEqual([
      "Filtry vyberou 900 z 18\u00a0766 lidí populace v17_4_0 (1\u00a0400 různých dárců).",
      "Samotný filtr Věk: 5\u00a0120 lidí.",
      "Samotný filtr Kraj: 1\u00a0200 lidí.",
    ]);
    // Without the catalogue, the id; one filter alone is the combined count and is not repeated.
    expect(filterCountLines(two, null)[1]).toBe("Samotný filtr kraj: 1\u00a0200 lidí.");
    expect(filterCountLines(PREVIEW, cat)).toEqual([]);
    expect(filterCountLines({ ...two, per_filter: null }, cat)).toEqual([]);
  });

  it("says what the filters select and whether n can be drawn", () => {
    expect(liveVerdict(PREVIEW)).toEqual({ ok: true, lines: ["Filtry vyberou 5 120 z 18 766 lidí populace v17_4_0 (1 400 různých dárců).", "Vzorek N=500 z tohoto publika lze vybrat."] });
    expect(liveVerdict({ ...PREVIEW, sample: { ok: true, status: "PASS_WEIGHTED" } }).lines[1]).toContain("až po kalibraci");
  });

  it("says each refusal in Czech, with the unit's own reasons", () => {
    const small = liveVerdict({ ...PREVIEW, n: 8, sample: { ok: false, reason: "sampling_unrepresentative", message: "a sample of 8 ..." } });
    expect(small.ok).toBe(false);
    expect(small.lines[1]).toMatch(/nebyl reprezentativní/);
    const bad = liveVerdict({ ...PREVIEW, selected_rows: null, audience: { ok: false, reason: "sampling_filter_invalid", reasons: ["vek: očekáván interval min/max"] }, sample: null });
    expect(bad).toEqual({ ok: false, lines: ["Některý filtr nelze použít: vek: očekáván interval min/max."] });
    expect(liveVerdict({ ...PREVIEW, audience: { ok: false, reason: "something_new" }, sample: null }).lines[0]).toContain("something_new");
  });
});

describe("the built-in subpanels a search matches (audit B9)", () => {
  it("by name or description, as the factor search does, the query trimmed", () => {
    const all = CATALOGUE.subpanels;
    expect(matchingSubpanels(all, "").map((s) => s.key)).toEqual(["young_18_29", "students"]);
    expect(matchingSubpanels(all, "  ").map((s) => s.key)).toEqual(["young_18_29", "students"]);
    expect(matchingSubpanels(all, " MLADÍ ").map((s) => s.key)).toEqual(["young_18_29"]);
    expect(matchingSubpanels(all, "vestavěný").map((s) => s.key)).toEqual(["young_18_29"]);
    expect(matchingSubpanels(all, "nikdo")).toEqual([]);
  });
});
