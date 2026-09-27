// Dotazník, the research flow's third step (ADR 0014, area A4): what the
// classic questionnaire does to the project, ported from the bindings that run
// -- renderQuestionnaire (:341) under its wizard wrapper (:960), the guided
// editor and its handlers, the respondent preview, the XLSX/CSV import, and the
// three AI steps (build, optimise, deep research). Every function is pure and
// returns the next project; the screen hands it to the store with the classic
// save reason. questionnaire.parity.test.ts compares each with the original
// under Node. Survey: .planning/plans/research-flow-rehome.md (PR B).

import { type Boot, type Json, PROVIDER_FORCED, type ResearchProject, defaultsMerge } from "./model";
import type { Analysis } from "./store";

type Obj = { [k: string]: Json };
export type QType = "vyber" | "multi" | "skala" | "otevrena";
export type Question = Obj & {
  id?: string;
  text?: string;
  typ?: string;
  kategorie?: string[];
  volby?: string[];
  skala?: number[];
  popisky_skaly?: string[];
  povolit_nevim?: boolean;
};
export type Section = Obj & {
  id?: string;
  type?: string;
  title?: string;
  purpose?: string;
  questions?: Question[];
  object_family?: string;
  object_type?: string;
  objects?: string[];
  object_question?: string;
  scale?: number[];
  scale_labels?: string[];
  familiarity_required?: boolean;
  output_type?: string;
  visualize?: boolean;
  metadata?: Obj;
};

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T;

export function sections(p: ResearchProject): Section[] {
  return (p.sections || []) as Section[];
}
const withSections = (p: ResearchProject, xs: Section[]): ResearchProject => ({ ...p, sections: xs as Json[] });
/** A copy of the project's sections to edit, as the classic edits PROJECT.sections in place. */
const edit = (p: ResearchProject, f: (xs: Section[]) => void): ResearchProject => {
  const xs = clone(sections(p));
  f(xs);
  return withSections(p, xs);
};

/** questionnaireHasQuestions1789: a regular question somewhere. Tracked sets do not count (OI-52). */
export function questionnaireHasQuestions(p: ResearchProject): boolean {
  return sections(p).some((s) => (s.questions || []).length > 0);
}

/** The guided editor's heading: regular questions, and tracked sets. */
export function questionnaireCounts(p: ResearchProject): { questions: number; sets: number } {
  const xs = sections(p);
  return {
    questions: xs.reduce((n, x) => n + (x.type === "questions" ? (x.questions || []).length : 0), 0),
    sets: xs.filter((x) => x.type === "object_battery").length,
  };
}

export type QuestionnairePath = "choose" | "upload" | "manual" | "ai";
export type QuestionnaireView = "choose" | "upload" | "ai" | "editor";

/** Which screen renderQuestionnaire draws for the project's path. */
export function questionnaireView(p: ResearchProject): QuestionnaireView {
  const path = String(p.ui_state?.questionnaire_path || "choose");
  if (path === "choose") return "choose";
  if (path === "upload") return "upload";
  if (path === "ai" && !sections(p).length) return "ai";
  return "editor";
}

/** setQuestionnairePath (save 'questionnaire_path', the run check kept). */
export function setQuestionnairePath(p: ResearchProject, x: QuestionnairePath): ResearchProject {
  return { ...p, ui_state: { ...p.ui_state, questionnaire_path: x } };
}

// ---- the respondent preview ------------------------------------------------

export type PreviewItem =
  | { kind: "question"; index: number; text: string; typ: string; options: string[]; scale: [string, string] | null }
  | { kind: "battery"; index: number; title: string; rows: string[]; low: string; high: string };

/** questionnaireRespondentPreview1780: the first fourteen items as a respondent sees them. */
export function respondentPreview(p: ResearchProject): PreviewItem[] {
  const parts: PreviewItem[] = [];
  let i = 1;
  for (const sec of sections(p)) {
    if (sec.type === "questions") {
      for (const q of sec.questions || []) {
        parts.push(previewQuestion(q, i++));
        if (parts.length >= 14) break;
      }
    } else if (sec.type === "object_battery") parts.push(previewBattery(sec, i++));
    if (parts.length >= 14) break;
  }
  return parts;
}

/** previewQuestion1780 */
export function previewQuestion(q: Question, index: number): PreviewItem {
  const typ = String(q?.typ || "vyber");
  let options: string[] = [];
  let scale: [string, string] | null = null;
  if (typ === "vyber" || typ === "multi") options = (q.kategorie || q.volby || []).slice(0, 8).map(String);
  else if (typ === "skala") {
    const sc = q.skala || [1, 10];
    const lb = q.popisky_skaly || ["vůbec", "zcela"];
    scale = [String(lb[0] || sc[0]), String(lb[1] || sc[1])];
  }
  return { kind: "question", index, text: String(q.text || "Bez znění"), typ, options, scale };
}

