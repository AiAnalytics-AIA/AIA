---
status: done
chunks:
  - "[x] 1. Domain: identity, DatasetVersion, Population, lineage"
  - "[x] 2. Domain: import contract, validation, derived fields"
  - "[x] 3. Infrastructure: parser, asset source, registry"
  - "[x] 4. Application: PopulationRuntime"
  - "[x] 5. Parity against AIA-reference; merged PR #12 at 8da7261"
---
# Population version + import foundation

**Status:** done — merged to `main` in PR #12 (`8da7261`) · **Owner:** population-data · **Started:** 2026-09-22

## Problem

The Czech synthetic population (18,766 × 400, three versions) is a core runtime
dependency: without a valid version no respondent generation, questionnaire,
sampling, aggregation, simulation or Sociomapping can run. The reference resolves
"which population is in use" in four places (R4), swallows a registry failure and
an enrichment failure (R1, R2), silently falls back to the Census 2021 weight or to
no weight at all (R3, fixture F11), and exposes two loaders that return different
populations from the same bytes (F10). Nothing in this repository models a
population version yet.

Authoritative inputs, all in `AiAnalytics-AIA/AIA-reference` @ `678e298`:
`population-subsystem.md`, `data-import-contracts/czech-population.md`,
`field-policy.json`, `methodology-ledger.md` (M01, M04), `high-risk-behaviors.md`
(R1–R4, R8, R9), `golden-fixtures/F10_*`, `F11_*`.

## Approach

One bounded context, `population`, split across the layers exactly as the rest of
the codebase is:

- **Domain** (`aia_core/domain/population/`) — pure. Content-addressed
  `DatasetVersion`; `Population` roles (`STATIC` / `LIVE`); lineage and promotion
  rules; the import contract and its validation; the 8 derived runtime fields;
  weight-scheme resolution with no fallback; `PopulationBinding` (the resolved
  version + weight identity a run records); `RuntimePopulation`, constructible only
  by the canonical loader (module-private sentinel, as for `StudyContext`).
- **Infrastructure** — a text-preserving panel parser (stdlib `gzip`/`csv`, no type
  inference at all, so `occupation_isco08` cannot lose its leading zeros); a
  `PopulationAssetSource` protocol (filesystem + memory now; the EU object store
  later, behind the same seam); the registry repository and its tables; the
  run-binding table written by `WorkflowRepository.create_run`.
- **Application** (`application/population.py`) — `PopulationRuntime`, the single
  entry point: import (never promotes), establish, explicit promote, resolve, load.
  Nothing else may issue a `RuntimePopulation`; `layer_check` enforces it.

**The 400-field schema is pinned by hash, not copied.** The exposure guard keeps
detailed reference material out of this repository, and the field dictionary is
exactly that. The contract pins `FIELD_DICTIONARY_v17_1.csv` by SHA256 and the
ordered field names by a fingerprint (`sha256("\n".join(names))`). The dictionary
travels with the panel in the import bundle; import checks its hash, its count, its
fingerprint and that the panel header equals it in order. Unit tests build
synthetic bundles through the same code; the parity tier checks the pinned values
against `field-policy.json` in the reference repository and runs the real 400 names
through validation.

**Rejected:** committing the 400 names (or `field-policy.json`) here — exposure
rules 2b/2c and D5's "detail stays in AIA-reference". Adding pandas/pyarrow now —
a columnar backend is a separate decision; the lossless representation of a CSV is
text, and typed views are explicit transformations on top of it.

## Decisions taken in this plan

| Decision | Why |
|---|---|
| Version id is derived from content: `cz_synthetic_population@sha256:<16 hex>`, full SHA256 unique | Same bytes → same id; import is idempotent; a label can never be re-pointed |
| A label is bound to exactly one hash, and a hash to one label | `v17_0_BASE`, `v17_1_2`, `v17_4_0` stay distinct; no collapsing |
| Known versions carry their parent in the contract; the caller cannot supply another | Lineage for the preserved versions is fact, not input |
| `STATIC` is established once, only with the contract's declared static label, and has no promote path | "No mutation of the static reference" is structural |
| `LIVE` promotion is explicit, compare-and-set on the expected current version, recorded append-only; target must descend from the static reference and must not be it | Explicit promotion only; lineage always recoverable |
| A version never bound to a population (`v17_0_BASE`) cannot be resolved for a run | Build input only |
| Weights: no default, no fallback; unknown role, missing column, null, non-finite or negative value all fail | R3 / F11 — intentional difference from the reference, which clips and fills |
| Enrichment is an injected protocol; the `ANALYSIS` view without one fails closed | R1 — the 7 derivations are not recovered from the withheld archive |
| Null = empty CSV cell, preserved as `None`; no NA-token interpretation on import | Import rule "preserve nulls as nulls, do not fill" |
| Run binding is immutable, one per run; a step that loads population data gets it only from the run | One authority; no mid-run substitution |

