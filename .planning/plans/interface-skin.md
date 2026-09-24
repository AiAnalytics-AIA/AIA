# Interface skin — the AIA design system on the 18.6.6 screens

**Status:** in progress · **Owner:** product-surface (A9) + web · **Started:** 2026-09-23
**Decision:** [ADR 0013](../../docs/architecture/adr/0013-interface-skin-at-the-facade.md) (Proposed)
**Design source:** [`docs/design/aia-design-system-brief.md`](../../docs/design/aia-design-system-brief.md),
the token foundation on `feature/web-primitives` @ `cb26c15`.

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
  reachable from cloud sessions until `legacy.aia-develop.art-chain.io` is
  allow-listed and the three `AIA_LEGACY_REFERENCE_*` values are in the
  environment's secrets (requested 2026-09-23). A local run of the unit stops at
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
- [ ] 3. **The variable layer.** `skin.css` generated from `tokens.json`:
      18.6.6's variables (`--bg`, `--card`, `--soft`, `--rail`, `--line`,
      `--line-strong`, `--ink`, `--mut`, `--faint`, `--brand*`, `--ok*`,
      `--warn*`, `--bad*`, `--shadow`, `--r`, `--font-sans`, `--font-mono`)
      mapped onto design-system tokens, for light and dark. — verify: the
      contrast check covers every pair the mapping creates; drift check.
- [ ] 4. **Shared components.** Shell (header, product tabs, step rail, page
      title), buttons, cards and panels, forms, tables, badges and pills,
      dialogs and drawers, the assistant panel, focus rings, scrollbars. Hard
      coded colours that bypass the variables are overridden per component and
      listed below. — verify: in Chromium against the real document, both
      themes, 1440 / 1280 / 1024, +35 % Czech strings.
- [ ] 5. **Live baseline.** `tools/interface_screens.mjs`: every view above
      captured from the oracle (unskinned) and from a local skinned copy, side by
      side. **Blocked** on oracle access (Baseline, above).
- [ ] 6. **Per-area passes**, one PR each, in this order: home and projects;
      research flow (brief → plan → questionnaire → audience → persona → run);
      results and verify; command centre; simulation (`fullsim`, `sim_run`,
      `sim_change`); data library; settings; demos; Sociomap (its own seven
      style blocks). — verify: before/after from chunk 5 for the area.
- [ ] 7. **Promote.** ADR 0013 → Accepted after the first skinned deploy is seen
      working on develop; plan → `done/`.

## Hard-coded overrides

Listed here as they are written (chunk 4 onwards): selector, the 18.6.6 value it
replaces, the token it uses, and why the variable layer could not reach it.

## Needs structure — waits for re-homing

Design changes the skin cannot make, recorded as they are found, per area.

## Review outcome

Filled in when the plan is archived.
