"use client";

/**
 * The lift-off film (public/skin/brand/aia-liftoff.webm, VP9, and .mp4, H.264,
 * for the browsers without VP9; one 7.4 s cut, no sound): the mark's lattice
 * launches and lands as the lockup. It plays in place of the static mark on the
 * front door after a sign-in, and `onDone` is the way in. Centred on the mark's
 * slot and sized so the film's mark (428 of its 1920 px) matches the 240 px mark
 * it replaces, capped by the aside's width so the closing lockup fits; its edges
 * fade into `brand-stage`, the film's own ground.
 *
 * Decoration: muted, hidden from assistive technology, and never in the way. The
 * film is loaded while `playing` is false so it starts at once; it calls `onDone`
 * when it ends, when it cannot play (no source it can decode, a refused play()), after a ceiling
 * in case it stalls, and at once under prefers-reduced-motion.
 */

import { useEffect, useRef } from "react";

// In order of preference; the browser takes the first it can play.
export const LIFTOFF_SOURCES = [
  { src: "/skin/brand/aia-liftoff.webm", type: 'video/webm; codecs="vp9"' },
  { src: "/skin/brand/aia-liftoff.mp4", type: "video/mp4" },
] as const;
// The film is 7.4 s; past this, whatever it is doing, the person goes in.
export const LIFTOFF_CEILING_MS = 12_000;

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function Liftoff({ playing, onDone }: { playing: boolean; onDone: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const done = useRef(onDone);
  useEffect(() => {
    done.current = onDone;
  }, [onDone]);

  useEffect(() => {
    if (!playing) return;
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      done.current();
    };
    const el = video.current;
    if (!el || prefersReducedMotion()) {
      finish();
      return;
    }
    const ceiling = window.setTimeout(finish, LIFTOFF_CEILING_MS);
    // With <source> children a failed load fires on the last source, not the video.
    const last = el.querySelector("source:last-of-type");
    el.addEventListener("ended", finish);
    el.addEventListener("error", finish);
    last?.addEventListener("error", finish);
    try {
      const started = el.play();
      if (started && typeof started.catch === "function") started.catch(finish);
    } catch {
      finish();
    }
    return () => {
      finished = true;
      window.clearTimeout(ceiling);
      el.removeEventListener("ended", finish);
      el.removeEventListener("error", finish);
      last?.removeEventListener("error", finish);
    };
  }, [playing]);

  return (
    <video
      ref={video}
      data-liftoff={playing ? "playing" : "loading"}
      muted
      playsInline
      preload="auto"
      disablePictureInPicture
      aria-hidden="true"
      tabIndex={-1}
      className={`pointer-events-none absolute top-1/2 left-1/2 aspect-video w-[min(960px,220cqw)] max-w-none -translate-x-1/2 -translate-y-1/2 transition-opacity duration-[var(--duration-panel)] [mask-image:radial-gradient(closest-side,black_78%,transparent)] ${
        playing ? "opacity-100" : "opacity-0"
      }`}
    >
      {LIFTOFF_SOURCES.map((source) => (
        <source key={source.src} src={source.src} type={source.type} />
      ))}
    </video>
  );
}
