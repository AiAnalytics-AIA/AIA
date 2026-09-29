# Interface re-home — the screens rebuilt in React, area by area

**Status:** in progress · **Owner:** product-surface (A9) + web · **Started:** 2026-09-24
**Decision:** [ADR 0014](../../docs/architecture/adr/0014-rebuild-the-interface-in-react.md) (Proposed),
**superseded in part by [ADR 0015](../../docs/architecture/adr/0015-client-first-product-interface.md)**

> **Read this first (2026-09-24, [client-first-ia.md](done/client-first-ia.md)).** The
> React work below is kept, but its frame changed. AIA is the product at `/`
> (→ `/app/clients`); the classic interface is a hand-off at `/classic`, not the
> page `/app` sits beside. The classic rail is no longer copied: the global
> navigation is *Klienti, Společenská inteligence, Projektová paměť, Nastavení*
> and a study's stages are drawn only inside the study. A classic screen's capture
> is **evidence of what it does, not the specification** of the rebuilt one
> (ADR 0015 superseding ADR 0014 decision 4). The research stages live at
> `/app/clients/<client>/research/<study>/<stage>`; *Správa projektů* moved to
> `/app/settings/classic-projects` (the unit's store, OI-58). The area order below
> is historical; the next areas are chosen inside the client workspace.
**Tools:** [ui-workbench.md](ui-workbench.md) — every classic screen captured, every
rebuilt one beside it.

> **2026-09-27, [ADR 0018](../../docs/architecture/adr/0018-aia-runs-without-18-6-6.md)
> ([legacy-phase-out.md](legacy-phase-out.md) chunks 8–9).** `/app` has AIA's own gate,
> with no switch; nothing hands off to 18.6.6; the typed unit client (`src/unit/`) and
> `/app/settings/classic-projects` are removed with their last caller. A classic screen
> AIA has not rebuilt is `NOT_IN_AIA` in `interface-screens.json`, and says so where a
> person meets it. The chunk records below name files that no longer exist.

## Problem

The data owner wants full control of the UI — markup, copy, layout, components,
behaviour — edited quickly. The skin (ADR 0013) reaches only the look; the
document is frozen (ADR 0011). Decided 2026-09-24: rebuild in React.

## Approach

ADR 0014: the rebuilt interface is the web client under `/app`, behind the same
gate as `/`, calling the unit's own API through one typed, ledger-checked client
until each capability is ported to AIA's API. The classic interface stays at `/`
and is linked to for every area not yet rebuilt. The capture of each classic
screen is its specification.

**Order of areas** — the ones a person meets first, and the ones the DEMO library
fills with content so the rebuild can be seen, go first; the heaviest go last:

| # | Area | Classic routes | Why here |
|---|---|---|---|
| A1 | Shell: navigation, identity, build, the link to the classic interface | the sidebar, `home` | Every screen sits in it |
| A2 | Projects — *Správa projektů* | `projects` | The working landing page; filters, views, 30 DEMO cards |
| A3 | DEMO project | `demos`, `demo_project` and its tabs | Read-only, full content, no AI |
| A4 | Research flow ([plan](research-flow-rehome.md), in progress) | `brief`, `plan`, `questionnaire`, `audience`, `persona`, `run`, `research_progress`, `results`, `verify`, `next` | The core path, step by step |
| A5 | Simulation flow | `sim_context`, `sim_change`, `sim_people`, `sim_run`, `sim_results` | Second product path |
| A6 | Project overview | `project_overview` | Joins A4/A5 |
| A7 | Data Library, Settings, AI assistant | `data`, `settings`, `command` | Operator areas |
| A8 | Visualization / Sociomap | `visualization` | Heaviest; its maths is already ported (`aia_core.domain.sociomap`) |

## Chunks

| # | Chunk | Status |
|---|---|---|
| 0 | ADR 0014, this plan, the screen ledger generated from the first capture | done: 28 ledger rows (24 routes, 4 DEMO collections), all `CLASSIC`; `interface-screens.test.ts` 3 passed |
| 1 | Routing: Caddy `/app` gated like `/`; the workbench facade follows the Caddyfile; `AIA_INTERFACE_REHOME_ENABLED`; smoke check; CI config test | done: `@rehome` gate → web with the cookie dropped (CI's adapt assertion run locally against the real Caddyfile: pass); the facade picks every matcher that proxies to web:3000 (18 passed); `/app` 200 through the workbench; smoke: anonymous `/app` → `302 /login?next=%2Fapp` |
| 2 | Foundation: the typed unit client (`src/unit/`, every call ledger-checked), the UI primitives on tokens, the catalogue | client done: `unit()` + `UNIT_ROUTES` (5 routes, all ledger rows), Projects parse and logic ported from 14 classic functions, **220 parity checks against the originals run under Node** (`projects.parity.test.ts`), 225 tests in `src/unit/`. Primitives and catalogue land with the shell (3) |
| 3 | A1 Shell | rail and header done: the classic rail item for item (Nastavení and Pokročilé groups included), each unrebuilt item a hand-off marked as such; the rail's foot reads Claude Code and the joint core from the unit — 18.6.6 prints *Core joint · VALID* as a literal (OI-46). The classic `home` route itself is not rebuilt yet |
| 4 | A2 Projects | **done**: `/app/projects` + `/app/projects/trash`, every control of the classic screen, confirm/prompt as a modal dialog, toasts; ledger row `REBUILT`; capture pair 0 classic texts missing at 1440/1024; 7 component tests (jsdom), 220 parity checks; driven end to end in the workbench (views, search, pin, trash, restore, hand-off into a DEMO) |
| 5+ | A3–A8, one chunk per area, each: capture pair, tests, ledger row `REBUILT` | pending, re-planned inside the client workspace ([client-first-ia.md](done/client-first-ia.md)) |
| — | `/` moves to the rebuilt interface; the classic one to its own path | **done early, by decision** (ADR 0015, 2026-09-24): `/` → `/app/clients`, the classic interface at `/classic`; the shell of chunk 3 was replaced by the client-first `AppShell` |

## Deliberate differences from the classic screens

Recorded here so a capture diff is never mistaken for a regression:

| Screen | Classic | Rebuilt | Why |
|---|---|---|---|
| all | emoji in labels (🗑, ★, +) | icons, same words | design brief §5: no emoji |
| all | `confirm()` / `prompt()` | a modal dialog, same question | the browser's chrome is not the product's |
| Projects | running, waiting-on-you, waiting-on-the-world share one "warn" chip | three tones | brief §4.3; the parity test pins which classic class each replaces |
| Rail | *Core joint · VALID*, a literal | the status the unit reports | OI-46 |
| Header | Úvod / Výzkum / Simulace / Správa projektů repeated beside the title | in the rail only | the same four targets twice |

## Rules for every area chunk

- Start from the capture of the classic screen: list its labels, controls,
  states, and the unit routes its code calls (the ledger names them).
- Copy verbatim into `cs.ts` first; any change of wording is its own diff.
- No colour, radius, shadow or font outside the tokens.
- The screen fetches from the browser through `src/unit/`; nothing else talks to
  the unit.
- Done means: the capture pair in the workbench, component tests, `make verify`,
  the screen ledger row, and the skin rules for that area deleted once `/` moves.
