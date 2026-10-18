/**
 * Runnable is not answerable (research-integrity-report 1).
 *
 * Readiness's `ready` says a design can run; `answerability` says whether the run can answer the
 * research questions it states. Where the deployment requires it (the server's switch, read from
 * `acknowledgement_required`), a run with gaps starts only with the person's acknowledgement of
 * exactly those gaps (`digest`) and a reason, which the run records and the report prints.
 * Elsewhere the gaps are shown and nothing is asked. Each gap links to where it is fixed
 * (`gapFixes`). Pure.
 */
import { ApiError, type Answerability, type AnswerabilityAcknowledgement, type AnswerabilityGap, type QuestionOutlook } from "./api";
import { codedText, codeWords } from "./reason-words";
import { outlookFixStep } from "./research-execution";
import { t } from "@/i18n/t";
import type { Question, Section } from "@/research/questionnaire";
import type { StepKey } from "@/research/steps";

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
 * Whether ``run`` carries this acknowledgement. A start that found the revision's run (created:
 * false) recorded what the person just gave nowhere, unless that run already holds it: a start
 * whose answer was lost, asked again with the same reason (review 3).
 */
export function acknowledges(run: { answerability?: Answerability | null }, given: AnswerabilityAcknowledgement): boolean {
  const held = run.answerability?.acknowledgement;
  return !!held && held.reason === given.reason && run.answerability?.digest === given.digest;
}

/**
 * The gaps a retry was refused for, while they still apply: to the run they were refused for,
 * while it can be retried, by someone who may. A refusal for one run never offers to retry
 * another with its acknowledgement (review 2, F32).
 */
export function refusalFor(
  refusal: { runId: string; answer: Answerability } | null,
  run: { run_id: string; retryable?: boolean | null },
  canEdit: boolean,
): Answerability | null {
  return refusal && refusal.runId === run.run_id && canEdit && run.retryable ? refusal.answer : null;
}

/** A gap's reasons. A record from before every gap carried one: measured, but by nothing the run answers. */
function reasonsOf(gap: AnswerabilityGap): readonly string[] {
  return gap.reasons.length ? gap.reasons : gap.measures.length ? ["measures_unanswerable"] : ["unmeasured"];
}

/** A gap in words: the research question, whether the run will not or may not answer it, and why. */
export function gapWords(gap: AnswerabilityGap): { question: string; verdict: string; why: string } {
  if (gap.kind === "no_research_questions") return { question: "", verdict: "", why: t("research.exec.answerability.none") };
  // A reason this client has no words for keeps its code on screen (reason-words), never hidden.
  const why = reasonsOf(gap)
    .map((r) => codedText(codeWords("research.exec.answerability.reason", r, "research.exec.answerability.reasonUnknown")))
    .join("; ");
  const verdict = gap.verdict === "UNANSWERABLE" ? t("research.exec.answerability.wont") : t("research.exec.answerability.unshown");
  return { question: gap.research_question ?? "", verdict, why };
}

/**
 * Where a gap is fixed: a stage, and the place on it the link opens (an element id the stage reads
 * from the URL's hash), or the stage itself.
 */
export type GapFix = { step: StepKey; anchor: string | null; words: string };

const FIX = "research.exec.answerability.fixTo";
/** The questionnaire's editor (its outline's heading): each item there says which research questions it answers. */
const EDITOR = "q-editor";

/** Outlook reasons that keep an item's numbers out of the analysis (domain/answerability.py `_NOT_CITABLE`). */
const NOT_CITABLE: ReadonlySet<string> = new Set(["open_ended", "support_analysis_excluded"]);
const citable = (o: QuestionOutlook) => !o.reasons.some((r) => NOT_CITABLE.has(r));
const inSet = (o: QuestionOutlook) => o.battery_id !== null;

/**
 * The measure a gap's reason is about, of those ``keep`` admits: the first the outlook says the run
 * may not answer, else the first it knows; else the first it does not list (``item`` null: an id
 * that may name any item), else none.
 */
function measureOf(
  gap: AnswerabilityGap,
  outlook: readonly QuestionOutlook[],
  keep: (o: QuestionOutlook) => boolean = () => true,
): { id: string; item: QuestionOutlook | null } | null {
  const byId = new Map(outlook.map((o) => [o.question_id, o]));
  const known = gap.measures.map((id) => byId.get(id)).filter((o): o is QuestionOutlook => !!o && keep(o));
  const item = known.find((o) => o.verdict !== "ANSWERABLE") ?? known[0];
  if (item) return { id: item.question_id, item };
  const unlisted = gap.measures.find((id) => !byId.has(id));
  return unlisted ? { id: unlisted, item: null } : null;
}

