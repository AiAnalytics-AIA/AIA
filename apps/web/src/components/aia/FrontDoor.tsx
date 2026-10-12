// The frame of AIA's front door: /login, /logout and the sign-in callback. The
// identity on one side -- the mark (public/skin/brand/aia-mark.svg) over the
// lattice field, the wordmark and the lockup line -- and the one thing the page
// is doing on the other. Token utilities only, so it follows light, dark and
// system like every other screen.
//
// With `liftoff`, the aside readies the lift-off film over the mark; once it is
// `playing`, the aside goes to the film's ground (`brand-stage`, in both themes),
// the static mark gives way to the film in the same place, and on a narrow
// screen the aside takes the whole viewport, since its mark is hidden there.

import type { ReactNode } from "react";

import { AiaMark } from "@/components/brand/AiaMark";
import { LatticeField } from "@/components/brand/LatticeField";
import { Liftoff } from "@/components/brand/Liftoff";
import { Wordmark } from "@/components/brand/Wordmark";
import { t } from "@/i18n/t";

export type FrontDoorLiftoff = { playing: boolean; onDone: () => void };

export function FrontDoor({ title, liftoff, children }: { title?: string; liftoff?: FrontDoorLiftoff; children: ReactNode }) {
  const lifting = liftoff?.playing === true;
  return (
    <div className="flex min-h-screen flex-col bg-surface text-ink md:flex-row">
      <aside
        data-liftoff={liftoff ? (lifting ? "playing" : "ready") : undefined}
        className={`@container relative flex shrink-0 flex-col justify-between overflow-hidden border-b border-border bg-surface-sunken px-8 py-6 md:w-[44%] md:max-w-xl md:border-r md:border-b-0 md:px-12 md:py-12 ${
          lifting ? "max-md:fixed max-md:inset-0 max-md:z-[var(--z-overlay)]" : ""
        }`}
      >
        <LatticeField className="pointer-events-none absolute inset-0 hidden h-full w-full text-ink-faint md:block" />
        {liftoff ? (
          <span
            aria-hidden="true"
            className={`pointer-events-none absolute inset-0 z-10 bg-brand-stage transition-opacity duration-[var(--duration-panel)] ${lifting ? "opacity-100" : "opacity-0"}`}
          />
        ) : null}
        <div className="relative flex items-center gap-4">
          <Wordmark height={28} label={t("home.title")} />
          <span className="h-7 w-px bg-border-strong" aria-hidden="true" />
          <span className="text-sm font-medium tracking-wide text-ink-muted">{t("home.lockup")}</span>
        </div>
        <div className={`relative flex-1 items-center justify-center py-10 md:flex ${lifting ? "z-20 flex" : "hidden"}`}>
          <span className={`relative p-6 ${lifting ? "" : "bg-surface-sunken"}`}>
            <AiaMark
              size={240}
              className={`text-ink transition-opacity duration-[var(--duration-panel)] ${lifting ? "opacity-0" : "opacity-100"}`}
            />
            {liftoff ? <Liftoff playing={liftoff.playing} onDone={liftoff.onDone} /> : null}
          </span>
        </div>
        <p className="relative mt-4 hidden max-w-sm font-serif text-lg leading-snug text-ink-muted md:mt-0 md:block">
          {t("home.tagline")}
        </p>
      </aside>
      <main className="flex flex-1 items-center justify-center px-6 py-12">
        <section className="w-full max-w-sm space-y-5 text-sm" aria-labelledby={title ? "front-door-title" : undefined}>
          {title ? (
            <h1 id="front-door-title" className="font-display text-2xl font-semibold text-ink">
              {title}
            </h1>
          ) : null}
          {children}
        </section>
      </main>
    </div>
  );
}
