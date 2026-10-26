import { describe, expect, it } from "vitest";

import type { Readiness } from "./api";
import { ceilingOf, checkStage, compositionOf, outlookTiles, personaSourcesOf, readinessLine, readinessSummary, sourceChosenOnRun, supportForecastOf } from "./sample-view";

const readiness = (over: Partial<Readiness>): Readiness => ({
  design_revision_id: "r1", rules: "aia-readiness-1", ready: true, checks: [], questions: 3, batteries: 0, objects: 0, n: 200,
  fieldwork_source: "ai_runtime", cost_ceiling_usd: null, cost_ceiling_unknown: null, fieldwork_requests: 0, analysis_calls: 0,
  spend_confirm_usd: null, confirmation_required: false, ...over,
});

describe("ceilingOf", () => {
  it("is the server's ceiling at the n it read, or its reason, never a zero", () => {
    expect(ceilingOf(readiness({ n: 300, cost_ceiling_usd: 2.25 }))).toEqual({ known: true, usd: 2.25, n: 300 });
    expect(ceilingOf(readiness({ cost_ceiling_usd: 0 }))).toEqual({ known: true, usd: 0, n: 200 });
    expect(ceilingOf(readiness({ cost_ceiling_unknown: "fieldwork_reservation_missing" }))).toEqual({ known: false, code: "fieldwork_reservation_missing" });
    expect(ceilingOf(readiness({ n: null }))).toEqual({ known: false, code: "sample_size_missing" });
  });
});

describe("supportForecastOf", () => {
  it("reads the server's forecast check for the fictional roster", () => {
    const r = readiness({ persona_source: "fictional_roster", checks: [{ id: "support_forecast", status: "PASS", message: "Běh bude mít 67 různých dárců na 200 respondentů: opora stačí." }] });
    expect(supportForecastOf(r)).toEqual({ known: true, status: "PASS", message: "Běh bude mít 67 různých dárců na 200 respondentů: opora stačí." });
  });

  it("reads a panel run's forecast as unknown, never good, keeping the server's words", () => {
    const r = readiness({ persona_source: "panel", checks: [{ id: "support_forecast", status: "WARN", message: "Kolik různých dárců běh bude mít, se ukáže až při výběru." }] });
    expect(supportForecastOf(r)).toEqual({ known: false, message: "Kolik různých dárců běh bude mít, se ukáže až při výběru." });
  });

  it("reads a panel run's forecast as known when the server drew the sample a start would draw", () => {
    const composition = { refused: null, version_id: "DSV-1", seed: 7, quota_fields: ["pohlavi"], cells: [], sample_donors: 120, support_counted: true };
    const check = { id: "support_forecast", status: "PASS" as const, message: "Běh bude mít 120 různých dárců na 200 respondentů: opora stačí." };
    expect(supportForecastOf(readiness({ persona_source: "panel", checks: [check], sample_composition: composition }))).toEqual({ known: true, status: "PASS", message: check.message });
    // A refused draw counted nothing.
    expect(supportForecastOf(readiness({ persona_source: "panel", checks: [check], sample_composition: { ...composition, refused: "sampling_empty" } })).known).toBe(false);
    // Drawn, but the forecast was not counted from it (a respondent without a donor), or an older
    // API that does not say: the unknown check's words are never read as a counted forecast.
    expect(supportForecastOf(readiness({ persona_source: "panel", checks: [check], sample_composition: { ...composition, support_counted: false } })).known).toBe(false);
    expect(supportForecastOf(readiness({ persona_source: "panel", checks: [check], sample_composition: { ...composition, support_counted: undefined } })).known).toBe(false);
  });

  it("reads a readiness without the check as unknown", () => {
    expect(supportForecastOf(readiness({ checks: [{ id: "sample_size", status: "PASS", message: "n 200" }] }))).toEqual({ known: false, message: null });
  });
});

