/**
 * Evidence roles → the epistemic grade mark.
 *
 * The complete role enum is not published yet (OI-9, owner analysis-governance).
 * Until it is, only the roles named in docs/product/README.md are known. Any other
 * value — including null, undefined and the empty string — is UNKNOWN and renders
 * as "?". An unknown role is never shown as measured and never given the
 * strongest grade.
 */
export const KNOWN_EVIDENCE_ROLES = [
  "MEASURED_JOINT",
  "CALIBRATED_CORE",
  "MODELED_BEHAVIOR_PRIOR",
  "EXTERNAL_HOLDOUT_PENDING",
] as const;
export type KnownEvidenceRole = (typeof KNOWN_EVIDENCE_ROLES)[number];

/** The grade the UI draws. "unknown" is a grade of its own, not a fallback to another. */
export type EvidenceGrade = "measured" | "calibrated" | "modelled" | "holdout-pending" | "unknown";

export const EVIDENCE_GRADE = {
  MEASURED_JOINT: "measured",
  CALIBRATED_CORE: "calibrated",
  MODELED_BEHAVIOR_PRIOR: "modelled",
  EXTERNAL_HOLDOUT_PENDING: "holdout-pending",
} as const satisfies Record<KnownEvidenceRole, Exclude<EvidenceGrade, "unknown">>;

export function evidenceGrade(role: unknown): EvidenceGrade {
  if (typeof role !== "string") return "unknown";
  return (KNOWN_EVIDENCE_ROLES as readonly string[]).includes(role) ? EVIDENCE_GRADE[role as KnownEvidenceRole] : "unknown";
}
