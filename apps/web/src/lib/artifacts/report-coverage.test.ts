import { describe, expect, it } from "vitest";
import type { Answerability, AnswerabilityGap } from "@/lib/api";
import { t } from "@/i18n/t";
import { coverageRecord, type CoverageLine } from "./report-coverage";

const gap = (question: string, reasons: string[], verdict: AnswerabilityGap["verdict"] = "UNANSWERABLE"): AnswerabilityGap =>
  ({ kind: "not_answerable", research_question: question, verdict, reasons, measures: ["q1"] });
const answer = (gaps: AnswerabilityGap[], pending: string[] = []): Answerability =>
  ({ rules: "r", capable: !gaps.length, digest: "d", gaps, pending });
const words = (lines: CoverageLine[]) => lines.map((l) => `${l.label}: ${l.state}${l.why ? ` — ${l.why}` : ""}`);

describe("Záznam pokrytí (RPT4)", () => {
  it("lists a design's segment comparison as Segmenty: neprovedeno once, each question keeping its own line and reasons", () => {
    const lines = coverageRecord({ answerability: answer([
      gap("Liší se segmenty?", ["segments_unavailable", "unmeasured"]),
      gap("Liší se kraje?", ["segments_unavailable"]),
    ]) }, []);
    expect(words(lines).slice(0, 3)).toEqual([
      "Segmenty: neprovedeno — srovnání segmentů AIA zatím neumí",
      "„Liší se segmenty?“: Běh na ni neodpoví — srovnání segmentů AIA zatím neumí; žádná otázka dotazníku ji neměří",
      "„Liší se kraje?“: Běh na ni neodpoví — srovnání segmentů AIA zatím neumí",
    ]);
  });

  it("names a gap with no question text as such, never an empty quote", () => {
    const lines = coverageRecord({ answerability: answer([{ ...gap("x", ["unmeasured"]), research_question: null }]) }, []);
    expect(lines[0].label).toBe("Výzkumná otázka bez znění");
  });

  it("names every other gap by its question, verdict and why, and a pending question as unverified", () => {
    const lines = coverageRecord({ answerability: answer([gap("Kdo pije kávu?", ["unmeasured"], "UNKNOWN")], ["Proč?"]) }, []);
    expect(words(lines)).toEqual([
      "„Kdo pije kávu?“: Nelze doložit, že na ni běh odpoví — žádná otázka dotazníku ji neměří",
      "„Proč?“: při spuštění nešlo ověřit, že na ni běh odpoví — zda ji zpráva zodpovídá, ukazuje až její text",
      "Výstupy běhu: zpráva čte ze všech uložených",
    ]);
  });

  it("never reads what was not recorded as covered", () => {
    // A run from before answerability was recorded, and a -1 document with no manifest.
    expect(words(coverageRecord({ answerability: null }, undefined))).toEqual([
      "Výzkumné otázky: nezaznamenáno — běh nezaznamenal, zda na ně mohl odpovědět",
      "Výstupy běhu: nezaznamenáno — dokument nemá záznam, z čeho zpráva čte",
    ]);
    // A manifest that is not a list is not read as one, and never breaks the pane.
    expect(words(coverageRecord({ answerability: null }, null))[1]).toContain("nezaznamenáno");
    expect(words(coverageRecord({}, undefined))[0]).toContain("nezaznamenáno");
  });

  it("says only what the start recorded when it recorded no gap, never that the draft answers them all", () => {
    expect(words(coverageRecord({ answerability: answer([]) }, []))[0]).toBe("Výzkumné otázky: při spuštění běh nezaznamenal žádnou mezeru");
  });

  it("names the run's outputs no section read in words, never by id or raw type (RPT12)", () => {
    const lines = coverageRecord({ answerability: answer([]) }, [
      { kind: "artifact", artifact_type: "research_sociomapping_docx", artifact_id: "ART-s", sha256: "a" },
      { kind: "artifact", artifact_type: "research_unknown_kind" },
      { kind: "beside", node_key: "sociomapping", step_kind: "sociomapping" },
    ]);
    expect(words(lines).slice(1)).toEqual([
      "Zpráva Sociomappingu (interní koncept): uloženo, žádná kapitola z něj nečte",
      `Další uložený výstup (${t("research.exec.code.technical")}: research_unknown_kind): uloženo, žádná kapitola z něj nečte`,
      "Sociomapping (experimentální metoda AIA): souběžný krok, zpráva z něj nečte",
    ]);
  });
});
