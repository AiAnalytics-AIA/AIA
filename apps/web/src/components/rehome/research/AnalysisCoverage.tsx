"use client";
// Analýza §1 "Pokrytí výzkumných otázek" and its milestones (artifact-analysis ANL2): every
// research question of the run's frozen design, what the analysis answered, the findings that rest
// on the same measures and what is missing. Reads the stored analysis; decides nothing.
import { useEffect, useRef, useState } from "react";
import { tv } from "@/i18n/t";
import { gapWords } from "@/lib/answerability";
import { researchAgents, type ResearchAnalysis, type ResearchRun } from "@/lib/api";
import { analysisTarget, type AnalysisModuleKind } from "@/lib/artifacts/analysis";
import { LEAD_REVEAL } from "@/lib/lead";
import { coverage, findingAnchor, findingId, type CoverageRow, type CoverageVerdict, type FindingRef } from "@/lib/analysis-coverage";
import { ANALYSIS_ORDER, stepLabel, stepOf } from "@/lib/research-execution";
import type { ResearchProject } from "@/research/model";
import { researchQuestionsOf } from "@/research/trace";
import { findingItem, useOpenAnalysisItem } from "./AnalysisInspect";
import { FormattedText } from "./FormattedText";
import { useFrame } from "./frame-hook";
import { Icon } from "../icons";

/** A cell that, below md, stacks under its column's name; the explicit roles keep the table's semantics
 *  there, which display:block would strip. */
const CELL = "py-2 pr-3 max-md:block max-md:py-1";

/** A column's name over its cell below md, where the header row is visually hidden; read once, from the header. */
function ColumnName({ children }: { children: string }) {
  return <span aria-hidden className="block text-xs text-ink-muted md:hidden">{children}</span>;
}

