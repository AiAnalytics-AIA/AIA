// The Research Lead as the web reads it (ADR 0026): its turns, its closed output, and the pure
// part of its edit tools. An edit is applied only when the person accepts its change block; the
// server applies it to the working copy (domain/edit_ops.py apply_edit) and applyLeadEdit keeps
// the screen's copy the same, held to the server by one case file (ADR 0029 decision 1, WCE0).
// Nothing here calls a model or the API.

import type { BriefingField, TopField } from "@/research/brief";
import type { Json, ResearchProject } from "@/research/model";
import { proposalAnalysis, type Narrative } from "@/research/plan-edit";
import { qId, sections, type Question, type Section } from "@/research/questionnaire";
import type { Analysis } from "@/research/store";
import { parseAudienceId } from "./artifacts/audience";
import { withFixer } from "./route-refusal";
import type { WorkbenchStage } from "./workbench-stages";
import { parseAiaId, type TargetKind } from "./workbench-artifacts";

export type TextField = TopField | `briefing.${BriefingField}` | "plan.problem_summary";
export type PlanList = "plan.objectives" | "plan.research_questions" | "plan.hypotheses";
export type QType = "vyber" | "multi" | "skala" | "otevrena";

export type LeadEdit =
  | { op: "set_text"; field: TextField; value: string; why: string }
  | { op: "list_add"; list: PlanList; value: string; why: string }
  | { op: "list_replace"; list: PlanList; old: string; value: string; why: string }
  | { op: "list_remove"; list: PlanList; old: string; why: string }
  | { op: "question_add"; section_id: string | null; text: string; qtype: QType; options: string[]; why: string }
  | { op: "question_edit"; question_id: string; text: string | null; options: string[] | null; why: string }
  | { op: "question_remove"; question_id: string; why: string }
  | { op: "set_n"; value: number; why: string };

export type LeadView = { op: "open_stage"; stage: WorkbenchStage } | { op: "focus"; target: string };

export type LeadRequest =
  | { kind: "agent_job"; action: string; why: string }
  | { kind: "research_run"; why: string }
  | { kind: "design_research"; why: string }
  | { kind: "interpretation_research"; why: string };

/**
 * The card a person's typed start shows (LO5), as the request it starts: the server matched the
 * command, so nothing here reads the message for intent. The instruction after a colon, when the
 * person gave one, is the card's why. A command this client does not know shows no card.
 */
/** A typed start's why when the person gave no instruction: true only until the card is decided. */
export const TYPED_UNDECIDED_WHY = "Spustí se až vaším potvrzením.";

export function commandRequest(t: Pick<LeadTurn, "command" | "text">): LeadRequest | null {
  const said = t.text?.split(":").slice(1).join(":").trim() || TYPED_UNDECIDED_WHY;
  if (t.command === "research_run") return { kind: "research_run", why: said };
  const action = t.command?.startsWith("agent_job:") ? t.command.slice("agent_job:".length) : "";
  return action ? { kind: "agent_job", action, why: said } : null;
}

export type LeadSelfUpdate = {
  name?: string | null;
  soul?: string | null;
  user?: string | null;
  remember?: { scope: "personal" | "client"; text: string }[];
  forget?: string[];
};

export type LeadOutput = {
  reply: string;
  view?: LeadView[];
  edits?: LeadEdit[];
  request?: LeadRequest | null;
  follow?: string[];
  self_update?: LeadSelfUpdate | null;
  /** What the executor applied of self_update, and what grounding dropped. */
  applied?: Record<string, unknown> | null;
  dropped?: { edit?: unknown; reason: string }[];
};

export type LeadTurn = {
  turn_id: string;
  sequence_no: number;
  actor: "person" | "lead";
  kind: "message" | "greeting";
  stage: string;
  text: string | null;
  focus: { id: string; label: string } | null;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "WAITING" | "CANCELLED";
  reason: string | null;
  output: LeadOutput | null;
  run_id: string | null;
  workspace_revision: number | null;
  created_at: string;
  created_by: string | null;
  /** What the person decided on each of this turn's edits, from the approval ledger (by index). */
  edit_decisions?: Record<string, { status: "accepted" | "dismissed" | "refused"; reason: string | null; auto?: boolean }>;
  /** The person's approval of this turn's paid request, when given. */
  /** `reused`: a typed start approved on the job an earlier approval had already started for this
   *  design; nothing started (LO5). */
  request_decision?: { status: "approved"; run_id: string; reused?: boolean } | null;
  /**
   * The researcher's decision on what the turn wanted to keep for all of their work (a personal
   * note, a SOUL, USER or name change), from the approval ledger. Only what stays inside the
   * study's client applies with the turn; the rest waits for this (Codex on #484).
   */
  self_update_decision?: { status: "accepted" | "dismissed"; stale?: ("name" | "soul" | "user")[] } | null;
  /** Whether such a self-update waits for the researcher's decision. */
  self_update_pending?: boolean;
  /** What waits (or waited) for that decision, as the server split it; null when nothing did. */
  self_update_waiting?: SelfUpdateWaiting | null;
  /** The typed start the server matched in this person's message (lead-orchestration LO5:
   *  `agent_job:<action>` or `research_run`); its card is the person's own, approved through
   *  …/request. Absent or null on every other turn, and from an older API. */
  command?: string | null;
  /** What the turn applied at once to the Lead's own files and notes (a client note, forgetting one). */
  changes?: { name?: boolean; soul?: boolean; user?: boolean; remembered?: string[]; forgotten?: string[] } | null;
};