/** previewObjectBattery1780: eight object rows, the first {object} filled. */
export function previewBattery(sec: Section, index: number): PreviewItem {
  const tmpl = String(sec.object_question || "Jak hodnotíte {object}?");
  const lb = sec.scale_labels || ["vůbec", "velmi"];
  return {
    kind: "battery",
    index,
    title: String(sec.title || sec.object_type || "Objekty"),
    rows: (sec.objects || []).slice(0, 8).map((x) => tmpl.replace("{object}", x)),
    low: String(lb[0]),
    high: String(lb[1]),
  };
}

// ---- ids ------------------------------------------------------------------

export type IdSource = { now: () => number; random: () => number };
const SYSTEM: IdSource = { now: Date.now, random: Math.random };
/** secId */
export const secId = (s: IdSource = SYSTEM) => `sec_${s.now().toString(36)}${s.random().toString(36).slice(2, 5)}`;
/** qId */
export const qId = (s: IdSource = SYSTEM) => `Q_${s.now().toString(36)}${s.random().toString(36).slice(2, 4)}`;

// ---- the guided editor ------------------------------------------------------

export type GuidedKind = "choice" | "scale" | "open";
export const GUIDED_PROMPT: Record<GuidedKind, string> = {
  scale: "Co chcete změřit na škále 1–10?",
  open: "Na co se chcete zeptat otevřeně?",
  choice: "Jak zní otázka?",
};
export const PROMPT_CHOICES = "Odpovědi oddělte čárkou. Pokud necháte prázdné, použije se Ano / Ne.";
export const PROMPT_CHOICES_DEFAULT = "Ano, Ne";

/**
 * addGuidedQuestion: the question the kind asks for, into the first question
 * block (made as "Hlavní otázky" if there is none). `choices` is the second
 * prompt's answer for a choice question (cancelled: the default).
 */
export function addGuidedQuestion(
  p: ResearchProject,
  kind: GuidedKind,
  text: string | null,
  choices: string | null,
  ids: IdSource = SYSTEM,
): { project: ResearchProject; questionId: string } | null {
  if (!text?.trim()) return null;
  const xs = clone(sections(p));
  let sec = xs.find((x) => x.type === "questions");
  if (!sec) {
    sec = { id: secId(ids), type: "questions", title: "Hlavní otázky", purpose: "", questions: [] };
    xs.push(sec);
  }
  sec.questions = sec.questions || [];
  let q: Question = { id: qId(ids), text: text.trim(), typ: "vyber", kategorie: ["Ano", "Ne"], povolit_nevim: false };
  if (kind === "scale") q = { id: qId(ids), text: text.trim(), typ: "skala", skala: [1, 10], popisky_skaly: ["vůbec", "zcela"], povolit_nevim: false };
  if (kind === "open") q = { id: qId(ids), text: text.trim(), typ: "otevrena", povolit_nevim: false };
  if (kind === "choice") q.kategorie = (choices || PROMPT_CHOICES_DEFAULT).split(",").map((x) => x.trim()).filter(Boolean);
  sec.questions.push(q);
  return { project: withSections(p, xs), questionId: String(q.id) };
}

/** addQuestion */
export function addQuestion(p: ResearchProject, si: number, ids: IdSource = SYSTEM): ResearchProject {
  return edit(p, (xs) => {
    xs[si].questions = [...(xs[si].questions || []), { id: qId(ids), text: "Nová otázka?", typ: "vyber", kategorie: ["Ano", "Ne"], povolit_nevim: false }];
  });
}

/** removeQuestion (no confirm, as the classic) */
export function removeQuestion(p: ResearchProject, si: number, qi: number): ResearchProject {
  return edit(p, (xs) => {
    xs[si].questions = (xs[si].questions || []).filter((_, i) => i !== qi);
  });
}

/** changeQType: a choice gets Ano / Ne if it has no options; a scale gets 1–10 and its ends. */
export function changeQType(p: ResearchProject, si: number, qi: number, t: string): ResearchProject {
  return edit(p, (xs) => {
    const q = (xs[si].questions || [])[qi];
    q.typ = t;
    if ((t === "vyber" || t === "multi") && !(q.kategorie || []).length) q.kategorie = ["Ano", "Ne"];
    if (t === "skala") {
      q.skala = q.skala || [1, 10];
      q.popisky_skaly = q.popisky_skaly || ["vůbec", "zcela"];
    }
  });
}