function fixFor(reason: string, gap: AnswerabilityGap, outlook: readonly QuestionOutlook[] | null): GapFix {
  switch (reason) {
    case "unlinked_design":
    case "unmeasured":
      return { step: "questionnaire", anchor: EDITOR, words: t(`${FIX}.links`) };
    case "comparison_needs_tracked_set":
    case "comparison_needs_concept_set":
    case "segments_unavailable":
    case "comparison_unknown":
      return { step: "questionnaire", anchor: "q-comparisons", words: t(`${FIX}.comparison`) };
    case "comparison_set_unanswerable": {
      // The set by the outlook's battery_id, never read out of a measure's id.
      const set = outlook ? measureOf(gap, outlook, inSet)?.item?.battery_id : null;
      return { step: "questionnaire", anchor: set ? `qset_${set}` : EDITOR, words: t(`${FIX}.set`) };
    }
    case "measures_unanswerable":
    case "no_citable_measure": {
      // Without an outlook (a refused retry), only the editor: nothing says what the measure is.
      if (!outlook) return { step: "questionnaire", anchor: EDITOR, words: t(`${FIX}.measure`) };
      // Measured only by items the run will not answer: of those the analysis may cite, as the
      // domain decides it. An open question beside them is answered and never cited, so editing
      // it closes nothing (F10). Measured only by uncitable items: any of them.
      const measure = measureOf(gap, outlook, reason === "measures_unanswerable" ? citable : undefined);
      const item = measure?.item;
      if (item && outlookFixStep(item.reasons) === "persona") return { step: "persona", anchor: null, words: t(`${FIX}.support`) };
      // An id the outlook does not list may name any item: its question, and where no element has
      // that id, Dotazník opens the editor (QuestionnaireStep's hash reader).
      const anchor = item?.battery_id ? `qset_${item.battery_id}` : measure ? `qedit_${measure.id}` : EDITOR;
      return { step: "questionnaire", anchor, words: t(`${FIX}.measure`) };
    }
    default:
      // A reason this client does not know: the questionnaire, never no way at all.
      return { step: "questionnaire", anchor: null, words: t(`${FIX}.questionnaire`) };
  }
}

/**
 * Where each of a gap's reasons is fixed, one link per place, in the order of its reasons: no
 * research question in Návrh; links, comparisons, a set or a measure in Dotazník; a measure's
 * support on Dimenze. ``outlook`` is readiness's: without one (a refused retry), a stage and its
 * sections only.
 */
export function gapFixes(gap: AnswerabilityGap, outlook: readonly QuestionOutlook[] | null): GapFix[] {
  if (gap.kind === "no_research_questions") return [{ step: "plan", anchor: "plan-understanding", words: t(`${FIX}.plan`) }];
  const out: GapFix[] = [];
  for (const reason of reasonsOf(gap)) {
    const fix = fixFor(reason, gap, outlook);
    if (!out.some((f) => f.step === fix.step && f.anchor === fix.anchor)) out.push(fix);
  }
  return out;
}

/** A fix as a link: the stage's address, and the place on it as the hash. */
export function fixHref(fix: GapFix, stepHref: (step: StepKey) => string): string {
  return fix.anchor ? `${stepHref(fix.step)}#${encodeURIComponent(fix.anchor)}` : stepHref(fix.step);
}