/**
 * What a turn wants to keep or drop for all of the researcher's work: file changes, personal notes
 * to keep, and personal notes to forget with the text the turn was shown.
 */
export type SelfUpdateWaiting = {
  name: string | null;
  soul: string | null;
  user: string | null;
  remember: string[];
  forget: { memory_id: string; text: string | null }[];
};

/** The answer to a decision; `stale`: files another turn changed since, left as they are. */
export type SelfUpdateDecision = { status: "accepted" | "dismissed"; changes: Record<string, unknown> | null; stale: ("name" | "soul" | "user")[] };

/**
 * What of a self-update waits for the researcher, in words: personal notes to keep, personal notes
 * to forget, and file changes. Read from the server's split, never re-derived from the output: only
 * the server knows which notes a forget names.
 */
export function pendingSelfUpdate(w: SelfUpdateWaiting | null | undefined): { notes: string[]; forget: string[]; files: { file: string; text: string }[] } {
  if (!w) return { notes: [], forget: [], files: [] };
  const files: { file: string; text: string }[] = [];
  if (w.name) files.push({ file: "Jméno", text: w.name });
  if (w.soul) files.push({ file: "SOUL", text: w.soul });
  if (w.user) files.push({ file: "USER", text: w.user });
  return { notes: [...w.remember], forget: w.forget.map((f) => f.text ?? `poznámka ${f.memory_id}`), files };
}

export type EditDecisionResult = { workspace_revision: number | null; results: { index: number; status: "accepted" | "dismissed" | "refused"; reason: string | null }[] };
export type RequestApproval = { run_id: string; design_revision_id: string; status: string };

export type LeadState = { available: boolean; unavailable_reason: string | null; busy: boolean; turns: LeadTurn[] };

export type LeadMemory = { memory_id: string; scope: "personal" | "client"; client_id: string | null; client_name?: string | null; text: string; created_at: string; source_turn_id: string | null };
export type ResearcherLead = {
  hatched: boolean;
  lead: {
    lead_id: string; name: string; hatched_at: string; updated_at: string; files: { soul: string; user: string }; memories: LeadMemory[];
    /** The researcher's own choices (plan inline-decisions 2); absent from an older API: all off. */
    preferences?: LeadPreferences;
  } | null;
};

/** Accept the Lead's text edits (wording, never structure or the sample) without a click. Off by default. */
export type LeadPreferences = { auto_accept_text_edits: boolean };

type Content = { project: ResearchProject; analysis: Analysis | null };
const norm = (s: string) => s.replace(/\s+/g, " ").trim().toLocaleLowerCase("cs");
const LIST_KEY: Record<PlanList, "objectives" | "research_questions" | "hypotheses"> = {
  "plan.objectives": "objectives",
  "plan.research_questions": "research_questions",
  "plan.hypotheses": "hypotheses",
};

function narrativeOf(c: Content): Narrative {
  const a = proposalAnalysis(c) ?? {};
  const list = (k: string) => (Array.isArray(a[k]) ? (a[k] as unknown[]).map(String) : []);
  return {
    problem_summary: typeof a.problem_summary === "string" ? a.problem_summary : "",
    research_questions: list("research_questions"),
    objectives: list("objectives"),
    hypotheses: list("hypotheses"),
  };
}

const withSections = (p: ResearchProject, xs: Section[]): ResearchProject => ({ ...p, sections: xs as ResearchProject["sections"] });
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T;

function findQuestion(p: ResearchProject, id: string): { si: number; qi: number } | null {
  // Only a questions section's questions, as the server's vocabulary finds them.
  const xs = sections(p);
  for (let si = 0; si < xs.length; si++) {
    if (xs[si]!.type !== "questions") continue;
    const qi = (xs[si]!.questions || []).findIndex((q) => q.id === id);
    if (qi >= 0) return { si, qi };
  }
  return null;
}

type Doc = { [k: string]: Json };
const isDoc = (x: unknown): x is Doc => !!x && typeof x === "object" && !Array.isArray(x);

function questionFor(text: string, qtype: QType, options: string[], id: string): Question {
  if (qtype === "skala") return { id, text, typ: "skala", skala: [1, 10], popisky_skaly: options.length === 2 ? options : ["vůbec", "zcela"], povolit_nevim: false };
  if (qtype === "otevrena") return { id, text, typ: "otevrena", povolit_nevim: false };
  return { id, text, typ: qtype, kategorie: options.length ? options : ["Ano", "Ne"], povolit_nevim: false };
}

