# UI workbench — see every screen, change the skin in seconds

**Status:** in progress · **Owner:** product-surface (A9) + web · **Started:** 2026-09-24
**Serves:** [interface-skin.md](interface-skin.md) chunk 6 (per-area passes) and the
data owner's direction of 2026-09-24: "we need to be able to edit the UI very quick
and you need to be able to see everything."

> **2026-09-27, [ADR 0018](../../docs/architecture/adr/0018-aia-runs-without-18-6-6.md)
> decision 4.** The skin is gone, so the workbench no longer builds it and `/classic` is
> AIA's page saying 18.6.6 is not part of AIA. The unit still runs beside AIA, bare at
> `:8767`, as the reference a screen is compared with; `up --no-unit` runs AIA alone.
> The records below that name the skin describe what landed at the time.

**Decision, 2026-09-24 (data owner):** full UI control, not only the skin — markup,
text, layout, components and behaviour — by **rebuilding the screens in React** in
the web client, area by area; D-L1 extends to the rebuilt screens (the real-client
demo identifiers they carry are accepted, `exposure_check` still enforces client
names everywhere else). Copying `ui_app.html` and patching it at runtime were both
declined. That programme has its own ADR
([0014](../../docs/architecture/adr/0014-rebuild-the-interface-in-react.md)) and plan
([interface-rehome.md](interface-rehome.md)); this workbench is where every rebuilt
screen is seen next to the one it replaces, and the capture of the classic screens
is the rebuild's specification.

## Problem

The skin is live on develop (run 15, `230ee7e`; smoke "caddy: running the deployed
Caddyfile" ok). The loop for changing it is not usable:

1. **Nobody but the data owner can see the screens.** An agent session cannot reach
   `aia-develop.art-chain.io`: the cloud egress policy refuses the CONNECT (403,
   2026-09-24), and even with egress it would need a Cognito owner/admin identity
   to pass the gate. Every design decision so far was checked on a *specimen* of
   18.6.6 templates, not the screens.
2. **Every change is a deploy.** PR → CI → merge → deploy is ~15 minutes before
   anyone sees a changed border colour.
3. **Nobody knows what is left.** 328 hard-coded colours were counted in the
   source; which of them still show on a screen after the skin is unknown.

## Approach

A local workbench that runs **the real thing** — the vendored unit's own
`ui_server.py` serving the pinned `ui_app.html`, the web client's own
`/interface-document` route applying the skin, and a facade that routes like the
develop Caddyfile — and a capture pass that walks **every route the interface's
router knows**, skinned and bare, and measures what the skin did not reach.

Why not the obvious alternatives:

- *Point the capture at develop.* Needs an egress exception and a standing
  Cognito identity with owner rights — a credential in a session environment for
  a develop host that holds licence-bound data. It is a data owner's decision and
  it stays optional (below); the workbench must not depend on it.
- *Screenshot a specimen.* That is what chunk 4 did; it proves components, not
  screens. The router, the demos and the runtime-injected styles only exist in the
  running document.
- *A Caddy binary.* Highest routing fidelity, but a binary download per session
  and upstream names rewritten by sed. The facade reads the `@web` matcher out of
  the committed Caddyfile instead, so the one routing fact that matters here
  (which paths go to the web client) cannot drift.

**What it is not:** a parity harness. The unit runs on a scratch copy with the
licence-bound population panel replaced by a small, obviously fictional frame
(`FIKTIVNI-###` respondents). Numbers on its screens mean nothing and are never
compared with anything. Parity stays with `tools/legacy_oracle.py` (ADR 0011).

**Trade-off accepted:** screens that need the real panel (population views, a
research run's numbers) show their empty or error states locally. The DEMO
library ships in `app/` and fills the project, results and simulation screens;
anything still empty is listed in the capture report, not guessed at.

## Chunks

| # | Chunk | Status |
|---|---|---|
| 0 | This plan | done |
| 1 | `tools/ui_workbench/`: `up` / `down` / `status`. A venv for the unit's runtime requirements (uv when present), a scratch copy of `app/` under `tmp/ui-workbench/unit/`, the fictional panel, `next dev` for the web client with the skin switched on, and `facade.py` routing like the Caddyfile minus the gate. `npm run skin:watch` rebuilds `skin.css` on every save of `src/skin/*` or `tokens.json`; a reload shows it. Facade routing tested against the committed Caddyfile | done: `make ui-workbench` boots the real `ui_app.html` with `X-AIA-Skin: applied` and the 30 DEMO projects listed; `test_ui_workbench.py` 15 passed; a save of `components.css` rebuilds in < 0.1 s (`logs/skin.log`) |
| 2 | `tools/ui_workbench/capture.mjs`: every route parsed from `ui_app.html`'s router, then a DEMO project and each of its tabs; bare (the unit direct) and skinned (the facade) at 1440 and 1024 px; per screen: page errors, horizontal overflow, and every computed colour not in the token palette with a sample selector. `report.json` + a side-by-side `index.html` | done: 24 routes (4 aliases folded) + 4 DEMO collections × 6 views = 48 screens × 2 widths × bare/skinned in ~8 min, 48 MB under `tmp/`; 0 page errors, 0 horizontal overflow at 1440/1024; most off-palette paint: `projects` (188 elements), `demos` (127). The screen ledger `docs/migration/interface-screens.json` is generated from it and checked against the router by `interface-screens.test.ts` |
| 3 | Docs (CLAUDE.md map and commands, AGENTS.md gotchas, PROGRESS), PR into `develop`, the first capture published to the data owner as a review page | docs for chunk 1 done; the rest pending |
| 4 | The capture covers the rebuilt React screens too, each beside the classic screen it replaces (paths come from the same `@web` matcher, so nothing is configured twice) | done: every ledger row not `CLASSIC` is shot at its `react_path` and every classic text it does not show is listed; the facade tunnels WebSockets, so `next dev` live-reloads through it (19 passed) |

## Optional, the data owner's decision: the capture against develop

To see develop's own data rather than the fictional panel, the capture can take a
base URL. It needs, in order: `aia-develop.art-chain.io` in the cloud
environment's allowed domains, and a dedicated reviewer identity in the develop
Cognito pool with an owner or admin grant, its credentials held as environment
secrets. Neither exists; the workbench does not wait for them.
