"use client";

/**
 * The launch film, full-screen on the film's own ground (`brand-stage`), object-fit:
 * contain: mounted with the front door's handoff so it is loaded before it is
 * needed, out of sight until `aia:mark-formed`. Then it shows, still paused on
 * its first frame, beneath the dot field's canvas -- which by then paints the same
 * ground and the same mark, at the film's frame-0 geometry; `onFirstFrame` lets the
 * canvas go, and only then does the film play, so the first frame anyone sees is
 * frame 0 and the cut cannot be seen. Its end is `onDone`. A browser that will not
 * load a video before it plays (iOS) gets it played after a second, the canvas
 * going on its first presented frame.
 *
 * Never in the way: muted, hidden from assistive technology; `onDone` also when no
 * source can be played (said the moment the mark forms, never during the
 * handoff), when play() is refused, after a ceiling in case it stalls, and at once
 * under prefers-reduced-motion, where the film does not play.
 */

import { useEffect, useRef, useState } from "react";

import { MARK_FORMED_EVENT } from "@/lib/dot-field";

// In order of preference; the browser takes the first it can play.
export const FILM_SOURCES = [
  { src: "/skin/brand/aia-liftoff.webm", type: 'video/webm; codecs="vp9"' },
  { src: "/skin/brand/aia-liftoff.mp4", type: "video/mp4" },
] as const;
// The film is 7.4 s; past this, whatever it is doing, the person goes in.
export const FILM_CEILING_MS = 12_000;
// How long a formed mark waits for frame 0 to load before the film is played to get it.
export const FILM_FRAME0_WAIT_MS = 1_000;

function reducedMotion(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

type FrameVideo = HTMLVideoElement & { requestVideoFrameCallback?: (cb: () => void) => number };

export function LaunchFilm({ onFirstFrame, onDone }: { onFirstFrame: () => void; onDone: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [rolling, setRolling] = useState(false);
  const calls = useRef({ onFirstFrame, onDone });
  useEffect(() => {
    calls.current = { onFirstFrame, onDone };
  }, [onFirstFrame, onDone]);

  useEffect(() => {
    const el = video.current as FrameVideo | null;
    if (!el) return;
    let started = false;
    let broken = false;
    let finished = false;
    let shown = false;
    let ceiling = 0;
    let wait = 0;
    const still = reducedMotion();
    const finish = () => {
      if (finished) return;
      finished = true;
      calls.current.onDone();
    };
    const show = () => {
      if (shown || finished) return;
      shown = true;
      calls.current.onFirstFrame();
    };
    // A source that fails while the mark is still forming is said when it has formed.
    const fail = () => (started ? finish() : (broken = true));
    const roll = () => {
      if (finished) return;
      try {
        const playing = el.play();
        if (playing && typeof playing.catch === "function") playing.catch(finish);
      } catch {
        finish();
      }
    };
    // Frame 0 is on screen under the canvas: let the canvas go, paint once, then play.
    const reveal = () => {
      window.clearTimeout(wait);
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          show();
          requestAnimationFrame(roll);
        }),
      );
    };
    const start = () => {
      if (started) return;
      started = true;
      if (still || broken) return finish();
      setRolling(true);
      ceiling = window.setTimeout(finish, FILM_CEILING_MS);
      if (el.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) return reveal();
      el.addEventListener("loadeddata", reveal, { once: true });
      wait = window.setTimeout(() => {
        el.removeEventListener("loadeddata", reveal);
        if (typeof el.requestVideoFrameCallback === "function") el.requestVideoFrameCallback(show);
        else el.addEventListener("playing", () => requestAnimationFrame(show), { once: true });
        roll();
      }, FILM_FRAME0_WAIT_MS);
    };
    const last = el.querySelector("source:last-of-type");
    el.addEventListener("ended", finish);
    el.addEventListener("error", fail);
    last?.addEventListener("error", fail);
    window.addEventListener(MARK_FORMED_EVENT, start);
    return () => {
      finished = true;
      window.clearTimeout(ceiling);
      window.clearTimeout(wait);
      el.removeEventListener("loadeddata", reveal);
      el.removeEventListener("ended", finish);
      el.removeEventListener("error", fail);
      last?.removeEventListener("error", fail);
      window.removeEventListener(MARK_FORMED_EVENT, start);
    };
  }, []);

  return (
    <video
      ref={video}
      data-film={rolling ? "rolling" : "standby"}
      muted
      playsInline
      preload="auto"
      disablePictureInPicture
      aria-hidden="true"
      tabIndex={-1}
      className={`pointer-events-none fixed inset-0 z-[5] h-full w-full bg-brand-stage object-contain ${rolling ? "visible" : "invisible"}`}
    >
      {FILM_SOURCES.map((source) => (
        <source key={source.src} src={source.src} type={source.type} />
      ))}
    </video>
  );
}
