# Interface skin — the AIA design system on the 18.6.6 screens

**Status:** in progress · **Owner:** product-surface (A9) + web · **Started:** 2026-09-23
**Decision:** [ADR 0013](../../docs/architecture/adr/0013-interface-skin-at-the-facade.md) (Proposed)
**Design source:** [`docs/design/aia-design-system-brief.md`](../../docs/design/aia-design-system-brief.md),
the token foundation on `feature/web-primitives` @ `cb26c15`.

> **2026-09-24, [ADR 0015](../../docs/architecture/adr/0015-client-first-product-interface.md).**
> The skinned document is now served at `/classic`, the labelled hand-off, not at
> `/`; the develop site is AIA's client-first application, and the classic
> screens are the behavioural reference rather than the canonical baseline. The
> skin, its pin and its kill switch are unchanged. Chunk 5 (the live baseline)
> still waits on the oracle's reach from an agent session.

## Problem

The develop site is the canonical baseline for every screen (data owner,
2026-09-23): the 18.6.6 interface, served at `/` from the frozen unit behind AIA
sign-in (ADR 0012). It has every feature, button and label, and it looks like a
prototype: 17 inline `<style>` blocks accumulated over releases, 328 distinct hex
colours, 356 inline `style=` attributes, a system-font stack, and status colours
that are not the design system's. The AIA design system exists — tokens, fonts,
identity, status and evidence semantics, decisions DS-1 to DS-3 — but it has
never reached a screen anyone uses, because its compositions targeted AIA's own
Next.js pages, which ADR 0012 replaced.

## Approach

Skin now, re-home later (ADR 0013). The unit stays byte-identical; the web
client adds one stylesheet to the one document the unit serves at `/`, and only
when that document's SHA256 is the pinned one. The stylesheet is generated from
`tokens.json` and re-points the variables the interface is already built on,
then restyles shared components with selectors taken from the real markup.

Why not the obvious alternatives: re-homing now reverses ADR 0012's order and
needs D-L1; editing the unit violates ADR 0011; a Caddy body rewrite needs a
custom module and puts presentation at the edge. The skin is also the cheapest
way to find out which design changes need structure (and so must wait for
re-homing) and which do not.

**What the skin may change:** colour, type, spacing, radii, borders, elevation,
focus rings, density, iconography where it is CSS, and the visual treatment of
states the interface already names.
**What it may not change:** markup, labels, order, flows, behaviour, or what a
state *means*. Anything that needs those is written down in *Needs structure*
below and waits for the area's re-homing.

## Trade-off accepted

A skin cannot restructure a screen, so this buys a consistent, modern surface
on every screen now at the cost of carrying some structural debt until each
area is re-homed.

## Baseline

- **Source structure:** `legacy/npc-panel-18.6.6/app/ui_app.html`, SHA256
  `d844dd6f…81eaee` (`app-manifest.json`). One router, `go(view)`, with views
  `home`, `production`, `brief`, `plan`, `questionnaire`, `audience`, `persona`,
  `run`, `results`, `verify`, `next`, `command`, `fullsim`, `data`, `settings`,
  `demo`, and the later-layer views `projects`, `demos`, `demo_project`,
  `sim_run`, `sim_change`; products `research`, `simulation`, `library`;
  library tabs `upload`, `sources`, `proposals`, `learning`, `research`.
- **Live screens with real data:** from the parity oracle
  (`AIA_LEGACY_REFERENCE_URL` + basic auth), which is never skinned. Not
  reachable from cloud sessions until, in order: the oracle hostname exists on
  develop (the three optional `aia_legacy_hostname` / `_basic_user` /
  `_basic_hash` parameters and a DNS record, OI-39 — on 2026-09-24 only the
  product hostname is configured); `legacy.aia-develop.art-chain.io` is
  allow-listed in the session environment; and the three
  `AIA_LEGACY_REFERENCE_*` values are in its secrets (requested 2026-09-23). A local run of the unit stops at
  `/api/bootstrap` without the licence-bound data bundle, and a fictional
  stand-in was abandoned after three layers of population dependencies: it would
  have meant fabricating the population layer.

## Chunks

- [x] 0. **This plan and ADR 0013.** `design-system.md` marked: its screen
      chunks (V, 4–11) are superseded by the 18.6.6 baseline; its foundation
      (chunks 1–3) is carried by chunk 1 here and by the re-homing slices.
