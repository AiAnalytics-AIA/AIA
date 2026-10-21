// Which research question each questionnaire item measures (plan run-recovery-and-truth 3b).
// An item -- a question, or a tracked set -- carries `research_questions`: the texts of the
// research questions it measures, as the plan states them. The server compiles them and
// traces each research question to its measures before a run (domain/research_trace.py);
// this module only reads and writes the declaration. Pure: every function returns the next
// project.

import type { Json, ResearchProject } from "./model";
import type { Question, Section } from "./questionnaire";

type Obj = { [k: string]: Json };

/** The analysis reads at most this many research questions (native.py MAX_RESEARCH_QUESTIONS). */
export const MAX_RESEARCH_QUESTIONS = 8;

const texts = (raw: unknown): string[] =>
  Array.isArray(raw) ? raw.filter((x): x is string => typeof x === "string" && x.trim() !== "").map((x) => x.trim()) : [];

/** Collapsed whitespace: how the server compares a link with a research question. */
export const linkKey = (text: string): string => text.replace(/\s+/g, " ").trim();

/**
 * The research questions the analysis will answer, read as the server reads them
 * (`research_questions_of`): the plan's research questions, else its objectives, else the
 * goal; exact repeats dropped; at most eight.
 */
export function researchQuestionsOf(p: ResearchProject): string[] {
  const plan = (p.research_plan && typeof p.research_plan === "object" && !Array.isArray(p.research_plan) ? p.research_plan : {}) as Obj;
  let out = texts(plan.research_questions);
  if (!out.length) out = texts(plan.objectives);
  const goal = typeof p.goal === "string" ? p.goal.trim() : "";
  if (!out.length && goal) out = [goal];
  return [...new Set(out)].slice(0, MAX_RESEARCH_QUESTIONS);
}

/** The research questions an item declares, as written. */
export const linksOf = (item: Question | Section): string[] => texts(item.research_questions);

/** An item's links that name no stated research question: they measure nothing checkable. */
export function danglingLinks(item: Question | Section, stated: readonly string[]): string[] {
  const keys = new Set(stated.map(linkKey));
  return linksOf(item).filter((l) => !keys.has(linkKey(l)));
}

const toggled = (links: string[], rq: string): string[] =>
  links.some((l) => linkKey(l) === linkKey(rq)) ? links.filter((l) => linkKey(l) !== linkKey(rq)) : [...links, rq];

const withLinks = <T extends Obj>(item: T, links: string[]): T => {
  const next = { ...item } as Obj;
  if (links.length) next.research_questions = links;
  else delete next.research_questions; // none declared is no declaration (out of the fingerprint)
  return next as T;
};

const sectionsOf = (p: ResearchProject): Section[] => (p.sections || []) as Section[];
const withSections = (p: ResearchProject, xs: Section[]): ResearchProject => ({ ...p, sections: xs as Json[] });

/** Question `qi` of section `si` measures `rq`, or stops measuring it. */
export function toggleQuestionLink(p: ResearchProject, si: number, qi: number, rq: string): ResearchProject {
  return withSections(
    p,
    sectionsOf(p).map((s, i) =>
      i !== si ? s : { ...s, questions: (s.questions || []).map((q, j) => (j !== qi ? q : withLinks(q, toggled(linksOf(q), rq)))) },
    ),
  );
}

/** Tracked set `si` measures `rq`, or stops measuring it. */
export function toggleSectionLink(p: ResearchProject, si: number, rq: string): ResearchProject {
  return withSections(
    p,
    sectionsOf(p).map((s, i) => (i !== si ? s : withLinks(s, toggled(linksOf(s), rq)))),
  );
}

/** How a research question is answered (plan run-recovery-and-truth 3c); the server checks it. */
export const COMPARISONS = ["describe", "rank_objects", "compare_segments", "ab_test"] as const;
export type Comparison = (typeof COMPARISONS)[number];

const planOf = (p: ResearchProject): Obj =>
  (p.research_plan && typeof p.research_plan === "object" && !Array.isArray(p.research_plan) ? p.research_plan : {}) as Obj;

/** The comparison the plan declares for a research question, if one AIA knows. */
export function comparisonOf(p: ResearchProject, rq: string): Comparison | null {
  const raw = planOf(p).research_question_comparisons;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const hit = Object.entries(raw as Obj).find(([text]) => linkKey(text) === linkKey(rq));
  const kind = hit?.[1];
  return typeof kind === "string" && (COMPARISONS as readonly string[]).includes(kind) ? (kind as Comparison) : null;
}

