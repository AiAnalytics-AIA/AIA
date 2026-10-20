---
status: in-progress
chunks:
  - "[x] 0. This plan"
  - "[x] 1. Read -5 maps in the web: the stored fields typed, pure readers for the panel renderer, a stored -5 fixture; nothing drawn changes"
  - "[x] 2. The object map as the AIA panel draws it: terrain, colour ramp, relief, frame, nodes, labels, relation lines, legend, camera; a -5 map read first and routed to it"
  - "[x] 3. Map credibility on the map: the weakly-determined banner, the uncertainty circle, the sparse and label notes, objects not placed"
  - "[ ] 4. The respondent map: Objekty | Respondenti, dots, faint dots, the density terrain, object markers, the notes below six and three objects"
  - "[ ] 5. Taste segments on the respondent map: colours, legend, borderline hint"
  - "[ ] 6. Detail on click: an object's and a respondent's detail, in the panel's content"
  - "[ ] 7. The Word report's -5 map figure in the panel's look; the web map's PNG snapshot, with its legend"
---
# aia-sociomap-5 in the web — the map drawn as the AIA panel draws it

**Owner:** A. Bahbouh (methodology) · **Started:** 2026-10-20 · **Follows:** `signed-off-sociomap-method.md`
(computation, merged as #504).

## Problem

`-5` maps are computed and stored (`compute_object_map`, contract-3 artifact) but the web does not read them:
`OBJECT_MAP_METHODS` (`apps/web/src/lib/object-map-view.ts:20`) names `-2/-3/-4` only; the map draws absolute 0–1
heights on ten terraces (`terraceBand`, `TERRACE_BANDS`), though `-5` stores relative heights; it frames its own square
(`mapFrame`), not the frame `-5` stores; and there is no respondent map or segment view at all.

## Approach

**Standing rule (methodology owner, 2026-10-19):** every visual decision inside the Sociomap visualisation panel follows
the current AIA panel (`NPC_Panel/ui_app.html`); the website around it stays as it is.

**Decided (methodology owner, 2026-10-20):**

| Decision | Chosen |
|---|---|
| Which maps get the panel's drawing | `-5` maps only. `-2/-3/-4` keep today's drawing (the approved terrace design; `-3` is the register-approved client map) |
| Interactions in this round | The drawing and the core controls: camera (rotate, tilt, zoom, top / 3D), Objekty / Respondenti, Relativní / Absolutní, relation display (5 strongest / selected / all), detail on click. Not: Zajímavé skupiny, A/B comparison, filters, What-if (open, Q57) |
| The Word report | The `-5` figure in the panel's look, as a later chunk (the methodology's `sociomap_3d` renderer already draws it) |
| Numbers inside the map panel (2026-10-20) | Czech decimal comma, at the panel's precision |
| A run storing a `-5` map and the register-approved `-3` (2026-10-20) | The `-5` map is shown |
| Mouse wheel and full screen (2026-10-20, revised the same day) | As the panel embedded in a page: the wheel zooms while the pointer is over the map and the page scrolls elsewhere; ⛶ opens the map in the browser's full screen (the panel's `socioFullscreen66`). Replaces the Ctrl/⌘-only zoom first chosen |
| PNG snapshot of the `-5` map (2026-10-20) | With its legend, in chunk 7; none before |

**How.** The panel's drawing (`color66`, `normalizer66`, `density66`, `projection66`, the terrain triangles, `drawObjects66`,
`relationLine66`, `drawRespondents66`, `segColor66`, `drawAiaOverlay66`, `placeLabels66`) is ported to a TypeScript module of
pure functions that draw on a `CanvasRenderingContext2D` from the stored artifact, plus one React component that owns the
canvas, the camera and the controls. The renderer computes no methodological number: heights, frames, densities and
statuses are the artifact's; only the panel's display transforms (normalisation for colour, ×26 relief, projection) are
applied. Texts are the panel's Czech texts, in `cs.ts`.

