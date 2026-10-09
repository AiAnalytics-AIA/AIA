---
status: in-progress
chunks:
  - "[x] 1. Frozen-grid 3D rendering geometry and integrity tests"
  - "[x] 2. Production map workspace, controls and grounded interpretation"
  - "[x] 3. Report introduction and paragraph structure"
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

Workspace acceptance: 29 focused web tests pass, web lint and TypeScript pass.
Browser verified actual library artifact: rotate buttons, arrow key, pointer drag,
selection (Filmový večer = 5.80), six gated signed relationships, top/3D switching,
360px iframe layout and theme palette. Canvas carries 2,437 triangles.
Geometry preparation 5.57ms; 100-frame projection/sort median 0.56ms, p95 1.59ms
on this machine (does not include raster drawing). No AI calls or infrastructure
charges. 3D is user-activated, off by default including tests; switching to top
view unmounts its renderer immediately. This is the rendering kill switch.

React review: expensive mesh memoized; no new dependencies or data requests;
SVG object controls and DOM selectors accessible; observer cleanup present;
responsive label density limits overlap without moving stored object positions.

Report acceptance: 37 focused tests pass; the internal document now begins with
study/client context, a reading guide, frozen research questions and the synthetic
interpretation boundary. Admitted summary paragraphs remain separate lede/body
blocks without another model call or evidence rewrite. Contract is bumped to
`aia-internal-report-2`; stored old reports remain frozen. The generated fixture
DOCX passes structural lint; rendered introduction and adjacent pages inspected.
Map inclusion in the main DOCX remains outside this change and its internal gate
is preserved.

Production build finding: Next.js rejects arbitrary value exports from route
modules. Move the unchanged public config type, switches and parsers into
`lib/public-config.ts`, import them in `/config` and its consumers. Preserve
cross-language worker vocabulary and Compose coverage assertions at the new
source location. Document this wrong/right boundary in AGENTS.md after merge.

Local full verification: typecheck (310 Python sources and web), 101 layer rules,
7 exposure rules and formatting pass. Core suite: 5,486 passed, 104 expected
environment/reference skips, one strict frozen-fixture failure. The unchanged
builder/domain/fixture differ on this Mac by 147 floating-point roundings, at most
7.11e-15 (and the resulting fingerprint), with both Python 3.12 and 3.14. Do not
regenerate the fixture or loosen the byte assertion. Require the official Linux
CI fixture test and every blocking gate to pass before merge. API: 355 passed;
worker: 54 passed, 8 PostgreSQL-only skips. Executor rerun and remaining web
checks follow the config source relocation. Webpack production build passes.
