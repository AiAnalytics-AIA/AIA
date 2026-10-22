"use client";
// Analýza §1 "Pokrytí výzkumných otázek" and its milestones (artifact-analysis ANL2): every
// research question of the run's frozen design, what the analysis answered, the findings that rest
// on the same measures and what is missing. Reads the stored analysis; decides nothing.
import { useEffect, useState } from "react";
import { gapWords } from "@/lib/answerability";
import { researchAgents, type ResearchAnalysis, type ResearchRun } from "@/lib/api";
import { analysisTarget } from "@/lib/artifacts/analysis";
import { coverage, findingAnchor, findingId, type CoverageRow, type CoverageState } from "@/lib/analysis-coverage";
import { ANALYSIS_ORDER, stepLabel, stepOf } from "@/lib/research-execution";
import type { ResearchProject } from "@/research/model";
import { researchQuestionsOf } from "@/research/trace";
import { useFrame } from "./frame-hook";

/** A cell that, below md, stacks under its column's name; the explicit roles keep the table's semantics
 *  there, which display:block would strip. */
const CELL = "py-2 pr-3 max-md:block max-md:py-1";

/** A column's name over its cell below md, where the header row is visually hidden; read once, from the header. */
function ColumnName({ children }: { children: string }) {
  return <span aria-hidden className="block text-xs text-ink-muted md:hidden">{children}</span>;
}

const STATE_WORDS: Record<CoverageState, string> = {
  answered: "ano",
  unsupported: "slovy, bez doložených čísel",
  gap: "bez doložené odpovědi",
  blocked: "nelze říct",
  pending: "čeká na analýzu",
  unanswered: "bez odpovědi",
};

function missing(row: CoverageRow): string {
  if (row.gap && "words" in row.gap) return `Při spuštění běh zaznamenal: ${row.gap.words}`;
  if (row.gap) {
    const g = gapWords(row.gap.recorded);
    return `Při spuštění běh zaznamenal: ${[g.verdict, g.why].filter(Boolean).join(" ")}`;
  }
  if (row.state === "unsupported") return "Odpověď necituje žádné připuštěné číslo.";
  if (row.state === "blocked") return "Analýza výzkumných otázek neprošla kontrolou a potřebuje opravu.";
  if (row.state === "unanswered") return "Uložená analýza na otázku neodpovídá.";
  return "—";
}

/** The frozen design's research questions as read: loading, failed (unknown, never "none"), or read. */
type DesignQuestions = { state: "loading" } | { state: "failed" } | { state: "ready"; questions: string[] };

function useDesignQuestions(studyId: string, revisionId: string): DesignQuestions {
  const [read, setRead] = useState<DesignQuestions & { key: string }>({ state: "loading", key: "" });
  const key = `${studyId}/${revisionId}`;
  useEffect(() => {
    let live = true;
    researchAgents.design(studyId, revisionId).then(
      (revision) => live && setRead(
        revision?.content && typeof revision.content === "object"
          ? { state: "ready", questions: researchQuestionsOf(revision.content as ResearchProject), key }
          : { state: "failed", key },
      ),
      () => live && setRead({ state: "failed", key }),
    );
    return () => { live = false; };
  }, [studyId, revisionId, key]);
  return read.key === key ? read : { state: "loading" };
}

/**
 * Bring a finding into view and focus it. Not a link: a hash that names no view sends the results
 * workspace back to Přehled and the workbench to Výsledky (ResultsWorkspace reads the hash).
 */
function showFinding(anchor: string): void {
  const el = document.getElementById(anchor);
  if (!el) return;
  el.scrollIntoView?.({ block: "center" });
  if (!el.hasAttribute("tabindex")) el.setAttribute("tabindex", "-1");
  el.focus({ preventScroll: true });
}

