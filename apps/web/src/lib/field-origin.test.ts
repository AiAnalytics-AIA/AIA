import { describe, expect, it } from "vitest";

import fixture from "./fixtures/methodology.json";
import type { FieldPolicyTables, PopulationField } from "./api";
import { counts, fieldRules, originName, ruleIds, ruleName, selectFields } from "./field-origin";

const tables = fixture.field_policy as FieldPolicyTables;

const field = (name: string, over: Partial<PopulationField>): PopulationField => ({
  field: name, block: "core", source: "fictional", evidence_status: "CANONICAL_CORE", provenance_class: "OBSERVED",
  production_grade: "A", recommended_use: "PERSONA_OR_ANALYSIS_WITH_SCOPE", description: "", persona_eligible: true,
  is_weight: false, derived: false, uses: [], materialized: false, ...over,
});

const FIELDS = [
  field("vek", { description: "Věk respondenta" }),
  field("phq9", { provenance_class: "CALIBRATED", production_grade: "C", recommended_use: "aggregate planning and persona background with modeled-value disclosure" }),
  field("donor_id", { provenance_class: "PROVENANCE", production_grade: "T", recommended_use: "technical/provenance only", block: "audit" }),
  field("odd", { recommended_use: "a sentence no table knows" }),
];

describe("field origin", () => {
  it("names every origin and rule the policy serves in words", () => {
    for (const o of tables.origins) expect(originName(o.id)).not.toBe(o.id);
    for (const r of ruleIds(tables)) expect(ruleName(r)).not.toBe(r);
  });

  it("reads a field's rules from its sentence, and an unknown sentence as unknown", () => {
    expect(fieldRules(tables, FIELDS[1])).toEqual(["AGGREGATE_ONLY", "REQUIRES_MODELED_DISCLOSURE"]);
    expect(fieldRules(tables, FIELDS[3])).toBeNull();
  });

  it("counts fields per origin, rule and grade, and nothing as unknown, never zero", () => {
    const c = counts(tables, FIELDS);
    expect(c.origins).toMatchObject({ OBSERVED: 2, CALIBRATED: 1, PROVENANCE: 1, MODELLED: 0 });
    expect(c.rules).toMatchObject({ REQUIRES_SCOPE: 1, AUDIT_ONLY: 1, AGGREGATE_ONLY: 1 });
    expect(c.grades).toMatchObject({ A: 2, C: 1, T: 1, D: 0 });
    const unknown = counts(tables, null);
    expect(Object.values(unknown.origins).every((n) => n === null)).toBe(true);
  });

  it("filters by origin, rule or grade, then by the search", () => {
    const names = (sel: Parameters<typeof selectFields>[2], q = "") => selectFields(tables, FIELDS, sel, q).map((f) => f.field);
    expect(names({ kind: "origin", id: "OBSERVED" })).toEqual(["vek", "odd"]);
    expect(names({ kind: "rule", id: "AUDIT_ONLY" })).toEqual(["donor_id"]);
    expect(names({ kind: "grade", id: "T" })).toEqual(["donor_id"]);
    expect(names(null, "věk")).toEqual(["vek"]);
  });
});
