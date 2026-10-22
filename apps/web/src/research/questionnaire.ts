// Dotazník, the research flow's third step (ADR 0014, area A4): what the
// classic questionnaire does to the project, ported from the bindings that run
// -- renderQuestionnaire (:341) under its wizard wrapper (:960), the guided
// editor and its handlers, the respondent preview, the XLSX/CSV import, and the
// three AI steps (build, optimise, deep research). Every function is pure and
// returns the next project; the screen hands it to the store with the classic
// save reason. questionnaire.parity.test.ts compares each with the original
// under Node. Survey: .planning/plans/research-flow-rehome.md (PR B).

import { tv } from "@/i18n/t";

import { type Template, type Json, PROVIDER_FORCED, type ResearchProject, defaultsMerge } from "./model";
import { keepPointLabels } from "./scale-labels";
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

/** A Czech count of `kind`, the word by its number: 1 otázka, 2–4 otázky, 0 and 5+ otázek. */
export function countWords(kind: "questions" | "sets", n: number): string {
  const form = n === 1 ? "one" : n >= 2 && n <= 4 ? "few" : "many";
  return tv(`research.questionnaire.countWords.${kind}.${form}`, { n });
}

/** The questionnaire's counts in words: "4 otázky · 1 sledovaná sada". */
export function countsWords(c: { questions: number; sets: number }): string {
  return tv("research.questionnaire.editorCounts", { questions: countWords("questions", c.questions), sets: countWords("sets", c.sets) });
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
    // A scale labelled on every point shows its first and last label as its ends (#559); two
    // labels or fewer read as previewQuestion1780 read them.
    const high = lb.length > 2 ? lb[lb.length - 1] : lb[1];
    scale = [String(lb[0] || sc[0]), String(high || sc[1])];
  }
  return { kind: "question", index, text: String(q.text || "Bez znění"), typ, options, scale };
}

