"use client";

// The hero of a top-level page (the look contract, UI-1; prototype-build PBA4): an eyebrow, the
// title in the serif at 40/46, a one-line lede, an optional edit chip, and a row of figures whose
// values the page passes in. Only top-level pages carry it (Klienti and a client's workspace,
// Společenská inteligence, Projektová paměť, Můj Vedoucí, Settings' sections); inside a study the
// compact stage header stays (sans 20/26). A figure the page could not read says "neznámé", never 0.

import type { ReactNode } from "react";

import { t } from "@/i18n/t";

/** One figure of the hero's row. `value` null or undefined: not known, said in words. */
export type HeroFigure = {
  label: string;
  value: ReactNode | null | undefined;
  /** An id or a version: set in mono, smaller. */
  mono?: boolean;
  /** Something that waits on the person reading (the coral ink); only for those who can act. */
  you?: boolean;
};

/** Whether the person may change what the page shows: "edit" in the signal, "read" quiet. */
export type HeroEdit = { label: string; tone: "edit" | "read"; title?: string };

export function Hero({ eyebrow, title, lede, edit, figures, action, aside }: {
  eyebrow?: ReactNode;
  title: string;
  lede?: ReactNode;
  edit?: HeroEdit;
  figures?: readonly HeroFigure[];
  /** The page's one dominant action, beside the edit chip. */
  action?: ReactNode;
  /** A state beside the action (a save state). */
  aside?: ReactNode;
}) {
  const top = eyebrow || edit || action || aside;
  return (
    <div data-hero="" className="min-w-0">
      {top ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          {eyebrow ? (
            <span data-hero-eyebrow="" className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase leading-4 tracking-[0.06em] text-signal">
              {eyebrow}
            </span>
          ) : <span />}
          <span className="flex flex-wrap items-center gap-3">
            {edit ? (
              <span
                data-hero-edit={edit.tone}
                title={edit.title}
                className={`inline-flex min-h-6 items-center gap-1.5 whitespace-nowrap rounded-control border px-2 text-xs font-medium ${edit.tone === "edit" ? "border-signal-edge bg-signal-tint text-ink" : "border-border bg-surface-raised text-ink-muted"}`}
              >
                {edit.label}
              </span>
            ) : null}
            {aside}
            {action}
          </span>
        </div>
      ) : null}
      <h1 className="mt-1.5 break-words font-serif text-[40px] font-semibold leading-[46px] tracking-[-0.01em] text-ink">{title}</h1>
      {lede ? <p className="mt-2 max-w-[62ch] text-base leading-6 text-ink-muted">{lede}</p> : null}
      {figures?.length ? (
        <dl aria-label={t("aia.hero.figures")} className="mt-[18px] flex flex-wrap gap-x-9 gap-y-3">
          {figures.map((f) => {
            const known = f.value !== null && f.value !== undefined && f.value !== "";
            return (
              <div key={f.label} className="flex flex-col gap-0.5">
                <dt className="text-xs leading-4 text-ink-faint">{f.label}</dt>
                <dd
                  data-hero-figure={known ? "known" : "unknown"}
                  title={known ? undefined : t("aia.hero.unknownTitle")}
                  className={`m-0 flex items-center gap-1.5 tabular-nums ${known ? (f.mono ? "font-mono text-base font-medium leading-6" : "text-xl font-semibold leading-[26px]") : "text-base font-medium leading-[26px] text-ink-faint"} ${known && f.you ? "text-status-you-ink" : ""}`}
                >
                  {known ? f.value : t("aia.hero.unknown")}
                </dd>
              </div>
            );
          })}
        </dl>
      ) : null}
    </div>
  );
}
