"use client";

// Návrh: "Výzkumné otázky a jejich pokrytí" (artifact-design DSN2; V2 DesignArt § 1). Each of the
// working copy's research questions with what measures it, whether the run will answer it and its
// gaps, from readiness's research_trace on the working revision (the server's rule; WCE7,
// lib/design-coverage.ts reads it). Reading it saves an edit still waiting and submits nothing.

import Link from "next/link";
import { useState } from "react";

import { t, tv } from "@/i18n/t";
import { type CoverageInputs, type CoverageStatus, type RqCoverage, coverageInputs, coverageInputsChanged, coverageStatus, rqCoverage } from "@/lib/design-coverage";
import { codeWords } from "@/lib/reason-words";
import type { Tone } from "@/lib/tone";
import type { ResearchState } from "@/research/store";
import { researchQuestionsOf } from "@/research/trace";
import { useSampleReadiness } from "../../workbench/useSampleReadiness";
import { StepSection } from "../step";
import { Chip } from "../ui";
import { CodedWords } from "./CodedWords";
import { useResearch } from "./context";

const C = "research.plan.coverage";
const TONE: Record<CoverageStatus, Tone> = { covered: "done", partial: "you", gap: "fault", unknown: "neutral" };

export function DesignCoverage({ id = "plan-coverage" }: { id?: string }) {
  const { store, state, frame, stepHref } = useResearch();
  const at = useCoverageRevision(state);
  // The working copy's readiness (WCE7b), nothing submitted. Návrh's own autosave keeps saving on its
  // debounce: this section never flushes (canEdit false), it reads a revision once it is saved.
  const read = useSampleReadiness(store, frame.studyId, false, at.revision);
  // A change it is computed from, not read yet (typed, saving, or read again now): said, never shown as current.
  const behind = read.kind === "ready" && (read.revision !== at.revision || coverageInputsChanged(at.inputs, coverageInputs(state.project)));

  const working = researchQuestionsOf(state.project);
  const body = (() => {
    if (read.kind === "loading") return <p className="text-[13px] text-ink-muted">{t(`${C}.loading`)}</p>;
    if (read.kind === "failed") return <p role="alert" className="text-[13px] text-status-fault-ink">{tv(`${C}.failed`, { message: read.message })}</p>;
    if (read.kind === "none") return <p className="text-[13px] text-ink-muted">{t(`${C}.none`)}</p>;
    const { revision, readiness } = read;
    const trace = readiness.research_trace ?? null;
    if (!trace) return <p className="text-[13px] text-ink-muted">{tv(`${C}.noTrace`, { revision })}</p>;
    const rows = rqCoverage(working, trace, readiness.question_outlook ?? []);
    return (
      <>
        <p className="text-[13px] text-ink-muted">{tv(`${C}.${behind ? "recomputing" : "fromWorking"}`, { revision })}</p>
        {rows.length ? (
          <ol className="mt-3 flex flex-col gap-3">
            {rows.map((row, i) => (
              <RqRow key={`${i}-${row.text}`} row={row} revision={revision} questionnaire={stepHref("questionnaire")} />
            ))}
          </ol>
        ) : (
          <p className="mt-2 text-sm">{t(`${C}.noQuestions`)}</p>
        )}
      </>
    );
  })();

  return (
    <StepSection id={id} title={t(`${C}.title`)} hint={t(`${C}.help`)} aside={<span className="text-xs text-ink-faint">{t(`${C}.aside`)}</span>}>
      <div className="p-4">{body}</div>
    </StepSection>
  );
}

/**
 * The working revision the coverage is read on: the saved revision at which something the coverage is
 * computed from last changed. A save that touched nothing it reads (a comment, a set's name) does not
 * move it, so the whole readiness is not recomputed for it.
 */
function useCoverageRevision(state: ResearchState): { revision: number | null; inputs: CoverageInputs } {
  const [at, setAt] = useState<{ revision: number | null; inputs: CoverageInputs }>(() => ({ revision: state.revision, inputs: coverageInputs(state.project) }));
  const saved = state.save.kind === "saved" && state.revision !== null;
  if (saved && state.revision !== at.revision && coverageInputsChanged(at.inputs, coverageInputs(state.project))) {
    setAt({ revision: state.revision, inputs: coverageInputs(state.project) });
  }
  return at;
}

function RqRow({ row, revision, questionnaire }: { row: RqCoverage; revision: number; questionnaire: string }) {
  return (
    <li className="rounded-sm border border-border p-3">
      <div className="flex flex-wrap items-start gap-2">
        <p className="min-w-0 flex-1 text-sm font-semibold">{row.text}</p>
        <Chip tone={TONE[row.status]}>{t(`${C}.status.${row.status}`)}</Chip>
      </div>
      {!row.checked ? (
        <p className="mt-1 text-[13px] text-ink-muted">{tv(`${C}.notChecked`, { revision })}</p>
      ) : (
        <dl className="mt-2 grid grid-cols-1 gap-x-3 gap-y-1 text-[13px] leading-5 sm:grid-cols-[150px_minmax(0,1fr)]">
          <dt className="text-ink-muted">{t(`${C}.items`)}</dt>
          <dd className="m-0">
            {row.measures.length ? (
              <ul className="flex flex-col gap-0.5">
                {row.measures.map((m) => (
                  <li key={m.key} className="flex items-start gap-2">
                    <Chip tone={TONE[coverageStatus(m.verdict)]}>{t(`${C}.status.${coverageStatus(m.verdict)}`)}</Chip>
                    <Link href={`${questionnaire}#${encodeURIComponent(m.anchor)}`} className="min-w-0 flex-1 text-ink no-underline hover:underline">
                      {m.code ? <CodedWords inline coded={{ words: m.text, code: m.code }} /> : m.text}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              t(`${C}.noMeasures`)
            )}
          </dd>
          {row.comparison ? (
            <>
              <dt className="text-ink-muted">{t(`${C}.comparison`)}</dt>
              <dd className="m-0"><CodedWords inline coded={codeWords("research.questionnaire.comparisons.kind", row.comparison)} /></dd>
            </>
          ) : null}
          <dt className="text-ink-muted">{t(`${C}.gaps`)}</dt>
          <dd className="m-0">
            {row.reasons.length ? (
              <ul className="flex flex-col gap-0.5">
                {row.reasons.map((r) => (
                  <li key={r}><CodedWords coded={codeWords("research.exec.trace.reason", r)} /></li>
                ))}
              </ul>
            ) : (
              t(`${C}.noGaps`)
            )}
          </dd>
        </dl>
      )}
    </li>
  );
}
