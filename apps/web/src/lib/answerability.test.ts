import { describe, expect, it } from "vitest";
import { ApiError, type Answerability } from "./api";
import { t } from "@/i18n/t";
import {
  acknowledgementOf,
  GAP_REASONS,
  gapWords,
  hasGaps,
  NO_ACKNOWLEDGEMENT,
  needsAcknowledgement,
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

  it("reads the server's refusal of a start or retry as a requirement", () => {
    const e = new ApiError(409, "research_questions_unanswerable", "…", null, { ...FIO_LIKE, acknowledgement_required: undefined } as unknown as Record<string, unknown>);
    const asked = unanswerableAsked(e);
    expect(asked?.digest).toBe(FIO_LIKE.digest);
    expect(needsAcknowledgement(asked)).toBe(true);
    expect(unanswerableAsked(new ApiError(409, "cost_confirmation_required", "…", null))).toBeNull();
  });
});