- [x] 1. **Token foundation onto `develop`.** From `feature/web-primitives`
      @ `cb26c15`, the foundation only: `src/design/tokens.json` (74 colours × 2
      themes, byte-identical), `scripts/build-tokens.mjs` with `--check`, the
      generated `tokens.css` / `tokens-theme.css` / `tokens.ts` / `fonts.css`,
      IBM Plex Sans/Mono and Source Serif 4 as woff2 with their OFL licences
      (byte-identical to the branch), the brand SVGs, the AIA favicon and icons,
      `scripts/check-design.mjs`. No screen compositions. Two deliberate
      differences from the branch: font stacks name the self-hosted families
      instead of `next/font` variables, and the generator emits `@font-face`
      from one `FACES` list (`AGENTS.md` § Next.js); fonts and identity live
      under `public/skin/`, because Caddy sends `/brand/*` to the unit.
      `next/font/google` (Geist) removed: nothing is fetched from a font CDN.
      Vitest **4.1.11**, not the branch's 3.2.7 (GHSA-82fw-gwwq-j7x9); npm 10
      cannot add it, npm 11 can (`AGENTS.md`). `make web_design` and
      `make test-web` join `check` and `verify`; CI's frontend job runs
      `tokens:check`, `check:design` and `npm test`. — measured: contrast
      146 checks, 0 failures; palette and client-accent checks PASS in both
      themes; 4 token tests pass; lint, `tsc --noEmit`, `next build` clean;
      `npm audit` 13 findings against `develop`'s 14, none from Vitest.
- [x] 2. **The injector.** `src/lib/interface-skin.ts` (`applySkin`, pure):
      SHA256 against `PINNED_INTERFACE_SHA256`; on a match a `preload` before
      `</head>` and the stylesheet before the last `</body>` — last, because
      18.6.6 keeps three `<style>` blocks in `<body>` and appends nine to
      `<head>` at runtime; anything else byte-for-byte with a named outcome.
      `src/app/interface-document/route.ts` fetches `AIA_LEGACY_PANEL_URL` and
      says what happened in `X-AIA-Skin`; unit errors pass through, an
      unreachable unit is a 502. Caddy: `/` → `route { forward_auth → rewrite →
      web }` (a bare `handle` re-sorts the rewrite ahead of the gate — proven,
      `AGENTS.md` § Caddy); direct `/interface-document` → 404; `/skin/*` and
      the icon set → web. Compose: `AIA_INTERFACE_SKIN_ENABLED: "false"` until
      the skin exists, no `depends_on` the unit (OI-44). CI: a new
      `develop-host-config` step asserts gate → rewrite → web and the direct
      404. — measured: 20 web tests (pin = `app-manifest.json`; exactly two
      tags added on the real document; off, mismatch, no head/body; route
      against a local stub of the unit). End to end through the real Caddyfile
      (upstreams pointed at localhost), the real `ui_server.py`, `next start`
      and a stub gate: signed-out `/` → `/login?next=%2F` with the gate seeing
      `/`; signed-in `/` 200 `X-AIA-Skin: applied`, 896 591 → 896 758 bytes;
      direct injector 404; fonts and favicon ungated; unit paths gated. The
      CI check fails on the swapped order and on the bare-`handle` form.
- [x] 3. **The variable layer.** `scripts/build-skin.mjs` → `public/skin/skin.css`:
      the self-hosted faces (`scripts/faces.mjs`, shared with AIA's pages), the
      tokens as `--aia-*` (18.6.6 already defines `--ink` and a `--space-*` scale
      with other values), then `src/skin/legacy-variables.json`: 29 of 18.6.6's
      variables re-pointed at tokens, each with its reason, and 13 deliberately
      left (`--claude`, layout widths, spacing, component-local variables).
      `src/skin/components.css` is the hand-written layer, linted by
      `scripts/skin-lint.mjs` for raw colour, radius, shadow and font values.
      Decisions taken here, recorded in the mapping: **light only**, as 18.6.6
      is (its last variable block forces light under a dark preference, and 328
      hard-coded colours would leave a dark theme half dark); **`--ok` is quiet
      ink** — the design system has no green; **`--warn` is the "waiting on a
      person" family**, amber ink and wash only, because each 18.6.6 WARNING names
      a fix step a person must take — the solid amber stays reserved (OI-11).
      Four tokens added to `tokens.json`: `signal-hover`, `signal-wash-strong`,
      `signal-tint`, `signal-edge`, with their contrast pairs; the check caught
      `signal` on the first `signal-wash-strong` at 4.31:1 and the value moved to
      `#cde8f8` (4.58:1). — measured: contrast 164 checks, 0 failures; 36 web
      tests, including that every variable 18.6.6 defines or uses is mapped or
      left with a reason; in Chromium against the real document (bootstrap held,
      shell only): body and buttons in IBM Plex Sans (loaded 400/500/600, Mono
      400/500), page on `surface`, soft actions on `signal-wash`. Still 18.6.6's:
      the white workspace and 3 px radii, which are hard-coded (chunk 4).
- [x] 4. **Shared components.** `src/skin/components.css`, token-only (lint
      clean): shell (paper workspace and top bar, sunken rail, step list, tool
      buttons), Studio type scale (page title 28/32, card titles 20/26, headings
      15/20, labels 13/18), `.metric` as the design system's hero number (sans,
      tabular — 18.6.6 set it in monospace), cards and section heads on raised
      and sunken surfaces with one 4 px radius and no shadow, `.info` on
      `signal-tint`, callouts (`okbox` quiet ink rule; `warnbox` the person
      family; `badbox` fault) with a coloured left rule on a hairline, choice
      cards with a signal selection, every button variant, chips with a shape as
      well as a colour (a drawn check, a ring, a cross), forms with
      `border-strong` controls and the one focus ring, tables with sentence-case
      left-aligned headers and tabular figures, the toast, and the progress bar.
      **The progress bar no longer travels:** 18.6.6 slides a segment back and
      forth, which reads as progress the backend is not reporting; the skin
      draws a still line whose live edge breathes, and stops even that under
      `prefers-reduced-motion`. — verified in Chromium against the real
      document with a specimen built from 18.6.6's own render templates
      (fictional labels; `renderSteps()` draws the real research rail): 1440 and
      1024 px; the +35 % Czech stress at 1280 px — no clipped control, no page
      scroll, the same result unskinned. Not yet seen: screens with real data
      (chunk 5).