const VERDICT_WORDS: Record<CoverageVerdict, string> = {
  answered: "Odpovězeno",
  indicative: "Orientačně",
  no_data: "Bez dat",
  pending: "Čeká",
  unknown: "Neznámé",
};
/** No state here waits on the person, so none is coral; done reads green, the rest in ink. */
const VERDICT_TONE: Record<CoverageVerdict, string> = {
  answered: "text-status-done",
  indicative: "text-ink",
  no_data: "text-ink",
  pending: "text-ink-muted",
  unknown: "text-ink-muted",
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
  if (row.state === "pending") return "Analýza výzkumných otázek ještě není uložená.";
  return "";
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
function showFinding(f: FindingRef): boolean {
  const el = document.getElementById(findingAnchor(f));
  if (!el) return false;
  el.scrollIntoView?.({ block: "center" });
  if (!el.hasAttribute("tabindex")) el.setAttribute("tabindex", "-1");
  el.focus({ preventScroll: true });
  return true;
}

/** Ask the findings list to show a finding its filter leaves off (LEAD_REVEAL, the Lead's own way). */
function bringBack(f: FindingRef): void {
  const target = analysisTarget({ kind: "finding", module: f.module as AnalysisModuleKind, index: f.index });
  if (target && !document.getElementById(findingAnchor(f))) window.dispatchEvent(new CustomEvent(LEAD_REVEAL, { detail: target }));
}

/** Sběr dokončen · Povinná analýza: where the run stands on the way to a report. */
export function AnalysisMilestones({ run, analysis }: { run: ResearchRun; analysis: ResearchAnalysis | null }) {
  // Fieldwork is the run's "run" step (STEP_ORDER); there is no step keyed "fieldwork".
  const fieldwork = stepOf(run, "run");
  const done = fieldwork?.status === "SUCCEEDED";
  const blocked = ANALYSIS_ORDER.filter((id) => analysis?.modules[id]?.outcome === "BLOCKED").length;
  const analysed = !!analysis?.complete && blocked === 0;
  const items: [string, boolean, string][] = [
    ["Sběr dokončen", done, done ? "hotovo" : "čeká"],
    ["Povinná analýza", analysed, analysed ? "všech 8 částí" : blocked ? `k opravě: ${blocked}` : "čeká"],
  ];
  return (
    <ul aria-label="Stav dokončení" data-analysis-milestones className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
      {items.map(([label, ok, note]) => (
        <li key={label} data-done={ok ? "true" : "false"}>
          <span aria-hidden className={`inline-flex align-[-2px] ${ok ? "text-status-done" : "text-ink-muted"}`}><Icon name={ok ? "done" : "dot"} size={13} /></span>{" "}
          <span className="font-semibold">{label}</span> <span className="text-ink-muted">{note}</span>
        </li>
      ))}
    </ul>
  );
}

export function AnalysisCoverage({ run, analysis }: { run: ResearchRun; analysis: ResearchAnalysis | null }) {
  const frame = useFrame();
  const openItem = useOpenAnalysisItem();
  // A finding the list's module filter left off the page, asked back (bringBack): focused after the
  // render that mounts it, never on a guess at React's timing (AGENTS.md). The list is drawn by this
  // table's parent, so every render of the list renders this table too.
  const pending = useRef<FindingRef | null>(null);
  useEffect(() => {
    if (pending.current && showFinding(pending.current)) pending.current = null;
  });
  const design = useDesignQuestions(frame.studyId, run.design_revision_id);
  const rows = design.state === "ready" ? coverage(design.questions, analysis, run.answerability?.gaps ?? []) : [];
  return (
    <section aria-labelledby="analysis-coverage-title" data-analysis-coverage data-aia={analysisTarget({ kind: "module", module: "research_questions" }) ?? undefined} className="rounded-md border border-border bg-surface-raised p-4">
      <h3 id="analysis-coverage-title" className="text-base font-semibold">Pokrytí výzkumných otázek</h3>
      {rows.length ? (
        <div className="mt-3">
          <table role="table" className="w-full text-left text-sm max-md:block">
            <thead role="rowgroup" className="text-xs text-ink-muted max-md:sr-only">
              <tr role="row">{["Otázka", "Odpověď", "Stav"].map((h) => <th key={h} role="columnheader" className="py-1 pr-3 font-medium">{h}</th>)}</tr>
            </thead>
            <tbody role="rowgroup" className="max-md:block">
              {rows.map((row) => (
                <tr key={row.index} data-rq={row.index} data-state={row.state} data-verdict={row.verdict} role="row" className="border-t border-border align-top max-md:block max-md:py-2">
                  <td role="cell" className="py-2 pr-3 max-md:block max-md:py-1 md:w-1/3"><span className="font-semibold">{tv("research.questionnaire.strip.rq", { n: row.index + 1 })}</span> {row.question}</td>
                  <td role="cell" className={CELL}><ColumnName>Odpověď</ColumnName>
                    {row.answer ? <FormattedText text={row.answer} /> : <span className="text-ink-muted">—</span>}
                    {/* Where the answer comes from: the findings on the same measures, else what is missing. */}
                    {row.findings.length || missing(row) ? <div data-answer-origin className="mt-1 flex flex-wrap items-center gap-1 text-xs text-ink-muted">
                      {row.findings.map((f) => (
                        <button key={findingId(f)} type="button" data-finding-chip={findingId(f)} onClick={() => {
                          const item = findingItem(f.module, f.index);
                          // In the inspector too, the finding is put back on the page, so "Ukázat na stránce" finds it.
                          if (openItem?.(item.id, item.title)) bringBack(f);
                          else if (!showFinding(f)) { pending.current = f; bringBack(f); }
                        }}
                          className="rounded-control border border-border bg-surface-sunken px-1.5 text-left text-xs text-ink hover:underline focus-visible:outline-2 focus-visible:outline-focus-ring">
                          {stepLabel(`analysis_${f.module}`)} {f.index + 1}
                        </button>
                      ))}
                      {missing(row) ? <span>{missing(row)}</span> : null}
                    </div> : null}
                  </td>
                  <td role="cell" className={`${CELL} whitespace-nowrap font-semibold`}><ColumnName>Stav</ColumnName><span className={VERDICT_TONE[row.verdict]}>{VERDICT_WORDS[row.verdict]}</span></td>
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
