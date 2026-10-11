---
status: done
chunks:
  - "[x] 1. Plan, terrace tokens and design evidence: a ten-step terrace ramp, stage, ground and link tokens; adjacent-band ΔE, CVD and label-contrast checks"
  - "[x] 2. View logic over the frozen artifact: absolute ten-band display quantization, terrace edges, ranked list, pair detail (UNKNOWN-with-r apart from undefined r), screen-space label placement"
  - "[x] 3. Terraced 3D geometry: display elevation by band, stored height kept on every vertex, relief and the entrance rise as presentation only, measured view size"
  - "[x] 4. The redesigned workspace: dark stage, HUD, toolbar (3D / Shora / Otáčet / Jen názvy / Vztahy / Přehrát animaci), labels that avoid each other and the panels, selected-object, pair and ranked cards, legend, Czech copy"
  - "[x] 5. Boundary tests, full checks, browser comparison against the prototype (top, 3D, pair card, labels-only, relations off, 360 px, both themes), PR"
  - "[x] 6. Visual fidelity correction: the prototype as the composition acceptance spec (checklist V1-V25 below), paired screenshots, remaining differences named"
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

## Visual fidelity correction (chunk 6, 2026-10-11)

Owner's review of PR #268: the result is "an AIA Sociomap inspired by the design", not "the
production implementation of that design". From now on the standalone prototype is the
**visual composition acceptance specification**. Every methodology safeguard above stays
(contract 3, `aia-sociomap-3`, frozen fingerprints, stored terrain and coordinates, Stress-1,
pair evidence, UNKNOWN vs undefined r, `mapLinks` gating, PRIMARY / SECONDARY, ten fixed 0-1
bands, Canvas/SVG renderer, no three.js, all boundary tests).

Compared at 1440 × 1100 and 360 px wide: prototype (`1-proto-top` … `5-proto-narrow`) against
PR #268 head `c3a0c56d`. A difference may remain only if caused by stored research data,
accessibility, the no-three.js constraint, or an explicit AIA requirement; each kept one is
named in the paired-screenshot table at the end of this section.

### Checklist: what differs, and what production must become

