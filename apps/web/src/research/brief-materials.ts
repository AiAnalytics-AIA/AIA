// The Brief's materials (plan client-data-in-analysis 8a, a PROPOSED interface; ADR 0027 is
// Proposed). A Brief names a client dataset by its source id and the reading the person picked,
// with the data contract it is meant to be used under; it never holds a row, and it holds no
// eligibility: whether a dataset may feed analysis is the server's to compute from the contracts
// it holds (aia_core.domain.brief_materials eligibility_of), and none is accepted before the data
// contract (chunk 2) exists. No client dataset is admitted by being attached.
//
// materialSignature is what briefFingerprint signs of `briefing.materials`, byte for byte with the
// server's material_signature: the shared cases in
// packages/aia_core/tests/fixtures/design_items/cases.json hold the two to one string.

/** One material as the Brief stores it: what a person picked, nothing about what it may do. */
export type BriefMaterial = {
  kind: "client_dataset";
  source_id: string;
  reading_sha256: string;
  contract_id?: string | null;
  contract_version?: number | null;
};

/** What the server computes for a material; the web shows it, never decides it. */
export type MaterialEligibility = "no_contract" | "contract_not_accepted" | "contract_stale" | "eligible";

type Signed = { source_id: string | null; reading_sha256: string | null; contract_id: string | null; contract_version: number | null };

const str = (v: unknown): string | null => (typeof v === "string" ? v : null);

/** Per entry its source, reading and named contract, in the person's order; null for a non-object. */
export function materialSignature(materials: unknown[]): (Signed | null)[] {
  return materials.map((x) => {
    if (!x || typeof x !== "object" || Array.isArray(x)) return null;
    const m = x as Record<string, unknown>;
    return {
      source_id: str(m.source_id),
      reading_sha256: str(m.reading_sha256),
      contract_id: str(m.contract_id),
      contract_version: Number.isInteger(m.contract_version) ? (m.contract_version as number) : null,
    };
  });
}