## Trade-off accepted

The loader holds the panel as Python strings (~7.5 M cells) rather than a columnar
frame, buying zero new dependencies and exact losslessness at the cost of memory
and speed that the research engine will need a typed columnar view to recover.

## Chunks

- [x] 1. Domain: identity, `DatasetVersion`, `Population`, lineage, establish /
  promote rules, errors — `domain/population/{versions,errors}.py` ·
  `tests/test_population_versions.py`
- [x] 2. Domain: import contract, validation over a parsed table, derived fields,
  weight resolution, `PopulationBinding`, `RuntimePopulation`, `CZ_SYNTHETIC_V17`
  — `domain/population/{contract,czech,table,validation,weights,binding,runtime}.py`
  · `tests/test_population_contract.py`
- [x] 3. Infrastructure: parser, asset source, registry tables + repository,
  run-binding table, migration `1068fd22455d` — `infrastructure/population_*.py`,
  `tables.py`, `workflow_repository.py` · `tests/test_population_infrastructure.py`,
  `tests/test_workflow_concurrency.py::test_concurrent_live_promotions_have_exactly_one_winner`
- [x] 4. Application: `PopulationRuntime`, `StepDefinition.consumes_population`,
  `create_run(population=…)`, four `layer_check` rules — `application/population.py`
  · `tests/test_population_runtime.py`
- [x] 5. Parity against AIA-reference (field policy, dataset ledger, F10, F11) and
  the docs — `tests/test_population_reference_parity.py` (18, `parity`-marked)

## Review outcome

**Merged after automated verification; no independent human review comments
were recorded.** PR #12 was marked ready and merged at `8da7261` with no review
threads, no review comments and no review approvals on record. The verification
basis is the CI run on the head commit `260b652` (all six checks green: backend
lint/types/tests, frontend, API contract, startup smoke, security scan, and the
advisory parity job, which skips without the prototype) plus the author's local
evidence below. Nothing here should be read as a reviewer's finding.

What the author's own verification found and changed:

- **SQLite returns naive timestamps.** `DatasetVersion` refused its own rows on
  SQLite only. Fixed at the row boundary with `tables.as_utc`, not by loosening the
  domain guard; written into `AGENTS.md`.
- **A test that passed by accident.** The history-order assertion relied on the
  random `promotion_id` tiebreak under a fixed test clock; it passed on SQLite and
  failed on PostgreSQL. Made order-independent and the tie rule documented.
- **The concurrency test has teeth.** With the compare-and-set clause and the row
  lock removed, 4 of 8 concurrent promoters "won"; restored, exactly 1 wins.
- **The layer rules fire.** A probe `parse_panel(` in `apps/api` and a probe
  `RuntimePopulation._issue(` in `infrastructure/` each failed `layer_check`.
- **Exposure.** `exposure_check` scans tracked files only, so its rules were run by
  hand over the new untracked files: no reference hashes, no dataset-shaped names;
  the only token hit is the exempt snapshot-tag literal in `czech.py`.

**Measured** (Python 3.12.3, PostgreSQL 16): SQLite 546 passed / 117 skipped at
`17c0a6b` → 773 / 118; PostgreSQL with `AIA_REQUIRE_POSTGRES=1` 563 / 100 → 791 /
100; without the reference checkout 755 / 136 (the 18 parity tests skip).
`mypy --strict` clean over 51 files, `layer_check` 16/16, `exposure_check` 7/7,
migration upgrade / `alembic check` / downgrade-to-base / upgrade clean.

**Left open, filed:** OI-6 (free-text population identity in project content),
OI-7 (enrichment derivations unrecovered), OI-8 (no permission on promote).