/**
 * The words the server's vocabulary refuses an edit with (domain/edit_ops.py `REFUSALS`), each with
 * what the person is told. The shared case file holds the two sides to the same word.
 */
export type EditRefusal =
  | "already_present"
  | "unknown_item"
  | "unknown_section"
  | "unknown_question"
  | "options_on_non_selection"
  | "too_few_options"
  | "options_on_open_question"
  | "scale_labels_not_two"
  | "unknown_question_type"
  | "plan_not_an_object"
  | "briefing_not_an_object"
  | "sections_not_a_list";
const REFUSED: Record<EditRefusal, string> = {
  already_present: "Položka už v seznamu je.",
  unknown_item: "Položka, kterou návrh mění, už v seznamu není.",
  unknown_section: "Oddíl, do kterého návrh přidává, už v dotazníku není.",
  unknown_question: "Otázka, kterou návrh mění, už v dotazníku není.",
  options_on_non_selection: "Možnosti lze nahradit jen u výběrové otázky.",
  too_few_options: "Výběrová otázka potřebuje aspoň dvě možnosti.",
  options_on_open_question: "Otevřená otázka nemá možnosti.",
  scale_labels_not_two: "Škála má popisky obou krajů, nebo žádné.",
  unknown_question_type: "Takový typ otázky AIA nezná.",
  plan_not_an_object: "Plán výzkumu v pracovní kopii nelze přečíst.",
  briefing_not_an_object: "Zadání v pracovní kopii nelze přečíst.",
  sections_not_a_list: "Dotazník v pracovní kopii nelze přečíst.",
};
const refuse = (reason: EditRefusal) => ({ refused: REFUSED[reason], reason });

/** Why a new question of `qtype` cannot carry `options` (the server's `question_add_problem`). */
export function questionAddProblem(qtype: string, options: readonly string[]): EditRefusal | null {
  if (qtype === "vyber" || qtype === "multi") return options.length < 2 ? "too_few_options" : null;
  if (qtype === "otevrena") return options.length ? "options_on_open_question" : null;
  if (qtype === "skala") return options.length === 0 || options.length === 2 ? null : "scale_labels_not_two";
  return "unknown_question_type";
}

/** The plan narrative's two homes, as the server writes them: the plan, and the analysis, which
 * starts from the plan when there is none. */
function narrativeHomes(c: Content): { plan: Doc; started: Doc } | EditRefusal {
  const raw = (c.project as unknown as Doc).research_plan ?? {};
  if (!isDoc(raw)) return "plan_not_an_object";
  const plan = { ...raw };
  return { plan, started: isDoc(c.analysis) ? { ...(c.analysis as unknown as Doc) } : { ...plan } };
}

/** One narrative key written to both homes, and the plan marked changed by hand; nothing else of
 * the analysis is copied over the plan. */
function writeNarrative(c: Content, plan: Doc, started: Doc, key: string, value: Json): Content {
  plan[key] = value;
  started[key] = value;
  const ui = (c.project as unknown as Doc).ui_state;
  const project = { ...c.project, research_plan: plan, ui_state: { ...(isDoc(ui) ? ui : {}), plan_manual_changed: true } } as ResearchProject;
  return { project, analysis: started as unknown as Analysis };
}

/**
 * The working content with one edit applied, or the reason it no longer applies: the item it
 * names is gone or changed since the Lead read it. Never a guess: an edit that does not fit is
 * refused, not bent to fit. It is the server's `apply_edit` (domain/edit_ops.py), word for word:
 * the server applies the accepted edit and this keeps the screen's copy the same, so the shared
 * case file (packages/aia_core/tests/fixtures/edit_ops/cases.json) holds the two together.
 */
