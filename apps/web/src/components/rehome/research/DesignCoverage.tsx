"use client";

// Návrh: "Výzkumné otázky a jejich pokrytí" (artifact-design DSN2; V2 DesignArt § 1). Each of the
// working copy's research questions with what measures it, whether the run will answer it and its
// gaps, from readiness's research_trace (the server's rule, lib/design-coverage.ts reads it). Until
// coverage is computed on the working revision (working-copy-edit-ops#WCE7), it is the study's
// newest Design Revision's, and the section says which revision and whether the copy moved since.
// Reading readiness is a GET: nothing is submitted, started or paid here.

import Link from "next/link";
import { useEffect, useState } from "react";

import { t, tv } from "@/i18n/t";
import { type DesignRevision, type Readiness, research } from "@/lib/api";
import { type CoverageStatus, type RqCoverage, coverageStatus, newestRevision, revisionIsCurrent, rqCoverage } from "@/lib/design-coverage";
import { codeWords } from "@/lib/reason-words";
import type { Tone } from "@/lib/tone";
import { researchQuestionsOf } from "@/research/trace";
import { StepSection } from "../step";
import { Chip } from "../ui";
import { CodedWords } from "./CodedWords";
import { useResearch } from "./context";

const C = "research.plan.coverage";
const TONE: Record<CoverageStatus, Tone> = { covered: "done", partial: "you", gap: "fault", unknown: "neutral" };

type Read =
  | { kind: "loading" }
  | { kind: "failed"; message: string }
  | { kind: "none" }
  | { kind: "ready"; revision: DesignRevision; readiness: Readiness };

export function DesignCoverage({ id = "plan-coverage" }: { id?: string }) {
  const { state, frame, stepHref } = useResearch();
  const [read, setRead] = useState<Read>({ kind: "loading" });
  useEffect(() => {
    let live = true;
    (async () => {
      const newest = newestRevision(await research.revisions(frame.studyId));
      if (!newest) return { kind: "none" } as const;
      return { kind: "ready", revision: newest, readiness: await research.readiness(frame.studyId, newest.revision_id) } as const;
    })().then(
      (r) => live && setRead(r),
      (e: unknown) => live && setRead({ kind: "failed", message: e instanceof Error ? e.message : String(e) }),
    );
    return () => {
      live = false;
    };
  }, [frame.studyId]);

  const working = researchQuestionsOf(state.project);
  const body = (() => {
    if (read.kind === "loading") return <p className="text-[13px] text-ink-muted">{t(`${C}.loading`)}</p>;
    if (read.kind === "failed") return <p role="alert" className="text-[13px] text-status-fault-ink">{tv(`${C}.failed`, { message: read.message })}</p>;
    if (read.kind === "none") return <p className="text-[13px] text-ink-muted">{t(`${C}.none`)}</p>;
    const { revision, readiness } = read;
    const trace = readiness.research_trace ?? null;
    if (!trace) return <p className="text-[13px] text-ink-muted">{tv(`${C}.noTrace`, { revision: revision.revision })}</p>;
    const current = revisionIsCurrent(revision, state.revision);
    const source = current === true ? "fromCurrent" : current === false ? "fromOlder" : "fromUnknown";
    const rows = rqCoverage(working, trace, readiness.question_outlook ?? []);
    return (
      <>
        <p className="text-[13px] text-ink-muted">{tv(`${C}.${source}`, { revision: revision.revision })}</p>
        {rows.length ? (
          <ol className="mt-3 flex flex-col gap-3">
            {rows.map((row, i) => (
              <RqRow key={`${i}-${row.text}`} row={row} revision={revision.revision} questionnaire={stepHref("questionnaire")} />
            ))}
          </ol>
        ) : (
          <p className="mt-2 text-sm">{t(`${C}.noQuestions`)}</p>
        )}
        {current !== true ? (
          <p className="mt-3 text-[13px]">
            <Link href={stepHref("run")} className="text-signal no-underline hover:underline">{t(`${C}.check`)}</Link>
          </p>
        ) : null}
      </>
    );
  })();

  return (
    <StepSection id={id} title={t(`${C}.title`)} hint={t(`${C}.help`)} aside={<span className="text-xs text-ink-faint">{t(`${C}.aside`)}</span>}>
      <div className="p-4">{body}</div>
    </StepSection>
  );
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
