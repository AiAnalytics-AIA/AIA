// How the population registry reads on Společenská inteligence (population-operations P2).
// Read-only: nothing here, and nothing on the page, can import, establish or promote.

import type { PopulationField, PopulationMaterialized, PopulationRegistry, PopulationSubpanel, PopulationVersion } from "./api";

export type RegistrySummary = {
  /** The version the LIVE population points at now, or null: no LIVE yet. */
  live: PopulationVersion | null;
  /** The version the STATIC reference is pinned to, or null. */
  reference: PopulationVersion | null;
  /** Registered, never bound to a population: build inputs and candidates. */
  candidates: number;
  /** Newest first: what a person reads first is the latest move. */
  history: PopulationRegistry["history"];
};

export function summarize(registry: PopulationRegistry): RegistrySummary {
  const byId = new Map(registry.versions.map((v) => [v.version_id, v]));
  const pointedBy = (kind: "STATIC" | "LIVE") => {
    const p = registry.populations.find((x) => x.kind === kind);
    return p ? (byId.get(p.current_version_id) ?? null) : null;
  };
  return {
    live: pointedBy("LIVE"),
    reference: pointedBy("STATIC"),
    candidates: registry.versions.filter((v) => v.owner_client_id === null && v.status === "REGISTERED").length,
    history: [...registry.history].sort((a, b) => b.promoted_at.localeCompare(a.promoted_at)),
  };
}

/** A content hash as a person compares it: the first twelve characters. */
export function shortSha(sha: string): string {
  return sha.slice(0, 12);
}

/** A version's label by id, or the id itself when the registry does not list it. */
export function labelOf(registry: PopulationRegistry, versionId: string | null): string {
  if (!versionId) return "—";
  return registry.versions.find((v) => v.version_id === versionId)?.label ?? versionId;
}

/** The versions every study may run over: shared, never a client's child. */
export function sharedVersions(registry: PopulationRegistry): PopulationVersion[] {
  return registry.versions.filter((v) => v.owner_client_id === null);
}

// ------------------------------------------------------------ materialized children (P4d4)

/** This organization's owned children, newest first. */
export function children(registry: PopulationRegistry): PopulationVersion[] {
  return registry.versions
    .filter((v) => v.owner_client_id !== null)
    .sort((a, b) => b.imported_at.localeCompare(a.imported_at));
}

export type TargetVerdict = "met" | "unmet" | "unknown";

/** Met, not met, or unknown: a child without a recorded outcome is never shown as met. */
export function targetVerdict(m: PopulationMaterialized | null | undefined): TargetVerdict {
  if (!m) return "unknown";
  return m.target_met ? "met" : "unmet";
}

/** A target or an achieved value as a person reads it: a binary share in percent, a scale to two decimals. */
export function outcomeValue(kind: PopulationMaterialized["kind"], value: number): string {
  if (kind === "binary") return `${(value * 100).toLocaleString("cs", { maximumFractionDigits: 1 })} %`;
  return value.toLocaleString("cs", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ------------------------------------------------------------ characteristics (P7d)

/** The version whose characteristics the page opens on: LIVE, else the reference, else the newest. */
export function defaultVersionId(registry: PopulationRegistry): string | null {
  const s = summarize(registry);
  const newest = [...registry.versions].sort((a, b) => b.imported_at.localeCompare(a.imported_at))[0];
  return s.live?.version_id ?? s.reference?.version_id ?? newest?.version_id ?? null;
}

/** A subpanel's filter as a person reads it: `vek 18–29` or `is_student = 1`. */
export function subpanelFilterText(f: PopulationSubpanel["filter"]): string {
  if (f.equals !== null) return `${f.field} = ${f.equals}`;
  return `${f.field} ${f.minimum ?? "…"}–${f.maximum ?? "…"}`;
}

export type Usability = "usable" | "unusable" | "unknown";

/** Usable, not usable, or unknown -- an unknown is never shown as usable. */
export function usability(s: Pick<PopulationSubpanel, "usable">): Usability {
  if (s.usable === null) return "unknown";
  return s.usable ? "usable" : "unusable";
}

/** The fields a search and a block choose; an empty search and no block choose every field. */
export function filterFields(fields: PopulationField[], query: string, block: string | null): PopulationField[] {
  const needle = query.trim().toLocaleLowerCase("cs");
  return fields.filter((f) => {
    if (block && f.block !== block) return false;
    if (!needle) return true;
    return [f.field, f.description, f.block, f.evidence_status, f.source].some((text) => text.toLocaleLowerCase("cs").includes(needle));
  });
}

/** An i18n key under `reason.` and its values for a policy reason; unknown codes come back as `raw`. */
export function reasonKey(reason: string): { key: string; values: Record<string, string> } {
  const grade = /^grade_(.+)_not_client_facing$/.exec(reason);
  if (grade) return { key: "grade_not_client_facing", values: { grade: grade[1] } };
  const rule = /^rule_(.+)$/.exec(reason);
  if (rule) return { key: "rule", values: { rule: rule[1] } };
  return KNOWN_REASONS.has(reason) ? { key: reason, values: {} } : { key: "raw", values: { code: reason } };
}

const KNOWN_REASONS = new Set([
  "audit_only",
  "declared_weight_column",
  "disclosed_modelled_claim",
  "internal_use",
  "measured_evidence",
  "not_a_weight_column",
  "not_persona_eligible",
  "persona_eligible",
  "phrase_permits_modelled_claims_only",
  "phrase_permits_no_client_claim",
  "unclassified_derived_field",
  "unknown_field",
  "unmapped_policy",
]);

