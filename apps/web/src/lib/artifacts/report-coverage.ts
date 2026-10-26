// Zpráva's "Záznam pokrytí (mimo text zprávy)" (artifact-report RPT4): what the draft does not
// hold and why, beside the document, never in it. Pure: it reads what the run recorded at start
// (its answerability) and the stored document's manifest (artifact-chain CHN1: the run's outputs no
// section read), and decides nothing the server did not. What was never recorded is said so,
// never read as covered.
import type { Answerability } from "@/lib/api";
import { gapWords } from "@/lib/answerability";
import { stepLabel } from "@/lib/research-execution";
import type { RunOutput } from "./report";

/** One line: what (a research question, "Segmenty", an output), its state, why, and the stored
 *  output it names, if any. */
export type CoverageLine = { kind: "question" | "output"; label: string; state: string; why: string | null };

/** The step whose words name a stored output; any other type keeps its type, never hidden. */
const OUTPUT_STEP: Record<string, string> = {
  research_aggregate: "aggregate",
  research_sociomap: "sociomap",
  research_sociomapping_docx: "sociomapping_report",
};

const quoted = (question: string) => (question ? `„${question}“` : "Výzkumná otázka bez znění");

function questionLines(answer: Answerability | null | undefined): CoverageLine[] {
  const line = (label: string, state: string, why: string | null = null): CoverageLine => ({ kind: "question", label, state, why });
  // A run from before it recorded this: nothing is known about its research questions.
  if (!answer) return [line("Výzkumné otázky", "nezaznamenáno", "běh nezaznamenal, zda na ně mohl odpovědět")];
  const lines: CoverageLine[] = [];
  // A segment comparison is analysis AIA does not do yet: said once, as such, before the questions
  // that asked for it, which keep their own lines and every reason.
  if (answer.gaps.some((g) => g.reasons.includes("segments_unavailable"))) {
    lines.push(line("Segmenty", "neprovedeno", "srovnání segmentů AIA zatím neumí"));
  }
  for (const gap of answer.gaps) {
    const words = gapWords(gap);
    lines.push(gap.kind === "no_research_questions"
      ? line("Výzkumné otázky", "žádné", words.why)
      : line(quoted(words.question), words.verdict, words.why || null));
  }
  for (const question of answer.pending ?? []) {
    lines.push(line(quoted(question), "při spuštění nešlo ověřit, že na ni běh odpoví", "zda ji zpráva zodpovídá, ukazuje až její text"));
  }
  // What the start recorded, not what the draft holds: no gap then is all this record can say.
  return lines.length ? lines : [line("Výzkumné otázky", "při spuštění běh nezaznamenal žádnou mezeru")];
}

function outputLines(unread: unknown): CoverageLine[] {
  const line = (label: string, state: string, why: string | null = null): CoverageLine => ({ kind: "output", label, state, why });
  // A document stored before the manifest (aia-report-document-1), or one whose manifest is not a
  // list, names no outputs: never read as all read.
  if (!Array.isArray(unread)) return [line("Výstupy běhu", "nezaznamenáno", "dokument nemá záznam, z čeho zpráva čte")];
  if (!unread.length) return [line("Výstupy běhu", "zpráva čte ze všech uložených")];
  return (unread as RunOutput[]).map((o) => (o.kind === "beside"
    ? line(stepLabel(o.node_key), "souběžný krok, zpráva z něj nečte")
    // In words, never by its id or a raw type (RPT12): an output the page has no words for is said so.
    : line(o.artifact_type in OUTPUT_STEP ? stepLabel(OUTPUT_STEP[o.artifact_type]) : "Další uložený výstup", "uloženo, žádná kapitola z něj nečte")));
}

/** The record: the research questions first, then the run's outputs the draft does not read. */
export function coverageRecord(run: { answerability?: Answerability | null }, unread: unknown): CoverageLine[] {
  return [...questionLines(run.answerability), ...outputLines(unread)];
}
