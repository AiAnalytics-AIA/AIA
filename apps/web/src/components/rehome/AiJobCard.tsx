"use client";

// One card for a piece of work that runs on its own (DS v3.1 AiJobCard): an AI job (a design worker,
// Deep Research, an analysis retry) or a research run. Its anatomy is fixed so every such card reads
// alike wherever it stands -- in the Lead's conversation, beside a stage, in the tray:
//   the kind's mark · its title · one StatusPill
//   what it is doing now (the step's live activity, as the API reports it)
//   its facts as label / value rows, the stake first
//   its actions, the primary one last.
// An AI job wears the spark edge (globals.css), turning while a model works on it; a research run,
// which code drives, is drawn in ink. The card never adds a state of its own: its words and tone are
// the caller's, read from the API (lib/lead-cards.ts workerCard, runCard).

import type { ReactNode } from "react";

import { Icon, Sparkle } from "./icons";
import { StatusPill, type StatusTone } from "./ui";

/** One fact of a card: a label and its value; `key` marks the stake (the cost a person approves). */
export type Fact = { label: string; value: ReactNode; key?: boolean; sub?: ReactNode };

/** A card's facts as label / value rows. */
export function Facts({ facts }: { facts: Fact[] }) {
  if (!facts.length) return null;
  return (
    <dl data-card-facts className="mt-2 grid grid-cols-[7rem_minmax(0,1fr)] gap-x-3 gap-y-1 border-t border-border pt-2 text-[13px] leading-5">
      {facts.map((f) => (
        <div key={f.label} className="contents">
          <dt className="text-ink-muted">{f.label}</dt>
          <dd className="min-w-0 tabular-nums">
            {f.key ? <span data-fact-key className="text-lg font-semibold leading-6 text-ink">{f.value}</span> : f.value}
            {f.sub ? <span className="block text-xs leading-4 text-ink-muted">{f.sub}</span> : null}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export type JobKind = "ai" | "run";

const MARK: Record<JobKind, { title: string; className: string }> = {
  ai: { title: "Úloha AI", className: "bg-ai-wash" },
  run: { title: "Výzkumný běh", className: "bg-surface-inverse text-ink-inverse" },
};

export function AiJobCard({ kind, title, state, working = false, activity, facts = [], actions, ...data }: {
  kind: JobKind;
  title: ReactNode;
  state: { word: ReactNode; tone: StatusTone };
  /** A model is working on it now: the AI card's edge turns. */
  working?: boolean;
  activity?: ReactNode;
  facts?: Fact[];
  actions?: ReactNode;
} & { [attribute: `data-${string}`]: string | undefined }) {
  const edge = kind === "ai" ? `ai-spark${working ? " ai-spark--working" : ""}` : "border-border bg-surface-raised";
  return (
    <div data-job-card={kind} aria-busy={working || undefined} className={`rounded-panel border px-3 pb-2.5 pt-2 ${edge}`} {...data}>
      <div className="flex flex-wrap items-center gap-2">
        <span title={MARK[kind].title} className={`inline-flex size-[22px] shrink-0 items-center justify-center rounded-[4px] ${MARK[kind].className}`}>
          {kind === "ai" ? <Sparkle size={13} /> : <Icon name="worker" size={13} />}
        </span>
        <span className="min-w-0 text-sm font-semibold">{title}</span>
        <StatusPill tone={state.tone}>{state.word}</StatusPill>
      </div>
      {activity}
      <Facts facts={facts} />
      {actions ? <div className="mt-2 flex flex-wrap items-center justify-end gap-2">{actions}</div> : null}
    </div>
  );
}
