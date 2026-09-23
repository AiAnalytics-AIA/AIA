# OI-7 — the seven enrichment derivations need the archive

**Result: outcome B.** The exact derivations of the seven `*_derived` runtime
fields are **not recoverable** from the committed evidence in
`AiAnalytics-AIA/AIA-reference` @ `678e298`. This is a data/archive acquisition
task, not an engineering task. The ANALYSIS population view stays fail-closed
(`PopulationRuntime._enrich` raises `EnrichmentFailed` with no `Enricher`), which is
correct (R1). The BASE view — the 400 source fields — loads.

## The seven fields

`ad_receptivity_tier_derived`, `digital_engagement_tier_derived`,
`dominant_leisure_derived`, `dominant_media_derived`,
`financial_capability_tier_derived`, `life_stage_derived`,
`shopping_orientation_derived` (fixture F10 `loader_a.extra_vs_400`).

## Exactly what is missing

| Needed | Where it is | Identity (from the authoritative archive) |
|---|---|---|
| The derivation source | `audience_dimensions.py` — `attach_derived` (with helpers `_tier`, `_label`, `_series_numeric`), called from `enrich_panel` as `attach_evidence_overlays(attach_derived(df))` | 23,462 bytes, 345 LOC, SHA256 `6ae1d1f8d9ae8a5a9e007e0aee1b842b2c087ca16e888cc2cbf0e55ab7c754bf` |
| Its executable specification | `tests/test_audience_dimensions_1793.py` — incl. `test_derived_dimensions_are_deterministic`, `test_real_sampling_honors_derived_factor_filter` | 8,872 bytes, SHA256 `36efe9883b63b88ea0963f200a687852668dd378e41532608b828f6edda2d602` |
| The input it runs on | `FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz` (and, for parity on the static reference, `v17_1_2`) | as pinned in `aia_core.domain.population.czech` |

Both source hashes are already recorded in `docs/migration/reference-manifest.json`,
so the bytes delivered with the archive can be verified before use.

## What the reference repository does hold — and why it is not enough

Searched: every `.md`, `.json`, `.csv` and tool script in AIA-reference for
`_derived`, `attach_derived`, `enrich_panel` and `audience_dimensions`.

| Evidence | Content | Sufficient? |
|---|---|---|
| `dependency-graph.json` | module structure: 16 function names, fan-in 6, no imports of its own | No — names only |
| `methodology-candidates.json` | four threshold expressions (`uniq <= 2`, `uniq <= 12`, `sd <= 1e-12`, `1 <= mean <= 10`) and call counts (`mean` 6, `std` 1, `quantile` 2) | No — no mapping from threshold to field, no inputs, no tier cut points, no labels |
| `ai-prompt-inventory.json` | a truncated docstring: *"deterministic dimensions derived only from existing respondent signals"* | No — says they are deterministic, not how |
| `population-subsystem.md`, `data-import-contracts/czech-population.md`, F10 | where they are attached, and that they exist | No |

**Why no safe reconstruction is possible.** Each field is a categorical tier or
label over unnamed source fields with unrecorded cut points. Reconstructing from
the names (for example, deciding which of the 400 fields "digital engagement"
reads and where its tiers break) would put a guess into audience filtering and
sampling, where it changes who is in a study's sample. Reverse-engineering from
outputs is also unavailable: no output values for these fields are recorded in any
fixture. Per the assignment, no further time is spent on either.

## The parity fixture needed with the archive

**F12 — `population.enrichment`, parity type EXACT.** Run the reference's
`audience_dimensions.enrich_panel` over `v17_4_0` (and separately `v17_1_2`) and
record, per derived field:

1. the value counts, nulls counted explicitly;
2. a per-row digest: SHA256 over `panel_row_id` + the seven values, rows sorted by
   `panel_row_id`;
3. the reference environment (Python, pandas, numpy versions), as the other
   fixtures do.

Acceptance for the production `Enricher`: identical per-row digest on both
versions, and the determinism the reference test asserts. The enricher then gets
an `enricher_id` naming the archive SHA256 of the source it was ported from.

## Who does what

| Step | Owner |
|---|---|
| Release the archive to an approved EU destination (`REF-WITHHELD-REFERENCE-ARCHIVE`, ADR 0008) | data owner |
| Capture F12 from the archive | parity-quality |
| Port `attach_derived` behind `Enricher`, pass F12 | population-data |
| Classify the eight fields ([population-derived-fields-decision.md](population-derived-fields-decision.md)) | data owner + analysis-governance |