- [x] 5. **Baseline, locally.** Replaced by the UI workbench
      ([ui-workbench.md](ui-workbench.md)): the real `ui_app.html` on a fictional
      panel, every route its router knows plus the DEMO views, captured bare and
      skinned by `tools/ui_workbench/capture.mjs`. The oracle-with-real-data
      capture stays optional (it needs egress and an identity; ui-workbench.md).
- [ ] 6. **Per-area passes** — now only while an area waits for its React
      rebuild ([ADR 0014](../../docs/architecture/adr/0014-rebuild-the-interface-in-react.md),
      [interface-rehome.md](interface-rehome.md)); each area's skin rules are
      deleted when `/` moves. Original order, one PR each, in this order: home and projects;
      research flow (brief → plan → questionnaire → audience → persona → run);
      results and verify; command centre; simulation (`fullsim`, `sim_run`,
      `sim_change`); data library; settings; demos; Sociomap (its own seven
      style blocks). — verify: before/after from chunk 5 for the area.
- [x] 6a. **Switched on for develop** (`AIA_INTERFACE_SKIN_ENABLED: "true"` in
      `deploy/develop/docker-compose.yml`), as its own commit, so that merging
      is what shows the skin and reverting one value removes it. Per-area
      passes (6) follow the live baseline. **Merged in PR #45 @ `4dc7966` and
      deployed by run 14, but not visible:** the running Caddy never read the
      new Caddyfile (OI-45). Fixed by hashing the Caddyfile into the caddy
      service's configuration, with a smoke check that only the current
      Caddyfile passes.
- [x] 7. **Promote.** ADR 0013 → Accepted, 2026-09-24: the data owner saw the
      skin on develop (run 15, `230ee7e`). The plan stays open for 6 until the
      re-home retires it.

## Hard-coded overrides

Listed here as they are written (chunk 4 onwards): selector, the 18.6.6 value it
replaces, the token it uses, and why the variable layer could not reach it.

Every rule in `components.css` overrides a hard-coded 18.6.6 value; the
variable layer reaches only what 18.6.6 wrote as `var()`. The ones that need
`!important`, because 18.6.6 itself declares them `!important`:

| Selector | 18.6.6 value | Token | Why |
| --- | --- | --- | --- |
| `.toast` background, color, border-radius, box-shadow | `var(--ink)`, `#fff`, 3 px, a literal rgba shadow, all `!important` | `surface-inverse`, `ink-inverse`, `radius-md`, `shadow-overlay` | the toast is an overlay; its colours come from the inverse pair |
| `.moving` border-radius, background | 999 px, `#E8F0F3`, `!important` | `radius-sm`, `border` | the track is a hairline, not a pill |
| `.moving i` background | `var(--brand)`, `!important` | `signal` | the live edge |

## Needs structure — waits for re-homing

Design changes the skin cannot make, recorded as they are found, per area.

- **Dark theme.** Not a structural change, but out of reach until every
  hard-coded colour the interface uses is overridden or re-homed; 18.6.6 itself
  forces light. Chunk 4 onwards reduces the count; dark is turned on when it is
  zero for an area, not before.

## Review outcome

Filled in when the plan is archived.
