// The frame of AIA's front door: /login, /logout and the sign-in callback. The
// identity on one side -- the mark (public/skin/brand/aia-mark.svg) over the
// lattice field, the wordmark and the lockup line -- and the one thing the page
// is doing on the other. Token utilities only, so it follows light, dark and
// system like every other screen.

import type { ReactNode } from "react";

import { AiaMark } from "@/components/brand/AiaMark";
import { LatticeField } from "@/components/brand/LatticeField";
import { Wordmark } from "@/components/brand/Wordmark";
import { t } from "@/i18n/t";

export function FrontDoor({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-surface text-ink md:flex-row">
      <aside className="relative flex shrink-0 flex-col justify-between overflow-hidden border-b border-border bg-surface-sunken px-8 py-6 md:w-[44%] md:max-w-xl md:border-r md:border-b-0 md:px-12 md:py-12">
        <LatticeField className="pointer-events-none absolute inset-0 hidden h-full w-full text-ink-faint md:block" />
        <div className="relative flex items-center gap-4">
          <Wordmark height={28} label={t("home.title")} />
          <span className="h-7 w-px bg-border-strong" aria-hidden="true" />
          <span className="text-sm font-medium tracking-wide text-ink-muted">{t("home.lockup")}</span>
        </div>
        <div className="relative hidden flex-1 items-center justify-center py-10 md:flex">
          <span className="bg-surface-sunken p-6">
            <AiaMark size={240} className="text-ink" />
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
