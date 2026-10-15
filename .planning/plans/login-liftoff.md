---
status: done
chunks:
  - "[x] 1. The film as a brand asset: VP9 + H.264, no sound, and its ground as a token"
  - "[x] 2. Liftoff: the film in the mark's slot, ended / failed / stalled / reduced motion all lead in"
  - "[x] 3. /login: the sign-in button arms it, the opened session plays it, its end is the redirect"
---
# The lift-off film on sign-in

**Drafted:** 2026-10-12 · **Base:** `develop` @ `5d545eb` · **Owner:** the product owner, who supplied
`aia-liftoff.mp4` and asked that "when a user presses login, it plays this video where the current
AIA logo is, and after it's done, that's when it redirects to the actual software".

## Decisions

1. **When it plays.** Pressing *Přihlásit se přes Google* goes to Google and back before AIA's
   session can open, so the film cannot play on the press itself without delaying Google. The press
   **arms** it (`lib/liftoff.ts`, `sessionStorage`, ten minutes); `/login` takes it when the session
   opens, plays it, and its end is `window.location.replace(next)`. Anything else that lands on
   `/login` -- the gate bouncing a navigation, a reload, a session already open -- goes straight in,
   as before. It plays at most once per press.
2. **Where.** In the mark's own slot on the front door's aside, centred on it and sized so the film's
   mark (428 of 1920 px, measured from its first frame) matches the 240 px static mark; capped at
   220 % of the aside's width (container units) so the closing lockup fits from 1024 px down. The
   aside goes to the film's ground, `brand-stage` (`#111015`, sampled from the film, both themes), and
   the film's edges fade into it with a radial mask. On a narrow screen, where the aside hides its
   mark, the aside takes the viewport while the film plays.
3. **Never in the way.** Muted (no user gesture survives the Google round trip, so sound could not
   autoplay), hidden from assistive technology, and the status line still says *Otevírám AIA…*.
   The film leads in when it ends, when no source decodes or `play()` is refused, after a 12 s
   ceiling if it stalls, and at once under `prefers-reduced-motion`.
4. **The asset.** The supplied file is 3.2 MB H.264 + AAC. Shipped as VP9 WebM (551 KB, preferred)
   and H.264 MP4 (465 KB, `+faststart`, for Safari), 1920×1080 at 60 fps, no audio; the film's
   lockup frame holds to the end, so nothing is trimmed.
5. **The loop guard** (`aia.session.openedAt`) now starts its clock as the browser leaves for `next`,
   not when the session opens, so a 7.4 s film cannot run past the 10 s window and hide a cookie that
   did not stick.

## Measured

Next dev + Chromium (Playwright), API stubbed: the film plays from the opened session and the page
redirects 8.7 s after load (0.8 s stubbed session + 7.4 s film); light, dark, 1440 / 1024 / 390 px,
lockup within the aside at every width.

## Doc follow-up

- `CLAUDE.md` § 2, under `src/components/brand/`: "Liftoff: the lift-off film
  (`public/skin/brand/aia-liftoff.{webm,mp4}`) in the front door's mark slot after a sign-in the
  person started (`lib/liftoff.ts` arms and takes it); muted, decoration, its end the way in."
- `apps/web/src/design/tokens.json` gained `brand-stage`: the film's ground, front door only.
