// Analýza's "Pokrytí výzkumných otázek" (artifact-analysis ANL2): each research question of the
// run's frozen design with what the analysis answered, the findings that rest on the same
// measures, and what is missing. Pure: it reads the stored analysis and the gaps the run recorded
// at start, and decides nothing the server did not.
import { t } from "@/i18n/t";
import type { AnswerabilityGap, ResearchAnalysis } from "@/lib/api";
import { ANALYSIS_ORDER, type OriginKind } from "@/lib/research-execution";
import { linkKey } from "@/research/trace";

type Module = ResearchAnalysis["modules"][string];

/**
 * Where a research question stands in the analysis:
 * - `answered`: the research-questions module answered it, citing at least one admitted claim;
 * - `unsupported`: answered in words, citing no claim;
 * - `gap`: the run recorded it as a gap at start, so any answer reads as undocumented;
 * - `blocked`: the research-questions module did not pass its checks, so nothing is known;
 * - `pending`: that module has not been stored yet;
 * - `unanswered`: the module is stored but holds no answer to it (the gate refuses this; read as unknown).
 */
export type CoverageState = "answered" | "unsupported" | "gap" | "blocked" | "pending" | "unanswered";

/** A finding, pointed at as `finding:<module>:<n>` (artifact-analysis §4). */
export type FindingRef = { module: string; index: number };
export const findingId = (f: FindingRef): string => `${f.module}:${f.index}`;
/** The element id a finding is opened at, on the page and from a coverage row. */
export const findingAnchor = (f: FindingRef): string => `analysis-finding-${f.module}-${f.index}`;


export type CoverageRow = {
  /** The question's place in the design's order. Not a Lead target: `rq:<id>` waits for stable
   *  research-question ids (WCE1); until then the Lead points at the module or a finding. */
  index: number;
  question: string;
  state: CoverageState;
  /** The answer as the module wrote it; null when there is none. */
  answer: string | null;
  /** What the run recorded at start about this question, in words (the API's), or the
   *  recorded gap itself when only the run says so; null when it recorded none. */
  gap: { words: string } | { recorded: AnswerabilityGap } | null;
  /** Findings of completed modules that cite a measure this answer cites. */
  findings: FindingRef[];
};

const RESEARCH_QUESTIONS_MODULE = "research_questions";

/** The measures a set of claim ids rests on, within one module. */
function refsOf(module: Module, ids: readonly string[]): Set<string> {
  const wanted = new Set(ids);
  return new Set(module.claims.filter((c) => wanted.has(c.claim_id)).map((c) => c.evidence_ref));
}

/** Every key finding of a completed module, in module order, with the measures it cites. */
export function findingsOf(analysis: ResearchAnalysis | null): { ref: FindingRef; text: string; refs: Set<string> }[] {
  if (!analysis) return [];
  return ANALYSIS_ORDER.flatMap((module) => {
    const outcome = analysis.modules[module];
    if (outcome?.outcome !== "COMPLETED") return [];
    return outcome.key_findings.map((f, index) => ({ ref: { module, index }, text: f.text, refs: refsOf(outcome, f.claim_ids) }));
  });
}

/**
 * The coverage table. `questions` are the frozen design's research questions in order
 * (`researchQuestionsOf`), read; nothing stands in for them, since the module's own answers would
 * drop a question nobody answered and read as full coverage. `gaps` are the run's recorded
 * answerability gaps.
 */
export function coverage(
  questions: readonly string[],
  analysis: ResearchAnalysis | null,
  gaps: readonly AnswerabilityGap[],
): CoverageRow[] {
  const rq = analysis?.modules[RESEARCH_QUESTIONS_MODULE];
  const answers = rq?.outcome === "COMPLETED" ? rq.research_question_answers : [];
  const findings = findingsOf(analysis);
  const recorded = new Map(
    gaps.filter((g) => g.research_question).map((g) => [linkKey(g.research_question as string), g] as const),
  );
  return questions.map((question, index) => {
    const key = linkKey(question);
    const answer = answers.find((a) => linkKey(a.question) === key) ?? null;
    const gapRecord = recorded.get(key);
    const gap = answer?.gap ? { words: answer.gap } : gapRecord ? { recorded: gapRecord } : null;
    const cited = answer && rq ? refsOf(rq, answer.claim_ids) : new Set<string>();
    const linked = findings.filter((f) => [...f.refs].some((r) => cited.has(r))).map((f) => f.ref);
    const state: CoverageState =
      rq?.outcome === "BLOCKED" ? "blocked"
      : !rq ? (gap ? "gap" : "pending")
      : gap ? "gap"
      : !answer ? "unanswered"
      : cited.size ? "answered" : "unsupported";
    return { index, question, state, answer: answer?.answer ?? null, gap, findings: linked };
  });
}

/**
 * Analýza's header line (ANL10): "Běh z 21. 10. · interní · modelováno", the year added when it is
 * not this year's. A date that was not recorded or cannot be read is left out, never guessed; an
 * origin not read is said unknown.
 */
export function analysisHeader(createdAt: string | null | undefined, origin: OriginKind | null, now: Date = new Date()): string {
  const date = createdAt ? new Date(createdAt) : null;
  const known = date && !Number.isNaN(date.getTime()) ? date : null;
  const day = known?.toLocaleDateString("cs-CZ", known.getFullYear() === now.getFullYear() ? { day: "numeric", month: "numeric" } : { day: "numeric", month: "numeric", year: "numeric" });
  return [day ? `Běh z ${day}` : "Běh", "interní", t(`research.exec.results.analysisHeaderOrigin.${origin ?? "UNKNOWN"}`)].join(" · ");
}
