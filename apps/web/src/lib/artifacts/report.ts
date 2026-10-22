// Zpráva's artifact as the pane reads it (artifact-report RPT1): the stored document model of a run's
// report (report-delivery RD5a, contract aia-report-document-1) and what on it the Lead can point at:
// every target is the report's own kind, `report:`, so a focus lands on Zpráva.
// Pure: the pane renders what this says, and never formats a number -- each ref's text is the one the
// DOCX prints, stored beside it by the server (domain/report/document_model.py).

import { czechDate } from "@/lib/report-variant";
import { aiaId } from "@/lib/workbench-artifacts";

/**
 * The contracts this reader knows; a document of any other is refused, never read in part. -2
 * (artifact-chain-to-draft-report CHN1) only adds each section's `sources` and the document's `unread`,
 * -3 (report-delivery RD0) each ledger entry's `level`: the draft is drawn without them, and
 * Záznam pokrytí reads `unread` (RPT4).
 */
export const DOCUMENT_CONTRACTS = ["aia-report-document-1", "aia-report-document-2", "aia-report-document-3"] as const;

export type Inline =
  | { type: "text"; text: string; emphasis: "none" | "em" | "strong" }
  | { type: "value"; ref: string; with_interval: boolean }
  | { type: "footnote"; text: string }
  | { type: "cross_ref"; target: string }
  | { type: "link"; text: string; url: string };

export type ListItem = { content: Inline[]; children: ListItem[] };

export type Cell =
  | { type: "text"; text: string }
  | { type: "number"; ref: string; with_interval: boolean }
  | { type: "empty"; reason: string };

export type Chart = {
  kind: string;
  categories: string[];
  series: { name: string; refs: (string | null)[]; modelled: boolean }[];
  value_label: string;
};

type Common = { id: string; refs: string[] };

export type Block = Common & (
  | { type: "heading"; text: string; level: 2 | 3; anchor: string | null }
  | { type: "paragraph"; role: "body" | "lede" | "lead_in"; content: Inline[]; marks: string[] }
  | { type: "list"; ordered: boolean; items: ListItem[] }
  | { type: "quote"; text: string; attribution: string; synthetic: boolean }
  | { type: "callout"; kind: string; title: string | null; content: Inline[]; marks: string[] }
  | { type: "key_finding"; headline: string; finding: string; evidence: string; meaning: string; confidence: string; marks: string[] }
  | { type: "recommendation"; action: string; why: string; priority: string; marks: string[] }
  | { type: "kpi_row"; items: { label: string; ref: string }[] }
  | {
      type: "table"; anchor: string; title: string;
      columns: { label: string; align: "left" | "right"; unit: string | null }[];
      rows: { cells: Cell[]; emphasis: boolean }[];
      suppressed_rows: number; source: string; base_ref: string | null; notes: string[];
    }
  | { type: "figure"; anchor: string; title: string; chart: Chart; source: string; alt: string; base_ref: string | null; notes: string[] }
  | {
      type: "sociomap_figure"; anchor: string; title: string; image_sha256: string; methodology_status: string;
      stress_1: number | null; fit_caption: string | null; source: string; alt: string;
    }
  | { type: "page_break" }
  | { type: "evidence_key" }
  | { type: "evidence_appendix" }
  | { type: "audit"; entries: [string, string][] }
);

export type Section = { id: string; title: string; appendix: boolean; blocks: Block[]; refs: string[] };

/** One cited ref: its printed text, or, suppressed, only why it is not printed. */
export type LedgerEntry =
  | { suppressed: true; reasons: string[] }
  | {
      suppressed: false; value_text: string; number_text: string; interval_text: string | null;
      base_text: string | null; metric: string; unit: string; grade: string; indicative: boolean;
      modelled_panel: boolean; basis: string; support: string; question_id: string | null; data_origin: string | null;
    };

/** One of the run's outputs, as the manifest names it (`source_payload`): a stored artifact (its id and
 *  SHA-256 dropped in a client deliverable), or a step that runs beside the report. */
export type RunOutput =
  | { kind: "artifact"; artifact_type: string; artifact_id?: string; sha256?: string }
  | { kind: "beside"; node_key: string; step_kind: string };

export type ReportDocumentModel = {
  contract: (typeof DOCUMENT_CONTRACTS)[number];
  meta: {
    kind: string; title: string; subtitle: string; client_name: string; study_name: string; study_id: string;
    issued_on: string; revision: number; method_status: string; classification: string;
    identifiers: [string, string][];
  };
  sections: Section[];
  ledger: { surface: string; refs: Record<string, LedgerEntry> };
  /** The run's outputs no section read (CHN1); absent from a -1 document. */
  unread?: RunOutput[];
};

/** What the document route answers: the document and the DOCX it is beside, with that DOCX's review. */
export type StoredReportDocument = {
  run_id: string;
  artifact_id: string;
  sha256: string;
  report_artifact_id: string;
  report_sha256: string;
  review_state: "DRAFT_UNAPPROVED" | "APPROVED_INTERNAL";
  approved_on: string | null;
  stamped: boolean;
  /** Who approved the DOCX and when, from its ledger row (report-delivery RD2); null for a draft. */
  approval?: Approval | null;
  document: ReportDocumentModel;
};

/** One approval as the ledger recorded it. `approver_name` null: a person with no name, or one the store no longer knows. */
export type Approval = {
  approved_at: string;
  approver_name: string | null;
  by_you: boolean;
  self_approved: boolean;
  self_approval_allowed: boolean;
  self_approval_source: string;
  note: string;
};

