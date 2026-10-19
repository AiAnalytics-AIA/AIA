// The Research Lead as the web reads it (ADR 0026): its turns, its closed output, and the pure
// part of its edit tools. An edit is applied only when the person accepts its change block, to
// the working copy, through the same helpers the stages use (editBrief, applyNarrative, the
// questionnaire's own edits), and saved as that person's edit (reason "lead_edit_accepted").
// Nothing here calls a model or the API.

import { editBrief, type BriefingField, type TopField } from "@/research/brief";
import type { ResearchProject } from "@/research/model";
import { applyNarrative, proposalAnalysis, type Narrative } from "@/research/plan-edit";
import { qId, sections, type Question, type Section } from "@/research/questionnaire";
import type { Analysis } from "@/research/store";
import type { WorkbenchStage } from "./workbench-stages";

export const LEAD_EDIT_REASON = "lead_edit_accepted";

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
  edit_decisions?: Record<string, { status: "accepted" | "dismissed" | "refused"; reason: string | null }>;
  /** The person's approval of this turn's paid request, when given. */
  request_decision?: { status: "approved"; run_id: string } | null;
  /**
   * The researcher's decision on what the turn wanted to keep for all of their work (a personal
   * note, a SOUL, USER or name change), from the approval ledger. Only what stays inside the
   * study's client applies with the turn; the rest waits for this (Codex on #484).
   */
  self_update_decision?: { status: "accepted" | "dismissed" } | null;
  /** Whether such a self-update waits for the researcher's decision. */
  self_update_pending?: boolean;
};

export type SelfUpdateDecision = { status: "accepted" | "dismissed"; changes: Record<string, unknown> | null };

/** What of a self-update waits for the researcher: personal notes and file changes, in words. */
export function pendingSelfUpdate(u: LeadSelfUpdate | null | undefined): { notes: string[]; files: { file: string; text: string }[] } {
  if (!u) return { notes: [], files: [] };
  const files: { file: string; text: string }[] = [];
  if (u.name) files.push({ file: "Jméno", text: u.name });
  if (u.soul) files.push({ file: "SOUL", text: u.soul });
  if (u.user) files.push({ file: "USER", text: u.user });
  return { notes: (u.remember ?? []).filter((m) => m.scope === "personal").map((m) => m.text), files };
}

export type EditDecisionResult = { workspace_revision: number | null; results: { index: number; status: "accepted" | "dismissed" | "refused"; reason: string | null }[] };
export type RequestApproval = { run_id: string; design_revision_id: string; status: string };

export type LeadState = { available: boolean; unavailable_reason: string | null; busy: boolean; turns: LeadTurn[] };

export type LeadMemory = { memory_id: string; scope: "personal" | "client"; client_id: string | null; client_name?: string | null; text: string; created_at: string; source_turn_id: string | null };
export type ResearcherLead = {
  hatched: boolean;
  lead: { lead_id: string; name: string; hatched_at: string; updated_at: string; files: { soul: string; user: string }; memories: LeadMemory[] } | null;
};

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

function findQuestion(p: ResearchProject, id: string): { si: number; qi: number } | null {
  const xs = sections(p);
  for (let si = 0; si < xs.length; si++) {
    const qi = (xs[si]!.questions || []).findIndex((q) => q.id === id);
    if (qi >= 0) return { si, qi };
  }
  return null;
}

const withSections = (p: ResearchProject, xs: Section[]): ResearchProject => ({ ...p, sections: xs as ResearchProject["sections"] });
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T;

function questionFor(text: string, qtype: QType, options: string[], id: string): Question {
  if (qtype === "skala") return { id, text, typ: "skala", skala: [1, 10], popisky_skaly: options.length === 2 ? options : ["vůbec", "zcela"], povolit_nevim: false };
  if (qtype === "otevrena") return { id, text, typ: "otevrena", povolit_nevim: false };
  return { id, text, typ: qtype, kategorie: options.length ? options : ["Ano", "Ne"], povolit_nevim: false };
}