/** Sběr dokončen · Povinná analýza: where the run stands on the way to a report. */
export function AnalysisMilestones({ run, analysis }: { run: ResearchRun; analysis: ResearchAnalysis | null }) {
  // Fieldwork is the run's "run" step (STEP_ORDER); there is no step keyed "fieldwork".
  const fieldwork = stepOf(run, "run");
  const done = fieldwork?.status === "SUCCEEDED";
  const blocked = ANALYSIS_ORDER.filter((id) => analysis?.modules[id]?.outcome === "BLOCKED").length;
  const analysed = !!analysis?.complete && blocked === 0;
  const items: [string, boolean, string][] = [
    ["Sběr dokončen", done, done ? run.run_id : "čeká"],
    ["Povinná analýza", analysed, analysed ? "všech 8 částí" : blocked ? `k opravě: ${blocked}` : "čeká"],
  ];
  return (
    <ul aria-label="Stav dokončení" data-analysis-milestones className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
      {items.map(([label, ok, note]) => (
        <li key={label} data-done={ok ? "true" : "false"}>
          <span aria-hidden className={ok ? "text-status-done" : "text-ink-muted"}>{ok ? "✓" : "○"}</span>{" "}
          <span className="font-semibold">{label}</span> <span className="text-ink-muted">{note}</span>
        </li>
      ))}
    </ul>
  );
}

export function AnalysisCoverage({ run, analysis }: { run: ResearchRun; analysis: ResearchAnalysis | null }) {
  const frame = useFrame();
  const design = useDesignQuestions(frame.studyId, run.design_revision_id);
  const rows = design.state === "ready" ? coverage(design.questions, analysis, run.answerability?.gaps ?? []) : [];
  return (
    <section aria-labelledby="analysis-coverage-title" data-analysis-coverage data-aia={analysisTarget({ kind: "module", module: "research_questions" }) ?? undefined} className="rounded-md border border-border bg-surface-raised p-4">
      <h3 id="analysis-coverage-title" className="text-base font-semibold">Pokrytí výzkumných otázek</h3>
      {rows.length ? (
        <div className="mt-3">
          <table role="table" className="w-full text-left text-sm max-md:block">
            <thead role="rowgroup" className="text-xs text-ink-muted max-md:sr-only">
              <tr role="row">{["Otázka", "Odpověď", "Zjištění", "Co chybí"].map((h) => <th key={h} role="columnheader" className="py-1 pr-3 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody role="rowgroup" className="max-md:block">
              {rows.map((row) => (
                <tr key={row.index} data-rq={row.index} data-state={row.state} role="row" className="border-t border-border align-top max-md:block max-md:py-2">
                  <td role="cell" className="py-2 pr-3 max-md:block max-md:py-1"><span className="font-semibold">RQ{row.index + 1}</span> {row.question}</td>
                  <td role="cell" className={CELL}><ColumnName>Odpověď</ColumnName>{STATE_WORDS[row.state]}</td>
                  <td role="cell" className={CELL}><ColumnName>Zjištění</ColumnName>
                    {row.findings.length ? (
                      <span className="flex flex-wrap gap-1">
                        {row.findings.map((f) => (
                          <button key={findingId(f)} type="button" data-finding-chip={findingId(f)} onClick={() => showFinding(findingAnchor(f))}
                            className="rounded-control border border-border bg-surface-sunken px-1.5 text-left text-xs hover:underline focus-visible:outline-2 focus-visible:outline-focus-ring">
                            {stepLabel(`analysis_${f.module}`)} {f.index + 1}
                          </button>
                        ))}
                      </span>
                    ) : "—"}
                  </td>
                  <td role="cell" className={CELL}><ColumnName>Co chybí</ColumnName><span className="text-ink-muted">{missing(row)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-2 text-sm text-ink-muted" data-coverage-read={design.state}>
          {design.state === "loading" ? "Výzkumné otázky běhu se načítají."
            : design.state === "failed" ? "Výzkumné otázky běhu jsou neznámé: návrh, ze kterého běh vznikl, se nenačetl. Pokrytí proto nelze posoudit."
            : "Návrh, ze kterého běh vznikl, neuvádí výzkumné otázky."}
        </p>
      )}
    </section>
  );
}
