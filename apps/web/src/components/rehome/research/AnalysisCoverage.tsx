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

/** Sběr dokončen · Povinná analýza: where the run stands on the way to a report. */
export function AnalysisMilestones({ run, analysis }: { run: ResearchRun; analysis: ResearchAnalysis | null }) {
  const fieldwork = stepOf(run, "fieldwork");
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
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[36rem] text-left text-sm">
            <thead className="text-xs text-ink-muted">
              <tr><th className="py-1 pr-3 font-medium">Otázka</th><th className="py-1 pr-3 font-medium">Odpověď</th><th className="py-1 pr-3 font-medium">Zjištění</th><th className="py-1 font-medium">Co chybí</th></tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.index} data-rq={row.index} data-state={row.state} className="border-t border-border align-top">
                  <td className="py-2 pr-3"><span className="font-semibold">RQ{row.index + 1}</span> {row.question}</td>
                  <td className="py-2 pr-3">{STATE_WORDS[row.state]}</td>
                  <td className="py-2 pr-3">
                    {row.findings.length ? (
                      <span className="flex flex-wrap gap-1">
                        {row.findings.map((f) => (
                          <a key={findingId(f)} href={`#${findingAnchor(f)}`} className="rounded-control border border-border bg-surface-sunken px-1.5 text-xs no-underline hover:underline" title={stepLabel(`analysis_${f.module}`)}>
                            {stepLabel(`analysis_${f.module}`)} {f.index + 1}
                          </a>
                        ))}
                      </span>
                    ) : "—"}
                  </td>
                  <td className="py-2 text-ink-muted">{missing(row)}</td>
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