export function applyLeadEdit(c: Content, e: LeadEdit, newId: () => string = () => qId()): { content: Content } | { refused: string; reason: EditRefusal } {
  switch (e.op) {
    case "set_text": {
      if (e.field === "plan.problem_summary") {
        const homes = narrativeHomes(c);
        if (typeof homes === "string") return refuse(homes);
        return { content: writeNarrative(c, homes.plan, homes.started, "problem_summary", e.value) };
      }
      if (e.field.startsWith("briefing.")) {
        const raw = (c.project as unknown as Doc).briefing;
        if (raw !== undefined && raw !== null && !isDoc(raw)) return refuse("briefing_not_an_object");
        const briefing = { ...(raw ?? {}), [e.field.slice("briefing.".length)]: e.value };
        // A brief edit drops the analysis that was made of the brief as it was.
        return { content: { project: { ...c.project, briefing } as ResearchProject, analysis: null } };
      }
      const project = { ...c.project, [e.field]: e.value } as ResearchProject;
      return { content: { project, analysis: e.field === "title" ? c.analysis : null } };
    }
    case "list_add":
    case "list_replace":
    case "list_remove": {
      const homes = narrativeHomes(c);
      if (typeof homes === "string") return refuse(homes);
      const key = LIST_KEY[e.list];
      const current = Array.isArray(homes.started[key]) ? homes.started[key] : homes.plan[key];
      const items = Array.isArray(current) ? current.map(String) : [];
      if (e.op === "list_add") {
        if (items.some((x) => norm(x) === norm(e.value))) return refuse("already_present");
        items.push(e.value);
      } else {
        const i = items.findIndex((x) => norm(x) === norm(e.old));
        if (i < 0) return refuse("unknown_item");
        if (e.op === "list_replace") items[i] = e.value;
        else items.splice(i, 1);
      }
      return { content: writeNarrative(c, homes.plan, homes.started, key, items) };
    }
    case "question_add": {
      const problem = questionAddProblem(e.qtype, e.options);
      if (problem) return refuse(problem); // never a question other than the one accepted
      const raw = (c.project as unknown as Doc).sections;
      if (raw !== undefined && raw !== null && !Array.isArray(raw)) return refuse("sections_not_a_list");
      const xs = clone((raw ?? []) as Section[]);
      let sec = e.section_id
        ? xs.find((s) => isDoc(s) && s.id === e.section_id && s.type === "questions")
        : xs.find((s) => isDoc(s) && s.type === "questions");
      if (e.section_id && !sec) return refuse("unknown_section");
      if (!sec) {
        sec = { id: `sec_${newId().slice(2)}`, type: "questions", title: "Hlavní otázky", purpose: "", questions: [] };
        xs.push(sec);
      }
      sec.questions = [...(sec.questions || []), questionFor(e.text, e.qtype, e.options, newId())];
      return { content: { project: withSections(c.project, xs), analysis: c.analysis } };
    }
    case "question_edit":
    case "question_remove": {
      const at = findQuestion(c.project, e.question_id);
      if (!at) return refuse("unknown_question");
      const xs = clone(sections(c.project));
      const qs = xs[at.si]!.questions || [];
      if (e.op === "question_remove") qs.splice(at.qi, 1);
      else {
        const q = qs[at.qi]!;
        if (e.options !== null && e.options !== undefined) {
          // Options replace a selection question's categories, and only with a real choice; on
          // any other question they would change nothing yet be accepted.
          if (q.typ !== "vyber" && q.typ !== "multi") return refuse("options_on_non_selection");
          if (e.options.length < 2) return refuse("too_few_options");
          q.kategorie = e.options;
        }
        if (e.text !== null && e.text !== undefined) q.text = e.text;
      }
      xs[at.si]!.questions = qs;
      return { content: { project: withSections(c.project, xs), analysis: c.analysis } };
    }
    case "set_n":
      return { content: { project: { ...c.project, n: e.value }, analysis: c.analysis } };
  }
}

const FIELD_LABEL: Record<TextField, string> = {
  title: "Název",
  goal: "Cíl",
  decision_use: "K čemu rozhodnutí poslouží",
  "briefing.product_description": "Produkt nebo služba",
  "briefing.situation": "Situace",
  "briefing.what_is_known": "Co už víme",
  "briefing.constraints": "Omezení",
  "plan.problem_summary": "Shrnutí problému",
};
const LIST_LABEL: Record<PlanList, string> = {
  "plan.objectives": "Cíle výzkumu",
  "plan.research_questions": "Výzkumné otázky",
  "plan.hypotheses": "Hypotézy",
};

/**
 * A Lead edit's refusal, as the server names it (grounding's drop or the accept's refusal,
 * domain/edit_ops.py `REFUSALS`), in Czech: the words `applyLeadEdit` refuses with, and the server's
 * own beside them -- the sample-size reasons are RQC9's (the readiness limits in force decide a valid
 * n, at the turn and again at the accept). A code with no words is kept as is, never guessed.
 */
export const EDIT_REFUSAL_WORDS: Readonly<Record<string, string>> = {
  ...REFUSED,
  sample_size_out_of_range: "Velikost vzorku je mimo platný rozsah metodiky v platnosti; úprava nebyla přijata.",
  sample_size_limits_unknown: "Platný rozsah vzorku se nepodařilo zjistit, proto úprava velikosti vzorku nebyla přijata.",
  op_not_available: "Takovou úpravu AIA zatím neumí použít.",
  sociomap_input_locked: "Vstupy Sociomapy jsou zamčené; úprava je nezmění.",
  not_a_text_edit: "Tuto úpravu nelze přijmout automaticky; čeká na vaše rozhodnutí.",
  unknown_edit: "Úpravu už nelze použít.",
};

export function editRefusalWords(reason: string | null | undefined): string {
  if (!reason) return "Úpravu už nelze použít.";
  return EDIT_REFUSAL_WORDS[reason] ?? reason;
}

/**
 * What a turn says of the edits grounding dropped: a sample size outside the valid range in its
 * own words (it concerned the sample, not nothing), the rest counted as before.
 */
