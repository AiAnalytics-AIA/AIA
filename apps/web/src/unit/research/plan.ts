// Návrh, the research flow's second step (ADR 0014, area A4): what the classic
// plan does to the project and its analysis, ported from the bindings that run
// -- renderPlan @313280 and its four wrappers (1785, 1789, 1793, 26), the
// comparable-set editors, projectVariants1793 / applyProjectVariant1793,
// reanalyze, and the comment workflow (comments26, npcProcessComments26).
// Every function is pure and returns the next state; the screen hands it to
// the store with the classic save reason. plan.parity.test.ts compares each
// with the original under Node.

import type { Json, ResearchProject } from "./model";
import type { Analysis } from "./store";

type Obj = { [k: string]: Json };
export type TrackedSet = Obj & {
  title?: string;
  object_type?: string;
  purpose?: string;
  objects?: string[];
  object_question?: string;
  scale_labels?: string[];
};
export type Variant = Obj & {
  id?: string;
  badge?: string;
  title?: string;
  summary?: string;
  n?: number | string;
  complexity?: string;
  deep_research?: boolean;
  tradeoff?: string;
  research_questions?: string[];
  objectives?: string[];
  hypotheses?: string[];
};
export type PlanState = { project: ResearchProject; analysis: Analysis | null };

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T;
const strings = (x: unknown): string[] => (Array.isArray(x) ? x.filter((v): v is string => typeof v === "string") : []);

export function trackedSets(a: Analysis | null): TrackedSet[] {
  return Array.isArray(a?.tracked_sets) ? (a.tracked_sets as TrackedSet[]) : [];
}

/** questions_for_user, empty ones dropped. */
export function followUps(a: Analysis | null): string[] {
  return (Array.isArray(a?.questions_for_user) ? a.questions_for_user : []).filter(Boolean).map(String);
}

/** comparableFamily: the tag over a set, from what it compares. */
export function comparableFamily(set: TrackedSet): string {
  const x = String(set.object_type || set.title || "").toLowerCase();
  if (/region|kraj|obec/.test(x)) return "Geografické kategorie";
  if (/brand|znač/.test(x)) return "Značky";
  if (/argument/.test(x)) return "Argumenty";
  if (/motiv/.test(x)) return "Motivace";
  if (/bariér/.test(x)) return "Bariéry";
  if (/emo/.test(x)) return "Emoce";
  if (/purchase|intent|záměr/.test(x)) return "Varianty stejné metriky";
  if (/media|méd/.test(x)) return "Média / kanály";
  return "Porovnatelná sada";
}

export const SET_PURPOSE_DEFAULT = "stejný typ položek na stejné otázce/škále";

/** renderObjectSet's preview: how the first six objects become the question, on its 1–10 scale. */
export function objectQuestionRows(set: TrackedSet): { question: string; low: string; high: string }[] {
  const tmpl = String(set.object_question || "Jak hodnotíte {object}?");
  const lb = set.scale_labels || ["vůbec", "velmi"];
  // String.replace with a string pattern replaces the first {object} only, as the classic does.
  return (set.objects || []).slice(0, 6).map((x) => ({ question: tmpl.replace("{object}", x), low: String(lb[0]), high: String(lb[1]) }));
}

/** At most this many objects in one set (addPlanObject, addPlanSet). */
export const MAX_OBJECTS = 15;
export const SET_FULL = "Sledovaná sada má maximálně 15 položek.";
export const PROMPT_SET_TITLE = "Název porovnatelné sady, např. Značky, Regiony, Argumenty nebo Varianty nabídky:";
export const PROMPT_SET_OBJECTS = "Položky oddělte čárkou. Všechny musí jít porovnat na stejné otázce/škále:";
export const PROMPT_OBJECT = "Přidat srovnatelný objekt do této sady:";
export const PROMPT_RENAME = "Název sady:";
export const CONFIRM_REMOVE_SET = "Odstranit celou tuto porovnatelnou sadu?";

const withSets = (a: Analysis, sets: TrackedSet[]): Analysis => ({ ...a, tracked_sets: sets as Json[] });

/** addPlanSet: a new set from a title and a comma list; an analysis is started from the goal if there is none. */
export function addSet(s: PlanState, title: string | null, raw: string | null): Analysis | null {
  if (!title?.trim()) return null;
  const objects = String(raw || "").split(",").map((x) => x.trim()).filter(Boolean).slice(0, MAX_OBJECTS);
  const goal = s.project.goal as Json;
  const a: Analysis = s.analysis || { problem_summary: goal, objectives: [goal], tracked_sets: [] };
  const t = title.trim();
  return withSets(a, [...trackedSets(a), { title: t, object_type: t, purpose: "Porovnat tyto položky mezi sebou na stejné metrice.", objects }]);
}

/** addPlanObject: one more object, refused past fifteen. */
export function addObject(a: Analysis, si: number, value: string | null): { analysis: Analysis } | { error: string } | null {
  if (!value?.trim()) return null;
  const sets = clone(trackedSets(a));
  const objects = sets[si].objects || [];
  if (objects.length >= MAX_OBJECTS) return { error: SET_FULL };
  sets[si] = { ...sets[si], objects: [...objects, value.trim()] };
  return { analysis: withSets(a, sets) };
}