export function setQuestionText(p: ResearchProject, si: number, qi: number, text: string): ResearchProject {
  return edit(p, (xs) => {
    (xs[si].questions || [])[qi].text = text;
  });
}

/** The options textarea's change: one per line, trimmed, empty lines dropped. */
export function setQuestionOptions(p: ResearchProject, si: number, qi: number, raw: string): ResearchProject {
  return edit(p, (xs) => {
    (xs[si].questions || [])[qi].kategorie = raw.split(/\n/).map((x) => x.trim()).filter(Boolean);
  });
}

/** The scale's minimum / maximum inputs: `+value`, the other end kept or defaulted (1, 10). */
export function setScaleEnd(p: ResearchProject, si: number, qi: number, end: 0 | 1, raw: string): ResearchProject {
  return edit(p, (xs) => {
    const q = (xs[si].questions || [])[qi];
    q.skala = end === 0 ? [+raw, q.skala?.[1] || 10] : [q.skala?.[0] || 1, +raw];
  });
}

/** setScaleLabel */
export function setScaleLabel(p: ResearchProject, si: number, qi: number, i: 0 | 1, v: string): ResearchProject {
  return edit(p, (xs) => {
    const q = (xs[si].questions || [])[qi];
    q.popisky_skaly = [...(q.popisky_skaly || ["vůbec", "zcela"])];
    q.popisky_skaly[i] = v;
  });
}

/** addQuestionSection */
export function addQuestionSection(p: ResearchProject, ids: IdSource = SYSTEM): ResearchProject {
  return withSections(p, [...sections(p), { id: secId(ids), type: "questions", title: "Nový blok", purpose: "", questions: [] }]);
}

export const PROMPT_SET_TYPE = "Jaký typ položek chcete porovnávat? Např. média, emoce, značky, atributy:";
export const PROMPT_SET_ITEMS = "Zadejte 4–15 srovnatelných položek oddělených čárkou:";
export const SET_SIZE = "Sledovaná sada musí mít 4–15 srovnatelných položek.";

/** addTrackedSet: a type and 4–15 items, else nothing (cancelled) or the classic alert. */
export function addTrackedSet(
  p: ResearchProject,
  typ: string | null,
  raw: string | null,
  ids: IdSource = SYSTEM,
): { project: ResearchProject } | { error: string } | null {
  if (!typ || !raw) return null;
  const objs = raw.split(",").map((x) => x.trim()).filter(Boolean);
  if (objs.length < 4 || objs.length > 15) return { error: SET_SIZE };
  const set: Section = {
    id: secId(ids),
    type: "object_battery",
    title: `Sledovaná sada — ${typ}`,
    purpose: "",
    object_family: typ,
    object_type: typ,
    objects: objs,
    object_question: "Jak hodnotíte {object}?",
    scale: [1, 10],
    scale_labels: ["vůbec", "velmi"],
    familiarity_required: false,
    output_type: "pozicni_mapa",
    visualize: true,
    metadata: { tracked_set: true },
  };
  return { project: withSections(p, [...sections(p), set]) };
}

export const CONFIRM_REMOVE_SECTION = "Smazat celý blok?";

/** removeSection (after its confirm) */
export function removeSection(p: ResearchProject, si: number): ResearchProject {
  return withSections(p, sections(p).filter((_, i) => i !== si));
}

export type SectionField = "title" | "purpose" | "object_question" | "familiarity_required";

/** The section card's inline edits. */
export function setSectionField(p: ResearchProject, si: number, field: SectionField, value: string | boolean): ResearchProject {
  return edit(p, (xs) => {
    (xs[si] as Obj)[field] = value;
  });
}

/** The object type field writes both names, as the classic does. */
export function setObjectFamily(p: ResearchProject, si: number, v: string): ResearchProject {
  return edit(p, (xs) => {
    xs[si].object_family = v;
    xs[si].object_type = v;
  });
}

export const SET_TOO_SMALL = "Sledovaná sada potřebuje 4–15 položek.";

/** updateObjects: one per line, trimmed, fifteen at most; a note (not a refusal) under four. */
export function updateObjects(p: ResearchProject, si: number, v: string): { project: ResearchProject; note: string | null } {
  const a = v.split(/\n/).map((x) => x.trim()).filter(Boolean).slice(0, 15);
  return {
    project: edit(p, (xs) => {
      xs[si].objects = a;
    }),
    note: a.length && a.length < 4 ? SET_TOO_SMALL : null,
  };
}

/** setObjLabel */
export function setObjectLabel(p: ResearchProject, si: number, i: 0 | 1, v: string): ResearchProject {
  return edit(p, (xs) => {
    const s = xs[si];
    s.scale_labels = [...(s.scale_labels || ["vůbec", "velmi"])];
    s.scale_labels[i] = v;
  });
}

