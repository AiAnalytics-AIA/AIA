---
status: in-progress
chunks:
  - "[ ] 1. Plan, terrace tokens and design evidence: a ten-step terrace ramp, stage, ground and link tokens; adjacent-band ΔE, CVD and label-contrast checks"
  - "[ ] 2. View logic over the frozen artifact: absolute ten-band display quantization, terrace edges, ranked list, pair detail (UNKNOWN-with-r apart from undefined r), screen-space label placement"
  - "[ ] 3. Terraced 3D geometry: display elevation by band, stored height kept on every vertex, relief and the entrance rise as presentation only, measured view size"
  - "[ ] 4. The redesigned workspace: dark stage, HUD, toolbar (3D / Shora / Otáčet / Jen názvy / Vztahy / Přehrát animaci), labels that avoid each other and the panels, selected-object, pair and ranked cards, legend, Czech copy"
  - "[ ] 5. Boundary tests, full checks, browser comparison against the prototype (top, 3D, pair card, labels-only, relations off, 360 px, both themes), PR"
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

(kept current as chunks land)

## Findings

(none yet)

## Doc follow-up

(collected for the docs PR; this feature PR edits no shared document)