describe("outlookTiles", () => {
  const item = (verdict: "ANSWERABLE" | "AT_RISK" | "UNKNOWN" | "UNANSWERABLE", reasons: string[] = []) => ({ question_id: verdict, text: "", section_id: "s", battery_id: null, verdict, reasons });

  it("counts the server's verdicts, naming each tile's commonest reason, the first met on a tie", () => {
    const tiles = outlookTiles(readiness({ question_outlook: [
      item("ANSWERABLE"), item("ANSWERABLE"),
      item("AT_RISK", ["open_ended"]), item("AT_RISK", ["support_analysis_excluded"]), item("AT_RISK", ["support_analysis_excluded"]),
      item("UNKNOWN", ["support_unknown"]), item("UNKNOWN", ["support_unknown"]),
    ] }));
    expect(tiles).toEqual([
      { verdict: "ANSWERABLE", count: 2, reason: null },
      { verdict: "AT_RISK", count: 3, reason: "support_analysis_excluded" },
      { verdict: "UNKNOWN", count: 2, reason: "support_unknown" },
    ]);
  });

  it("captions a tile only by the reasons that give its verdict, never the support reason every item shares", () => {
    const tiles = outlookTiles(readiness({ question_outlook: [
      item("UNANSWERABLE", ["conditional", "support_indicative"]), item("UNANSWERABLE", ["fidelity_refused", "support_indicative"]),
      item("AT_RISK", ["open_ended", "support_unknown"]), item("UNKNOWN", ["support_unknown"]),
      item("AT_RISK", ["new_reason", "support_unknown"]), item("AT_RISK", ["new_reason"]),
    ] }));
    expect(tiles!.find((t) => t.verdict === "UNANSWERABLE")!.reason).toBe("conditional");
    // A code this client does not know still counts, so it is named.
    expect(tiles!.find((t) => t.verdict === "AT_RISK")!.reason).toBe("new_reason");
  });

  it("shows unanswerable only when an item is, and the three others even at zero", () => {
    expect(outlookTiles(readiness({ question_outlook: [item("ANSWERABLE")] }))!.map((t) => [t.verdict, t.count])).toEqual([["ANSWERABLE", 1], ["AT_RISK", 0], ["UNKNOWN", 0]]);
    expect(outlookTiles(readiness({ question_outlook: [item("UNANSWERABLE", ["fidelity_refused"])] }))!.at(-1)).toEqual({ verdict: "UNANSWERABLE", count: 1, reason: "fidelity_refused" });
  });

  it("is null when the API sent no outlook, never all answered", () => {
    expect(outlookTiles(readiness({}))).toBeNull();
    expect(outlookTiles(readiness({ question_outlook: [] }))).toBeNull();
  });
});

describe("personaSourcesOf", () => {
  it("lists the server's sources as sent", () => {
    const sources = [
      { source: "fictional_roster", offered: true, reason: null, default: true },
      { source: "panel", offered: false, reason: "panel_personas_disabled", default: false },
    ];
    expect(personaSourcesOf(readiness({ persona_sources: sources }))).toEqual(sources);
  });

  it("is null when the API sent none, never a default", () => {
    expect(personaSourcesOf(readiness({}))).toBeNull();
    expect(personaSourcesOf(readiness({ persona_sources: [] }))).toBeNull();
  });
});

describe("sourceChosenOnRun", () => {
  const sources = [{ source: "fictional_roster", offered: true, reason: null, default: true }];

  it("is true only for an AI-answered run with sources, as Spuštění offers the choice", () => {
    expect(sourceChosenOnRun(readiness({ persona_sources: sources }))).toBe(true);
    expect(sourceChosenOnRun(readiness({ fieldwork_source: "synthetic_fixture", persona_sources: sources }))).toBe(false);
    expect(sourceChosenOnRun(readiness({}))).toBe(false);
  });
});

describe("checkStage", () => {
  it("sends each known check to the stage that fixes it", () => {
    expect(checkStage("sample_size")).toBe("dimensions");
    expect(checkStage("sociomap_support")).toBe("dimensions");
    expect(checkStage("dimensions")).toBe("dimensions");
    expect(checkStage("audience")).toBe("audience");
    // A panel sample the sampler refuses: its filters are set on Cílová skupina (RQC6).
    expect(checkStage("panel_sample")).toBe("audience");
    expect(checkStage("conditional_questions")).toBe("questionnaire");
  });

  it("sends the server's per-item checks by their prefix: a design that does not compile, a tracked set's size", () => {
    expect(checkStage("compile:empty_questionnaire:sections")).toBe("questionnaire");
    expect(checkStage("battery_size:b1")).toBe("questionnaire");
    expect(checkStage("condition:q3")).toBe("questionnaire");
    expect(checkStage("compile")).toBeNull();
    expect(checkStage("toString:x")).toBeNull();
  });

  it("names no stage for a check it does not know, never a guess", () => {
    expect(checkStage("new_server_check")).toBeNull();
    expect(checkStage("toString")).toBeNull();
  });
});

describe("readinessSummary", () => {
  const check = (id: string, status: string) => ({ id, status, message: id }) as Readiness["checks"][number];

  it("orders worst first, keeping the server's order within a status, and counts each", () => {
    const s = readinessSummary(readiness({ checks: [check("a", "PASS"), check("b", "WARN"), check("c", "FAIL"), check("d", "WARN")] }));
    expect(s.checks.map((c) => c.id)).toEqual(["c", "b", "d", "a"]);
    expect(s).toMatchObject({ blocking: 1, warnings: 2, unknown: 0 });
  });

  it("puts a status it does not know first and never counts it as passed, an inherited name included", () => {
    const s = readinessSummary(readiness({ checks: [check("a", "PASS"), check("x", "SKIPPED"), check("y", "toString")] }));
    expect(s.checks.map((c) => c.id)).toEqual(["x", "y", "a"]);
    expect(s).toMatchObject({ blocking: 0, warnings: 0, unknown: 2 });
  });

  it("carries the server's verdict, which the counts never override", () => {
    expect(readinessSummary(readiness({ ready: false, checks: [check("a", "PASS")] }))).toMatchObject({ ready: false, blocking: 0 });
  });
});

