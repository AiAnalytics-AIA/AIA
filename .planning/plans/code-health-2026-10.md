---
status: in-progress
chunks:
  - "[x] 1. Fix the web suite's red test: Vzorek's pending ids are in the contract now (taken by #627; fix/sample-pending-ids dropped)"
  - "[x] 2. Remove web code nothing references (#701)"
  - "[x] 3. Remove Python code nothing references (#715, merged as 292dbaf2)"
  - "[ ] 4. Stop exporting what only its own module uses (knip's list below)"
  - "[ ] 5. Review the remaining `# type: ignore` sites (list below)"
---
# Code health, October 2026

An audit of develop at `bfe6d15` for bloat, dead code and anti-patterns (ARCHITECTURE.md §6),
with no change in behaviour. Each chunk is one small PR, cut from a fresh `origin/develop`.

## How it was found

- Python: `vulture --min-confidence 60` over the four source trees, then each name counted
  across the whole repository (tests, tools, docs and ledgers included). A name kept only when
  nothing but its own definition mentions it.
- Web: `npx knip@5` in `apps/web`, then the same count across `src`, `scripts` and `tests`.

## Chunk 1. The red web test

`apps/web/src/lib/artifacts/sample.test.ts:42 @ bfe6d15` asserts that `sample:ready`,
`sample:respondents` and `sample:respondents:fictional_roster` are *not* in the lead-artifact
contract yet. `90964e8` added them to `packages/aia_core/tests/fixtures/lead_artifacts/contract.json`,
so the test fails on develop.
Reproduce it with `cd apps/web && npx vitest run src/lib/artifacts/sample.test.ts`.
The fix retires the pending set and holds every id to the grammar alone.

## Chunk 2. Web dead code (no reference anywhere)

- `src/components/brand/LatticeField.tsx`: the whole component. CLAUDE.md's map names it, so it
  needs a Doc follow-up (below).
- `reportStatusTone` and its `TONE` map: `src/lib/report-status.ts:41-52 @ bfe6d15`.
- `catalogues()`: `src/research/audience.ts:129 @ bfe6d15`. It read the 18.6.6 bootstrap,
  which `liveSubpanels` replaced.
- `UPLOAD_TIMEOUT_MS`: `src/research/audience.ts:218 @ bfe6d15`.
- `activeDimensions()` and `REQUEST_TIMEOUT_MS`: `src/research/persona.ts:44,264 @ bfe6d15`.
- `researchCount()`: `src/research/questionnaire.ts:476 @ bfe6d15`.
- `screenScale()`: `src/lib/object-map-view.ts:282 @ bfe6d15`.
- `LEAD_EDIT_REASON`: `src/lib/lead.ts:15 @ bfe6d15`.

## Chunk 3. Python dead code (no reference anywhere)

- `ProductionAuthGateMiddleware`: `apps/api/src/aia_api/observability.py:139 @ bfe6d15`. It is
  never added to the app. `Settings.validate_for_production` refuses header identity outside
  local and test, so the guard it describes holds without it.
- `ResolvedAccess`: `packages/aia_core/src/aia_core/domain/scope.py:923 @ bfe6d15`. It is a
  leftover of the grant lookup ADR 0019 removed.
- `begin_field` / `end_field`: `packages/aia_core/src/aia_core/infrastructure/report_docx/ooxml.py:139,152 @ bfe6d15`.

**Verification (chunk 3):**

- `mypy --strict` is clean over 459 files, and `layer_check`'s 188 rules pass.
- The four Python suites were run through 94% of 10,106 tests before the session's time limit.
  One test failed: `test_report_document_model.py::test_the_web_reads_the_document_model_this_writes`.
  It fails on unchanged develop too, and #628 fixes it.
- The report DOCX, scope and API observability tests pass: 111 passed.
- The files of the last 6% were then run on their own: 746 passed, 2 skipped. The skipped tests
  need PostgreSQL, which this session did not have.

## Left for later

- **Chunk 4.** Knip lists about 70 exports that only their own module uses (for example
  `ControlPanel.tsx`'s `TABS`, `SettingRow` and `loadPanel`, and `object-map-panel.ts`'s geometry
  helpers). Dropping `export` changes nothing at runtime. It touches many files that open PRs are
  editing, so it waits for a quiet window.
- **Kept on purpose.** `SIDECAR_KEYS` in `src/research/item-ids.ts` is unused on the web, but the
  file is the port of `domain/item_ids.py`, which uses it.
- **Kept on purpose.** `ProviderEventRow` (`infrastructure/tables.py:378`) has no reader, but its
  table is in the migrations. Removing it needs a migration decision.
- **Chunk 5.** Twelve `# type: ignore` sites remain:
  - `domain/holdout/leakage.py` 105, 178, 207, 208
  - `domain/deep_research/settings.py` 226, 301, 885
  - `report_docx/charts.py` (4)
  - `signed_off_map_figure.py` (2)
  - `persona_signals.py:217`, `research_sociomapping.py:192`, `storage_settings.py:80`

  Each wants a narrowing helper instead of the ignore. These are hypotheses until a typed
  version passes `make typecheck`.
- `domain/deep_research/legacy.py:176`'s `except Exception: continue` is the 18.6.6 rule kept
  EXACT, so it is not a finding.
- No `any` and no empty `catch {}` in `apps/web/src` outside tests.

## The A4 sweep (`or 0` / `.get(…, 0)`)

ARCHITECTURE.md §6 A4's grep, run over the four source trees. Most hits are an SQL `SUM` or
`MAX` over no rows, where 0 is the true answer. Two hits need a closer look:

- **Hypothesis, A5.** `application/web_retrieval.py:1314 @ bfe6d15` records
  `charged_credits=scanned or 0` when Athena did not report the bytes it scanned. The cost is
  right: `scan_cost_usd(None)` charges the route's ceiling (`:280`), and the note says
  "unknown". But the ledger's credits column reads 0 for "unknown". The smallest fix is to let
  `charged_credits` be `int | None` through `_event` (`:592`). Check the meter's column first.
- **Low.** `infrastructure/report_docx/object_map_figure.py:76,78 @ bfe6d15` plots an object
  with no height at height 0 in the 3D snapshot. Its colour is already the muted "unknown"
  colour, so a reader can tell it apart. Leaving the point out, or marking it, would be more
  honest.
- **Not a finding.** `application/model_gateway.py:756` prices unreported cache tokens at 0.
  Its comment explains why: the adapters charge every unattributed token at the full input
  rate.

## Doc follow-up

- CLAUDE.md §2, `src/components/brand/`: "Wordmark and LatticeField: the identity inline" →
  "Wordmark: the identity inline" (LatticeField is removed in chunk 2).

## Findings

- F1 (chunk 1): the web suite is red on develop at `bfe6d15`. See chunk 1 for the anchor and the
  reproduction.
