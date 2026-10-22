---
status: done
chunks:
  - "[x] 1. Fix the web suite's red test: Vzorek's pending ids are in the contract now (taken by #627; fix/sample-pending-ids dropped)"
  - "[x] 2. Remove web code nothing references (#701)"
  - "[x] 3. Remove Python code nothing references (#715, merged as 292dbaf2)"
  - "[x] 4a. Stop exporting values only their own module uses: src/lib, src/research, scripts (#780)"
  - "[x] 4b. The same for src/components and what 4a left, with a standing knip check (make web_unused, in CI)"
  - "[x] 5. Replace the source trees' `# type: ignore` sites with real type fixes, outside the frozen engine and open PRs (#781)"
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

## Chunk 4a. Values only one module uses

These figures are from knip at develop `03989975`.

**What changed.** 48 functions and constants in `src/lib`, `src/research` and `scripts` lost their
`export` (21 files). Each one met three tests:

- knip listed it;
- `git grep -w` over the repository, outside `legacy/`, finds it in no other file;
- its own file still uses it.

Files that the 11 PRs open at the time touch were skipped.

**Types keep their `export`.** The first pass also un-exported 86 types. `/code-review` pointed
out that many of them are named in the signature of an exported function, for example:

- `MapOp` in `readMapOp` (`lib/artifacts/sociomap.ts`)
- `NumberReading` in `readNumber` (`lib/number-input.ts`)
- `ValueWords` in `showValue` (`lib/methodology.ts`)

Hiding such a type would make callers write `ReturnType<…>` or redeclare it. So every type and
interface kept its `export`. `RovingKey` (`lib/roving.ts:5 @ 03989975`) is unused, but it is the
only written list of the roving keys, so it stays too.

**Verification:** `tsc --noEmit` and `eslint src scripts` are clean;
`npm run tokens:check` and `check:design` pass.

## Chunk 4b. The rest of `apps/web`, and a check that keeps it so

These figures are from knip 5.88.1 at develop `9607ee09`.

**What changed in the code.**

- About 50 values lose their `export`: the rest of `src/components`, plus the `src/lib` and
  `src/testing` names 4a skipped because they were named elsewhere (in docs, or in a Python name).
  knip found no import of any of them.
- Five of the files are touched by open PRs. The changed lines were checked against each PR's diff
  hunks, and none overlap.
- Three types used nowhere at all are deleted: `IconName` (`workbench/Icons.tsx`), `QType`
  (`research/questionnaire.ts`) and `RovingKey` (`lib/roving.ts`). Chunk 4a had kept `RovingKey`
  as the only written list of the roving keys. It is dead code all the same, and the key sets in
  `roving.ts` carry the list.

**The standing check.**

- `knip` is pinned exactly in `apps/web`'s devDependencies, with the config in
  `apps/web/knip.jsonc`.
- It runs as `npm run knip` and `make web_unused`, is part of `make check` and `make verify`, and
  is a step in CI's Frontend job.
- A probe export used only in its own file made it exit 1; removing the probe brought it back to 0.
- **The trade-off.** knip's own dependencies now sit inside the blocking npm audit gate
  (`scripts/audit-gate.mjs`, dev and production alike). A high advisory there would stop CI
  until it is allowlisted or bumped, even though knip never ships. On adding it, the gate passed
  with its one standing allowlisted advisory.

**Kept on purpose, each with its reason in the code or the config.**

- **Types used inside their own file keep their `export`** (`ignoreExportsUsedInFile` for types
  and interfaces). Such a type is usually named in an exported signature.
- **`src/design/tokens.ts`** is generated by `scripts/build-tokens.mjs`, so knip ignores it.
- **The `AiaMark` component** (`src/components/brand/AiaMark.tsx`) is rendered by no page
  (`login-handoff.md:89`). Its `export` carries a `@public` tag until the PM decides whether to
  remove it (see Findings). The file's `MARK_POINTS` is imported by `AiaMark.test.tsx`, which pins
  it to `aia-mark.svg`.
- **`postcss`** is a dependency that Next.js supplies; `postcss.config.mjs` names only
  `@tailwindcss/postcss`.
- **`scripts/audit-gate.mjs`** is a knip entry point, because CI runs it.
- **`MaterialEligibility`** carries a `@public` tag, because brief-materials chunk 2 will use it.
- **The `item-ids.ts` names.** Being a port of `domain/item_ids.py` is no reason to export: this
  chunk un-exported other server mirrors (`DESIGN_RESEARCH_KEY`, `TEXT_ONLY_FIELDS`). So
  `OPTION_IDS` and `OBJECT_IDS` lost theirs, and `SIDECAR_KEYS` was deleted, since it was unused
  even in its own file.
- **`rmsDistance`** lost its `export` too. `object-map-boundary.test.ts`'s `body()` helper used to
  find a function only by the text `export function <name>(`. It now finds one with or without
  `export`, and throws if the function is missing. The assertion it serves (a square root only in
  the node size and the RMS distance) is unchanged.

**Verification:**

- `npm run knip`, `tsc --noEmit` and `eslint src scripts` are clean.
- vitest: 3,596 passed.
- `tokens:check`, `check:design`, `audit-gate.mjs` (nothing blocks) and `npm run build` pass.

## Left for later

