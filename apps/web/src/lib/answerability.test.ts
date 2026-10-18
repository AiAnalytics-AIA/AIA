import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { ApiError, type Answerability, type AnswerabilityGap, type QuestionOutlook } from "./api";
import { t } from "@/i18n/t";
import type { Section } from "@/research/questionnaire";
import {
  acknowledgementOf,
  acknowledges,
  compiledPlaces,
  fixHref,
  refusalFor,
  GAP_REASONS,
  gapFixes,
  gapWords,
  hashTarget,
  hasGaps,
  MAX_REASON,
  MIN_REASON,
  NO_ACKNOWLEDGEMENT,
  needsAcknowledgement,
  pythonCollapse,
  questionnairePlace,
  unanswerableAsked,
} from "./answerability";

const FIO_LIKE: Answerability = {
  rules: "aia-answerability-1",
  capable: false,
  digest: "a".repeat(64),
  acknowledgement_required: true,
  gaps: [
    { kind: "not_answerable", research_question: "Jak klienti důvěřují účtu?", verdict: "UNKNOWN", reasons: ["unlinked_design"], measures: [] },
    { kind: "not_answerable", research_question: "Co je odrazuje?", verdict: "UNANSWERABLE", reasons: ["measures_unanswerable"], measures: ["q2"] },
  ],
};
const given = (reason: string, digest: string | null = FIO_LIKE.digest) => ({ digest, confirmed: true, reason });