| # | Area | Prototype | PR #268 `c3a0c56d` | Correction |
|---|---|---|---|---|
| V1 | Page composition | kicker 12 px muted, title 24/30 semibold (the battery's title), interaction hint right-aligned 12 px; chips; then map column + aside | 14 px "Mapa objektů (aia-sociomap-3)" heading only; no title, no hint | header as the prototype: kicker = method, title = battery title, hint on the right |
| V2 | Map column | stage + legend bar only, the column sticky beside the aside | stage + legend + a row of camera buttons + slider + three help paragraphs | column is stage + legend; camera buttons, relief and help move into a collapsed disclosure; sticky when side by side |
| V3 | Map dominance / framing | plinth fills ~75 % of the stage height (top) and ~65 % of its width (3D) | ground square is the whole ±2.75 grid; the terrain uses ~45 % of it | frame the view on a square around the stored terrain's defined cells and every object (display zoom; same scale on both axes) |
| V4 | Stage | 16:10, min 420 px, radius 10, flat `#14171c`, no border | same aspect, min 320/420, a 1 px ring | no ring; min height 420 at every width |
| V5 | HUD | top-left 14 px, 10/12 padding, radius 8, translucent, 11/14 text; quality as a **filled** pill | same place; weak quality as an outlined orange pill | filled pill coloured by the stored quality |
| V6 | Toolbar | top-right, 12 px, 5/11 padding, regular weight, white/18 border; "Otáčet" usable from top view | medium weight, "Otáčet" disabled in top view | prototype sizes; "Otáčet" from top view opens 3D and rotates |
| V7 | Selected object | chip + 18/24 name, role, three 22/28 stats in one row (průměr 0–1 · škála 1–10 · pásmo), relation rows, pair card inside the same card | an "Objekt" select and a "Porovnat" select; stats wrap to two rows; long captions | no selects (pins, list rows and relation rows are the buttons); one stat row, short captions |
| V8 | Relation rows | name · 64 px diverging bar · value; state line; partner row washed; negative bar orange; U+2212 minus | same grid, wider value column, `viz-div-6` bar, hyphen minus | prototype widths and colours, true minus |
| V9 | Pair card | dark card in the selected card: title + ✕, r (20/26) · stav · podpora, one verdict, the "not drawn" note only when not drawn, "Prohodit pohled" | adds a "A × B: r = …" sentence, separate interval and floor lines, a reason line always | prototype order; interval, floor and drawn state as one 11 px evidence line (the handoff requires them) |
| V10 | Ranked list | rank · chip · name · value, selected row washed | same, plus "· kontext" suffix | names as in the prototype |
| V11 | "Jak mapu číst" | one paragraph, three 11 px lines (pairs, not placed, method + fingerprint), "Uložit snímek (PNG)" | paragraph, a details block, a fit paragraph, eight lines, no PNG | prototype card; everything else behind one "Podrobnosti a původ" disclosure; PNG export built |
| V12 | Legend | title, ten stepped bars, 0 / 0,5 / 1; bez dat, kladný, záporný; lines rule, context diamond; `#1c2026` | rating-scale ends, an extra bands sentence, stage colour + ring | prototype order and labels on the 0–1 scale; bands sentence to the disclosure |
| V13 | Explanatory copy | the hint line only | three paragraphs under the map | hint in the header; the rest in disclosures |
| V14 | Spacing | page 28/24, row gap 16, column gap 8, aside gap 14, card padding 16 | close, but extra rows change the rhythm | prototype values |
| V15 | Typography | title 24, name 18, stats 22, body 12, captions 11 | 14 px heading, 13–14 px body | prototype sizes |
| V16 | Colour hierarchy | selected label/pin **yellow**, compared object light blue, hovered white, others dark translucent pills | selected white, no hover colour | `viz-map-select` yellow (plot area only), partner blue, hover white |
| V17 | Labels | 12 px semibold pill, radius 6, 4/9 padding, soft drop shadow; meta line on the active label; dimmed 0.45 | same pill, no shadow, selected white | shadow, colours as V16 |
| V18 | Terrain silhouette | smooth concentric terraces, flat plateaus, light rim at each step, shaded risers | 3D: jagged triangulated cones; top: square-cell staircase | terraces as flat layers cut from the stored mesh at the band thresholds (marching triangles on the same piecewise-linear surface the mesh draws), vertical risers shaded by facing, light rims, display-only height scale |
| V19 | Camera | 3D from ~27° elevation, plinth diagonal to the viewer, slightly below centre | 38° elevation, whole grid | elevation ≈ 0.48 rad, yaw −0.66, framed as V3 |
| V20 | Top view | the plinth with shaded terraces and white rings round pin heads | flat cell squares, discs | layer paths with a lower-right shadow and a light rim, pin heads with rings, plinth edge |
| V21 | 3D view | plinth with dark sides and edge lines, drop shadow; sphere heads on thin stalks, base rings | grid-wide plinth, small discs | plinth framed to the terrain, edge stroke, canvas shadow; larger heads, base rings |
| V22 | Narrow (360) | HUD and toolbar stay over the stage (they collide in the prototype); stage 420 high | HUD and toolbar move above the stage | keep both over the stage, each capped at half its width so they do not collide |
| V23 | Choreography | on open: terraces rise 1.6 s, pins pop in turn, labels at 90 %, arcs draw 0.7 s; camera glides into 3D; rotation 75 s per turn | rise only on entering 3D, instant camera, 30 s per turn | the same choreography (skipped under reduced motion); glide into 3D, leave instantly (the kill switch) |
| V24 | Header hint and interaction | "Tažením otáčíte · kolečkem přibližujete · klik na objekt ukáže jeho vztahy" | in a paragraph under the map | header |
| V25 | PNG | "Uložit snímek (PNG)" | not built | client-side export of the current view, marked internal, no recomputation |

### What was built against the checklist

- V1, V13, V24: header with kicker (method), the battery's title at 24/30, the interaction hint on
  the right; the chips; nothing else above the map.
- V2, V14: map column = stage + legend (sticky beside the aside at `lg`); camera buttons, relief
  and their help in one collapsed "Ovládání 3D pohledu a výšky" disclosure, shown only in 3D.
- V3, V19, V20, V21: `mapFrame` frames a square around every stored terrain sample with a height
  and every object (6 % pad, never beyond the grid; one scale on both axes). Top view: the square
  at 72 % of the stage height on a raised plinth with a drop shadow. 3D: yaw −0.66, elevation
  0.48, plinth 4 % wider than the frame with dark walls, an edge line and a canvas shadow.
- V18: `terraceLayers` cuts the stored mesh (the same triangles `terrainMesh` draws, the same
  piecewise-linear surface) at each band's lower bound; each terrace is a flat top drawn in one
  fill at its band's top, risers facing the viewer shaded by the design's light direction, a
  light rim between terraces. Top view: the same layers as SVG paths with a lower-right shadow.
  `HEIGHT_SCALE` 0.62 (display only). Tests prove every piece corner is a stored sample or an
  exact edge crossing at the level, every sampled surface point lies in its own band's terrace
  and not the next, a triangle with a null corner draws nothing.
- V5, V6, V22: HUD and toolbar at the prototype's sizes, quality as a filled pill
  (`viz-fit-*`), "Otáčet" from top view opens 3D and turns at 75 s per turn; at 360 px both stay
  over the stage, the HUD capped at half the width.
- V7-V11: selected-object card without selects (pins, list rows and relation rows are the
  buttons), stats in one row (original scale to one decimal, as the design), relation rows with
  a true minus and the design's colours, the pair card inside it (r · stav · podpora, one
  evidence line: interval, floor, drawn; the verdict; the reason only when not drawn; swap);
  ranked list; "Jak mapu číst" with the three lines, one "Podrobnosti a původ" disclosure for
  everything else, and "Uložit snímek (PNG)".