/** setPriceBands: comma or line separated, as the person typed them (the AI may not invent prices). */
export function setPriceBands(p: ResearchProject, si: number, v: string): ResearchProject {
  return edit(p, (xs) => {
    const s = xs[si];
    s.metadata = { ...(s.metadata || {}), price_bands: String(v || "").split(/[,\n]/).map((x) => x.trim()).filter(Boolean) };
  });
}

// ---- import and the AI steps ----------------------------------------------

export const UPLOAD_NO_FILE = "Vyberte XLSX nebo CSV.";
export const UPLOAD_TIMEOUT_MS = 180_000;

/** uploadQuestionnaireFile, after the unit parsed the file: its project, on the editor. */
export function applyImport(result: unknown, boot: Boot): { project: ResearchProject; toast: string } {
  const r = (result || {}) as { project?: unknown; summary?: { question_count?: unknown; tracked_sets?: unknown } };
  const project = defaultsMerge(r.project, boot);
  project.ui_state.questionnaire_path = "manual";
  return { project, toast: `Načteno: ${r.summary?.question_count} otázek · ${r.summary?.tracked_sets} sledovaných sad` };
}

export const BUILD_TITLE = "AI tvoří dotazník";
export const BUILD_WARN_MS = 50_000;
export const BUILD_FAILED_SUFFIX = "\n\nProjekt zůstává uložený. Pokud se chyba opakuje, použijte Diagnostiku.";

/** buildQuestionnaire's body for /api/research/build_questionnaire. */
export function buildPayload(p: ResearchProject, analysis: Analysis | null): Record<string, unknown> {
  return {
    analysis,
    briefing: { ...p.briefing, goal: p.goal, decision_use: p.decision_use },
    project: p,
    n: p.n,
    model: "sonnet",
    provider: PROVIDER_FORCED,
  };
}

/** What buildQuestionnaire does with the job's result: the AI's project, whole, on the editor. */
export function applyBuilt(result: unknown, boot: Boot): ResearchProject {
  const r = (result || {}) as { project?: unknown };
  const project = defaultsMerge(r.project, boot);
  project.run_policy = { ...(project.run_policy || {}), provider: PROVIDER_FORCED, allow_provider_fallback: false };
  project.ui_state = { ...(project.ui_state || {}), questionnaire_path: "manual" };
  return project;
}

export const OPTIMIZE_TITLE = "Hloubkový research + optimalizace dotazníku";
export const OPTIMIZE_DONE = "Dotazník byl optimalizován s Evidence Packem";

/** optimizeQuestionnaireAI's body for /api/questionnaire/optimize. */
export function optimizePayload(p: ResearchProject): Record<string, unknown> {
  return { project: p, research: p.pre_research || null, provider: PROVIDER_FORCED, model: p.model };
}

/** What optimizeQuestionnaireAI keeps: the project, the research if returned, the analysis if returned. */
export function applyOptimized(result: unknown, analysis: Analysis | null, boot: Boot): { project: ResearchProject; analysis: Analysis | null } {
  const r = (result || {}) as { project?: unknown; research?: Json; analysis?: Analysis };
  const project = defaultsMerge(r.project, boot);
  if (r.research) project.pre_research = r.research;
  project.ui_state.questionnaire_path = "manual";
  return { project, analysis: r.analysis || analysis };
}

export const DEEP_TITLE = "Hloubkový research · ČR + zahraničí + studie";

/** runProjectDeepResearch's body for /api/research/deep. */
export function deepPayload(p: ResearchProject): Record<string, unknown> {
  return { project: p, provider: PROVIDER_FORCED, model: p.model };
}

/** What runProjectDeepResearch keeps, and what it says. */
export function applyDeep(p: ResearchProject, result: unknown): { project: ResearchProject; toast: string } {
  const r = (result || {}) as { research?: Json; accepted_count?: number; quarantined_count?: number };
  return {
    project: { ...p, pre_research: r.research || {} },
    toast: `Research uložen · ${r.accepted_count || 0} evidencí · ${r.quarantined_count || 0} v karanténě`,
  };
}

/** The evidence the project's research accepted (pre_research.accepted). */
export function researchCount(p: ResearchProject): number {
  const r = p.pre_research as { accepted?: unknown[] } | undefined;
  return (r?.accepted || []).length;
}

/** continueQuestionnaireToAudience: the audience starts at its first choice unless already chosen. */
export function toAudience(p: ResearchProject): ResearchProject {
  return { ...p, ui_state: { ...p.ui_state, audience_entry: p.ui_state?.audience_entry || "choose" } };
}