describe("answerability (research-integrity-report 1)", () => {
  it("asks exactly where the server would refuse: gaps and the deployment's requirement", () => {
    expect(needsAcknowledgement(FIO_LIKE)).toBe(true);
    // The switch off: the gaps are shown, nothing is asked.
    expect(hasGaps({ ...FIO_LIKE, acknowledgement_required: false })).toBe(true);
    expect(needsAcknowledgement({ ...FIO_LIKE, acknowledgement_required: false })).toBe(false);
    expect(needsAcknowledgement({ ...FIO_LIKE, capable: true, gaps: [] })).toBe(false);
    // An older API says nothing: never asked, never read as capable either.
    expect(needsAcknowledgement({ ...FIO_LIKE, acknowledgement_required: undefined })).toBe(false);
    expect(needsAcknowledgement(undefined)).toBe(false);
  });

  it("sends the digest the person saw with a reason, and nothing until both are given", () => {
    expect(acknowledgementOf(FIO_LIKE, NO_ACKNOWLEDGEMENT)).toBeNull();
    expect(acknowledgementOf(FIO_LIKE, { ...given("Ověřujeme postup."), confirmed: false })).toBeNull();
    expect(acknowledgementOf(FIO_LIKE, given("krátké"))).toBeNull();
    expect(acknowledgementOf(FIO_LIKE, given("  Ověřujeme   jen postup. "))).toEqual({
      digest: FIO_LIKE.digest,
      reason: "Ověřujeme jen postup.",
    });
    // Collapsed as the server collapses it, by Python's whitespace (review web#9), so the reason
    // the run holds is the one sent (acknowledges).
    expect(acknowledgementOf(FIO_LIKE, given("Ověřujeme\u0085jen\u001fpostup.\ufeff"))?.reason).toBe("Ověřujeme jen postup.\ufeff");
  });

  it("counts the reason in characters as the server does, never in UTF-16 units", () => {
    // Acknowledgement counts code points (len); a character beyond U+FFFF is two UTF-16 units,
    // so counting units sent five emoji the server refuses (422 acknowledgement_invalid).
    const emoji = "\u{1F600}";
    expect(acknowledgementOf(FIO_LIKE, given(emoji.repeat(9)))).toBeNull();
    expect(acknowledgementOf(FIO_LIKE, given(emoji.repeat(5)))).toBeNull();
    expect(acknowledgementOf(FIO_LIKE, given(emoji.repeat(10)))?.reason).toBe(emoji.repeat(10));
    // And at the top: the server takes 1,000 characters however many units they are.
    expect(acknowledgementOf(FIO_LIKE, given(emoji.repeat(MAX_REASON)))?.reason).toBe(emoji.repeat(MAX_REASON));
    expect(acknowledgementOf(FIO_LIKE, given(emoji.repeat(MAX_REASON + 1)))).toBeNull();
    expect(acknowledgementOf(FIO_LIKE, given("a".repeat(MIN_REASON)))?.reason).toBe("a".repeat(MIN_REASON));
    expect(acknowledgementOf(FIO_LIKE, given("a".repeat(MIN_REASON - 1)))).toBeNull();
  });

  it("covers only the gaps it was given for: a design that changed asks again", () => {
    const changed = { ...FIO_LIKE, digest: "b".repeat(64) };
    expect(acknowledgementOf(changed, given("Ověřujeme jen postup."))).toBeNull();
    expect(acknowledgementOf(changed, given("Ověřujeme jen postup.", changed.digest))?.digest).toBe(changed.digest);
  });

  it("words each gap: whether the run will not or may not answer it, and why", () => {
    const first = gapWords(FIO_LIKE.gaps[0]);
    expect(first.verdict).toBe(t("research.exec.answerability.unshown"));
    expect(first.why).toContain("žádná otázka dotazníku neuvádí");
    const second = gapWords(FIO_LIKE.gaps[1]);
    expect(second.verdict).toBe(t("research.exec.answerability.wont"));
    expect(second.why).toContain("měří ji jen otázky");
    expect(gapWords({ kind: "no_research_questions", research_question: null, verdict: null, reasons: [], measures: [] }).why).toContain(
      "neuvádí žádnou výzkumnou otázku",
    );
  });

  it("words every reason the server gives, and keeps a code it has no words for on screen", () => {
    for (const reason of GAP_REASONS) {
      const key = `research.exec.answerability.reason.${reason}`;
      expect(t(key), reason).not.toBe(key);
      expect(gapWords({ kind: "not_answerable", research_question: "X?", verdict: "UNKNOWN", reasons: [reason], measures: [] }).why).not.toContain(reason);
    }
    // Never hidden behind the generic words, never printed as if it were a sentence (reason-words).
    const unknown = gapWords({ kind: "not_answerable", research_question: "X?", verdict: "UNKNOWN", reasons: ["future_reason"], measures: [] });
    expect(unknown.why).toBe(`${t("research.exec.answerability.reasonUnknown")} (${t("research.exec.code.technical")}: future_reason)`);
  });

  it("tells a run that holds the acknowledgement from one a start only found", () => {
    const given = { digest: FIO_LIKE.digest, reason: "Ověřujeme jen postup." };
    const held = { ...FIO_LIKE, acknowledgement: { reason: given.reason, by: "u1" } };
    expect(acknowledges({ answerability: held }, given)).toBe(true);
    // The revision's earlier run, started where nothing was asked: nothing recorded now.
    expect(acknowledges({ answerability: { ...FIO_LIKE, acknowledgement: null, enforced: false } }, given)).toBe(false);
    expect(acknowledges({ answerability: { ...held, digest: "c".repeat(64) } }, given)).toBe(false);
    expect(acknowledges({ answerability: null }, given)).toBe(false);
  });

  it("keeps a refused retry's gaps for the run they were refused for alone", () => {
    // Review 3: no test reached the run-id binding; a refusal for one run offered to retry another.
    const refusal = { runId: "RUN-1", answer: FIO_LIKE };
    expect(refusalFor(refusal, { run_id: "RUN-1", retryable: true }, true)).toBe(FIO_LIKE);
    expect(refusalFor(refusal, { run_id: "RUN-2", retryable: true }, true)).toBeNull();
    expect(refusalFor(refusal, { run_id: "RUN-1", retryable: false }, true)).toBeNull();
    expect(refusalFor(refusal, { run_id: "RUN-1", retryable: true }, false)).toBeNull();
    expect(refusalFor(null, { run_id: "RUN-1", retryable: true }, true)).toBeNull();
  });

  it("reads the server's refusal of a start or retry as a requirement", () => {
    const e = new ApiError(409, "research_questions_unanswerable", "…", null, { ...FIO_LIKE, acknowledgement_required: undefined } as unknown as Record<string, unknown>);
    const asked = unanswerableAsked(e);
    expect(asked?.digest).toBe(FIO_LIKE.digest);
    expect(needsAcknowledgement(asked)).toBe(true);
    expect(unanswerableAsked(new ApiError(409, "cost_confirmation_required", "…", null))).toBeNull();
  });
});

