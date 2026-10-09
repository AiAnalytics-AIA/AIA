---
status: in-progress
chunks:
  - "[x] 1. Frozen-grid 3D rendering geometry and integrity tests"
  - "[ ] 2. Production map workspace, controls and grounded interpretation"
  - "[ ] 3. Report introduction and paragraph structure"
  - "[ ] 4. Full checks, visual verification, publication and live acceptance"
---

# Object map 3D workspace

User requested implementation of the map and report improvements, especially 3D.
Acceptance reference: RUN-1725024c5b8b480a, corrected contract-3 map fingerprint
6813425a17609b92511a60da883ca49d0d62a0f3136fe01159075d9ad06d4264.

## Boundaries

Render only the frozen backend layout and envelope grid; no browser kernel,
correlation, layout or uncertainty calculation. Unknown terrain remains absent.
Camera and vertical display scaling are presentation only. Preserve the top view
as the immediate rollback and distance-reading view. No new runtime dependency,
paid AI call, research run or alteration of frozen artifacts.

Deliver a large rotatable terrain, zoom/reset, keyboard controls, expanded view,
readable object selection, original rating scale when declared, and explicit
height/distance/fit explanations. Keep synthetic and provisional method labels.
Improve the deterministic report introduction and preserve author paragraphs;
do not fabricate study background or reinterpret admitted claims.

## Verification

Geometry tests cover stored heights, holes, rotations and display bounds;
component tests cover mode, object selection, reset and keyboard controls.
Report tests retain all admission gates and verify readable structure. Measure
render preparation on the stored 65x65 grid. Run make verify and web lint/build.
Use browser visual verification and the existing completed run after deployment.

## Layer review

- Domain/infrastructure: no map mathematics or storage changes.
- Application: report composition only; internal status and evidence gates intact.
- Executor: report contract bump for changed deterministic output.
- Transport: unchanged artifact route and scope.
- Presentation: camera/mesh geometry and accessible map controls.

## Doc follow-up

Describe the corrected contract-3 terrain workspace and its presentation-only
camera controls in the architecture sociomapping/research journey documentation,
and the internal report introduction/paragraph preservation in analysis docs.
Shared documentation stays out of this feature PR.

Geometry acceptance: 5 tests pass; TypeScript and all 101 layer rules pass.
The grid resolution denotes intervals (64), with 65 stored samples per axis.
