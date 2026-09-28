---
status: done
chunks:
  - "[x] 1. Parity matrix JSON for all 78 capabilities + consistency tests"
  - "[x] 2. Golden-fixture harness: pinned fetch, integrity checks"
  - "[x] 3. tools/parity_status.py"
  - "[x] 4. CI wiring: JUnit everywhere, golden-fixtures and parity-status jobs"
  - "[x] 5. MVP acceptance test definition"
  - "[x] 6. Own REF-GAP-SOCIO-R-SMACOF and REF-GAP-SIMULATION-WORLD-MODEL"
  - "[x] 7. Parity-status section naming the highest-risk capability"
---
# Production parity matrix and parity gates

**Status:** done — merged in PR #25 @ `a15be65` (2026-09-23); the `golden-fixtures` and `parity-status` jobs run in CI. Archived 2026-09-27. · **Owner:** parity-quality · **Started:** 2026-09-22

## Problem

The rebuild has no single place that says, for each of the reference's 78
capabilities, what production has built, what parity it owes, what evidence
exists and whether that evidence was actually executed.

- `docs/migration/parity-matrix.md` is keyed by legacy *module*, not by the 78
  stable capability ids the reference classifies
  (`AiAnalytics-AIA/AIA-reference` `parity-plan.json` @ 678e298). A capability
  with no row is invisible.
- CI cannot tell *not executed* from *passed*. The parity job ends in `|| true`
  and all 94 reference tests skip, so a green run carries no parity signal
  (OI-1, `.github/workflows/ci.yml:129-131 @ df294e2`).
- The 11 golden fixtures committed to the reference repository need **no raw
  archive** — each is one self-contained JSON with input and expected output —
  yet nothing in this repository reads them.
- Nobody has defined what "the MVP works" means end to end.

## Approach

1. **The matrix is data, not prose.** `docs/migration/parity-matrix.json`, one
   entry per capability id, carrying owner, implementation state, parity type,
   tolerance, fixtures, declared gates, recorded evidence, intentional
   difference, high-risk ids and release-blocker status. The markdown table is
   *rendered* from it and a test fails when the two drift.
2. **Verdicts are computed, never typed.** `tools/parity_status.py` reads the
   matrix plus pytest JUnit XML and derives one verdict per capability:
   `PASS`, `FAIL`, `NOT_EXECUTED` (a gate exists but did not run here),
   `NOT_RUNNABLE` (no gate exists that could establish parity) or
   `NOT_REQUIRED`. A skipped test is `NOT_EXECUTED`, never `PASS`.
3. **Golden fixtures are fetched, not vendored.** CI checks out the private
   reference repository at a pinned commit with a read-only deploy key and
   verifies every fixture's SHA256 against a pin committed here. The fixtures
   themselves never enter this repository (exposure policy, D5), and the raw
   archive is not needed at all.
4. **Gates ratchet in as capabilities land.** A fixture is either `GATED` (a
   registered production gate in `test_golden_fixtures.py`) or
   `AWAITING_IMPLEMENTATION`. A test fails when a capability claims an
   implementation while one of its fixtures is still ungated — so a port cannot
   land without its parity gate.
5. **The MVP acceptance test is defined now**, in
   `docs/migration/mvp-acceptance.md` and as machine-readable criteria in the
   matrix, so every cycle can say which capabilities still stand between the
   stack and a delivered study.

### Rejected

- **Vendoring the fixtures.** Simplest wiring, but it is detailed reference
  material in this repository, two fixture filenames already trip
  `exposure_check` rule 2c, and it would fork the fixtures from their authority.
- **Making the raw archive a CI dependency.** Explicitly out of bounds; it is
  withheld pending a licence decision and must satisfy EU residency.
- **Failing CI when the reference repository is unreachable.** Every PR would
  go red until a human provisions a deploy key. Instead absence is reported as
  `NOT_EXECUTED`, and a repository variable (`AIA_REQUIRE_REFERENCE_REPO=1`)
  turns absence into failure once the key exists — the same ratchet as
  `AIA_REQUIRE_POSTGRES`.
- **Counting production-only tests as parity for EXACT/NUMERICAL/SEMANTIC.**
  A production test proves self-consistency, not equivalence with the
  reference. Those types need at least one reference-backed gate to `PASS`.
  `INTENTIONAL_DIFFERENCE` is the exception: its criterion *is* a production
  test proving the new behaviour.

