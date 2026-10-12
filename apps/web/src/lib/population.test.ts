import { describe, expect, it } from "vitest";

import type { PopulationField, PopulationRegistry, PopulationVersion } from "./api";
import { defaultVersionId, filterFields, labelOf, reasonKey, shortSha, subpanelFilterText, summarize, usability } from "./population";

const version = (label: string, status: PopulationVersion["status"]): PopulationVersion => ({
  version_id: `DSV-${label}`,
  label,
  content_sha256: "a".repeat(64),
  row_count: 6,
  column_count: 4,
  parent_version_id: null,
  status,
  runtime_eligible: status !== "REGISTERED",
  companions_attached: true,
  imported_at: "2026-10-10T09:00:00Z",
  imported_by: "USR-operator",
  provenance: "fictional",
});

const registry: PopulationRegistry = {
  dataset_id: "cz_synthetic_population",
  contract_id: "c",
  versions: [version("v_BASE", "REGISTERED"), version("v_1", "STATIC_REFERENCE"), version("v_4", "SUPERSEDED"), version("v_5", "LIVE_CURRENT")],
  populations: [
    { population_id: "CZ_STATIC_REFERENCE", kind: "STATIC", current_version_id: "DSV-v_1", established_at: "", established_by: "" },
    { population_id: "CZ_LIVE", kind: "LIVE", current_version_id: "DSV-v_5", established_at: "", established_by: "" },
  ],
  history: [
    { population_id: "CZ_LIVE", from_version_id: null, to_version_id: "DSV-v_4", actor_id: "u", reason: "establish", promoted_at: "2026-10-10T09:00:00Z" },
    { population_id: "CZ_LIVE", from_version_id: "DSV-v_4", to_version_id: "DSV-v_5", actor_id: "u", reason: "newer", promoted_at: "2026-10-10T10:00:00Z" },
  ],
};

describe("the population registry, as Společenská inteligence reads it", () => {
  it("names LIVE and the reference by the versions their populations point at", () => {
    const s = summarize(registry);
    expect(s.live?.label).toBe("v_5");
    expect(s.reference?.label).toBe("v_1");
    expect(s.candidates).toBe(1);
    expect(s.history.map((h) => h.reason)).toEqual(["newer", "establish"]);
  });

  it("says no LIVE yet rather than guessing one", () => {
    const s = summarize({ ...registry, populations: [] });
    expect(s.live).toBeNull();
    expect(s.reference).toBeNull();
  });

  it("labels a version by id and keeps an unknown id as it is", () => {
    expect(labelOf(registry, "DSV-v_4")).toBe("v_4");
    expect(labelOf(registry, "DSV-gone")).toBe("DSV-gone");
    expect(labelOf(registry, null)).toBe("—");
    expect(shortSha("0123456789abcdef")).toBe("0123456789ab");
  });
});

describe("characteristics (P7d)", () => {
  it("opens on LIVE, else the reference, else the newest version", () => {
    expect(defaultVersionId(registry)).toBe("DSV-v_5");
    expect(defaultVersionId({ ...registry, populations: registry.populations.filter((p) => p.kind === "STATIC") })).toBe("DSV-v_1");
    const later = { ...version("v_9", "REGISTERED"), imported_at: "2026-10-11T09:00:00Z" };
    expect(defaultVersionId({ ...registry, populations: [], versions: [...registry.versions, later] })).toBe("DSV-v_9");
    expect(defaultVersionId({ ...registry, populations: [], versions: [] })).toBeNull();
  });

  it("reads a filter as a range or a value", () => {
    expect(subpanelFilterText({ field: "vek", minimum: 18, maximum: 29, equals: null })).toBe("vek 18–29");
    expect(subpanelFilterText({ field: "is_student", minimum: null, maximum: null, equals: 1 })).toBe("is_student = 1");
  });

  it("never reads an unknown check as usable", () => {
    expect(usability({ usable: null })).toBe("unknown");
    expect(usability({ usable: false })).toBe("unusable");
    expect(usability({ usable: true })).toBe("usable");
  });

  const field = (name: string, block: string, description: string): PopulationField => ({
    field: name,
    block,
    source: "fictional",
    evidence_status: "CANONICAL_CORE",
    provenance_class: "DONOR_MATCHED",
    production_grade: "A",
    recommended_use: "",
    description,
    persona_eligible: true,
    is_weight: false,
    derived: false,
    uses: [],
  });

  it("filters fields by search and block", () => {
    const fields = [field("vek", "population_anchor", "Věk"), field("vzdelani", "core", "Nejvyšší vzdělání")];
    expect(filterFields(fields, "", null).map((f) => f.field)).toEqual(["vek", "vzdelani"]);
    expect(filterFields(fields, "VZDĚL", null).map((f) => f.field)).toEqual(["vzdelani"]);
    expect(filterFields(fields, "", "population_anchor").map((f) => f.field)).toEqual(["vek"]);
    expect(filterFields(fields, "věk", "core")).toEqual([]);
  });

  it("words every policy reason, and shows an unknown code as it is", () => {
    expect(reasonKey("audit_only")).toEqual({ key: "audit_only", values: {} });
    expect(reasonKey("grade_C_not_client_facing")).toEqual({ key: "grade_not_client_facing", values: { grade: "C" } });
    expect(reasonKey("rule_internal_only")).toEqual({ key: "rule", values: { rule: "internal_only" } });
    expect(reasonKey("something_new")).toEqual({ key: "raw", values: { code: "something_new" } });
  });
});

