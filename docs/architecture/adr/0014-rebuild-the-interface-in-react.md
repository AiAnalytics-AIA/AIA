# ADR 0014 — Rebuild the interface in React, area by area, over the unit's API

**Status:** Proposed — develop only (data owner's decision, 2026-09-24; see
*Decision record* below). Changes the order of [ADR 0012](0012-legacy-interface-as-product-facade.md)
(re-homing starts now, not last); keeps [ADR 0011](0011-vendor-legacy-product-unit.md)
and [ADR 0013](0013-interface-skin-at-the-facade.md) for the screens not yet rebuilt;
extends decision D-L1.
**Superseded in part by [ADR 0015](0015-client-first-product-interface.md)**
(2026-09-24): decisions 1 (the classic interface stays at `/`), 4 (a classic
screen's capture is the specification) and 7 (hand-offs to `/#aia:…`, now
`/classic#aia:…`). The React rebuild under `/app`, the ledger-checked unit
client and the fragment hand-off mechanism stand, re-homed under the client
(`/app/clients/<client>/research/<study>/<stage>`).
**Date:** 2026-09-24

## Context

The skin (ADR 0013) is live on develop and the data owner has seen it working.
It can change how a screen looks and nothing else: the markup, the labels, the
order of a flow, what a component is, how a screen behaves all belong to
`ui_app.html`, which is frozen (ADR 0011). The data owner asked for full control
of the UI, edited quickly, with the agent able to see every screen.

Three ways were put to the data owner:

1. **Own a copy of the document.** Serve an editable copy of `ui_app.html` from
   the web client. Full control on day one, but ADR 0012 declined it: it forks a
   896,591-byte document whose screens are drawn by 737 functions from HTML
   strings, and every later change is made inside that.
2. **Patch the frozen document at runtime.** A script beside the skin that
   rewrites the DOM after each render. The interface re-renders from strings on
   every state change, so every patch must re-apply every time.
3. **Rebuild the screens in React**, in the web client, one area at a time.

The data owner chose 3.

## Decision

1. **The rebuilt interface is AIA's web client, under `/app`.** Next.js 16, React
   19, Tailwind 4, the design system's tokens as the only source of colour, type,
   spacing, radius and motion. No unit path begins with `/app`
   (`docs/migration/legacy-route-ledger.json`, 153 routes). The classic interface
   stays at `/` until the rebuilt one covers what the data owner uses; then `/`
   moves to the rebuilt interface and the classic one to a path of its own, by a
   Caddyfile change and a smoke check, never by removing it.

2. **The same gate.** `/app` and `/app/*` pass through `forward_auth` to
   `GET /api/v1/panel/gate` exactly as `/` does: organization owners and admins
   only. The pages hold no data; everything they show is fetched from the
   browser, through the same gated paths the classic document uses.

3. **The unit is the backend until each capability is ported.** Screens call
   the unit's own HTTP API (`/api/projects/...`, `/api/demos`, ...) through **one
   typed client** in `apps/web/src/unit/`. Every call names its route in the
   legacy route ledger; a test fails a call to a path the ledger does not list.
   When the strangler ports a capability to AIA's API, the client's call moves to
   `/api/v1/...` and the screen does not change. Behaviour therefore stays the
   unit's, verified by the oracle, while the presentation becomes AIA's.

4. **Screens are rebuilt from the classic ones, not from memory.** The UI
   workbench's capture (`tools/ui_workbench/capture.mjs`) of each classic screen
   is its specification: every label, control and state it shows. The rebuilt
   screen is captured beside it. Czech copy moves into the web client's catalogue
   (`src/i18n/cs.ts`) verbatim first; a changed label is a visible diff there.
   Where a classic screen computes something in the browser, the function is
   ported with a `U<nn>` fixture, as the strangler plan already requires.

5. **A screen ledger is the state.** `docs/migration/interface-screens.json`
   lists every classic screen the capture finds (24 routes, the DEMO views and
   their tabs) with `CLASSIC` / `REBUILDING` / `REBUILT`, its React path and the
   unit routes it calls. A screen is `REBUILT` only with its capture pair and its
   tests.

6. **Behind a switch.** `AIA_INTERFACE_REHOME_ENABLED` (off by default, on in the
   develop compose) decides whether `/app` renders or answers 404. *Retired for `/app`
   by [ADR 0018](0018-aia-runs-without-18-6-6.md) decision 3 (2026-09-27): AIA is the
   product, so nothing stands in for it; `/app` answers whenever AIA's gate admits the
   person.*

7. **A hand-off, not a patch, joins the two interfaces.** The classic interface
   has no deep links: it opens a project from its own state. So a rebuilt screen
   links to `/#aia:open=<id>` (or `#aia:start=research|simulation`,
   `#aia:go=<route>`, `#aia:switch=research|simulation|library`,
   `#aia:assistant=open`, `#aia:support=bundle`, `#aia:dimension=research`), and the web client adds one script,
   `/skin/handoff.js`, to the pinned document while `/app` is on. After the
   classic boot reports `ready`, it clears the fragment and calls the classic
   interface's own function for that instruction — `openProject1785`,
   `startProductionResearch`, `startSimulationProduct1773`, `go` for a route
   its router knows, `switchProduct1776`, `openAssistant1791`,
   `createSupportBundle`, `openDimensionResearch1793` — the function the
   classic button calls. A proposed dimension's name is free text the
   fragment's pattern cannot carry, so the rebuilt screen leaves it in
   same-origin `sessionStorage["aia:dimension-research"]` and the script reads
   it once. It changes no DOM
   and calls nothing else; an instruction that does not match is ignored. The
   pin guarantees the names exist; `X-AIA-Handoff` says whether it was added.
   This is the one behaviour the web client adds to the classic document, and it
   goes when `/` moves.

8. **D-L1 extends to the rebuilt screens.** The real-client demo identifiers the
   classic interface carries (`ui_app.html`, 9 hits in the unit's
   `exposure-report.json`) may appear where a rebuilt screen needs them, as
   identifiers only. `exposure_check` keeps enforcing client names everywhere
   else, and in file names everywhere.

## Consequences

- The design is no longer bounded by the classic markup: layout, components,
  copy and flow are AIA's to change, screen by screen, and each change is seen in
  seconds in the workbench (`next dev`).
- For a while there are two interfaces. The rebuilt one links to the classic one
  for any area not yet rebuilt, and the skin keeps the classic one consistent
  with the design system meanwhile; its rules are deleted as areas move.
- The web client gains a second backend (the unit) until the strangler retires
  it. The ledger check keeps that surface enumerable, and a unit route that
  changes shape breaks the client's validation rather than a screen.
- Calls go from the browser to the unit through Caddy, as the classic document's
  do: no new trust boundary, and no server-side path to the unit from the web
  client beyond the interface-document route ADR 0013 already added.

## Alternatives considered

- **Own a copy of `ui_app.html`.** Offered as the fastest path to full control.
  Declined by the data owner.
- **Patch the frozen document at runtime.** Declined: brittle against a document
  that re-renders from strings.
- **Rebuild against AIA's API only.** The end state, but most of the 153 unit
  routes have no AIA equivalent yet; waiting for them would mean no rebuilt
  screen for months. The typed client makes the switch per call.

## Revisit when

- The rebuilt interface covers the areas the data owner uses: `/` moves to it.
- A capability is ported to AIA's API: its calls move off the unit.
- Production is planned.

## Decision record

Asked and answered on 2026-09-24 in the session that wrote this ADR: *full UI
control, not only the skin*; of the three ways put, **rebuild in React**; for the
real-client demo identifiers, **extend D-L1 to the rebuilt screens**.
