---
status: done
chunks:
  - "[x] 1. The dot field's maths as pure functions: Halton homes, primes, drift, cursor spring, the mark at the film's frame-0 lattice and the row/column assignment"
  - "[x] 2. The front door in Graphite: the 34 % field panel, wordmark, tagline, the form unchanged in wording, stacked below 760 px"
  - "[x] 3. DotField: the full-viewport canvas, idle drift and cursor push, the handoff into the mark, aia:mark-formed"
  - "[x] 4. The launch film full-screen on aia:mark-formed, the canvas removed on its first frame, its end the way in"
  - "[x] 5. /login wired to the real session: authenticating copy, the handoff on success, reduced motion; browser proof of the cut"
---
# The login screen and its handoff into the launch film

**Drafted:** 2026-10-12 · **Base:** `develop` @ `400fa24` · **Owner:** the product owner, who supplied a
prototype (`aia-login-prototype.html`, artifact DRH37K8gPSSZ63we4Lhk6d) and asked for it to be ported:
a Graphite front door whose left panel is a field of 144 dots; on a successful sign-in 25 of them
fly into the AIA mark at the launch film's first-frame geometry, the film takes over without a
visible cut, and its end is the way into `next`.

Supersedes the lift-off film in the mark slot ([login-liftoff.md](login-liftoff.md)): the film now
plays full-screen after the handoff, `components/brand/Liftoff.tsx` goes, `lib/liftoff.ts` (armed by
the sign-in button, taken once) stays.

## Decisions

1. **Frame 0 is the lattice, checked.** The mark forms on the brief's lattice (centre +
   (coord − 20) · 15 · s, the A's points r 34.5 · s, the rest r 13.5 · s, the apex bold), and the
   film's first frame must be that same mark. The first film supplied did not start there (its
   frame 0 already carried the mark's breathing, dots up to 35 film px off, the apex r 15.6); the
   owner re-exported it, and the re-export's frame 0 is the lattice within 0.13 px.
   `tools/film_frame0.py` (stdlib over ffmpeg) measures a film's frame 0 and fails above 0.5 px, so
   a future export is checked before it ships: `python tools/film_frame0.py
   apps/web/public/skin/brand/aia-liftoff.webm`.
2. **Tokens over the prototype's hex, and the identity's cyan as the front door's signal.** The page
   is `data-theme="dark"` and uses AIA's Graphite tokens, which differ slightly from the prototype's
   (surface `#0d1015` not `#0f1215`, raised `#151a21`, border `#252c36`). AIA's UI `signal` is
   `#8aa2ff`; the identity draws in cyan `#6ac5e8` (aia-mark-on-graphite.svg, the favicon, the film),
   now the token `brand-apex`. The owner chose the cyan for the front door (2026-10-12): FrontDoor
   scopes `--signal`, `--signal-hover` and `--focus-ring` to it, so the button, the wordmark's point
   and the focus ring are cyan there and nowhere else. On-signal text on it is 10.0:1, the ring on
   the page 9.8:1. The film's ground is `brand-stage` (`#111015`, sampled).
3. **The cut.** During the handoff the page ground fades to `brand-stage` and the canvas paints
   that ground opaquely under its dots, so by the time the mark is formed the canvas alone is what
   shows. On `aia:mark-formed` the film is shown beneath the canvas, still paused on its preloaded
   frame 0; two frames later the canvas is removed, and a frame after that the film plays. Playing
   first and swapping on the first presented frame was measured and rejected: the film was already
   0.049 s (3 frames) in, and its dots move from frame 0. A browser that will not load a video
   before it plays (iOS) gets it played after 1 s and the canvas removed on its first presented
   frame (`requestVideoFrameCallback`, else `playing` + a frame).
4. **Reduced motion.** No drift, no cursor push, the handoff a 0.45 s move, and no film: the person
   goes in when the mark has formed.
5. **When.** Only after a sign-in the person started on this page (`lib/liftoff.ts`), as before; a
   bounce from the gate or a reload goes straight in.

## Measured

Next dev + headless Chromium, API stubbed, `/tmp` proof scripts (not committed):

| | 1440×900 | 1920×1080 | 390×844 |
|---|---|---|---|
| Film position when the canvas leaves | 0 s, paused | 0 s, paused | 0 s, paused |
| Canvas mark vs film frame 0 on screen, mean abs. diff | 0.96 / 255 | 1.06 / 255 | 0.38 / 255 |
| Pixels differing by > 16 | 0.11 % | 0.10 % | 0.17 % |
| Way in after the handoff starts | 7.40 s | 7.38 s | 7.40 s |

Measured with the re-exported film. The remaining difference is anti-aliasing only: a ring at each
dot's rim, where the scaled film is softer than the canvas; every centre agrees (1920×1080: canvas
780.00, 360.00; film on screen 780.11, 360.09). Idle, signed out, the cursor sweeping the panel for 3 s at 1440×900: 180 frames,
median and p95 16.7 ms, none over 20 ms; 0 layouts and 0 style recalculations
(`Performance.getMetrics`); 0.47 ms of script per frame. Reduced motion: in 530 ms after the
handoff starts, the film never plays.

## Findings

- The first film supplied did not start on the brief's frame-0 geometry (decision 1); found with
  `tools/film_frame0.py`, fixed by the owner's re-export, which the tool passes (0.13 px).

## Doc follow-up

- `CLAUDE.md` § 2, `src/components/brand/`: replace the Liftoff entry with: "DotField: the front
  door's 144-dot field (lib/dot-field.ts, pure) on a full-viewport canvas; on a sign-in the person
  started (lib/liftoff.ts) 25 primes fly into the mark at the launch film's frame-0 geometry
  (lattice, checked by tools/film_frame0.py) and `aia:mark-formed` fires; LaunchFilm then plays
  public/skin/brand/aia-liftoff.{webm,mp4} full-screen on `brand-stage`, takes over on its first
  frame, and its end is the way in." FrontDoor's entry: "the Graphite frame of /login, /logout,
  /auth/callback".
- `CLAUDE.md` § 2 `tools/`: "tools/film_frame0.py  Checks the launch film's frame 0 is the mark
  the handoff forms (stdlib over ffmpeg; fails above 0.5 px)".
- FrontDoor's entry also: "the identity's cyan (`brand-apex`) is the signal there".
- `tokens.json` gained `brand-apex`; `brand-stage`'s usage now names the handoff.
- `components/brand/AiaMark.tsx` and `LatticeField.tsx` are no longer used by any page (FrontDoor
  was their only user); kept, since AiaMark's test pins it to the mark's source SVG.