describe("where a gap is fixed (research-integrity-report 14, D1)", () => {
  const gap = (reasons: string[], measures: string[] = []): AnswerabilityGap => ({
    kind: "not_answerable", research_question: "Co klienty odrazuje?", verdict: "UNANSWERABLE", reasons, measures,
  });
  const item = (id: string, battery: string | null, verdict: QuestionOutlook["verdict"], reasons: string[] = []): QuestionOutlook => ({
    question_id: id, text: id, section_id: battery ?? "blok", battery_id: battery, verdict, reasons,
  });
  // A set's measure ids are <set>_obj_<object>; the set is read from battery_id, never from the id.
  const OUTLOOK = [
    item("q1", null, "ANSWERABLE"),
    item("q2", null, "UNANSWERABLE", ["conditional"]),
    item("q3", null, "AT_RISK", ["open_ended"]),
    item("q4", null, "AT_RISK", ["support_suppressed"]),
    item("banky_obj_fio", "sada_bank", "ANSWERABLE"),
    item("banky_obj_csob", "sada_bank", "UNANSWERABLE", ["familiarity"]),
  ];
  // Every reason the server gives a gap, with its measures and the place it is fixed.
  const PLACES: Record<(typeof GAP_REASONS)[number], [string[], string, string | null]> = {
    unmeasured: [[], "questionnaire", "q-editor"],
    unlinked_design: [[], "questionnaire", "q-editor"],
    comparison_needs_tracked_set: [["q1"], "questionnaire", "q-comparisons"],
    comparison_needs_concept_set: [["q1"], "questionnaire", "q-comparisons"],
    segments_unavailable: [["q1"], "questionnaire", "q-comparisons"],
    comparison_unknown: [["q1"], "questionnaire", "q-comparisons"],
    measures_unanswerable: [["q1", "q2"], "questionnaire", "qedit_q2"],
    no_citable_measure: [["q3"], "questionnaire", "qedit_q3"],
    comparison_set_unanswerable: [["q1", "banky_obj_fio", "banky_obj_csob"], "questionnaire", "qset_sada_bank"],
  };

  it("sends every reason the server gives to a place, in words", () => {
    expect(Object.keys(PLACES).sort()).toEqual([...GAP_REASONS].sort());
    for (const reason of GAP_REASONS) {
      const [measures, step, anchor] = PLACES[reason];
      const fixes = gapFixes(gap([reason], measures), OUTLOOK);
      expect(fixes.map((f) => [f.step, f.anchor]), reason).toEqual([[step, anchor]]);
      expect(fixes[0].words, reason).not.toContain("research.exec");
    }
  });

  it("sends a design with no research question to Návrh", () => {
    const none: AnswerabilityGap = { kind: "no_research_questions", research_question: null, verdict: null, reasons: [], measures: [] };
    expect(gapFixes(none, OUTLOOK)).toEqual([{ step: "plan", anchor: "plan-understanding", words: t("research.exec.answerability.fixTo.plan") }]);
  });

  it("sends a measure to its question, its set, or Dimenze where only more respondents help", () => {
    expect(gapFixes(gap(["measures_unanswerable"], ["q4"]), OUTLOOK)).toEqual([
      { step: "persona", anchor: null, words: t("research.exec.answerability.fixTo.support") },
    ]);
    expect(gapFixes(gap(["measures_unanswerable"], ["banky_obj_csob"]), OUTLOOK).map((f) => f.anchor)).toEqual(["qset_sada_bank"]);
    // An id the outlook does not list: its question, which Dotazník opens if it has one.
    expect(gapFixes(gap(["no_citable_measure"], ["q9"]), OUTLOOK).map((f) => f.anchor)).toEqual(["qedit_q9"]);
    expect(gapFixes(gap(["measures_unanswerable"], []), OUTLOOK).map((f) => f.anchor)).toEqual(["q-editor"]);
    // A set the outlook does not know: the editor, never a set guessed from an id.
    expect(gapFixes(gap(["comparison_set_unanswerable"], ["q1", "banky_obj_kb"]), OUTLOOK).map((f) => f.anchor)).toEqual(["q-editor"]);
  });

  it("sends a measure the run will not answer to one the analysis may cite, never to an open question beside it (F10)", () => {
    // The gaps and outlooks as domain/answerability.py gives them: measures_unanswerable is about
    // the citable measures alone, so an open question is never the one to edit.
    const refused = [item("q_open", null, "AT_RISK", ["open_ended"]), item("q_wtp", null, "UNANSWERABLE", ["fidelity_refused"])];
    expect(gapFixes(gap(["measures_unanswerable"], ["q_open", "q_wtp"]), refused).map((f) => f.anchor)).toEqual(["qedit_q_wtp"]);
    // A forecast that suppresses support marks every item, the open one first: only more respondents help.
    const suppressed = [
      item("q_open", null, "UNANSWERABLE", ["open_ended", "support_suppressed"]),
      item("q_scale", null, "UNANSWERABLE", ["support_suppressed"]),
    ];
    expect(gapFixes(gap(["measures_unanswerable"], ["q_open", "q_scale"]), suppressed)).toEqual([
      { step: "persona", anchor: null, words: t("research.exec.answerability.fixTo.support") },
    ]);
    // A citable id the outlook does not list comes before an uncitable one it knows.
    expect(gapFixes(gap(["measures_unanswerable"], ["q3", "q9"]), OUTLOOK).map((f) => f.anchor)).toEqual(["qedit_q9"]);
    // Measured only by uncitable items: any of them, the first the run may not answer.
    expect(gapFixes(gap(["no_citable_measure"], ["q_open", "q_wtp"]), refused).map((f) => f.anchor)).toEqual(["qedit_q_open"]);
  });

  it("without an outlook (a refused retry), stops at a stage or a section", () => {
    const anchors = (reasons: string[], measures: string[]) => gapFixes(gap(reasons, measures), null).map((f) => f.anchor);
    expect(anchors(["measures_unanswerable"], ["q2"])).toEqual(["q-editor"]);
    expect(anchors(["comparison_set_unanswerable"], ["banky_obj_csob"])).toEqual(["q-editor"]);
    expect(anchors(["comparison_unknown"], ["q1"])).toEqual(["q-comparisons"]);
    expect(anchors(["unlinked_design"], [])).toEqual(["q-editor"]);
  });

  it("names each place once, in the order of the reasons", () => {
    expect(gapFixes(gap(["unlinked_design", "unmeasured"]), OUTLOOK).map((f) => f.anchor)).toEqual(["q-editor"]);
    expect(gapFixes(gap(["comparison_unknown", "segments_unavailable", "no_citable_measure"], ["q3"]), OUTLOOK).map((f) => f.anchor)).toEqual([
      "q-comparisons",
      "qedit_q3",
    ]);
  });

  it("keeps a reason it does not know on the way to Dotazník, never without a way", () => {
    expect(gapFixes(gap(["future_reason"]), OUTLOOK)).toEqual([
      { step: "questionnaire", anchor: null, words: t("research.exec.answerability.fixTo.questionnaire") },
    ]);
    expect(gapFixes(gap(["future_reason", "unlinked_design"]), OUTLOOK).map((f) => f.anchor)).toEqual([null, "q-editor"]);
  });

  it("reads a record from before every gap carried a reason as gapWords does", () => {
    expect(gapFixes(gap([], ["q2"]), OUTLOOK).map((f) => f.anchor)).toEqual(["qedit_q2"]);
    expect(gapFixes(gap([], []), OUTLOOK).map((f) => f.anchor)).toEqual(["q-editor"]);
  });

  it("links to the stage with the place as its hash, and reads the hash back", () => {
    const stage = (step: string) => `/app/clients/CLI-1/research/STU-1/${step}`;
    expect(fixHref({ step: "questionnaire", anchor: "qset_sada bank", words: "" }, stage)).toBe("/app/clients/CLI-1/research/STU-1/questionnaire#qset_sada%20bank");
    expect(fixHref({ step: "persona", anchor: null, words: "" }, stage)).toBe("/app/clients/CLI-1/research/STU-1/persona");
    expect(hashTarget("#qset_sada%20bank")).toBe("qset_sada bank");
    expect(hashTarget("#qedit_q2")).toBe("qedit_q2");
    expect(hashTarget("")).toBeNull();
    expect(hashTarget("#")).toBeNull();
    expect(hashTarget("#%E0%A4%A")).toBeNull();
  });
});

