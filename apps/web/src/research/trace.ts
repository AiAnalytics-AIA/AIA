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
