// A stored code in words (run-recovery-and-truth 6b): words where the client has them, a plain
// "no words for this" otherwise, the code kept aside, never printed as if it were a sentence.
import { describe, expect, it } from "vitest";

import type { ResearchPhase } from "@/lib/api";
import { codedText, codeWords, coverageWords, deepStepLabel, known, stepProblem, searchedNothing } from "./reason-words";
import { phaseLabel } from "./research-execution";

const step = (extra: { status?: string; waiting_reason?: string | null; error_message?: string | null }) => ({
  status: "RUNNING",
  waiting_reason: null,
  error_message: null,
  ...extra,
});

describe("reason words", () => {
  it("says the words a code has, and keeps the code of one it has none for", () => {
    expect(codeWords("research.exec.trace.quarantine", "low_source_quality")).toEqual({ words: "nízká kvalita zdroje", code: null });
    expect(codeWords("research.exec.trace.quarantine", "brand_new_reason")).toEqual({
      words: "AIA k tomuto záznamu zatím nemá popis.",
      code: "brand_new_reason",
    });
    expect(known("research.exec.nothing.here")).toBeNull();
  });

  it("keeps an unknown code in a line of text, after the words, and words a known one alone", () => {
    expect(codedText(codeWords("research.deep.counts", "new_metric", "research.deep.counts.other"))).toBe("jiný počet (technický kód: new_metric)");
    expect(codedText(codeWords("research.deep.counts", "fetches", "research.deep.counts.other"))).toBe("otevřené stránky");
  });

  it("names Deep Research's steps and an investigate track, never by its node key", () => {
    expect(deepStepLabel("verify")).toBe("Ověření podkladů");
    expect(deepStepLabel("investigate/web-2")).toBe("Hledání zdrojů (web-2)");
    expect(deepStepLabel("something_new")).toBe("Krok rešerše");
  });

  it("tells what a step recorded: the wait's detail, a failure's message, then the bare reason", () => {
    expect(stepProblem(step({ status: "AWAITING_BUDGET", waiting_reason: "budget_exceeded" }))?.words).toBe("Krok čeká, protože by překročil rozpočet studie.");
    expect(stepProblem(step({ status: "FAILED", error_message: "Brána odmítla." }))).toEqual({ words: "Brána odmítla.", code: null });
    expect(stepProblem(step({ waiting_reason: "ai_runtime_unavailable" }))?.code).toBeNull();
    expect(stepProblem(step({ waiting_reason: "gate:licence" }))).toEqual({ words: "AIA k tomuto záznamu zatím nemá popis.", code: "gate:licence" });
    expect(stepProblem(step({}))).toBeNull();
  });

  it("never prints a phase or a coverage it does not know as a key or a code", () => {
    expect(phaseLabel("WAITING")).toBe("Čeká");
    expect(phaseLabel("SOMETHING_NEW" as ResearchPhase)).toBe("Neznámý stav");
    expect(coverageWords("PARTIAL")).toBe("Částečné pokrytí");
    expect(coverageWords("SOMETHING_NEW")).toBe("Pokrytí nelze určit");
  });
});

describe("searchedNothing (PC18)", () => {
  it("is a run that sent no query, never a run whose coverage is unknown", () => {
    expect(searchedNothing({ queries_sent: 0 })).toBe(true);
    expect(searchedNothing({ queries_sent: 3 })).toBe(false);
    expect(searchedNothing(null)).toBe(false);
    expect(searchedNothing(undefined)).toBe(false);
  });
});
