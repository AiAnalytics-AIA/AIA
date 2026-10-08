---
status: in-progress
chunks:
  - "[x] 1. Reconcile historical A1 proof with merged develop 09b75227"
  - "[x] 2. Share recorded fixtures and verify native fieldwork, both maps and stored report"
  - "[x] 3. Execute both Deep Research purposes over the same frozen design/result lineage"
  - "[x] 4. Complete refreshed PostgreSQL checks and prepare the publication candidate"
  - "[ ] 5. Verify the merged-base refresh, pass CI, review and integrate; reconcile shared documentation separately"
---
# Connected research assurance (AIA-90)

Owner: Codex. Started: 2026-10-08. Publication base: develop `09b75227`.
Parent: [AIA-90](https://makli.atlassian.net/browse/AIA-90); bounded A1 proof in
[draft PR #195](https://github.com/AiAnalytics-AIA/AIA/pull/195).

Promote the earlier local connected proof into maintained tests. Use the
application's native run creation, real worker/executors, scoped artifacts,
gateway/analysis gates and stored DOCX. Replace only external exchanges with
explicit recorded fixtures; do not use a production fallback or paid call.

Cover insufficient support (analysis/report refused), sufficient support,
canonical v1/v2 method pins and map payloads, internal DRAFT_UNAPPROVED report
dependencies and read-back. Design Research seals evidence on the same design
revision; Interpretation Research executes over its real stored map and OBJECTS
analysis module, pins exact lineage and leaves original artifacts unchanged.
Do not manufacture a report dependency on Deep Research before that integration
exists. Replay/idle execution sends no duplicate fieldwork/analysis calls.

Share recorded helpers through the executor conftest fixture, not an import
from one test module to another. Keep unrelated earlier local files intact.
The two jsdom download assertions must read the existing arrayBuffer polyfill
and still compare exact downloaded bytes.

Record test names, source base, results and environment below. These are
fictional/offline component integration proofs, not AIA-78 live acceptance or
AIA-40's browser/staging/all-four-area release gate.

## Measured evidence, 2026-10-08

Historical verification base: develop `4d8f07d934e88a9d15b9da47c78c42a1b01ca019`.
The results below refer to that earlier candidate. The publication candidate is
refreshed below; AIA-90 remains In Progress until review and integration.

`test_native_ai_study_connects_a_populated_map_to_admitted_report_inputs` has
three cases: insufficient support, an internal report, and Deep Research plus an
internal report. The latter executes Design Research and Interpretation Research
against both the actual stored Sociomap and OBJECTS module. Exact design/artifact
hashes remain pinned, the original evidence bundle and report remain unchanged,
and an idle worker dispatches nothing further.

- Connected analysis and original Deep Research journey suites: 63 passed on SQLite.
- The three connected cases: all passed on PostgreSQL 16 with
  `AIA_REQUIRE_POSTGRES=1`.
- Every executor regression, including process recovery and the shared helper's
  existing consumers: 327 passed on PostgreSQL.
- Shared exchanges now live in `deep_research_fixtures.py`; existing consumers
  import those exchanges directly. The new connected test receives them through
  conftest. No new cross-test import or production fallback was introduced.
- Web lint and the production build pass with Node 24.19 and existing lockfile
  dependencies. A local dependency copy resolves Turbopack's refusal of an
  external node_modules symlink; application configuration is unchanged.

- Complete `make verify` passes: Python source types, web types, layering,
  reference exposure, formatting, design checks, 6,052 Python passes with 114
  conditional skips, and 639 web passes across 40 files. Python/web lint pass.
- After adding JUnit identity/seal properties, the affected 63 tests pass again
  on SQLite and the three connected cases pass again on PostgreSQL. The XML
  contains the actual research/design/interpretation run IDs, artifact IDs,
  report hash, bundle seals and frozen interpretation lineage.
- The same three cases pass with AIA-88's revised core/API and this branch's
  executor/test code together on PostgreSQL.

The review package is prepared locally. Tests use recorded web
snapshots, scripted model responses, an in-memory artifact store and fictional
study material. They do not exercise live providers, object storage, Cognito,
staging, browser journeys, Simulation Studio, the knowledge intake lifecycle or
Project Memory. The report is synthetic and DRAFT_UNAPPROVED. Deep Research
bundles are review-only and are not report dependencies in the current code.

## Publication refresh, 2026-10-08

Current merged develop is `9edc30b999629bc8894ef8ffa9c94ad1985c46b3`,
including PR #196. PRs #197/#198 are still open drafts with green CI. Their
production files do not overlap this test change. The shared ladder-test import
change merges cleanly with their additions; all added assertions are preserved.

A separate compatibility candidate at #198's
`a90d81021ef6745b5d6e1c4fb96d546f4ea0c475` plus AIA-88/AIA-90 passed
340 executor, 355 API and 84 focused core tests on SQLite. The updated combination
then passed all 342 executor tests and all 12 knowledge revision tests on
PostgreSQL, with no skips, including the five contention/process cases.
Full `make verify` on current develop passes on PostgreSQL: 5,349 core,
352 API, 62 worker and 340 executor tests (6,103 passes total), with 77
reference-dependent core skips and no process/concurrency skips. All 639 web
tests, Python/web types, 101 layering rules, seven exposure rules, formatting
and design checks pass. Python/web lint pass.

Publish AIA-90 first, then verify AIA-88 on this base. CI, human review,
integration and the shared docs-only reconciliation remain outstanding. No
reference skip is reported as a successful comparison.

## Merged-base follow-up

Draft [PR #200](https://github.com/AiAnalytics-AIA/AIA/pull/200) is published.
During publication, PRs #195, #197 and #198 merged. The branch is now refreshed
onto `09b75227b9d204c7381519267bb6225b117971ce`; the historical 9edc30b9
counts above remain labelled with their original base. The earlier #198
combination already passed all 342 executor and 12 knowledge tests on PostgreSQL.
The complete PostgreSQL pre-commit sequence and GitHub CI are being repeated
on the refreshed publication candidate. The knowledge fix is stacked on this
PR and must follow it in the merge order.
