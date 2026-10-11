---
status: done
chunks:
  - "[x] 1. Plan, terrace tokens and design evidence: a ten-step terrace ramp, stage, ground and link tokens; adjacent-band ΔE, CVD and label-contrast checks"
  - "[x] 2. View logic over the frozen artifact: absolute ten-band display quantization, terrace edges, ranked list, pair detail (UNKNOWN-with-r apart from undefined r), screen-space label placement"
  - "[x] 3. Terraced 3D geometry: display elevation by band, stored height kept on every vertex, relief and the entrance rise as presentation only, measured view size"
  - "[x] 4. The redesigned workspace: dark stage, HUD, toolbar (3D / Shora / Otáčet / Jen názvy / Vztahy / Přehrát animaci), labels that avoid each other and the panels, selected-object, pair and ranked cards, legend, Czech copy"
  - "[x] 5. Boundary tests, full checks, browser comparison against the prototype (top, 3D, pair card, labels-only, relations off, 360 px, both themes), PR"
---

# Object map 3D redesign (`aia-sociomap-3`, presentation only)

**Source.** The design handoff `design_handoff_sociomapping_3d` (README + the standalone
prototype `AIA Sociomap 3D v3 (standalone).html`), received 2026-10-11; not vendored (its
`sources/` PDFs are the method owner's and stay out of the repository). The prototype is a
visual reference only: three.js, invented objects, invented relations and invented terrain
constants (`MOCK ONLY` in its source). Nothing methodological is taken from it.

**Builds on** [`object-map-3d-workspace.md`](object-map-3d-workspace.md) (done), whose
frozen-artifact and presentation-only boundaries remain binding, and on chunk 5a of
[`sociomap-formula-corrections.md`](sociomap-formula-corrections.md), which put the
contract-3 map on Results.

## Scope

A presentation redesign of the canonical contract-3 object Sociomap `aia-sociomap-3` on the
Results page. It is not the experimental `aia-research-sociomapping-*` H-Model path and does
not advance `sociomapping-engine.md`.

## Boundaries (binding)

- For the same inputs and the same pinned `aia-sociomap-3` spec the canonical artifact is
  byte-identical: relations, Q6 evidence states, Kish effective n, Fisher intervals, effect
  floor, PRIMARY / SECONDARY roles, correlation-distance SMACOF layout, Stress-1, heights, the
  F12 object envelope, its parameters, support, spec and artifact fingerprints.
- No change under `packages/aia_core/src/aia_core/domain/sociomap/`, no contract 4, no method
  or version bump, no IDW / WIND terrain, no Pearson t-test, no p-value, no `AIA-W1` or
  `AIA-A1`, no per-map rescaling.
- The browser renders `terrain.height` as stored and never evaluates a kernel; it never
  recomputes a relation, an interval, a layout or Stress-1. A link is drawn only where the
  existing `mapLinks` rule already draws it (PRIMARY ↔ PRIMARY, RELIABLE, floor met where
  declared, r defined); the redesign filters that set for focus and never widens it.
- The ten display bands sit on the absolute stored 0–1 scale (`floor(h × 10)`, clamped), never
  this map's min/max. Labels and cards show the stored number; the band is labelled as a
  display band.
- Relief (vertical exaggeration), the camera, auto-rotation and the entrance animation
  ("Přehrát animaci") are presentation state. The animation is an opening effect, not a time
  series.
- No three.js, no new runtime dependency. The existing canvas/SVG renderer and its
  orthographic projection stay. Top view is the default; returning to it unmounts the 3D
  renderer.
- UNKNOWN with a numeric r and an undefined r (`r == null`) are explained differently; the
  aggregate count is "neznámé vztahy", not "insufficient evidence".

## Chunk log

**1. Tokens and evidence (2026-10-11).** `viz-terrace-1..10`, `viz-stage`, `viz-stage-raised`,
`viz-stage-ink`, `viz-stage-muted`, `viz-ground`, `viz-link-positive`, `viz-link-negative`,
`viz-map-partner`, `viz-map-context` in `apps/web/src/design/tokens.json`. The prototype's
"spektrum" ramp failed protan between bands 6 and 7 (ΔE 1.8); bands 4-7 were retuned until
adjacent ΔE ≥ 12.6 (normal) and ≥ 9.9 (protan/deutan). `scripts/check-design.mjs` §4 fails
below ΔE 10 / 8, below ΔE 10 to the ground, and on 20 stage contrast pairs; a collapsed band
was shown to fail it. The stage is graphite in both themes, so light = dark values. The
generated `domain/report/print_tokens.py` gains the new viz-* colours (every viz- token is
exported); no existing value changes.

**2. View logic** (`apps/web/src/lib/object-map-view.ts`). `terraceBand` = `floor(h × 10)`
clamped to 0..9 on the absolute scale (test: k/10 lands on band k despite floating point; a map
whose heights sit in [0.40, 0.49] is one band). `terraceLevel`, `originalRating`,
`terraceEdges` (top-view steps between stored neighbours in different bands), `terrainAt`
(nearest stored sample, for a pin's ground), `rankedByHeight`, `pairDetail` (every field read
from the artifact; `drawn` is membership of `mapLinks`; `why` explains: undefined r → UNKNOWN →
WEAK → context → below floor), `placeLabels` (greedy screen-space placement around the anchor,
clear of other labels, panels and pins, inside the view; anchors are inputs and never move).
The seven-step `band()` is gone from this module (the map no longer uses `viz-seq`; other
charts still do).

**3. Geometry** (`apps/web/src/lib/object-map-3d.ts`). Each vertex keeps `height` (stored) and
gets `elevation` (its terrace top); faces across terraces are risers. `projectTerrain` takes
the measured view size; `HEIGHT_SCALE = 0.55` and the default camera (zoom 1.3, elevation
0.66) are display choices made after comparing with the prototype: σ = 0.25 hills drawn at full
height read as spikes. `plinthSides`, `easeOut` for the opening rise.

**4. Workspace** (`ObjectMapView.tsx`, `ObjectMapTerrain.tsx`, new `ObjectMapMarks.tsx`,
`i18n/cs.ts`). Dark stage with HUD (method, stored Stress-1 quality badge, Stress-1, placed of
respondents) and toolbar (3D / Shora / Otáčet / Jen názvy / Vztahy / Přehrát animaci); on
narrow screens both sit above the map instead of over it. Links: the selected object's subset
of `mapLinks` (all of them with nothing selected), cased for contrast, dashed when negative,
arcs in 3D; unlinked objects dimmed. Pins: discs, diamonds for SECONDARY. Labels measured with
canvas `measureText` in the browser (estimated in tests) and placed by `placeLabels`, clear of
the HUD and toolbar. Cards: selected object (stored 0–1 height, original scale, display band
labelled "zobrazovací pásmo", relations with diverging bars), pair card (r, state, n / n_eff,
Fisher interval, floor result, drawn-or-why, verdict, swap), ranked list, "Jak mapu číst"
(short reading, details, Stress-1 meaning, status counts as "neznámé vztahy", not placed,
provisional σ notice, synthetic notice, method + fingerprint). The expand/compact switch and
the "Zobrazit spolehlivé vztahy" checkbox are replaced by the responsive layout and the
"Vztahy" toggle. Auto-rotation stops on drag and in top view; the rise animation is skipped
under `prefers-reduced-motion`; the wheel zooms only in 3D.

**5. Verification.** Web: 47 files / 720 tests before the final polish (object map: 24 view, 8
geometry, 10 boundary, 20 view component, 2 terrain component). Boundary proofs:
`object-map-boundary.test.ts` (no exp/log/atanh/tanh/sqrt/cbrt, no SMACOF/Pearson/Fisher/Kish,
no read of `parameters.sigma` or `kernel_cutoff`); component tests for top view default, 3D
unmount (no canvas after "Shora"), only `mapLinks` pairs drawn (UNKNOWN-with-r, undefined r,
WEAK, below floor, SECONDARY all absent), SECONDARY changes no terrain cell, stored values
printed beside the band, UNKNOWN-with-r vs undefined r copy, names-only leaves the cards
unchanged, the artifact never mutated. Python: sociomap/object-map selection 658 passed / 5
reference skips before and after; 194 canonical fixture and sociomap source files hash-identical
to the pre-change baseline; `tools/object_map_web_fixture.py --check` passes;
`aia-sociomap-3` artifact `a46f3b0032c5…` and spec `e16dc0d06361…` fingerprints unchanged.
Browser (production build, a temporary uncommitted page rendering the builder's fixture,
Chromium via Playwright): top, 3D, pair card, names-only, relations off, 1440 and 360 px, light
and dark; no console errors, no horizontal overflow at 360 px, no canvas after returning to top
view. The prototype was rendered beside it (three.js served locally; esm.sh is blocked).

**Not done.** "Uložit snímek (PNG)" (optional) was not built: the 3D view is a canvas under an
SVG whose colours are CSS variables, and a faithful export means inlining every resolved colour
into a composited image; the report image remains `object_map_figure.py`. The live check on
`RUN-1725024c5b8b480a` needs the deployed develop site after merge; this session has no access
to it.

## Findings

- Next.js 16 `next dev` refuses its HMR and dev resources to a page opened as
  `http://127.0.0.1:<port>` unless `allowedDevOrigins` lists it; the page renders but never
  hydrates, so a headless click does nothing and no error is thrown. Wrong: drive `next dev`
  at `127.0.0.1`. Right: `next build && next start` (or `localhost`, or `allowedDevOrigins`).
  Reproduction: `next dev -p 3917`, open `http://127.0.0.1:3917/` in Playwright, wait for a
  `__reactProps` key on any button -- it never appears; the dev log prints "Blocked
  cross-origin request to Next.js dev resource /_next/hmr". (Hypothesis-free; observed
  2026-10-11.)

## Doc follow-up

- `CLAUDE.md` § 2 map, under `apps/web`: `src/lib/object-map-view.ts` -- the contract-3 object
  map read from the artifact: ten display terraces on the absolute 0-1 scale, terrace edges,
  pair evidence (`pairDetail`: UNKNOWN with r apart from undefined r), screen-space label
  placement; `src/lib/object-map-3d.ts` -- terraced orthographic geometry, stored height and
  display elevation on every vertex; `src/components/rehome/research/ObjectMap{View,Terrain,Marks}.tsx`
  -- the redesigned Results workspace (top default, 3D unmounts, presentation-only relief,
  rotation and opening animation).
- `CLAUDE.md` § 2 map, `src/design/tokens.json`: the object map's `viz-terrace-1..10` and stage
  tokens, checked by `check-design.mjs` § 4.
- `AGENTS.md`, Next.js: the `127.0.0.1` / `allowedDevOrigins` finding above, wrong and right
  side by side.
- `docs/architecture` research journey / sociomapping: the Results object map is a
  presentation of the stored `aia-sociomap-3` artifact; the ten bands are display-only.
