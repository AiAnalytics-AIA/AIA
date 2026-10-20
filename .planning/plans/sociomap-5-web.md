---
status: in-progress
chunks:
  - "[x] 0. This plan"
  - "[x] 1. Read -5 maps in the web: the stored fields typed, pure readers for the panel renderer, a stored -5 fixture; nothing drawn changes"
  - "[ ] 2. The object map as the AIA panel draws it: terrain, colour ramp, relief, frame, nodes, labels, relation lines, legend, camera; a -5 map read first and routed to it"
  - "[ ] 3. Map credibility on the map: the weakly-determined banner, the uncertainty circle, the sparse and label notes, objects not placed"
  - "[ ] 4. The respondent map: Objekty | Respondenti, dots, faint dots, the density terrain, object markers, the notes below six and three objects"
  - "[ ] 5. Taste segments on the respondent map: colours, legend, borderline hint"
  - "[ ] 6. Detail on click: an object's and a respondent's detail, in the panel's content"
  - "[ ] 7. The Word report's -5 map figure in the panel's look"
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

None yet.
