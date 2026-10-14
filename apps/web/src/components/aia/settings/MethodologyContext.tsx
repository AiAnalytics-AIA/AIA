"use client";

// Where a methodology step sits in the computation (product owner, 2026-10-14): what it is for,
// the steps it reads and the steps that read it, each a link to that step. The editor moves to
// the step; the read-only catalogue opens its stage and scrolls to it. Links, not buttons: they
// move within the page, and the catalogue draws every card at once.

import { t } from "@/i18n/t";
import type { MethodStepOut } from "@/lib/api";

const C = "aia.settings.methodology.context";

export function StepContext({ step, titles, onPick }: {
  step: MethodStepOut;
  /** Every step of the module by id, as its title reads. */
  titles: Record<string, string>;
  /** Moves to a step; without it, a link follows its anchor to the step's card (`#ms-<id>`). */
  onPick?: (stepId: string) => void;
}) {
  if (!step.role_cs) return null;
  const links = (ids: string[]) => ids.map((id, i) => (
    <span key={id}>
      <a
        data-context-link={id}
        href={`#ms-${id}`}
        onClick={onPick ? (e) => { e.preventDefault(); onPick(id); } : undefined}
        className="rounded-sm text-signal underline underline-offset-2 hover:text-signal-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
      >{titles[id] ?? id}</a>
      {i < ids.length - 1 ? ", " : ""}
    </span>
  ));
  return (
    <dl data-step-context={step.id} aria-label={t(`${C}.label`)} className="grid max-w-3xl grid-cols-[6.5rem_minmax(0,1fr)] gap-x-3 gap-y-1 border-l-[3px] border-signal-edge bg-surface-raised py-2.5 pl-3.5 pr-3 text-[13px] leading-5">
      <dt className="text-ink-faint">{t(`${C}.role`)}</dt>
      <dd className="text-ink">{step.role_cs}</dd>
      <dt className="text-ink-faint">{t(`${C}.from`)}</dt>
      <dd data-context="from" className="text-ink">{step.inputs.length ? links(step.inputs) : step.source_cs || "—"}</dd>
      <dt className="text-ink-faint">{t(`${C}.to`)}</dt>
      <dd data-context="to" className="text-ink">{step.feeds.length ? links(step.feeds) : t(`${C}.toResults`)}</dd>
    </dl>
  );
}