## Trade-off accepted

Until a human provisions the deploy key, CI reports golden fixtures as
`NOT_EXECUTED` rather than blocking on them — honest but not yet enforcing.

## Chunks

- [x] 1. Parity matrix JSON for all 78 capabilities + consistency tests (runs
      with no reference) — lands: `docs/migration/parity-matrix.json`,
      `packages/aia_core/tests/test_parity_matrix.py`. **The MVP acceptance
      definition moved into this chunk** (from 5): the release-blocker rule is
      "named by an acceptance criterion", so the criteria had to exist first.
- [x] 2. Golden-fixture harness: pinned fetch location, integrity checks,
      gate registry, first gate (F9 against `domain.sociomap.view`) — lands:
      `packages/aia_core/tests/test_golden_fixtures.py`, conftest fixture,
      `golden` marker
- [x] 3. `tools/parity_status.py`: verdicts from JUnit, highest-risk ranking,
      rendered markdown; `parity-matrix.md` regenerated section + sync test
- [x] 4. CI wiring: JUnit from every pytest step, `golden-fixtures` job,
      `parity-status` job with step summary; drop `|| true`; tiers in
      `ARCHITECTURE.md §8`; commands in `CLAUDE.md` / Makefile
- [x] 5. MVP acceptance test definition — landed with chunk 1
- [x] 6. Own `REF-GAP-SOCIO-R-SMACOF` (with A8) and
      `REF-GAP-SIMULATION-WORLD-MODEL` (with A7): F12/F13 slots in the matrix,
      register entries with blockers and definition of done
- [x] 7. `PROGRESS.md` parity-status section naming the highest-risk
      unverified capability; findings into `open-items.md`

## Found while doing it

- **Two rootdirs, one test.** Running the CI sequence against real PostgreSQL
  turned two gates red: the concurrency step reports `tests/test_x.py`
  (package rootdir), the SQLite step `packages/aia_core/tests/test_x.py` (root
  rootdir), and the tool judged the pass and the skip as two tests. Outcomes are
  now merged per test after path matching —
  `test_parity_status_tool.py::test_one_test_under_two_rootdirs_is_merged_before_it_is_judged`.
  The unit tests alone had not caught it; the end-to-end run did.
- **pytest reads the nearest `pyproject.toml`.** The `golden` marker registered
  only at the root failed collection for `pytest packages/aia_core`. Recorded in
  `AGENTS.md`.
- **The reference gap records understate their blockers.** Both F12 and F13
  recipes execute legacy code that exists only in the withheld archive (OI-15,
  OI-27).
- **A reference mis-link** — F11 listed under `cost.reservations` (OI-28,
  `REF-DISC-1`).

## Merge with `main` @ 8978b99

`main` landed the Sociomap engine, population readiness and the worker while this
branch was open. What changed here as a result:

- **F1–F9 are vendored on `main`** (`packages/aia_core/tests/fixtures/sociomap/`,
  hash-pinned). That supersedes this plan's "fetched, never copied" for those
  nine, and it was the better call for them: they then run in every backend job.
  The matrix now records each fixture's `source`; `test_golden_fixtures.py`
  checks that each vendored copy is byte-identical to the reference, and
  `test_parity_matrix.py` checks each copy against its pin without a checkout.
  My own F9 gate was dropped in favour of the engine's.
- **Two gate shapes were added**: `reference_contract` (comparison with a
  committed reference contract or ledger) and the `PARTIALLY_GATED` fixture
  state (F8). Fixtures name their gate (`gate.gate_id`) instead of a registry.
- **Fifteen capabilities changed state** (Sociomap core and study module, four
  population capabilities, product policy, integrity, four workflow and
  orchestration capabilities); the `IMPLEMENTED` ceiling is the stale module
  inventory (OI-30).
- **Numbering collisions resolved**: my SMACOF entry folded into OI-15; the other
  findings renumbered OI-27 to OI-29; the Simulation-scope decision is D9; the
  two fixtures named F12 are OI-31 (a second merge of `main` took OI-24 to
  OI-26 and D7/D8 first).
- **Ranking tightened**: a capability whose gates pass but whose port is
  unfinished ranks below one with no passing evidence.

## Review outcome

Filled in when the plan is archived.