/** A stored document of this contract, or null: one of any other is not read. */
export function readDocument(payload: unknown): ReportDocumentModel | null {
  if (typeof payload !== "object" || payload === null) return null;
  const doc = payload as Partial<ReportDocumentModel>;
  if (!(DOCUMENT_CONTRACTS as readonly unknown[]).includes(doc.contract) || !Array.isArray(doc.sections) || typeof doc.ledger !== "object" || doc.ledger === null) return null;
  return doc as ReportDocumentModel;
}

// ---------------------------------------------------------------- pointing (the Lead's targets)

/** A section's `data-aia`: `report:<the composer's section id>` (intro, ch-1 …, ch-native-map-<n>, app-audit). */
export const sectionTarget = (section: Section): string => aiaId("report", section.id);

/** A block's `data-aia`: `report:<section id>.<n>`, the id it was stored with and every later edit names. */
export const blockTarget = (block: Block): string => aiaId("report", block.id);

const ID = /^[A-Za-z0-9_.\-~/:]{1,80}$/;

/**
 * A number chip's `data-aia`: `report:<block id>:<ref>`, the report's own kind, so the Lead's focus lands on
 * Zpráva -- `claim:` is Analýza's (`claim:<module>:<claim_id>`), and one ref can sit in several blocks. Null
 * for a ref outside the id grammar (a ref may carry an answer's wording, `q3.pct.Spíše ano`): the chip still
 * opens its claim, the Lead names its block instead.
 */
export const claimTarget = (block: Pick<Block, "id">, ref: string): string | null => {
  const id = `${block.id}:${ref}`;
  return ID.test(id) ? aiaId("report", id) : null;
};

// ---------------------------------------------------------------- reading a ref

/** How one cited value prints: the stored text, with its interval where the DOCX prints one. */
export function valueWords(entry: LedgerEntry | undefined, withInterval: boolean): string {
  if (!entry) return "?"; // a ref the document does not hold: unknown, never a number
  if (entry.suppressed) return "potlačeno";
  return withInterval && entry.interval_text ? `${entry.value_text} ${entry.interval_text}` : entry.value_text;
}

const GRADE_WORDS: Record<string, string> = {
  measured: "měřeno",
  calibrated: "kalibrováno",
  modelled: "modelováno",
  "holdout-pending": "čeká na ověření",
  unknown: "neznámý stupeň",
};

/** A ref's grade in words; one this reader does not know is unknown, never measured. */
export const gradeWords = (grade: string): string => GRADE_WORDS[grade] ?? GRADE_WORDS.unknown;

const SUPPORT_WORDS: Record<string, string> = {
  REPORTABLE: "dostatečná",
  INDICATIVE: "orientační",
  SUPPRESS: "nedostatečná",
};

/** A ref's support in words; one this reader does not know is unknown, never sufficient. */
export const supportWords = (support: string): string => SUPPORT_WORDS[support] ?? "neznámá";

/** The lines a claim's inspector shows, in order: value, base, grade, support, origin. */
export function claimLines(entry: LedgerEntry | undefined): string[] {
  if (!entry) return ["Zpráva toto číslo nemá; nic se netiskne."];
  if (entry.suppressed) {
    return ["Potlačeno: zpráva ho netiskne.", ...entry.reasons.map((reason) => `Důvod: ${reason}`)];
  }
  return [
    `Hodnota: ${valueWords(entry, true)}`,
    `Základ: ${entry.base_text ?? "n = ?"}`,
    `Stupeň evidence: ${gradeWords(entry.grade)}${entry.indicative ? ", orientační" : ""}`,
    `Podpora: ${supportWords(entry.support)}`,
    ...(entry.modelled_panel ? ["modelováno: AI respondenti z populace"] : []),
    ...(entry.question_id ? [`Otázka: ${entry.question_id}`] : []),
  ];
}

/** Every ref a document cites that its ledger does not hold: an empty list, or the pane says so. */
export function unresolvedRefs(doc: ReportDocumentModel): string[] {
  const held = doc.ledger.refs;
  return [...new Set(doc.sections.flatMap((section) => section.refs))].filter((ref) => !(ref in held));
}

/**
 * Who approved and when, in words: "schválil(a) Jana Nováková 21. 10. 2026", "schválili jste …" for the
 * asker, a person with no name "člen bez jména" (never a guess), and "vlastní práce" when they approved
 * what they produced. The day is the server's (`approved_on`, the Prague day of the same ledger row).
 * Null for a draft or an approval the response does not carry.
 */
export function approvalWords(approval: Approval | null | undefined, approvedOn: string | null): string | null {
  if (!approval) return null;
  const day = approvedOn ? czechDate(approvedOn) : "neznámého dne";
  const said = approval.by_you ? `schválili jste ${day}` : `schválil(a) ${approval.approver_name ?? "člen bez jména"} ${day}`;
  return approval.self_approved ? `${said} · vlastní práce` : said;
}

/** The review the doc bar names: the DOCX's, since the DOCX is what a person approves. The server
 *  stores one approved state for both reports; the client report's approval signs it off for the
 *  client, never "for internal use". */
export const reviewWords = (stored: Pick<StoredReportDocument, "review_state">, kind: "internal" | "client" = "internal"): string =>
  stored.review_state !== "APPROVED_INTERNAL" ? "neschváleno"
    : kind === "client" ? "schváleno k předání klientovi" : "interně schváleno";
