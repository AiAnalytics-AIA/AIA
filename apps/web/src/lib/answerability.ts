/**
 * Runnable is not answerable (research-integrity-report 1).
 *
 * Readiness's `ready` says a design can run; `answerability` says whether the run can answer the
 * research questions it states. Where the deployment requires it (the server's switch, read from
 * `acknowledgement_required`), a run with gaps starts only with the person's acknowledgement of
 * exactly those gaps (`digest`) and a reason, which the run records and the report prints.
 * Elsewhere the gaps are shown and nothing is asked. Pure.
 */
import { ApiError, type Answerability, type AnswerabilityAcknowledgement, type AnswerabilityGap } from "./api";
import { codedText, codeWords } from "./reason-words";
import { t } from "@/i18n/t";

export const MIN_REASON = 10;
export const MAX_REASON = 1000;

/** Every reason the server gives a gap (domain/answerability.py GapReason): each has words. */
export const GAP_REASONS = [
  "unmeasured",
  "unlinked_design",
  "comparison_needs_tracked_set",
  "comparison_needs_concept_set",
  "segments_unavailable",
  "comparison_unknown",
  "measures_unanswerable",
  "no_citable_measure",
  "comparison_set_unanswerable",
] as const;

/** What the person said, and the gaps (`digest`) they said it about. */
export type AcknowledgementState = { digest: string | null; confirmed: boolean; reason: string };
export const NO_ACKNOWLEDGEMENT: AcknowledgementState = { digest: null, confirmed: false, reason: "" };

/** Whether the run cannot show an answer to every research question it states. Absent (an older API): never. */
export function hasGaps(answer: Answerability | null | undefined): answer is Answerability {
  return !!answer && !answer.capable;
}

/** Whether starting needs the person's acknowledgement: exactly where the server would refuse. */
export function needsAcknowledgement(answer: Answerability | null | undefined): answer is Answerability {
  return hasGaps(answer) && answer.acknowledgement_required === true;
}

/** Whether the confirmation is of these gaps: one given for gaps the design no longer has covers nothing. */
export function confirmedFor(answer: Answerability, state: AcknowledgementState): boolean {
  return state.confirmed && state.digest === answer.digest;
}

/** The acknowledgement to send, or null while the person has not given a valid one for these gaps. */
export function acknowledgementOf(
  answer: Answerability | null | undefined,
  state: AcknowledgementState,
): AnswerabilityAcknowledgement | null {
  if (!needsAcknowledgement(answer) || !confirmedFor(answer, state)) return null;
  const reason = state.reason.split(/\s+/).filter(Boolean).join(" ");
  if (reason.length < MIN_REASON || reason.length > MAX_REASON) return null;
  return { digest: answer.digest, reason };
}

/**
 * Whether ``run`` carries this acknowledgement: false when a start over a revision that already
 * had a run returned that run, so what the person just gave was recorded nowhere.
 */
export function acknowledges(run: { answerability?: Answerability | null }, given: AnswerabilityAcknowledgement): boolean {
  const held = run.answerability?.acknowledgement;
  return !!held && held.reason === given.reason && run.answerability?.digest === given.digest;
}

/** A gap in words: the research question, whether the run will not or may not answer it, and why. */
export function gapWords(gap: AnswerabilityGap): { question: string; verdict: string; why: string } {
  if (gap.kind === "no_research_questions") return { question: "", verdict: "", why: t("research.exec.answerability.none") };
  // A record from before every gap carried a reason: measured, but by nothing the run answers.
  const reasons = gap.reasons.length ? gap.reasons : gap.measures.length ? ["measures_unanswerable"] : ["unmeasured"];
  // A reason this client has no words for keeps its code on screen (reason-words), never hidden.
  const why = reasons
    .map((r) => codedText(codeWords("research.exec.answerability.reason", r, "research.exec.answerability.reasonUnknown")))
    .join("; ");
  const verdict = gap.verdict === "UNANSWERABLE" ? t("research.exec.answerability.wont") : t("research.exec.answerability.unshown");
  return { question: gap.research_question ?? "", verdict, why };
}

/** The server refused a start or retry for its research questions: the answerability it gave. */
export function unanswerableAsked(e: unknown): Answerability | null {
  if (!(e instanceof ApiError) || e.code !== "research_questions_unanswerable") return null;
  const d = e.details as Partial<Answerability>;
  if (typeof d.digest !== "string" || !Array.isArray(d.gaps) || d.capable !== false) return null;
  // A refusal is the requirement itself, whatever an older payload said.
  return { ...(d as Answerability), acknowledgement_required: true };
}
