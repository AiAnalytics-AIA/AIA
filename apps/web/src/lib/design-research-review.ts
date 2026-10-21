// A Design Research run's proposal, reviewed by a person (ADR 0021 checkpoint 1; research-lead-workbench
// 7b, F-DRL-1). The run only proposes: per subject its accepted findings (EVIDENCE) or none (GAP). A person
// ticks the EVIDENCE items to take, and the server writes them into the design under `design_research`
// (domain/deep_research/design_proposals.py, through the accept service) in one transaction with the working copy, a
// new Design Revision and a ledger row (application/design_research.py). This module decides nothing the
// server decides: it reads the proposal and the working copy, builds the accept's body and says a refusal
// in words. Pure: no fetch.

import { ApiError, type DesignFinding, type DesignProposal } from "@/lib/api";
import { CONFLICT_MESSAGE } from "@/research/store";
import { staleDetails, staleMessage } from "@/research/proposal-items";

/** The one design key an accept writes (design_proposals.py DESIGN_RESEARCH_KEY). */
export const DESIGN_RESEARCH_KEY = "design_research";
/** The block's contract (design_proposals.py DESIGN_PROPOSAL_CONTRACT); another is not read as this one. */
export const DESIGN_PROPOSAL_CONTRACT = "aia-design-research-proposal-1";

type Obj = Record<string, unknown>;
const isObj = (x: unknown): x is Obj => !!x && typeof x === "object" && !Array.isArray(x);

export type ReviewItem = {
  itemId: string;
  kind: "EVIDENCE" | "GAP";
  subjectKind: string;
  subjectText: string;
  findings: DesignFinding[];
  /** Already in the working copy's design, taken from this run. */
  accepted: boolean;
  /** Whether a person may tick it now: EVIDENCE, admissible, not yet taken, the proposal not spent. */
  selectable: boolean;
};

export type ProposalReading = {
  items: ReviewItem[];
  /** The design moved past this proposal by its own accept: the server refuses another (design_moved). */
  spent: boolean;
  admissible: boolean;
};

/**
 * The items of the working copy's `design_research` block that came from `runId`, by id. A block of
 * another contract is read as none: the server refuses to write over it (block_invalid), and this
 * never guesses what it holds.
 */
export function acceptedFrom(project: Obj | null, runId: string): Set<string> {
  const block = project?.[DESIGN_RESEARCH_KEY];
  if (!isObj(block) || block.contract_version !== DESIGN_PROPOSAL_CONTRACT || !isObj(block.items)) return new Set();
  const out = new Set<string>();
  for (const [id, entry] of Object.entries(block.items)) {
    if (isObj(entry) && isObj(entry.provenance) && entry.provenance.run_id === runId) out.add(id);
  }
  return out;
}

/**
 * The proposal as the review shows it, against the design the person has. An accept writes a new Design
 * Revision, so the proposal, researched from the one before, is spent: the server refuses another accept
 * from it (`stale_proposal`, `design_moved`), and the review offers none. A newer revision made any other
 * way is the server's to say, when the person accepts.
 */
export function readProposal(proposal: DesignProposal, project: Obj | null): ProposalReading {
  const taken = acceptedFrom(project, proposal.run_id);
  const spent = taken.size > 0;
  const items = proposal.items.map((i): ReviewItem => {
    const accepted = taken.has(i.item_id);
    return {
      itemId: i.item_id,
      kind: i.kind,
      subjectKind: i.subject_kind,
      subjectText: i.subject_text,
      findings: i.findings,
      accepted,
      selectable: i.kind === "EVIDENCE" && proposal.admissible && !accepted && !spent,
    };
  });
  return { items, spent, admissible: proposal.admissible };
}

export type DesignProposalAcceptBody = {
  item_ids: string[];
  expected_revision_id: string;
  expected_workspace_revision: number;
};

/**
 * The accept's body: exactly the ticked items the review may send (EVIDENCE, selectable), each once, on
 * both baselines: the Design Revision the run researched and the working revision the person has. Null
 * when nothing may be sent: no item, or a working copy not yet saved.
 */
export function acceptBody(
  proposal: DesignProposal,
  reading: ProposalReading,
  chosen: Iterable<string>,
  workspaceRevision: number | null,
): DesignProposalAcceptBody | null {
  const allowed = new Set(reading.items.filter((i) => i.selectable).map((i) => i.itemId));
  const ids = [...new Set(chosen)].filter((id) => allowed.has(id)).sort();
  if (!ids.length || workspaceRevision === null) return null;
  return { item_ids: ids, expected_revision_id: proposal.design_revision_id, expected_workspace_revision: workspaceRevision };
}

const SUBJECT: Record<string, string> = {
  QUESTION: "Výzkumná otázka",
  OBJECT: "Sledovaný objekt",
  CROSS: "Otázka k objektu",
};
/** What the run researched, in words (contracts.py SubjectKind); an unknown kind is said as its code. */
export const subjectWords = (kind: string): string => SUBJECT[kind] ?? kind;

/** The proposal is not admissible (a recorded fixture in a real client's design): why, in Czech. */
export const INADMISSIBLE = "Tento běh stojí na nahraných ukázkových zdrojích. Do návrhu skutečného klienta ho přijmout nejde.";
/** Why the review offers no further accept once the proposal took items. */
export const SPENT = "Z tohoto běhu už jsou podklady v návrhu. Přijetí vytvořilo novou revizi návrhu, nad kterou běh nevznikl; pro další podklady spusťte výzkum znovu.";

const REFUSAL: Record<string, string> = {
  inadmissible: INADMISSIBLE,
  block_too_large: "Vybrané podklady by v návrhu zabraly víc místa, než návrh unese. Vyberte jich méně.",
  design_context_too_large: "S vybranými podklady by návrh přerostl to, co AI kroky návrhu umí přečíst. Vyberte jich méně.",
  block_invalid: "Podklady z hloubkového výzkumu jsou v návrhu v jiném tvaru, než AIA zná. Přijetí by je přepsalo, proto se nezapsalo nic.",
  unknown_item: "Vybraná položka v tomto návrhu není. Načtěte studii znovu.",
  empty_selection: "Vyberte alespoň jednu položku.",
  proposal_not_ready: "Výzkum ještě neskončil; návrh zatím není.",
  not_design_research: "Tento běh návrh pro dotazník nedělá.",
  stale_revision: CONFLICT_MESSAGE,
};

/**
 * A refused accept in words. A `stale_proposal` names, through proposal-items.ts, each item both changed
 * (or the newer revision, or the moved lineage); the other refusals the route names have words of their
 * own. Null for an error this does not know: the caller says its message.
 */
export function refusalWords(e: unknown, project: Obj | null = null): string | null {
  const stale = staleDetails(e);
  if (stale) return staleMessage(stale, project);
  if (!(e instanceof ApiError)) return null;
  return REFUSAL[e.code] ?? null;
}

/** "1 položka", "2 položky", "5 položek". */
export function itemsWord(n: number): string {
  return `${n} ${n === 1 ? "položka" : n >= 2 && n <= 4 ? "položky" : "položek"}`;
}
