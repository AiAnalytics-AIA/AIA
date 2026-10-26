"use client";

// The open study's stages as one track under the study bar (research-lane-redesign
// chunk 2). Every stage can be opened in any order; beside each name the track says
// where it stands -- done, waiting on a person, running, failed, or nothing yet --
// from src/research/lane.ts, which reads the same conditions the stages enforce. It
// replaces ResearchRail: no step numbers, Průběh is a stage of its own, and the
// width goes back to the work.

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { t } from "@/i18n/t";
import { research, type ResearchRun } from "@/lib/api";
import { pollMs, shouldPoll } from "@/lib/research-execution";
import { type LaneStage, type LaneTone, designLane, runLane } from "@/research/lane";
import { readySetLimits, useSampleLimits } from "./useSampleLimits";
import type { ResearchState } from "@/research/store";
import type { StepKey } from "@/research/steps";
import { Icon } from "../icons";

const GROUPS: { key: "design" | "sample" | "run"; steps: StepKey[] }[] = [
  { key: "design", steps: ["brief", "plan", "questionnaire"] },
  { key: "sample", steps: ["audience", "persona"] },
  { key: "run", steps: ["run", "progress", "results"] },
];

/** The track's stages, in order: what the navigation lists. */
export const TRACK_STEPS: StepKey[] = GROUPS.flatMap((g) => g.steps);

const GLYPH: Record<LaneTone, string> = {
  done: "bg-status-done text-surface-raised",
  you: "bg-status-you text-ink",
  running: "border-2 border-status-running border-r-transparent",
  fault: "bg-status-fault text-surface-raised",
  idle: "border-[1.5px] border-border-strong",
};
const LINE: Record<LaneTone, string> = {
  done: "text-ink-faint",
  you: "text-status-you-ink",
  running: "text-status-running",
  fault: "text-status-fault",
  idle: "text-ink-faint",
};
const TONE_WORD: Record<LaneTone, string> = { done: "hotovo", you: "čeká na vás", running: "běží", fault: "selhalo", idle: "" };

function Glyph({ tone }: { tone: LaneTone }) {
  return (
    <span aria-hidden="true" className={`inline-flex size-[18px] shrink-0 items-center justify-center rounded-full ${GLYPH[tone]}`}>
      {tone === "done" ? <Icon name="done" size={10} /> : tone === "you" ? <span className="text-[11px] font-semibold leading-none">!</span> : tone === "fault" ? <span className="text-[11px] font-semibold leading-none">×</span> : null}
    </span>
  );
}

/**
 * The study's runs: the run stages' state. Read when the study or the stage changes, and read
 * again while one of them can still change on its own, by the rule and at the pace Progress reads
 * its run (`shouldPoll` / `pollMs`). Read once, the track said "běží" and "Zatím nic" beside a page
 * whose run had finished, until a reload (productization-coherence PC5). A change of `epoch` reads
 * them again: a run started from the Lead's conversation is followed at once.
 */
export function useRuns(studyId: string, current: StepKey, epoch = 0) {
  const [runs, setRuns] = useState<ResearchRun[] | null>(null);
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const read = () => {
      research.runs(studyId).then(
        (items) => {
          if (!live) return;
          const list = Array.isArray(items) ? items : null;
          setRuns(list);
          const moving = list?.find(shouldPoll);
          if (moving) timer = setTimeout(read, pollMs(moving));
        },
        () => live && setRuns(null),
      );
    };
    read();
    return () => {
      live = false;
      if (timer) clearTimeout(timer);
    };
  }, [studyId, current, epoch]);
  return runs;
}

export function StageTrack({ studyId, state, current, stepHref }: {
  studyId: string;
  /** The working content, when loaded: without it the design stages say nothing. */
  state: Pick<ResearchState, "project" | "analysis"> | null;
  current: StepKey;
  stepHref: (step: StepKey) => string;
}) {
  const runs = useRuns(studyId, current);
  const setLimits = readySetLimits(useSampleLimits(studyId));
  const lane: Partial<Record<StepKey, LaneStage>> = { ...(state ? designLane(state, setLimits) : {}), ...runLane(runs) };
  const list = useRef<HTMLOListElement>(null);
  useEffect(() => {
    const track = list.current;
    const link = track?.querySelector<HTMLElement>('[aria-current="step"]');
    if (track && link && track.scrollWidth > track.clientWidth) {
      track.scrollLeft += link.getBoundingClientRect().left - track.getBoundingClientRect().left - track.clientWidth / 2 + link.clientWidth / 2;
    }
  }, [current]);
  return (
    <nav aria-label={t("aia.study.stagesLabel")} className="border-t border-border">
      <ol ref={list} className="flex items-stretch overflow-x-auto px-4 lg:px-6">
        {GROUPS.map((group, gi) => (
          <li key={group.key} className={`flex items-stretch ${gi ? "border-l border-border pl-2" : ""} pr-2`}>
            <span aria-hidden="true" className="hidden self-center whitespace-nowrap pl-1 pr-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-ink-faint md:inline">
              {t(`aia.study.phases.${group.key}`)}
            </span>
            <ol className="flex gap-0.5">
              {group.steps.map((step) => {
                const on = step === current;
                const s = lane[step] ?? { tone: "idle" as const, line: "" };
                return (
                  <li key={step} className="flex">
                    <Link
                      href={stepHref(step)}
                      aria-current={on ? "step" : undefined}
                      className={`relative flex min-h-[52px] items-center gap-2 whitespace-nowrap rounded-control px-2.5 py-1.5 text-ink no-underline hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-focus-ring ${on ? "after:absolute after:inset-x-2 after:bottom-0 after:h-[3px] after:rounded-t-mark after:bg-signal" : ""}`}
                    >
                      <Glyph tone={s.tone} />
                      <span>
                        <span className={`block text-[13px] leading-[18px] ${on ? "font-semibold" : "font-medium"}`}>{t(`aia.stages.${step}`)}</span>
                        {s.line ? <span className={`block text-[11px] leading-[14px] ${LINE[s.tone]}`}>{s.line}</span> : null}
                        {TONE_WORD[s.tone] ? <span className="sr-only"> · {TONE_WORD[s.tone]}</span> : null}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ol>
          </li>
        ))}
      </ol>
    </nav>
  );
}