- V12: legend in the design's order on the 0 / 0,5 / 1 scale.
- V16, V17: `viz-map-select` yellow for the selected pin and pill (plot area only; contrast
  checked), compared object blue, hovered light, others translucent pills with the design's
  drop shadow.
- V23: one choreography clock: terraces rise and build up (1.6 s), pins pop in turn from 0.9 s
  (60 ms apart), labels at 1.35 s, arcs draw in over 0.7 s after a selection, the camera glides
  from straight down into 3D over 0.9 s; leaving 3D is instant (the kill switch). Nothing runs
  under `prefers-reduced-motion`.
- V25: PNG export composes the canvas and the SVG as shown (token colours resolved by
  `resolveVars`), adds a strip "Interní · nesmí ke klientovi · aia-sociomap-3 · otisk …", and
  downloads `sociomapa-interni.png`; nothing redrawn from data.

### Paired screenshots and what still differs (1440 × 1100; 360 px; light and dark)

| Pair | Remaining difference | Cause |
|---|---|---|
| Top | Fewer, narrower hills; most of the terrain in the lowest band; 6 objects, not 8 | stored data: σ = 0.25 on the ruler, heights 0.24-0.66 |
| Top, 3D | The lowest terrace's outer edge is stepped | stored data: the grid is null beyond the kernel cutoff at 64 intervals; rounding it would draw terrain where nothing is stored ("holes stay holes") |
| Top | Terraces lit by a flat offset shadow, not a lit 3D surface | no-three.js constraint (SVG, no lighting) |
| 3D | Orthographic, no fog, no soft cast shadows, flat discs for pin heads with a highlight | no-three.js constraint; orthographic is the fixed-ruler requirement |
| 3D | Vertical risers instead of smoothstep slopes | Canvas 2D flat polygons (no-three.js); a sloped riser would need an invented in-between surface |
| 3D | "Ovládání 3D pohledu a výšky" disclosure under the legend | accessibility: buttons and a slider for the camera and relief besides drag and wheel |
| All | Negative links dashed; a faint stage casing under links | accessibility: sign not by colour alone; ≥ 3:1 over every terrace (check-design) |
| Labels, card | "zobrazovací pásmo 7/10", "pásmo (zobrazení)" instead of "pásmo 8/10", "pásmo" | handoff: the band is display-only and labelled as such |
| Pair | An evidence line (interval, floor, drawn); "—" for an undefined r | handoff: the pair card consumes those fields; "r = —" copy |
| Relation rows | "nedefinováno ·" before the state of an undefined r | requirement: UNKNOWN with r and undefined r stay distinct |
| Reading card | A "Podrobnosti a původ" disclosure | AIA requirement: provenance, σ notice, support and the fictional-data sentence stay reachable |
| Header | Kicker "Mapa objektů (aia-sociomap-3)" and the battery title, not "Návrh · …" | the design's own text is a mock-up label; the method and title come from the artifact |
| Narrow | The HUD does not overlap the toolbar | accessibility: in the prototype the two collide and hide text |
| Dark | A faint inset edge on the stage, legend and pair card | the prototype has no dark theme; without it the stage merges into the graphite page |

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
- `CLAUDE.md` map: `object-map-3d.ts` also holds `terraceLayers` (terraces cut from the stored
  mesh at the band thresholds) and the framed projection; `object-map-view.ts` `mapFrame`,
  `frameToScreen`, `resolveVars`; new tokens `viz-map-select`, `viz-fit-*`.
- `docs/architecture` research journey / sociomapping: the Results object map is a
  presentation of the stored `aia-sociomap-3` artifact; the ten bands are display-only.
