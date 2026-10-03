---
status: in-progress
chunks:
  - "[x] Version and test native respondent and object workspace calculations"
  - "[x] Store workspace fields in research artifacts with a deployment switch"
  - "[x] Render two interactive 3D views in research results and verify the journey"
---
# Native Sociomapping workspace

User-authorized implementation of the inspected 18.6.6 reference. Base:
2224f5b. `ExecutionSteps.tsx:SociomapView` currently shows a coordinate table.
The first integrated delivery provides respondent density and object relationship
landscapes, metric selection, rotation/zoom, and inspectable input rows. Existing
artifacts remain readable and explain when a new run is needed.

Calculation contract: native reference-circle barycentres and mutual-strength
object relaxation, separately named from current unfolding. Port pure math, not
the legacy application. Reuse the tested server terrain calculation. Unknown
correlations block object geometry rather than becoming neutral relationships.
Only the native 1–10 scale is supported. Record weights policy and source hash.
Keep D6 internal-only and synthetic labels; no claim of proprietary equivalence.

All study data travels through the existing scoped artifact route. No AI calls,
browser calculation of analytical values, legacy service dependency, or mutation
of stored data. Broader segment/scenario/time-series workflows and report maps
remain subsequent increments in the restoration roadmap.

## Validation

The native fixture captures eleven fictional respondents and four objects from
`visualization_lab.py`, pins that source's SHA256 and checks coordinates, metrics,
pair counts and deterministic replay. Missing, constant and low-support pairs
preserve missingness; unsupported scales and oversized inputs are explicit.
The worker tests exercise the real five-step run with the switch both off/on,
including artifact dependencies, internal-only status and synthetic provenance.

A local browser journey completed a 450-respondent, four-object fictional study
through the real API, worker, store and Results page. Verified respondent rows,
object pair counts, both map modes, metric selection, top view and rotation.
Metric switching preserved horizontal coordinates; only terrain and glyph heights
changed. No console warnings/errors were captured and no provider calls were made.

Measured pure workspace computation on this laptop (single synthetic run each):
450 × 4: 0.137 s, 429,148 JSON bytes; configured maximum 2,000 × 32: 0.963 s,
936,255 bytes. This is local timing, not a production latency guarantee.

Web lint and the production build (`npm run build -- --webpack`) pass. Turbopack
could not bind its build helper's loopback socket in this local environment.
`make verify` passed: 3,292 core, 300 API, 50 worker, 151 executor and
541 web tests. PostgreSQL concurrency and unavailable external reference suites
were explicitly skipped (108 total); the captured native geometry fixture ran.
Strict typing, layering, formatting, design checks, Python and web lint passed.

Validation found pre-existing Next.js route exports rejected by the production
build. Move the public configuration helpers/types to `lib/public-config.ts`;
the route now exports only supported route values. Preserve its behavior and
update the cross-language vocabulary tests to read the helper's new location.
Download assertions read actual bytes through Blob.text when supported (Node
fetch) or FileReader for jsdom Blobs. Both Blob implementations have explicit
coverage; the existing expected-content assertions are preserved.

## Delivery and remaining scope

Prepared on `feature/sociomap-workspace` from `develop` at `2224f5b`.
Prepared for a PR into develop; deployment follows review and merge. Develop Compose enables this
workspace after deployment; `AIA_SOCIOMAP_WORKSPACE_ENABLED=false` disables future
calculation. Other compositions default off. Stored maps remain readable.
Older completed runs are immutable and are not backfilled: a new design revision
and run is needed. This increment introduces no additional fieldwork reruns.

Segment/scenario controls, time-series alignment, report inclusion and the
multi-source Deep Research-to-evidence adapter remain later increments. D6 is
still internal-only. This delivery ports the inspected native workspace behavior;
it does not assert validation of proprietary Sociomapping methodology.

## Doc follow-up

Add `sociomap/workspace.py` to the domain map: versioned native workspace
geometry and server terrain fields, appended to research Sociomap artifacts.
Add `SociomapWorkspace.tsx` to the research UI map. Document the worker's
`AIA_SOCIOMAP_WORKSPACE_ENABLED` switch, default off outside develop, on in the
develop Compose configuration. Existing unfolding and D6 remain unchanged.