// Sections and the ids compile_design writes for them; test_compiled_ids_web_fixture.py checks the server's side.
const COMPILED = JSON.parse(readFileSync(join(process.cwd(), "src/lib/fixtures/compiled-ids.json"), "utf8")) as {
  sections: Section[];
  questions: string[];
  sets: string[];
  /** Every code point Python's ``re`` ``\s`` and ``str.strip()`` take (the Python test checks it). */
  whitespace: number[];
};

describe("the place a link names in Dotazník (review, 2026-10-18)", () => {
  it("writes each question's and set's id as the server compiles it", () => {
    const anchors = compiledPlaces(COMPILED.sections).map((p) => p.anchor);
    expect(anchors.filter((a) => a.startsWith("qedit_"))).toEqual(COMPILED.questions.map((id) => `qedit_${id}`));
    expect(anchors.filter((a) => a.startsWith("qset_"))).toEqual(COMPILED.sets.map((id) => `qset_${id}`));
  });

  it("opens the element drawn for the item a link names, never a guess between two", () => {
    const place = (anchor: string) => questionnairePlace(anchor, COMPILED.sections);
    // The server lower-cases and folds the web's ids; Dotazník draws the web's.
    expect(place("qedit_q_wb1")).toBe("qedit_Q_wb1");
    expect(place("qedit_q1_2")).toBe("qedit_q1");
    expect(place("qedit_q_1a")).toBe("qedit_1a");
    expect(place("qedit_ci")).toBe("qedit_Čí?");
    expect(place("qedit_sec_brands_7")).toBe("qedit_  ");
    expect(place("qedit_q_12")).toBe("qedit_12");
    expect(place("qedit_x1")).toBe("qedit_X1");
    // Python's whitespace, not JavaScript's (review web#9): U+001C–U+001F and U+0085 are
    // whitespace to the server, so an id of only those is none; U+FEFF is not, so one of only it
    // is the server's "q".
    expect(place("qedit_sec_brands_9")).toBe("qedit_\u001c");
    expect(place("qedit_sec_brands_10")).toBe("qedit_\u0085");
    expect(place("qedit_q")).toBe("qedit_\ufeff");
    expect(place("qset_sekce_9")).toBe("qset_\u001f");
    // Python's truthiness, not JavaScript's: an empty list or object is nothing to the server.
    // A question typed [] or {} is its "vyber", so the ids after it move on; a link to the
    // server's t1 opens the question it compiled as t1, never the next one.
    expect(place("qedit_t1")).toBe("qedit_T1");
    expect(place("qedit_t1_2")).toBe("qedit_t1");
    expect(place("qedit_t2")).toBe("qedit_T2");
    // A section typed [] or {} is questions to the server and a set to Dotazník: drawn nowhere.
    expect(place("qedit_e1")).toBe("q-editor");
    expect(place("qedit_e2")).toBe("q-editor");
    expect(place("qset_sada_bank")).toBe("qset_Sada bank");
    expect(place("qset_druha_sada")).toBe("qset_3");
    expect(place("qset_sekce_5")).toBe("qset_4");
    // Drawn under an id another question's element has too ("Q1" twice, three without one): the editor.
    expect(place("qedit_q1")).toBe("q-editor");
    expect(place("qedit_q1_3")).toBe("q-editor");
    expect(place("qedit_sec_brands_4")).toBe("q-editor");
    expect(place("qedit_sada_bank_2_2")).toBe("q-editor");
    // In a section without a type, which Dotazník draws as a set: drawn nowhere.
    expect(place("qedit_n1")).toBe("q-editor");
    // The web's own id names no item a link can name; nor does one the questionnaire no longer has.
    expect(place("qedit_Q_wb1")).toBe("q-editor");
    expect(place("qedit_gone")).toBe("q-editor");
    // A place that is not an item is its own element.
    expect(place("q-comparisons")).toBe("q-comparisons");
  });

  it("collapses exactly Python's whitespace, code point by code point (review web#9)", () => {
    const python = new Set(COMPILED.whitespace);
    const apart: number[] = [];
    for (let c = 0; c <= 0x10ffff; c++) {
      if (c >= 0xd800 && c <= 0xdfff) continue; // a lone surrogate is no Python str a design holds
      const ch = String.fromCodePoint(c);
      const collapsed = pythonCollapse(`a${ch}${ch}b`) === "a b" && pythonCollapse(`${ch}a${ch}`) === "a";
      const kept = pythonCollapse(`a${ch}b`) === `a${ch}b`;
      if (python.has(c) ? !collapsed : !kept) apart.push(c);
    }
    expect(apart).toEqual([]);
    // Where JavaScript's own \s would have parted from it.
    expect(pythonCollapse("\u001c\u0085 Q \u001f")).toBe("Q");
    expect(pythonCollapse("\ufeff")).toBe("\ufeff");
  });

  it("gives no id to a question the server refuses, and stops at one it may write otherwise", () => {
    const q = (id: unknown, text = "Jak často?") => ({ id, text, typ: "skala" }) as unknown as NonNullable<Section["questions"]>[number];
    const blank: Section[] = [{ id: "s", type: "questions", questions: [q("Q1", " "), q("q1")] }];
    expect(compiledPlaces(blank)).toEqual([{ anchor: "qedit_q1", element: "qedit_q1" }]);
    // A number that is not whole: Python and JavaScript write some apart (1e16, 1e-7), so none is guessed at.
    const odd: Section[] = [{ id: "s", type: "questions", questions: [q("Q1"), q(1.5), q("Q2")] }];
    expect(compiledPlaces(odd).map((p) => p.anchor)).toEqual(["qedit_q1"]);
    expect(questionnairePlace("qedit_q2", odd)).toBe("q-editor");
  });
});
