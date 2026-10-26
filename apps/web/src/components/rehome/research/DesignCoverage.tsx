"use client";

// Návrh: each research question with what measures it, whether the run will answer it and its gaps,
// on the question's own row (artifact-design DSN2, DSN2b; spec navrh/D3), from readiness's
// research_trace on the working revision (the server's rule; WCE7, lib/design-coverage.ts reads it).
// Reading it saves an edit still waiting and submits nothing.

import Link from "next/link";
import { useMemo, useState } from "react";

import { t, tv } from "@/i18n/t";
import { type CoverageAt, type CoverageStatus, type RqCoverage, coverageInputs, coverageInputsChanged, coverageStatus, nextCoverageAt, rqCoverage, seedCoverageAt } from "@/lib/design-coverage";
import { codeWords } from "@/lib/reason-words";
import type { Tone } from "@/lib/tone";
import type { ResearchState } from "@/research/store";
import { linkKey } from "@/research/trace";
import { useSampleReadiness } from "../../workbench/useSampleReadiness";
import { Chip } from "../ui";
import { CodedWords } from "./CodedWords";
import { useResearch } from "./context";

const C = "research.plan.coverage";
const TONE: Record<CoverageStatus, Tone> = { covered: "done", partial: "you", gap: "fault", unknown: "neutral" };

export type DesignCoverage = {
  /** The one line that says what the rows were read on, or why there are none. */
  line: { words: string; alert: boolean };
  /** Each shown research question's coverage, in their order; empty while none was read. */
  rows: RqCoverage[];
  /** What the server traces that the list does not show (the objectives or the goal it falls back to). */
  elsewhere: RqCoverage[];
  revision: number | null;
};

/**
 * The coverage of the research questions `shown`, read on the working revision once a change it is
 * computed from is saved. A shown question the read does not hold is not checked: unknown, never covered.
 */
export function useDesignCoverage(shown: readonly string[]): DesignCoverage {
  const { store, state, frame } = useResearch();
  const at = useCoverageRevision(state);
  // The working copy's readiness (WCE7b), nothing submitted. Návrh's own autosave keeps saving on its
  // debounce: this never flushes (canEdit false), it reads a revision once it is saved.
  const read = useSampleReadiness(store, frame.studyId, false, at.revision);
  const readiness = read.kind === "ready" ? read.readiness : null;
  const shownKey = shown.join("\n");
  // Recomputed when the read or the list changes, not on every edit's render.
  const traced = useMemo(() => {
    const trace = readiness?.research_trace ?? null;
    if (!trace) return null;
    const outlook = readiness?.question_outlook ?? [];
    const list = shownKey ? shownKey.split("\n") : [];
    const keys = new Set(list.map(linkKey));
    const elsewhere = rqCoverage(trace.questions.map((q) => q.text).filter((q) => !keys.has(linkKey(q))), trace, outlook);
    return { rows: rqCoverage(list, trace, outlook), elsewhere };
  }, [readiness, shownKey]);
  const empty = { rows: [], elsewhere: [], revision: null };
  if (read.kind === "loading") return { ...empty, line: { words: t(`${C}.loading`), alert: false } };
  if (read.kind === "failed") return { ...empty, line: { words: tv(`${C}.failed`, { message: read.message }), alert: true } };
  if (read.kind === "none") return { ...empty, line: { words: t(`${C}.none`), alert: false } };
  const { revision } = read;
  if (!traced) return { ...empty, revision, line: { words: tv(`${C}.noTrace`, { revision }), alert: false } };
  // A change it is computed from, not read yet (typed, saving, or read again now): said, never shown as current.
  const behind = read.revision !== at.revision || coverageInputsChanged(at.inputs, coverageInputs(state.project));
  return { ...traced, revision, line: { words: tv(`${C}.${behind ? "recomputing" : "fromWorking"}`, { revision }), alert: false } };
}

/**
 * The working revision the coverage is read on: the saved revision at which something the coverage is
 * computed from last changed. A save that touched nothing it reads (a comment, a set's name) does not
 * move it, so the whole readiness is not recomputed for it.
 */
function useCoverageRevision(state: ResearchState): CoverageAt {
  const [at, setAt] = useState<CoverageAt>(() => seedCoverageAt(state));
  const next = nextCoverageAt(at, state);
  if (next !== at) setAt(next);
  return next;
}

/**
 * A research question's coverage on its row: its status, what measures it (each measure's own
 * verdict where it is not answerable), its comparison and its gaps. AIA's words, not the design's:
 * never quoted into a comment (data-no-quote, PlanStep's Commentable).
 */
export function RqCoverageLine({ row, revision }: { row: RqCoverage; revision: number }) {
  const { stepHref } = useResearch();
  const questionnaire = stepHref("questionnaire");
  return (
    <div data-no-quote className="mt-1 flex flex-col gap-1 text-[13px] leading-5">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Chip tone={TONE[row.status]}>{t(`${C}.status.${row.status}`)}</Chip>
        {!row.checked ? (
          <span className="text-ink-muted">{tv(`${C}.notChecked`, { revision })}</span>
        ) : row.measures.length ? (
          <span className="min-w-0">
            <span className="text-ink-muted">{t(`${C}.measures`)} </span>
            {row.measures.map((m, i) => {
              const own = coverageStatus(m.verdict);
              return (
                <span key={m.key}>
                  {i ? ", " : null}
                  <Link href={`${questionnaire}#${encodeURIComponent(m.anchor)}`} className="text-ink underline decoration-border-strong underline-offset-2 hover:decoration-ink">
                    {m.code ? <CodedWords inline coded={{ words: m.text, code: m.code }} /> : m.text}
                  </Link>
                  {own !== "covered" ? <span className="text-ink-muted"> ({t(`${C}.status.${own}`)})</span> : null}
                </span>
              );
            })}
          </span>
        ) : (
          <span className="text-ink-muted">{t(`${C}.noMeasures`)}</span>
        )}
        {row.comparison ? (
          <span className="rounded-md bg-surface-sunken px-1.5 text-xs leading-5 text-ink-muted">
            <span className="sr-only">{t(`${C}.comparison`)}: </span>
            <CodedWords inline coded={codeWords("research.questionnaire.comparisons.kind", row.comparison)} />
          </span>
        ) : null}
      </div>
      {row.checked && row.reasons.length ? (
        <ul className="flex flex-col gap-0.5 text-ink-muted" aria-label={t(`${C}.gaps`)}>
          {row.reasons.map((r) => (
            <li key={r}><CodedWords coded={codeWords("research.exec.trace.reason", r)} /></li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