export function droppedLines(dropped: { reason: string }[]): string[] {
  const sample = dropped.filter((d) => d.reason.startsWith("sample_size_"));
  const other = dropped.length - sample.length;
  const lines = [...new Set(sample.map((d) => editRefusalWords(d.reason)))];
  if (other === 1) lines.push("1 navržená změna se netýkala ničeho v pracovní kopii a byla vynechána.");
  else if (other > 1) lines.push(`${other} navržené změny se netýkaly ničeho v pracovní kopii a byly vynechány.`);
  return lines;
}

/** The stage an edit belongs to: where its change block is shown. */
export function editStage(e: LeadEdit): WorkbenchStage {
  if (e.op === "set_text") return e.field.startsWith("plan.") ? "design" : "brief";
  if (e.op.startsWith("list_")) return "design";
  if (e.op === "set_n") return "dimensions";
  return "questionnaire";
}

/** An edit in words: what it changes, from what, to what. */
export function describeEdit(c: Content, e: LeadEdit): { where: string; before: string | null; after: string | null } {
  const qText = (id: string) => {
    const at = findQuestion(c.project, id);
    return at ? String(sections(c.project)[at.si]!.questions![at.qi]!.text ?? "") : null;
  };
  switch (e.op) {
    case "set_text": {
      const before = e.field === "plan.problem_summary"
        ? narrativeOf(c).problem_summary
        : e.field.startsWith("briefing.")
          ? String(c.project.briefing?.[e.field.slice("briefing.".length)] ?? "")
          : String(c.project[e.field] ?? "");
      return { where: FIELD_LABEL[e.field], before: before || null, after: e.value };
    }
    case "list_add":
      return { where: `${LIST_LABEL[e.list]} · přidat`, before: null, after: e.value };
    case "list_replace":
      return { where: `${LIST_LABEL[e.list]} · upravit`, before: e.old, after: e.value };
    case "list_remove":
      return { where: `${LIST_LABEL[e.list]} · odebrat`, before: e.old, after: null };
    case "question_add":
      return { where: "Dotazník · nová otázka", before: null, after: e.options.length ? `${e.text} (${e.options.join(" / ")})` : e.text };
    case "question_edit":
      return { where: "Dotazník · upravit otázku", before: qText(e.question_id), after: [e.text, e.options?.join(" / ")].filter(Boolean).join(" · ") || null };
    case "question_remove":
      return { where: "Dotazník · odebrat otázku", before: qText(e.question_id), after: null };
    case "set_n":
      return { where: "Velikost vzorku", before: c.project.n ? String(c.project.n) : null, after: String(e.value) };
  }
}

/**
 * The element a Lead `focus` names, as the stage screens already identify it: a question's editor
 * (answerability.ts questionElementId), a section's block, a brief field, a part of the plan.
 * Unknown targets fall through to an element carrying the same `data-aia` or id; null: nothing.
 */