/**
 * The working content with one edit applied, or the reason it no longer applies: the item it
 * names is gone or changed since the Lead read it. Never a guess: an edit that does not fit is
 * refused, not bent to fit.
 */
export function applyLeadEdit(c: Content, e: LeadEdit, newId: () => string = () => qId()): { content: Content } | { refused: string } {
  switch (e.op) {
    case "set_text": {
      if (e.field === "plan.problem_summary") {
        const s = applyNarrative(c, { ...narrativeOf(c), problem_summary: e.value });
        return { content: { project: s.project, analysis: s.analysis } };
      }
      const field = (e.field.startsWith("briefing.") ? e.field.slice("briefing.".length) : e.field) as TopField | BriefingField;
      const r = editBrief(c.project, c.analysis, field, e.value);
      return { content: { project: r.project, analysis: r.analysis } };
    }
    case "list_add":
    case "list_replace":
    case "list_remove": {
      const n = narrativeOf(c);
      const key = LIST_KEY[e.list];
      const items = [...n[key]];
      if (e.op === "list_add") {
        if (items.some((x) => norm(x) === norm(e.value))) return { refused: "Položka už v seznamu je." };
        items.push(e.value.trim());
      } else {
        const i = items.findIndex((x) => norm(x) === norm(e.old));
        if (i < 0) return { refused: "Položka, kterou návrh mění, už v seznamu není." };
        if (e.op === "list_replace") items[i] = e.value.trim();
        else items.splice(i, 1);
      }
      const s = applyNarrative(c, { ...n, [key]: items });
      return { content: { project: s.project, analysis: s.analysis } };
    }
    case "question_add": {
      const xs = clone(sections(c.project));
      let sec = e.section_id ? xs.find((s) => s.id === e.section_id && s.type === "questions") : xs.find((s) => s.type === "questions");
      if (e.section_id && !sec) return { refused: "Oddíl, do kterého návrh přidává, už v dotazníku není." };
      if (!sec) {
        sec = { id: `sec_${newId().slice(2)}`, type: "questions", title: "Hlavní otázky", purpose: "", questions: [] };
        xs.push(sec);
      }
      sec.questions = [...(sec.questions || []), questionFor(e.text.trim(), e.qtype, e.options, newId())];
      return { content: { project: withSections(c.project, xs), analysis: c.analysis } };
    }
    case "question_edit":
    case "question_remove": {
      const at = findQuestion(c.project, e.question_id);
      if (!at) return { refused: "Otázka, kterou návrh mění, už v dotazníku není." };
      const xs = clone(sections(c.project));
      const qs = xs[at.si]!.questions || [];
      if (e.op === "question_remove") qs.splice(at.qi, 1);
      else {
        const q = qs[at.qi]!;
        if (e.text !== null) q.text = e.text;
        if (e.options !== null && (q.typ === "vyber" || q.typ === "multi")) q.kategorie = e.options;
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
  if (kind === "question" && id) return `[id="qedit_${css(id)}"]`;
  if (kind === "section" && id) return `[id="qblock_${css(id)}"]`;
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

/** A Lead target in words, for a link that shows it: never the raw code when its kind is known. */
export function targetLabel(target: string): string {
  const [kind, ...rest] = target.split(":");
  const id = rest.join(":");
  if (!id) return target;
  if (kind === "question") return `Otázka ${id}`;
  if (kind === "section") return `Oddíl ${id}`;
  if (kind === "brief") return `Zadání: ${id}`;
  if (kind === "plan") return PLAN_LABELS[id] ?? "Návrh";
  return target;
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
    let m: RegExpMatchArray | null;
    if ((m = id.match(/^qedit_(.+)$/))) {
      const field = at.querySelector("textarea, input");
      const wording = field && "value" in field && typeof field.value === "string" && field.value.trim() ? field.value : text;
      return { id: `question:${m[1]}`, label: `Otázka ${m[1]}: ${label(wording)}` };
    }
    if ((m = id.match(/^qblock_(.+)$/))) return { id: `section:${m[1]}`, label: `Oddíl: ${label(at.querySelector("h3, h2")?.textContent?.trim() || m[1]!)}` };
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