describe("compositionOf", () => {
  const drawn = (over: Partial<NonNullable<Readiness["sample_composition"]>> = {}) => ({
    refused: null, version_id: "DSV-1", seed: 7, quota_fields: ["pohlavi", "vek_skupina"], sample_donors: 9,
    cells: [
      { key: "muz/18-29", values: ["muž", "18-29"], n: 2 },
      { key: "zena/18-29", values: ["žena", "18-29"], n: 5 },
      { key: "zena/30-44", values: ["žena", "30-44"], n: 0 },
      { key: "missing/65", values: ["<missing>", "65+"], n: 3 },
    ],
    ...over,
  });

  it("reads the sampler's allotment: cells with respondents, largest first, each with its share of n", () => {
    const c = compositionOf(readiness({ persona_source: "panel", sample_composition: drawn() }));
    expect(c).toEqual({
      kind: "drawn",
      fields: ["Pohlaví", "Věk"],
      total: 10,
      donors: 9,
      rows: [
        { key: "zena/18-29", label: "žena · 18-29", n: 5, share: 0.5 },
        { key: "missing/65", label: "neuvedeno · 65+", n: 3, share: 0.3 },
        { key: "muz/18-29", label: "muž · 18-29", n: 2, share: 0.2 },
      ],
    });
  });

  it("says why the sampler refused, in the audience step's words", () => {
    expect(compositionOf(readiness({ persona_source: "panel", sample_composition: drawn({ refused: "sampling_empty", cells: [] }) }))).toEqual({
      kind: "refused",
      words: "Filtry nevyberou žádného člověka z populace.",
    });
    expect(compositionOf(readiness({ persona_source: "panel", sample_composition: drawn({ refused: "something_new", cells: [] }) }))).toEqual({
      kind: "refused",
      words: "Výběr odmítnut (something_new).",
    });
  });

  it("names what a refusal names, and finishes a fragment that names nothing (review on #725)", () => {
    expect(compositionOf(readiness({ persona_source: "panel", sample_composition: drawn({ refused: "sampling_field_refused", refused_reasons: ["kraj: research_only"], cells: [] }) }))).toEqual({
      kind: "refused",
      words: "Politika pole nepovoluje filtrovat podle: kraj: research_only.",
    });
    for (const code of ["sampling_field_refused", "sampling_filter_invalid"]) {
      const c = compositionOf(readiness({ persona_source: "panel", sample_composition: drawn({ refused: code, cells: [] }) }));
      expect(c.kind === "refused" && c.words.endsWith(".")).toBe(true);
      expect(c.kind === "refused" && /podle$|použít$/.test(c.words)).toBe(false);
    }
  });

  it("is unknown for a panel run the server drew nothing for, and the roster's when respondents are fictional", () => {
    expect(compositionOf(readiness({ persona_source: "panel", sample_composition: null }))).toEqual({ kind: "unknown" });
    expect(compositionOf(readiness({ persona_source: "panel" }))).toEqual({ kind: "unknown" });
    expect(compositionOf(readiness({ persona_source: "fictional_roster", sample_composition: drawn() }))).toEqual({ kind: "roster" });
  });
});

describe("readinessLine", () => {
  const c = (status: string) => ({ id: status, status, message: "" }) as never;
  it("says whether a run can start and what holds it, in the board's words", () => {
    expect(readinessLine(readinessSummary(readiness({ ready: false, checks: [c("FAIL"), c("FAIL"), c("WARN")] })))).toEqual({ tone: "fault", words: "Nelze spustit · 2 kontroly brání" });
    expect(readinessLine(readinessSummary(readiness({ ready: true, checks: [c("WARN"), c("PASS")] })))).toEqual({ tone: "done-warn", words: "Lze spustit · 1 upozornění" });
    expect(readinessLine(readinessSummary(readiness({ ready: true, checks: [c("PASS")] })))).toEqual({ tone: "done", words: "Lze spustit · nic nebrání" });
  });

  it("takes the server's verdict, and never reads an unknown status as passed", () => {
    expect(readinessLine(readinessSummary(readiness({ ready: false, checks: [c("PASS")] })))).toEqual({ tone: "fault", words: "Nelze spustit: server spuštění nepovolí" });
    expect(readinessLine(readinessSummary(readiness({ ready: true, checks: [c("SKIPPED")] }))).tone).toBe("inert");
  });
});