/** The prompt's starting value when a set is renamed. */
export function setTitle(set: TrackedSet): string {
  return set.title || set.object_type || "";
}

/** renamePlanSet */
export function renameSet(a: Analysis, si: number, value: string | null): Analysis | null {
  const sets = clone(trackedSets(a));
  if (!sets[si] || !value?.trim()) return null;
  sets[si] = { ...sets[si], title: value.trim() };
  return withSets(a, sets);
}

/** removePlanSet (after its confirm) */
export function removeSet(a: Analysis, si: number): Analysis | null {
  const sets = trackedSets(a);
  if (!sets[si]) return null;
  return withSets(a, sets.filter((_, i) => i !== si));
}

/** removePlanObject */
export function removeObject(a: Analysis, si: number, oi: number): Analysis | null {
  const sets = clone(trackedSets(a));
  if (!sets[si]) return null;
  sets[si] = { ...sets[si], objects: (sets[si].objects || []).filter((_, i) => i !== oi) };
  return withSets(a, sets);
}

/** projectVariants1793: the analysis's design variants, else the ones the project kept; three at most. */
export function projectVariants(s: PlanState): Variant[] {
  const v = (s.analysis?.project_variants || s.project.design_variants || []) as Variant[];
  return Array.isArray(v) ? v.slice(0, 3) : [];
}

export function selectedVariant(p: ResearchProject): string {
  return String(p.selected_design_variant || "recommended");
}

/** applyProjectVariant1793: the variant's scope becomes the project's plan and the analysis's. */
export function applyVariant(s: PlanState, id: string): { state: PlanState; title: string } | null {
  const vars = projectVariants(s);
  const v = vars.find((x) => x.id === id);
  if (!v || !s.analysis) return null;
  const rq = strings(v.research_questions), ob = strings(v.objectives), hy = strings(v.hypotheses);
  const project: ResearchProject = {
    ...s.project,
    selected_design_variant: id,
    design_variants: clone(vars) as Json[],
    n: Number(v.n || s.project.n || 300),
    research_plan: { ...(s.project.research_plan || {}), research_questions: rq, objectives: ob, hypotheses: hy, complexity: v.complexity || "standard" },
    ui_state: { ...(s.project.ui_state || {}), deep_research_recommended: !!v.deep_research },
  };
  const complexity = v.complexity || s.analysis.complexity;
  const analysis: Analysis = {
    ...s.analysis,
    research_questions: [...rq],
    objectives: [...ob],
    hypotheses: [...hy],
    ...(complexity === undefined ? {} : { complexity }),
  };
  return { state: { project, analysis }, title: String(v.title) };
}

export const ANSWERS_EMPTY = "Napište odpovědi.";

/** reanalyze: the person's answers become part of what is known, and the brief is analysed again. */
export function answerFollowUps(p: ResearchProject, answers: string): { project: ResearchProject } | { error: string } {
  const x = answers.trim();
  if (!x) return { error: ANSWERS_EMPTY };
  // The classic concatenates the field as is; a missing one would read "undefined". defaultsMerge always sets it.
  const known = String(p.briefing.what_is_known ?? "");
  return { project: { ...p, briefing: { ...p.briefing, what_is_known: `${known}\n\nDoplnění k analýze:\n${x}`.trim() } } };
}

export type PlanComment = { quote: string; comment: string };
export const PROMPT_COMMENT = "Komentář k označenému textu";

/** comments26 */
export function planComments(p: ResearchProject): PlanComment[] {
  return Array.isArray(p.ui_state?.plan_comments26) ? (p.ui_state.plan_comments26 as PlanComment[]) : [];
}

/** floatButton26's click: the selected text (500 characters at most) and the comment on it. */
export function addComment(p: ResearchProject, quote: string, comment: string | null): ResearchProject | null {
  if (!comment?.trim()) return null;
  return { ...p, ui_state: { ...p.ui_state, plan_comments26: [...planComments(p), { quote: quote.slice(0, 500), comment: comment.trim() }] } };
}

/** npcRemoveComment26 */
export function removeComment(p: ResearchProject, i: number): ResearchProject {
  return { ...p, ui_state: { ...p.ui_state, plan_comments26: planComments(p).filter((_, j) => j !== i) } };
}

/** A selection long enough to comment on (the classic mouseup handler: two characters, trimmed). */
export function commentableSelection(text: string): string | null {
  const t = String(text || "").trim();
  return t.length < 2 ? null : t;
}

/** npcProcessComments26, before its analysis: the comments become the brief's review comments. */
export function commentsToReview(p: ResearchProject): ResearchProject | null {
  const cs = planComments(p);
  if (!cs.length) return null;
  return {
    ...p,
    briefing: { ...p.briefing, review_comments: cs.map((c, i) => `${i + 1}. K textu „${c.quote}“: ${c.comment}`).join("\n") },
    ui_state: { ...p.ui_state, plan_comments26: [] },
  };
}

/** setQuestionnairePath('choose'), the plan's way on: the questionnaire starts at its three paths. */
export function toQuestionnaire(p: ResearchProject): ResearchProject {
  return { ...p, ui_state: { ...p.ui_state, questionnaire_path: "choose" } };
}
