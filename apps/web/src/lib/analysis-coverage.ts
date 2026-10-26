// Analýza's "Pokrytí výzkumných otázek" (artifact-analysis ANL2): each research question of the
// run's frozen design with what the analysis answered, the findings that rest on the same
// measures, and what is missing. Pure: it reads the stored analysis and the gaps the run recorded
// at start, and decides nothing the server did not.
import type { AnswerabilityGap, ResearchAnalysis } from "@/lib/api";
import { ANALYSIS_ORDER } from "@/lib/research-execution";
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

/**
 * The row's state as Analýza says it (ANL2b, spec szz A3):
 * - `answered`, Odpovězeno: answered citing an admitted claim, no gap recorded;
 * - `indicative`, Orientačně: answered citing a claim, but the comparison it asked for could not be
 *   made (the run recorded `segments_unavailable` at start);
 * - `no_data`, Bez dat: a gap recorded at start, or an answer in words that cites no claim;
 * - `pending`, Čeká: the research-questions module has not been stored yet, whatever was recorded at start;
 * - `unknown`, Neznámé: that module did not pass its checks, or holds no answer. Never Odpovězeno.
 */
export type CoverageVerdict = "answered" | "indicative" | "no_data" | "pending" | "unknown";

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
  verdict: CoverageVerdict;
  /** The answer as the module wrote it; null when there is none. */
  answer: string | null;
  /** What the run recorded at start about this question, in words (the API's), or the
   *  recorded gap itself when only the run says so; null when it recorded none. */
  gap: { words: string } | { recorded: AnswerabilityGap } | null;
  /** Findings of completed modules that cite a measure this answer cites. */
  findings: FindingRef[];
};

const RESEARCH_QUESTIONS_MODULE = "research_questions";
/** The gap reason a run records for a research question that asks to compare segments, which no run
 *  can yet (domain/research_trace.py TraceReason.SEGMENTS_UNAVAILABLE). */
const SEGMENTS_UNAVAILABLE = "segments_unavailable";

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
    // Indicative only when the segment comparison is the one thing the run could not do: another
    // recorded reason (no citable measure, measures unanswered) leaves it without data.
    const segmentsOnly = !!gapRecord?.reasons.length && gapRecord.reasons.every((r) => r === SEGMENTS_UNAVAILABLE);
    const verdict: CoverageVerdict =
      !rq ? "pending"
      : state === "answered" ? "answered"
      : state === "gap" && cited.size && segmentsOnly ? "indicative"
      : state === "gap" || state === "unsupported" ? "no_data"
      : state === "pending" ? "pending"
      : "unknown";
    return { index, question, state, verdict, answer: answer?.answer ?? null, gap, findings: linked };
  });
}