/** The element a stage's hash names (``fixHref``), or null: an empty or malformed hash names none. */
export function hashTarget(hash: string): string | null {
  try {
    return decodeURIComponent(hash.replace(/^#/, "")) || null;
  } catch {
    return null;
  }
}

/** The element Dotazník draws for a question (its card and outline row), by the id the web gave it. */
export const questionElementId = (q: Pick<Question, "id">) => `qedit_${q.id || "Q"}`;
/** The element Dotazník draws for a tracked set, by the id the web gave it, else its place among the sections. */
export const setElementId = (sec: Pick<Section, "id">, si: number) => `qset_${sec.id || si}`;

const isObject = (x: unknown): x is Record<string, unknown> => typeof x === "object" && x !== null && !Array.isArray(x);
/** research_design.py ``_QUESTION_TYPES``: a question of another type is not compiled. */
const QUESTION_TYPES: ReadonlySet<string> = new Set(["vyber", "multi", "skala", "otevrena"]);

/**
 * research_design.py ``_text``: whitespace collapsed and trimmed, nothing as "". Null for a value
 * Python may write otherwise than JavaScript (anything but text or a whole number): never guessed.
 */
function serverText(v: unknown): string | null {
  if (v === null || v === undefined) return "";
  if (typeof v === "string") return v.replace(/\s+/g, " ").trim();
  return typeof v === "number" && Number.isSafeInteger(v) ? String(v) : null;
}

/**
 * research_design.py ``_slug``: ASCII (diacritics folded), lower case, every run of anything else
 * one underscore, none at either end; empty is ``prefix``, a leading digit takes it.
 */
export function compiledSlug(value: string, prefix: string): string {
  const slug = value
    .normalize("NFKD")
    .replace(/[^\x00-\x7f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  if (!slug) return prefix;
  return /^[0-9]/.test(slug) ? `${prefix}_${slug}` : slug;
}

/** research_design.py ``_unique``: the first free of ``base``, ``base_2``, ``base_3``…, then taken. */
function unique(base: string, used: Set<string>): string {
  let candidate = base;
  for (let i = 2; used.has(candidate); i++) candidate = `${base}_${i}`;
  used.add(candidate);
  return candidate;
}

/** A question or tracked set by the anchor a link names it with, and the element Dotazník draws for it (none: null). */
export type CompiledPlace = { anchor: string; element: string | null };

/**
 * Every question and tracked set as the server compiles the design (research_design.py
 * ``compile_design``: the sections in order, each id slugged and made unique), as a link names it
 * (``qedit_<id>``, ``qset_<id>``: a gap's measure is the outlook's id), beside the element
 * Dotazník draws for it. The server lower-cases and folds what the web wrote: the web's question
 * ``Q_lx3abc`` is the server's ``q_lx3abc``. A section the server reads as questions without
 * saying so is drawn as a set, so its questions have no element. An id the server may write
 * otherwise than this (neither text nor a whole number) ends the list: every later id is unknown.
 */
export function compiledPlaces(xs: readonly Section[]): CompiledPlace[] {
  const out: CompiledPlace[] = [];
  const sectionIds = new Set<string>();
  const questionIds = new Set<string>();
  for (const [si, sec] of xs.entries()) {
    if (!isObject(sec)) continue;
    const kind = serverText(sec.type || "questions");
    if (kind !== "questions" && kind !== "object_battery") continue;
    const name = serverText(sec.id || sec.title);
    if (name === null) return out;
    const sid = unique(compiledSlug(name || `sekce_${si + 1}`, "sec"), sectionIds);
    if (kind === "object_battery") {
      out.push({ anchor: `qset_${sid}`, element: setElementId(sec, si) });
      continue;
    }
    for (const [qi, q] of (Array.isArray(sec.questions) ? sec.questions : []).entries()) {
      // A question the server refuses takes no id (a design with one does not compile).
      if (!isObject(q) || !QUESTION_TYPES.has(serverText(q.typ || "vyber") ?? "") || serverText(q.text) === "") continue;
      const id = serverText(q.id);
      if (id === null) return out;
      const qid = unique(compiledSlug(id || `${sid}_${qi + 1}`, "q"), questionIds);
      out.push({ anchor: `qedit_${qid}`, element: sec.type === "questions" ? questionElementId(q) : null });
    }
  }
  return out;
}

/** Every element Dotazník draws for a question or a set, once for each (QuestionnaireStep). */
function drawnElements(xs: readonly Section[]): string[] {
  return xs.flatMap((sec, si) =>
    !isObject(sec) ? [] : sec.type === "questions" ? (sec.questions || []).map((q) => questionElementId(isObject(q) ? q : {})) : [setElementId(sec, si)],
  );
}

/**
 * The element a link to Dotazník opens (``gapFixes``, read from the hash). A question or set is
 * named by the server's id (``compiledPlaces``) and opens the element drawn for it, never one the
 * web's own id happens to match. One the questionnaire no longer has, one drawn nowhere, and one
 * whose element shares its id with another's (two questions the web gave one id) open the editor:
 * never a guess between them. Any other place (the comparisons card) is its own element.
 */
export function questionnairePlace(anchor: string, xs: readonly Section[]): string {
  if (!/^q(edit|set)_/.test(anchor)) return anchor;
  const element = compiledPlaces(xs).find((p) => p.anchor === anchor)?.element;
  return element && drawnElements(xs).filter((id) => id === element).length === 1 ? element : EDITOR;
}

/** The server refused a start or retry for its research questions: the answerability it gave. */
export function unanswerableAsked(e: unknown): Answerability | null {
  if (!(e instanceof ApiError) || e.code !== "research_questions_unanswerable") return null;
  const d = e.details as Partial<Answerability>;
  if (typeof d.digest !== "string" || !Array.isArray(d.gaps) || d.capable !== false) return null;
  // A refusal is the requirement itself, whatever an older payload said.
  return { ...(d as Answerability), acknowledgement_required: true };
}
