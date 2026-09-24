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
- [ ] 2. **The injector.** `apps/web` route `/interface-document`: fetch
      `legacy-panel:8765/`, SHA256 against the pin, insert the stylesheet link
      before `</head>` or pass through unchanged with `X-AIA-Skin: bypassed`;
      `AIA_INTERFACE_SKIN_ENABLED` off by default. Caddy: `/` → `forward_auth` →
      rewrite → web; direct `/interface-document` → 404; `/skin/*` → web.
      Compose and `env.example`. Also route `/favicon.ico`, `/icon.svg` and
      `/apple-icon.png` to the web client, which now serves AIA's identity
      there and the unit would otherwise answer. — verify: unit tests of the pure injector
      (applied, bypassed on mismatch, bypassed when off, no `</head>`), a test
      that the pin equals `app-manifest.json`, `develop-host-config` validates
      the Caddyfile, a local run end to end against the real `ui_server.py`.
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