export function focusSelector(target: string): string {
  const [kind, ...rest] = target.split(":");
  const id = rest.join(":");
  const css = (s: string) => s.replace(/["\\]/g, "\\$&");
  // A screen's data-aia mark first (a tracked set's card is qset_, not qblock_), then the ids
  // the stages used before they marked themselves.
  if (kind === "question" && id) return `[data-aia="${css(target)}"], [id="qedit_${css(id)}"]`;
  if (kind === "section" && id) return `[data-aia="${css(target)}"], [id="qblock_${css(id)}"]`;
  if (kind === "brief" && id) return `[id="brief-${css(id)}"]`;
  if (kind === "plan" && id) {
    const section: Record<string, string> = { sets: "plan-sets", tracked_sets: "plan-sets", comments: "plan-comments", variants: "plan-variants", questions: "plan-questions" };
    return `[id="${section[id] ?? "plan-understanding"}"]`;
  }
  return `[data-aia="${css(target)}"], [id="${css(target)}"]`;
}

const PLAN_LABELS: Record<string, string> = {
  sets: "Návrh: sledované sady",
  tracked_sets: "Návrh: sledované sady",
  comments: "Návrh: komentáře",
  variants: "Návrh: varianty výzkumu",
  questions: "Návrh: otázky k doplnění",
  narrative: "Návrh: porozumění zadání",
};

/** An item row's words as a person sees them: without its numbering and icons (aria-hidden), what
 * only a screen reader reads, a save note, or an icon button's name (the row's ×); an inline field's
 * text button keeps its words. */
function visibleWords(row: Element): string {
  const copy = row.cloneNode(true) as Element;
  copy.querySelectorAll("[aria-hidden='true'], .sr-only, [role='status'], button[aria-label]").forEach((n) => n.remove());
  return (copy.textContent ?? "").replace(/\s+/g, " ").trim();
}

/** The kinds whose element is one item of a list, named by an opaque id: labelled by its words. */
const ITEM_KINDS: ReadonlySet<TargetKind> = new Set<TargetKind>(["objective", "rq", "hypothesis", "set", "assumption", "material", "measure", "finding", "claim"]);

/** Each target kind in words (lib/workbench-artifacts.ts TargetKind). */
const KIND_WORDS: Readonly<Record<TargetKind, string>> = {
  brief: "Zadání", objective: "Cíl", material: "Podklad", plan: "Návrh", rq: "Výzkumná otázka",
  hypothesis: "Hypotéza", set: "Sada", assumption: "Předpoklad", section: "Oddíl", question: "Otázka",
  audience: "Cílová skupina", dimension: "Dimenze", own_dimension: "Vlastní dimenze", sample: "Vzorek",
  step: "Krok", receipt: "Kdo odpovídal", measure: "Měření", object: "Objekt", pair: "Dvojice", module: "Modul",
  finding: "Zjištění", claim: "Tvrzení", report: "Zpráva",
};

const AUDIENCE_PARTS: Readonly<Record<string, string>> = {
  definition: "Cílová skupina: popis", filters: "Cílová skupina: filtry", preview: "Cílová skupina: náhled",
};

/** A Lead target in words, for a link that shows it: never the raw code when its kind is known. */
export function targetLabel(target: string): string {
  const [kind, ...rest] = target.split(":");
  const id = rest.join(":");
  if (!id) return target;
  if (kind === "question") return `Otázka ${id}`;
  if (kind === "section") return `Oddíl ${id}`;
  if (kind === "brief") return `Zadání: ${id}`;
  if (kind === "plan") return PLAN_LABELS[id] ?? "Návrh";
  const parsed = parseAiaId(target);
  if (!parsed) return target;
  if (parsed.kind === "audience") {
    // Read by Cílová skupina's own contract (artifact-audience AUD1), never a second parser here.
    const t = parseAudienceId(target);
    if (t?.kind === "filter") return `Filtr: ${t.factor}`;
    if (t?.kind === "subpanel") return `Podpanel: ${t.key}`;
    return t ? AUDIENCE_PARTS[t.part] : `Cílová skupina: ${id}`;
  }
  if (parsed.kind === "receipt" && id === "respondents") return "Kdo odpovídal";
  return `${KIND_WORDS[parsed.kind]} ${id}`;
}

/** A section card's title: its heading, else its first field (Dotazník edits a block's or a set's
 * title in place, as an input), else its id. */
function titleOf(card: Element, id: string): string {
  const heading = card.querySelector("h3, h2")?.textContent?.trim();
  if (heading) return heading;
  const field = card.querySelector('input:not([type="checkbox"]):not([type="radio"]), textarea');
  const value = field && "value" in field && typeof field.value === "string" ? field.value.trim() : "";
  return value || id;
}

/** A question card's wording: its first field's value, else the card's text. */
function wordingOf(card: Element, text: string): string {
  const field = card.querySelector("textarea, input");
  return field && "value" in field && typeof field.value === "string" && field.value.trim() ? field.value : text;
}

/**
 * The Lead target an element of a stage screen stands for: the reverse of focusSelector, for the
 * person pointing at what they mean. Walks up from the clicked element to the nearest one the
 * stage screens identify; null when the click was on nothing the Lead can name.
 */
export function targetOfElement(el: Element | null): { id: string; label: string } | null {
  for (let at: Element | null = el; at; at = at.parentElement) {
    const id = at.getAttribute("id") ?? "";
    const text = (at.textContent ?? "").replace(/\s+/g, " ").trim();
    const label = (s: string) => (s.length > 60 ? `${s.slice(0, 57)}…` : s);
    // An element a screen marked for the Lead (data-aia="<kind>:<id>", aiaId) names itself.
    const aia = at.getAttribute("data-aia");
    const parsed = aia ? parseAiaId(aia) : null;
    // A question keeps its wording as its label, a section its title: a card's first heading can
    // be a part of it (the research-question legend), never what the person pointed at.
    if (aia && parsed?.kind === "question") return { id: aia, label: `Otázka ${parsed.id}: ${label(wordingOf(at, text))}` };
    if (aia && parsed?.kind === "section") {
      return { id: aia, label: `Oddíl: ${label(titleOf(at, parsed.id))}` };
    }
    if (aia && parsed) {
      const heading = at.querySelector("h2, h3, h4, label, legend")?.textContent?.trim();
      if (heading) return { id: aia, label: `${targetLabel(aia)}: ${label(heading)}` };
      // An item row (an objective, a hypothesis, a finding) has no heading: its own words name it,
      // never its opaque id (Zadání and Návrh, workbench audit 2026-10-22).
      const words = ITEM_KINDS.has(parsed.kind) ? visibleWords(at) : "";
      if (words) return { id: aia, label: `${KIND_WORDS[parsed.kind]}: ${label(words)}` };
      return { id: aia, label: targetLabel(aia) };
    }
    let m: RegExpMatchArray | null;
    // A questionnaire card before its screen marks it (#607): named by its DOM id, but only an id
    // the contract can send. The ids the screen invents for a card without one are never a
    // target: questionElementId's placeholder `Q`, a block's index, an id outside the grammar.
    // A card whose id another card already carries as its mark is a duplicate (#607 marks the
    // first only): it names nothing, never the first card's target with its own wording.
    // The ids are the contract's (parseAiaId: no quote), so they sit in the selector as they are.
    const marked = (target: string) => !!at.ownerDocument.querySelector(`[data-aia="${target}"]`);
    if ((m = id.match(/^qedit_(.+)$/)) && m[1] !== "Q" && parseAiaId(`question:${m[1]}`)) {
      if (marked(`question:${m[1]}`)) return null;
      return { id: `question:${m[1]}`, label: `Otázka ${m[1]}: ${label(wordingOf(at, text))}` };
    }
    if ((m = id.match(/^qblock_(.+)$/)) && !/^\d+$/.test(m[1]!) && parseAiaId(`section:${m[1]}`)) {
      if (marked(`section:${m[1]}`)) return null;
      return { id: `section:${m[1]}`, label: `Oddíl: ${label(titleOf(at, m[1]!))}` };
    }
    if ((m = id.match(/^brief-(.+)$/))) return { id: `brief:${m[1]}`, label: `Zadání: ${label(at.querySelector("h2, h3, label")?.textContent?.trim() || m[1]!)}` };
    const plan: Record<string, { id: string; label: string }> = {
      "plan-sets": { id: "plan:sets", label: "Návrh: sledované sady" },
      "plan-comments": { id: "plan:comments", label: "Návrh: komentáře" },
      "plan-variants": { id: "plan:variants", label: "Návrh: varianty výzkumu" },
      "plan-questions": { id: "plan:questions", label: "Návrh: otázky k doplnění" },
      "plan-understanding": { id: "plan:narrative", label: "Návrh: porozumění zadání" },
    };
    if (plan[id]) return plan[id]!;
  }
  return null;
}

// --------------------------------------------------------------------------- automatic text edits

/** The `set_text` fields whose edit changes their wording alone (the server's `TEXT_ONLY_FIELDS`). */
export const TEXT_ONLY_FIELDS: ReadonlySet<TextField> = new Set<TextField>(["title", "plan.problem_summary"]);
/** The plan lists whose items are wording alone (the server's `TEXT_ONLY_LISTS`): not research
 * questions, nor objectives, which are read as research questions where a plan states none. */
export const TEXT_ONLY_LISTS: ReadonlySet<PlanList> = new Set<PlanList>(["plan.hypotheses"]);

/**
 * The edits that change wording only, with no other effect, as the server's `is_text_edit` holds
 * them (domain/research_lead.py): the title or the problem summary, a hypothesis replaced, a question's text with its options left as they are. Anything that adds, removes,
 * re-options or resizes is structure; a brief field is not wording only (its edit drops the
 * analysis), nor a research question or an objective (items and comparisons name them by text). The server
 * refuses any other edit in an automatic accept; this only chooses what to ask.
 */
export function isTextEdit(e: LeadEdit): boolean {
  if (e.op === "set_text") return TEXT_ONLY_FIELDS.has(e.field);
  if (e.op === "list_replace") return TEXT_ONLY_LISTS.has(e.list);
  return e.op === "question_edit" && e.text !== null && e.text !== undefined && (e.options === null || e.options === undefined);
}

/** A finished Lead turn's text edits nobody has decided yet: what an automatic accept asks for. */
export function autoAcceptIndices(t: LeadTurn): number[] {
  if (t.actor !== "lead" || t.status !== "COMPLETED") return [];
  const decided = t.edit_decisions ?? {};
  return (t.output?.edits ?? []).flatMap((e, i) => (isTextEdit(e) && !decided[String(i)] ? [i] : []));
}

/**
 * The turns to accept automatically now: those that finished after the screen first read the
 * conversation (`seen`: the turns already finished then, so opening a study replays nothing) and
 * have not been tried (`tried`), each with its undecided text edits. Off: nothing.
 */
export function autoAcceptPlan(turns: LeadTurn[], on: boolean, seen: ReadonlySet<string>, tried: ReadonlySet<string>): { turnId: string; indices: number[] }[] {
  if (!on) return [];
  return turns.flatMap((t) => {
    if (seen.has(t.turn_id) || tried.has(t.turn_id)) return [];
    const indices = autoAcceptIndices(t);
    return indices.length ? [{ turnId: t.turn_id, indices }] : [];
  });
}

function textOf(c: Content, e: LeadEdit): string | null {
  if (e.op === "question_edit") {
    const at = findQuestion(c.project, e.question_id);
    return at ? String(sections(c.project)[at.si]!.questions![at.qi]!.text ?? "") : null;
  }
  if (e.op === "set_text") return describeEdit(c, e).before ?? "";
  if (e.op === "list_replace") {
    const found = narrativeOf(c)[LIST_KEY[e.list]].find((x) => norm(x) === norm(e.old));
    return found ?? null;
  }
  return null;
}

/**
 * The edit that puts back the wording a text edit replaced, read from the content it was applied
 * to; null when that content no longer held what the edit changes (nothing to put back).
 */
export function textEditInverse(before: Content, e: LeadEdit): LeadEdit | null {
  const old = textOf(before, e);
  if (old === null) return null;
  const why = "Vráceno výzkumníkem: původní znění.";
  if (e.op === "set_text") return { op: "set_text", field: e.field, value: old, why };
  if (e.op === "list_replace") return { op: "list_replace", list: e.list, old: e.value, value: old, why };
  if (e.op === "question_edit") return { op: "question_edit", question_id: e.question_id, text: old, options: null, why };
  return null;
}

/**
 * "Vrátit": the working content with an automatically accepted text edit undone, as the person's own
 * edit -- or why not: the wording is no longer the one the edit wrote (it changed since), so nothing
 * is put back over it.
 */
export function revertTextEdit(now: Content, e: LeadEdit, inverse: LeadEdit): { content: Content } | { refused: string } {
  const current = textOf(now, e.op === "list_replace" ? { ...e, old: e.value } : e);
  const wrote = e.op === "set_text" || e.op === "list_replace" ? e.value : e.op === "question_edit" ? e.text : null;
  if (current === null || wrote === null || norm(current) !== norm(wrote)) {
    return { refused: "Text se mezitím změnil, proto ho nevracím. Upravte ho přímo." };
  }
  return applyLeadEdit(now, inverse);
}

/** A Lead turn's or a refused post's reason code in words, as the pane shows it. A turn parked on
 * the study's budget comes back as `budget_exceeded` (the step's waiting reason, never the status
 * AWAITING_BUDGET); it holds nothing, and it is sent by itself once a person sets or raises the
 * budget (the product owner, 2026-10-21, Q39), so its words say where. A cancelled Lead turn is one
 * a message written before the budget was set superseded: no other path cancels a Lead turn. */
export const LEAD_REASON_WORDS: Readonly<Record<string, string>> = {
  research_lead_unavailable: "Vedoucí výzkumu není v tomto prostředí zapnutý.",
  research_lead_disabled: "Vedoucí výzkumu není v tomto prostředí zapnutý.",
  egress_unclassified_material: "Tuto zprávu zatím nelze poslat modelu: materiál studie není klasifikovaný. Rozhoduje o tom správce AIA.",
  egress_no_approved_route: "Vedoucí výzkumu čeká: pro model AI není schválená trasa.",
  egress_route_not_approved_for_class: "Tuto studii nelze poslat modelu: trasa AI není schválena pro třídu jejích dat.",
  research_lead_unconfigured: "Vedoucí výzkumu čeká: model AI není pro pracovníka nastavený.",
  ai_runtime_unavailable: "Vedoucí výzkumu čeká: AI v tomto prostředí neběží.",
  licence_undetermined: "Tuto studii nelze poslat modelu: licence dat panelu to neumožňuje.",
  lead_context_too_large: "Studie je pro jednu odpověď příliš velká. Zkuste se zeptat na konkrétní část.",
  lead_busy: "Vedoucí ještě odpovídá na předchozí zprávu.",
  lead_not_hatched: "Nejdřív si vylíhněte vlastního Vedoucího výzkumu.",
  stale_card: "Studie se od přípravy této karty změnila; úloha se nespustila.",
  agent_context_too_large: "Studie je pro návrhovou úlohu příliš rozsáhlá (úloha přečte nejvýš 64 KB); nic se nespustilo. Zkraťte přílohy nebo design.",
  budget_exceeded: "Na odpověď nezbývá rozpočet studie. Nastavte ho v Nastavení → Studie a zpráva se odešle sama.",
  reservation_exhausted: "Na odpověď nezbývá rozpočet studie. Nastavte ho v Nastavení → Studie a zpráva se odešle sama.",
  CANCELLED: "Na tuto zprávu Vedoucí neodpověděl zvlášť: přečetl ji s vaší další zprávou.",
};

/** Asked when a card is approved after the design moved past what its turn read (LO10). */
export const STALE_CARD_QUESTION = "Od chvíle, kdy Vedoucí kartu připravil, se studie změnila. Spustit úlohu nad studií, jak je teď?";

export function leadReasonWords(code: string | null | undefined): string {
  return code ? withFixer(LEAD_REASON_WORDS[code] ?? `Vedoucí se zastavil (${code}).`, code) : "Vedoucí se zastavil.";
}

/** Why the Lead's composer is shut, said in its own field, or null while it is open. A disabled
 * field that still reads "Napište Vedoucímu výzkumu…" invites typing it refuses (workbench
 * audit, 2026-10-22). Unknown is said as loading, or as failed after a refused read; never as open. */
export function composerHint(s: { canEdit: boolean; hatched: boolean | undefined; available: boolean | undefined; failed: boolean }): string | null {
  if (!s.canEdit) return "Jen ke čtení: Vedoucímu v této studii psát nemůžete.";
  if (s.hatched === false) return "Nejdřív si vylíhněte svého Vedoucího (výše).";
  if (s.available === false) return "Vedoucí teď neodpovídá: důvod je výše.";
  if (s.hatched === undefined || s.available === undefined) return s.failed ? "Vedoucího se nepodařilo načíst: důvod je výše." : "Načítám Vedoucího…";
  return null;
}
