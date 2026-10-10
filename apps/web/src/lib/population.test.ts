import { describe, expect, it } from "vitest";

import type { PopulationRegistry, PopulationVersion } from "./api";
import { labelOf, shortSha, summarize } from "./population";

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