/** previewObjectBattery1780: eight object rows, the first {object} filled. */
export function previewBattery(sec: Section, index: number): PreviewItem {
  const tmpl = String(sec.object_question || "Jak hodnotíte {object}?");
  const lb = sec.scale_labels || ["vůbec", "velmi"];
  // A set labelled on every point shows its first and last label as its ends (#559).
  const high = lb.length > 2 ? lb[lb.length - 1] : lb[1];
  return {
    kind: "battery",
    index,
    title: String(sec.title || sec.object_type || "Objekty"),
    rows: (sec.objects || []).slice(0, 8).map((x) => tmpl.replace("{object}", x)),
    low: String(lb[0]),
    high: String(high),
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

/**
 * A question's display condition (`filtr`): who is asked it. AIA cannot yet ask a question only of
 * those it is meant for, so the run refuses one: readiness fails a condition compile cannot read
 * or check by name at its question (domain/research_design.py read_condition, condition:<id>), and
 * a valid one too (conditional_questions); null when the question has none. A condition of only whitespace, or
 * an empty one, is none, as the server reads it. Shown here as stored, never interpreted.
 */
export function questionCondition(q: Question): string | null {
  const raw = q.filtr;
  if (raw === null || raw === undefined) return null;
  const text = (typeof raw === "string" ? raw : JSON.stringify(raw)).trim();
  return text ? text : null;
}

/** The question asked of everyone: its condition removed, nothing else changed (PC15). */
export function removeCondition(p: ResearchProject, si: number, qi: number): ResearchProject {
  return edit(p, (xs) => {
    delete (xs[si].questions || [])[qi].filtr;
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

/**
 * The scale editor's write (input-interactions 3b2): a question's range and its labels, the two
 * ends or one per point, together, as `ScaleEditor` decided them. The range is whole numbers,
 * low < high (`scale-labels.ts` `readRange`); the classic `setScaleEnd` (`+raw`) stays for the
 * parity tests and no screen calls it.
 */
export function setQuestionScale(p: ResearchProject, si: number, qi: number, scale: readonly [number, number], labels: readonly string[]): ResearchProject {
  return edit(p, (xs) => {
    const q = (xs[si].questions || [])[qi];
    q.skala = [scale[0], scale[1]];
    q.popisky_skaly = [...labels];
  });
}

/** A tracked set's labels from the scale editor: its two ends (the set's range is not edited). */
export function setSetScaleLabels(p: ResearchProject, si: number, labels: readonly string[]): ResearchProject {
  return edit(p, (xs) => {
    xs[si].scale_labels = [...labels];
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
  if (objs.length < SET_MIN || objs.length > SET_MAX) return { error: SET_SIZE };
  return { project: withSections(p, [...sections(p), trackedSet(typ, objs, ids)]) };
}

/** The tracked set addTrackedSet makes: the classic's defaults, its family and objects. */
function trackedSet(typ: string, objects: string[], ids: IdSource): Section {
  return {
    id: secId(ids),
    type: "object_battery",
    title: `Sledovaná sada — ${typ}`,
    purpose: "",
    object_family: typ,
    object_type: typ,
    objects,
    object_question: "Jak hodnotíte {object}?",
    scale: [1, 10],
    scale_labels: ["vůbec", "velmi"],
    familiarity_required: false,
    output_type: "pozicni_mapa",
    visualize: true,
    metadata: { tracked_set: true },
  };
}

/**
 * A new block named as the person typed it in its row (input-interactions I5, audit A21), instead
 * of "Nový blok" to be renamed afterwards. Null for an empty name.
 */
export function addNamedSection(p: ResearchProject, title: string, ids: IdSource = SYSTEM): { project: ResearchProject; sectionId: string } | null {
  const name = title.trim();
  if (!name) return null;
  const id = secId(ids);
  return { project: withSections(p, [...sections(p), { id, type: "questions", title: name, purpose: "", questions: [] }]), sectionId: id };
}

/**
 * Where a section a screen drew stands in the copy now: found by its id, or, for an older section
 * without one, at its index while that place still holds an id-less section; -1 when it is gone (a
 * remove, or the copy reloaded under the screen).
 */
function sectionNow(xs: Section[], si: number, sectionId: string | undefined): number {
  return sectionId ? xs.findIndex((x) => x.id === sectionId) : si < xs.length && !xs[si].id ? si : -1;
}

/**
 * A question with its wording typed in the block's own row (audit A5): a single choice with the
 * options Ano / Ne, as addQuestion and the quick add give it. Null for an empty wording or a block
 * that is gone or no longer a question block; a block with an id never takes another's question.
 */
export function addQuestionTo(p: ResearchProject, si: number, sectionId: string | undefined, text: string, ids: IdSource = SYSTEM): { project: ResearchProject; questionId: string } | null {
  const wording = text.trim();
  const xs = sections(p);
  const at = sectionNow(xs, si, sectionId);
  if (!wording || at < 0 || xs[at].type !== "questions") return null;
  const id = qId(ids);
  const project = edit(p, (ys) => {
    ys[at].questions = [...(ys[at].questions || []), { id, text: wording, typ: "vyber", kategorie: ["Ano", "Ne"], povolit_nevim: false }];
  });
  return { project, questionId: id };
}

/**
 * A tracked set named in its row (audit A8): the same set addTrackedSet makes, with no objects yet.
 * Its 4–15 objects are then added on its card, the count beside them; readiness holds a set
 * outside 4–15, as it holds one made any other way. Null for an empty name.
 */
export function addNamedTrackedSet(p: ResearchProject, typ: string, ids: IdSource = SYSTEM): { project: ResearchProject; sectionId: string } | null {
  const family = typ.trim();
  if (!family) return null;
  const set = trackedSet(family, [], ids);
  return { project: withSections(p, [...sections(p), set]), sectionId: String(set.id) };
}

export const CONFIRM_REMOVE_SECTION = "Smazat celý blok?";

/** removeSection (after its confirm) */
export function removeSection(p: ResearchProject, si: number): ResearchProject {
  return withSections(p, sections(p).filter((_, i) => i !== si));
}

/**
 * An undo of removeSection (input-interactions I6): `sec` put back at `si`, or last when fewer
 * sections remain. Nothing when a section with its id is already there (the undo ran twice).
 */
export function restoreSection(p: ResearchProject, si: number, sec: Section): ResearchProject {
  const xs = sections(p);
  if (sec.id && xs.some((x) => x.id === sec.id)) return p;
  const at = Math.min(Math.max(si, 0), xs.length);
  return withSections(p, [...xs.slice(0, at), clone(sec), ...xs.slice(at)]);
}

/**
 * An undo of removeQuestion: `q` put back at `qi` of its section, found by the section's id (a
 * section without one: by its index while it is still `si`). Nothing when the section is gone, or
 * when a question with its id is already there.
 */
export function restoreQuestion(p: ResearchProject, si: number, sectionId: string | undefined, qi: number, q: Question): ResearchProject {
  const xs = sections(p);
  const at = sectionNow(xs, si, sectionId);
  if (at < 0 || xs[at].type !== "questions") return p;
  const qs = xs[at].questions || [];
  if (q.id && qs.some((x) => x.id === q.id)) return p;
  return edit(p, (ys) => {
    const list = ys[at].questions || [];
    const i = Math.min(Math.max(qi, 0), list.length);
    ys[at].questions = [...list.slice(0, i), clone(q), ...list.slice(i)];
  });
}

/**
 * An undo of an option's removal (input-interactions I6, audit A3): `value` put back at `index` of
 * its question's options, the question found by its section's id and its own (by index only while
 * neither has one). Only on a choice question (no type reads as one, as the compiler reads it);
 * nothing when the question is gone or another type, or the option is already there. Other
 * options edited since are kept as they are.
 */
export function restoreOption(p: ResearchProject, si: number, sectionId: string | undefined, qi: number, questionId: string | undefined, index: number, value: string): ResearchProject {
  const xs = sections(p);
  const at = sectionNow(xs, si, sectionId);
  if (at < 0 || xs[at].type !== "questions") return p;
  const qs = xs[at].questions || [];
  const qat = questionId ? qs.findIndex((x) => x.id === questionId) : qi < qs.length && !qs[qi].id ? qi : -1;
  if (qat < 0 || !["", "vyber", "multi"].includes(String(qs[qat].typ || ""))) return p;
  if ((qs[qat].kategorie || []).includes(value)) return p;
  return edit(p, (ys) => {
    const q = (ys[at].questions || [])[qat];
    const list = q.kategorie || [];
    const i = Math.min(Math.max(index, 0), list.length);
    q.kategorie = [...list.slice(0, i), value, ...list.slice(i)];
  });
}

/**
 * Esc on a question's wording (input-interactions I1, audit A1): what it puts back. `base` is the
 * wording this field's typing started from, `typed` the last value it wrote. A wording changed under
 * the field (a Lead edit, a reload) becomes the new base before the next keystroke, so Esc never
 * puts back anything older than a change accepted from elsewhere.
 */
export type WordingEdit = { base: string; typed: string };
export const wordingFocused = (value: string): WordingEdit => ({ base: value, typed: value });
export function wordingTyped(w: WordingEdit, current: string, next: string): WordingEdit {
  return { base: w.typed === current ? w.base : current, typed: next };
}
/** The wording Esc writes back, or null: nothing typed here, or the copy moved since. */
export function wordingEscape(w: WordingEdit, current: string): string | null {
  return w.typed === current && w.base !== current ? w.base : null;
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

/**
 * A tracked set's sizes as the readiness methodology in force states them (GET …/research/limits
 * tracked_set): the compiler refuses a set outside min-max (battery_size); readiness only warns
 * outside recommended_min-recommended_max. Above the recommendation a set is allowed and warned (the
 * product owner, Q75 (a), 2026-10-22); the editors still refuse one under the recommended minimum.
 */
export type SetLimits = { min: number; max: number; recommended_min: number; recommended_max: number };

/** The code's preset, research_design.py TRACKED_SET_LIMITS (held to it by questionnaire-set-limits.test.ts):
 * what a study runs by while nothing is stored, and what the screens use until the limits are read. */
export const SET_HARD_MIN = 3;
export const SET_HARD_MAX = 40;
export const SET_MIN = 4;
export const SET_MAX = 15;
export const SET_PRESET: SetLimits = { min: SET_HARD_MIN, max: SET_HARD_MAX, recommended_min: SET_MIN, recommended_max: SET_MAX };

/** A set the editors stop: under the recommended minimum, or over the hard maximum. */
export const setSizeRefused = (n: number, l: SetLimits = SET_PRESET) => n < l.recommended_min || n > l.max;
/** Above the recommendation, within the hard range: allowed, warned at the field. */
export const setAboveRecommended = (n: number, l: SetLimits = SET_PRESET) => n > l.recommended_max && n <= l.max;
/** The limits as the copy names them: the editors' range ({min}–{max}) and the recommendation ({rmin}–{rmax}). */
export const setWords = (l: SetLimits) => ({ min: l.recommended_min, max: l.max, rmin: l.recommended_min, rmax: l.recommended_max });

export const SET_TOO_SMALL = "Sledovaná sada potřebuje 4–15 položek.";

/** updateObjects: one per line, trimmed; a note (not a refusal) under four. Unlike the classic's,
 * nothing past the fifteenth is cut: a set may hold up to SET_HARD_MAX. */
export function updateObjects(p: ResearchProject, si: number, v: string): { project: ResearchProject; note: string | null } {
  const a = v.split(/\n/).map((x) => x.trim()).filter(Boolean);
  return {
    project: edit(p, (xs) => {
      xs[si].objects = a;
    }),
    note: a.length && a.length < SET_MIN ? SET_TOO_SMALL : null,
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

/** A concept-test set's price bands, as stored (metadata.price_bands): the person's own words. */
export function priceBandsOf(sec: Section): string[] {
  const raw = sec.metadata?.price_bands;
  return Array.isArray(raw) ? raw.filter((x): x is string => typeof x === "string" && x.trim() !== "").map((x) => x.trim()) : [];
}

/**
 * Why a typed price is not one (input-interactions I9, audit A16), or null: a positive amount with
 * at most two decimals, a space or a non-breaking space between thousands, a decimal comma or dot,
 * and Kč (or CZK, ",-") after it or nothing. Kept as typed when it is one: no prices are invented
 * or rewritten here, only refused at the field.
 */
export function priceProblem(raw: string): string | null {
  const text = raw.trim().replace(/\s*(Kč|Kc|CZK|,-)$/i, "");
  if (!/^\d{1,3}(?:[ \u00a0]?\d{3})*(?:[.,]\d{1,2})?$/.test(text)) return PRICE_REFUSED;
  return Number(text.replace(/[ \u00a0]/g, "").replace(",", ".")) > 0 ? null : PRICE_REFUSED;
}
export const PRICE_REFUSED = "Cena musí být kladná částka, např. 199 Kč nebo 1 299,90 Kč.";

/** The price bands as chips give them, one string each (the setter the screen uses). */
export function setPriceBandList(p: ResearchProject, si: number, bands: readonly string[]): ResearchProject {
  return edit(p, (xs) => {
    const s = xs[si];
    s.metadata = { ...(s.metadata || {}), price_bands: bands.map((x) => x.trim()).filter(Boolean) };
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
export const TEMPLATE_FILENAME = "AIA_dotaznik_sablona.xlsx";

/**
 * uploadQuestionnaireFile, after AIA read the file (ADR 0018): its sections, on the
 * editor, and the plan marked questionnaire_ready, as the unit's import left them.
 * The rest of the project is the person's own; the unit also re-normalized it, as a
 * side effect of returning a whole project, and AIA does not.
 */
export function applyImport(
  current: ResearchProject,
  result: unknown,
  template: Template,
): { project: ResearchProject; toast: string } {
  const r = (result || {}) as { sections?: unknown; summary?: { question_count?: unknown; tracked_sets?: unknown } };
  const plan = (current.research_plan || {}) as Obj;
  const project = defaultsMerge(
    { ...current, sections: (Array.isArray(r.sections) ? r.sections : []) as Json[], research_plan: { ...plan, status: "questionnaire_ready" } },
    template,
  );
  project.ui_state.questionnaire_path = "manual";
  // What was loaded, counted from the sections kept: a summary missing from the answer never prints
  // "undefined". The unit wrote "otázek · sledovaných sad" whatever the number; the words here
  // follow it (countWords), so the two read the same from 5 and at 0 and differ only where it erred.
  return { project, toast: tv("research.questionnaire.imported", { counts: countsWords(questionnaireCounts(project)) }) };
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
export function applyBuilt(result: unknown, template: Template, before?: ResearchProject): ResearchProject {
  const r = (result || {}) as { project?: unknown };
  const project = defaultsMerge(r.project, template);
  // A build over a questionnaire keeps its scales' labels on every point, as the optimiser does (#559).
  if (before) project.sections = keepPointLabels(project.sections, before.sections);
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
export function applyOptimized(
  result: unknown,
  analysis: Analysis | null,
  template: Template,
  before?: ResearchProject,
): { project: ResearchProject; analysis: Analysis | null } {
  const r = (result || {}) as { project?: unknown; research?: Json; analysis?: Analysis };
  const project = defaultsMerge(r.project, template);
  if (r.research) project.pre_research = r.research;
  // The optimiser's schema carries a scale's two ends only (`_question_schema`, maxItems 2):
  // labels the person gave every point are kept, never dropped without a word (#559).
  if (before) project.sections = keepPointLabels(project.sections, before.sections);
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

/** continueQuestionnaireToAudience: the audience starts at its first choice unless already chosen. */
export function toAudience(p: ResearchProject): ResearchProject {
  return { ...p, ui_state: { ...p.ui_state, audience_entry: p.ui_state?.audience_entry || "choose" } };
}