**Checks per chunk.** vitest for the pure functions (values from the panel's own functions on fixed inputs); `tsc`, eslint,
the web suite; a visual parity check outside the repository: the panel's functions and the port draw the same stored `-5`
map (from `AIA/repo_port/e2e`) on a Node canvas and the images are compared (no dependency added to the repo); an
independent review; the owner's look at screenshots before each commit.

**Minimal diff.** `-2/-3/-4` code paths untouched; no change outside the map panel's components, its lib modules and
`cs.ts`.

## Open questions

- Making `-5` the study default is outside this plan (register approval; until then an OWNER/ADMIN activates a version
  based on `aia-sociomap-5` in Nastavení → Metodika to see maps on a site).
- Visual check on a running site needs a study with `-5` in force; the Node-canvas comparison covers the drawing before that.

## Doc follow-up

- Where the web's map fixtures are described: `apps/web/src/lib/fixtures/object-map-signed-off.json` holds two stored
  `-5` maps of simulated ratings (one with clear segments and an object nobody rated, one weakly determined), written by
  `make_web_fixture.py` outside the repository from `compute_object_map`; it is read as data and never recomputed by a test
  (BB1 is platform-dependent).

## Findings

- Chunk 2 (the drawing): the port paints every fill, stroke and text of the panel's `draw66` to 4e-15 (colours exact) on four
  stored-map scenes, and the hudba map at 900×700 (opening camera, from above, Absolutní with a selection) is pixel-identical
  to the panel's own functions on a Node canvas. The panel's own Relativní terrain from the stored positions equals the stored
  grid to 7e-16.
- Panel inconsistencies seen while porting (`NPC_Panel/ui_app.html`), drawn as the panel draws them: the slab's edge is
  stroked at width 1 on the first frame and at the triangles' 0.28 afterwards, as `draw66` never resets the line width
  (2098, 2140); the legend's ramp (`.socio66Ramp`, 204) uses other stops than `color66` (2045) and shows 0–1 while
  Relativní colours only 0.15–1; `relationKeyHtml66`'s comment says width 1+3k, its code draws 1+5k (2144); the backend
  rounds `node_scale` to four decimals (`visualization_lab.py:149`), the methodology does not (the same up to 30 objects).

- Chunk 3 (the map's statements): the port of `drawAiaOverlay66`'s object-map part matches the panel's own function op
  for op on six scenes (the stored weakly determined `sum`, and `hudba` with the no-reliable-pair verdict, a sparse design,
  and a synthetic 36-object map whose labels do not all fit) and pixel for pixel at 900×700 on five. In a real browser the
  uncertainty circle sits left of the tool column (the panel's `W − 96 − r`), clear of it. As in the panel, the
  bottom-centre notes can run under the legend on a map narrower than about 1000 px, the circle's caption can cover an
  object's label, and the veil dims the circle under the banner.
- For chunk 4 (review of chunk 3): when the respondent map shares the canvas, the uncertainty circle and the label note
  must be limited to the object map, as the panel's `drawAiaOverlay66` limits them; the banner and the sparse note show on
  both maps. A map without `credibility` can still draw the label note, where the panel skips its whole overlay without a
  layout fit (harmless: every mapped `-5` map stores credibility).
- Decided (methodology owner, 2026-10-20): the list of objects nobody rated reads „Neumístěno (nikdo je nehodnotil,
  proto bez polohy na mapě): …“ — the cause, not the panel's „žádný známý vztah“ (true of them, but its consequence).

## Doc follow-up (chunk 2)

- `apps/web/src/lib/fixtures/object-map-draw-golden.json` holds values returned by the panel's own functions (whole lines
  of `ui_app.html`, listed in its `source` field, run in Node against a stub of the panel state) on the hudba and sum
  maps and synthetic variants of them (no reliable pair, sparse design, 36 objects), for
  `object-map-panel.test.ts`; regenerate it from the panel whenever the panel's drawing changes.
