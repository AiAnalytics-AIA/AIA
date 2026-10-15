"use client";

// The column beside every stage (research-lane-redesign chunk 3): what still stands
// between this study's design and a run, each line a way to the stage that fixes it,
// and the study's AI help under it. The list is src/research/lane.ts's: only the
// conditions the stages enforce; Kontrola's server readiness stays the authority.

import Link from "next/link";
import { type ReactNode, createContext, useContext, useState } from "react";
import { createPortal } from "react-dom";

import { t } from "@/i18n/t";
import { blockers } from "@/research/lane";
import type { ResearchState } from "@/research/store";
import type { StepKey } from "@/research/steps";

export function Blockers({ state, stepHref }: { state: Pick<ResearchState, "project" | "analysis">; stepHref: (step: StepKey) => string }) {
  const items = blockers(state);
  return (
    <section aria-labelledby="lane-blockers" className="rounded-card border border-border bg-surface-raised p-3.5">
      <h2 id="lane-blockers" className="text-sm font-semibold">Do spuštění zbývá</h2>
      {items.length ? (
        <ul className="mt-1.5 flex flex-col gap-0.5">
          {items.map((b, i) => (
            <li key={`${b.step}-${i}`}>
              <Link
                href={stepHref(b.step)}
                className="grid grid-cols-[18px_1fr_auto] items-start gap-2 rounded-control p-1.5 text-ink no-underline hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-focus-ring"
              >
                <span aria-hidden="true" className="mt-px inline-flex size-[18px] items-center justify-center rounded-full bg-status-you text-[11px] font-bold leading-none text-ink">!</span>
                <span className="min-w-0">
                  <span className="block text-[13px] font-medium leading-[18px]">{b.label}</span>
                  <span className="block text-xs leading-4 text-ink-muted">{b.detail}</span>
                </span>
                <span className="text-xs leading-4 text-ink-muted">{t("research.exec.fix")}</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-[13px] leading-5 text-ink-muted">Návrh splňuje podmínky jednotlivých kroků. Kontrola a spuštění ho ještě ověří na serveru.</p>
      )}
    </section>
  );
}

/** Where a stage's readiness is drawn: the inspector's own element, once it is mounted. */
const SlotContext = createContext<{ target: HTMLElement | null } | null>(null);

/**
 * The inspector column: the stage's readiness (InspectorSlot), then AI help (or its
 * open panel) and what is left before a run. It also provides the slot to the stage,
 * which is why it wraps the whole workspace and draws its column through `column`.
 */
export function InspectorProvider({ children }: { children: (column: (content: ReactNode) => ReactNode) => ReactNode }) {
  const [target, setTarget] = useState<HTMLElement | null>(null);
  const column = (content: ReactNode) => (
    <div data-inspector className="flex min-w-0 flex-col gap-3 lg:sticky lg:top-[136px]">
      <div ref={setTarget} className="contents" />
      {content}
    </div>
  );
  return <SlotContext.Provider value={{ target }}>{children(column)}</SlotContext.Provider>;
}

/**
 * A stage's readiness, drawn in the inspector beside it (a portal), or in place
 * when the stage is rendered without one (on its own, as in its tests).
 */
export function InspectorSlot({ children }: { children: ReactNode }) {
  const slot = useContext(SlotContext);
  if (!slot) return <>{children}</>;
  return slot.target ? createPortal(children, slot.target) : null;
}
