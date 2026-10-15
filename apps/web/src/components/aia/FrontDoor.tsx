"use client";

// The frame of AIA's front door: /login, /logout and the sign-in callback, in
// Graphite whatever the person's theme. A panel on the left -- the wordmark and
// its lockup line over a faint dot grid, the tagline at its foot, and the dot
// field (DotField) living in it -- and the one thing the page is doing on the
// right. Below 760 px the panel stacks on top. Token utilities only; the signal
// is the identity's cyan here (IDENTITY).
//
// With `handoff`, the launch film is loaded alongside; once `leaving` turns true
// the text fades, the panel and the page go to the film's ground, the dots form
// the mark, and the film takes over on its first frame (LaunchFilm). Its end is
// `onDone`.

import { useCallback, useRef, useState, type CSSProperties, type ReactNode } from "react";

import { DotField } from "@/components/brand/DotField";
import { LaunchFilm } from "@/components/brand/LaunchFilm";
import { Wordmark } from "@/components/brand/Wordmark";
import { t } from "@/i18n/t";

export type FrontDoorHandoff = { leaving: boolean; onDone: () => void };

// The panel's grid: one faint ink point every 24 px.
const GRID: CSSProperties = {
  backgroundImage: "radial-gradient(circle, color-mix(in srgb, var(--ink) 9%, transparent) 1px, transparent 1.4px)",
  backgroundSize: "24px 24px",
  backgroundPosition: "12px 12px",
};
// The front door's signal is the identity's own cyan (`brand-apex`), as on every Graphite
// asset and in the launch film: the wordmark's calibrated point, the sign-in button, its
// hover and the focus ring. Inside AIA the signal stays the UI token.
const IDENTITY = {
  "--signal": "var(--brand-apex)",
  "--signal-hover": "color-mix(in srgb, var(--brand-apex) 88%, var(--ink))",
  "--focus-ring": "var(--brand-apex)",
} as CSSProperties;

export function FrontDoor({ title, handoff, children }: { title?: string; handoff?: FrontDoorHandoff; children: ReactNode }) {
  const panel = useRef<HTMLElement>(null);
  const [filmOnScreen, setFilmOnScreen] = useState(false);
  const leaving = handoff?.leaving === true;
  const fade = `relative z-20 transition-[opacity,transform] duration-[320ms] ease-out ${leaving ? "-translate-y-1.5 opacity-0" : ""}`;
  const filmShows = useCallback(() => setFilmOnScreen(true), []);

  return (
    <div
      data-theme="dark"
      style={IDENTITY}
      data-handoff={handoff ? (leaving ? "leaving" : "ready") : undefined}
      className={`relative grid min-h-dvh grid-rows-[46dvh_auto] text-[15px] leading-[1.55] text-ink transition-colors duration-[600ms] min-[760px]:grid-cols-[minmax(380px,34%)_1fr] min-[760px]:grid-rows-none ${
        leaving ? "bg-brand-stage" : "bg-surface"
      }`}
    >
      <aside
        ref={panel}
        className={`relative flex min-w-0 flex-col justify-between gap-6 border-b px-5 py-7 transition-[background-color,border-color] duration-[600ms] min-[760px]:border-r min-[760px]:border-b-0 min-[760px]:px-14 min-[760px]:py-12 ${
          leaving ? "border-transparent bg-brand-stage" : "border-border bg-surface-raised"
        }`}
      >
        <span
          aria-hidden="true"
          className={`pointer-events-none absolute inset-0 transition-opacity duration-[600ms] ${leaving ? "opacity-0" : ""}`}
          style={GRID}
        />
        <div className={`flex items-center gap-[18px] ${fade}`}>
          <Wordmark height={32} label={t("home.title")} />
          <span className="h-[30px] w-px bg-border-strong" aria-hidden="true" />
          <span className="text-[15px] tracking-[0.01em] text-ink-muted min-[760px]:text-[17px]">{t("home.lockup")}</span>
        </div>
        <p className={`m-0 max-w-[22ch] font-serif text-[18px] leading-[1.45] text-balance text-ink-muted min-[760px]:text-[21px] ${fade}`}>
          {t("home.tagline")}
        </p>
      </aside>
      <main className="relative z-20 flex min-w-0 items-start justify-center px-5 pt-7 min-[760px]:items-center min-[760px]:px-8 min-[760px]:pt-0">
        <section
          className={`flex w-full max-w-[450px] flex-col gap-3.5 ${fade} ${leaving ? "pointer-events-none" : ""}`}
          aria-labelledby={title ? "front-door-title" : undefined}
        >
          {title ? (
            <h1 id="front-door-title" className="m-0 font-serif text-[28px] font-medium leading-[1.2] text-ink">
              {title}
            </h1>
          ) : null}
          {children}
        </section>
      </main>
      {filmOnScreen ? null : <DotField panel={panel} leaving={leaving} />}
      {handoff ? <LaunchFilm onFirstFrame={filmShows} onDone={handoff.onDone} /> : null}
    </div>
  );
}