- **Duplicate helpers.** `clamp01` and `easeOut` in `lib/dot-field.ts` duplicate
  `ObjectMapView.tsx`'s `clamp01` and `lib/object-map-3d.ts`'s `easeOut` (`/code-review`, 4b).
  One shared copy of each would stop the launch animation and the map from drifting apart. This
  predates the chunk.
- **Kept on purpose.** `ProviderEventRow` (`infrastructure/tables.py:378`) has no reader, but its
  table is in the migrations. Removing it needs a migration decision.
- `domain/deep_research/legacy.py:176`'s `except Exception: continue` is the 18.6.6 rule kept
  EXACT, so it is not a finding.
- No `any` and no empty `catch {}` in `apps/web/src` outside tests.

## Chunk 5. The `# type: ignore` sites in the source trees

These figures are from develop `03989975`. The four source trees (`packages/aia_core/src` and
`apps/*/src`) had 25 sites. This chunk replaced 18 of them with a type fix that mypy checks: no
cast, no `Any`, no new runtime behaviour.

- **A predicate that narrows.**
  - `holdout/leakage.py` and `holdout/eligibility.py` replace `_missing` with
    `_present(cell) -> TypeGuard[str]`: the same test, negated.
  - `_number`, `_age`, `ParsedColumns.get` and the donor check read `not _present(...)`.
  - `eligibility.py`'s option check is one loop that collects the answered rows and checks their
    codes.
- **A `None` the code already excluded, now excluded where mypy sees it.**
  - `leakage.py` `association`: the Pearson inputs are built in one pass that stops at the first
    missing number, then the Cramér inputs in another. Both lists come from the same rows, so
    they stay aligned.
  - `holdout/run.py`'s cell key: the parts filtered of `None`, with a length check.
  - `persona_signals.py` `_safe_num`: `None` returns `None` before `float()`. This is the same
    result the `TypeError` gave before.
  - `holdout/scoring.py`: each criterion's detail is built in a plain loop.
  - `charts.py`'s diverging neutral: bound once with `:=`.
- **A narrower type that was always true.**
  - `storage_settings.py`: a `TypeGuard` over `get_args(StorageBackend)`. It is the same check
    that raised before.
  - `methodology/expressions.py`: the series holds `Value`, not `object`.
  - `styles.py`: `_set_face` takes `CharacterStyle`; both callers pass one.
  - `ai_step.py`: `_execution_context` takes `CallJournal`. `StepCallJournal` and `_NoJournal`
    now declare that protocol, so if it grows, mypy errors on the class.
- **`holdout/arms.py`.** The seed check moved inside the `Arm.S` branch that uses it. It still
  raises before any plan is built.
- **`charts.py`'s three `barh` calls.** `_bar_style` returns a `_BarStyle` `TypedDict` instead of
  `dict[str, object]`.

**Left as they are:**

- **`domain/deep_research/settings.py:226, 301, 885 @ 03989975`.** This is Deep Research, which
  CLAUDE.md keeps frozen except for a defect.
- **`infrastructure/report_docx/signed_off_map_figure.py:432, 446 @ 03989975`.** An open PR
  (aia-sociomap-5) touches this file.
- **`domain/research_sociomapping.py:192 @ 03989975`.** Metodika pins
  `battery_sociomapping` by its source's SHA-256 (step `sociomapping/complete_cases` in
  `domain/methodology/sociomapping.py`). A typing-only rewrite would move that pin, and moving a pin
  is the methodology's decision, not a code-health one. The first push tried the rewrite;
  `test_methodology.py::test_every_step_pin_matches_the_function_it_describes` caught it in CI, and
  the rewrite was reverted.
- **`infrastructure/source_reading.py:485 @ 03989975`.** xlrd ships no stubs
  (`pyproject.toml`, `ignore_missing_imports`), so any annotation of the sheet would be `Any`. The
  ignore says more honestly what is unchecked.
- **Ten sites in `tools/`.** These are outside chunk 5's scope, which was the four source trees:
  - `ui_workbench/api_standin.py` (5)
  - `deep_research_capture.py` (2)
  - `caddy_routes.py:126`
  - `somecs_estimation_experiment.py:72`
  - `ui_workbench/unit_standin.py:78`

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

- **CLAUDE.md §3, the commands table.** Add a row: **Unused web code** | `make web_unused`. It
  runs knip over `apps/web`, with the config in `apps/web/knip.jsonc`: no unused file, dependency
  or export. A type used in its own file may stay exported.
- **CLAUDE.md §10.** `make verify`'s sequence now runs `make web_unused` between `make web_design`
  and `make test-web`. Add it to the listed block.
- **ARCHITECTURE.md §8, CI tiers.** The Frontend job runs `npm run knip`, and it is blocking.

- CLAUDE.md §2, `src/components/brand/`: "Wordmark and LatticeField: the identity inline" →
  "Wordmark: the identity inline" (LatticeField is removed in chunk 2).

## Findings

- **Decision needed: remove `AiaMark`?** `apps/web/src/components/brand/AiaMark.tsx` is rendered
  by no page (`login-handoff.md:89 @ 9607ee09`). The only thing holding it is `AiaMark.test.tsx`,
  which pins its geometry to `public/skin/brand/aia-mark.svg`. Removing both is a one-file change
  plus its test. A test names it, so the PM is asked first.

- F1 (chunk 1): the web suite is red on develop at `bfe6d15`. See chunk 1 for the anchor and the
  reproduction.