/** Declare how a research question is answered, or clear it (`null`): no declaration, not checked. */
export function setComparison(p: ResearchProject, rq: string, kind: Comparison | null): ResearchProject {
  const plan = planOf(p);
  const raw = plan.research_question_comparisons;
  const current = raw && typeof raw === "object" && !Array.isArray(raw) ? (raw as Obj) : {};
  const next: Obj = Object.fromEntries(Object.entries(current).filter(([text]) => linkKey(text) !== linkKey(rq)));
  if (kind) next[rq] = kind;
  const nextPlan: Obj = { ...plan };
  if (Object.keys(next).length) nextPlan.research_question_comparisons = next;
  else delete nextPlan.research_question_comparisons;
  return { ...p, research_plan: nextPlan };
}

/** The output type of a concept-test set: what an `ab_test` comparison needs (3c). */
export const CONCEPT_TEST = "test_konceptu";
const POSITION_MAP = "pozicni_mapa";

/** A set a person may turn into a concept test and back: a position map or a concept test.
 *  Another output type (an imported segmentation, a lovebrand) is left as it was set. */
export const togglesConceptTest = (sec: Section): boolean =>
  sec.type === "object_battery" && [undefined, "", POSITION_MAP, CONCEPT_TEST].includes(sec.output_type);

/** Tracked set `si` compares its objects as concepts (an A/B test), or maps them again. */
export function setConceptTest(p: ResearchProject, si: number, on: boolean): ResearchProject {
  return withSections(
    p,
    sectionsOf(p).map((s, i) => (i !== si ? s : { ...s, output_type: on ? CONCEPT_TEST : POSITION_MAP })),
  );
}

/** One stated research question in a proposed design: what measures it, how it is answered. */
export type ProposedLink = { researchQuestion: string; measures: string[]; comparison: Comparison | null };

/**
 * What a proposed design links each stated research question to (3e): its measures by the
 * wording a respondent reads (a question's text, a set's title), and its declared comparison.
 * Only reads; the server checks the chain on the Run stage.
 */
export function proposedTrace(p: ResearchProject): ProposedLink[] {
  return researchQuestionsOf(p).map((rq) => {
    const names = (item: Question | Section) => linksOf(item).some((l) => linkKey(l) === linkKey(rq));
    const measures: string[] = [];
    for (const s of sectionsOf(p)) {
      if (s.type === "object_battery") {
        if (names(s)) measures.push(s.title || s.id || "");
        continue;
      }
      for (const q of s.questions || []) if (names(q)) measures.push(q.text || q.id || "");
    }
    return { researchQuestion: rq, measures, comparison: comparisonOf(p, rq) };
  });
}

/** One stated research question on Dotazník's strip: how many items say they measure it. */
export type RqCoverage = { researchQuestion: string; measures: number };

/**
 * Dotazník's strip (artifact-questionnaire QST2; V2 DesignStages.tsx:103-107): the items a
 * respondent answers (each question, each distinct object of a tracked set) and, per stated
 * research question, how many items declare they measure it. Read as the server's trace reads
 * it (domain/research_trace.py:242-259): until some item declares a link, coverage is unknown
 * (`linked` false), never a gap; once one does, a research question nothing names is a gap.
 * The working copy, before compile: Kontrola decides what a run will answer.
 */
export function coverageOf(p: ResearchProject): { items: number; linked: boolean; questions: RqCoverage[] } {
  let items = 0;
  let linked = false;
  const counts = new Map<string, number>();
  const count = (item: Question | Section) => {
    const keys = new Set(linksOf(item).map(linkKey));
    if (keys.size) linked = true;
    for (const k of keys) counts.set(k, (counts.get(k) ?? 0) + 1);
  };
  for (const s of sectionsOf(p)) {
    const kind = s.type || "questions";
    if (kind === "object_battery") {
      items += new Set(texts(s.objects)).size;
      count(s);
    } else if (kind === "questions") {
      for (const q of s.questions || []) {
        items += 1;
        count(q);
      }
    }
  }
  return { items, linked, questions: researchQuestionsOf(p).map((rq) => ({ researchQuestion: rq, measures: counts.get(linkKey(rq)) ?? 0 })) };
}
