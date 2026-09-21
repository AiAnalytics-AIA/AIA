# Legacy system map — NPC Panel 18.6.6

How the supplied prototype works, what is worth keeping, and what is accidental.

The prototype is **not vendored into this repository**. It lives beside it at
`../npc-panel-reference` and is referenced by the parity test suite via
`AIA_LEGACY_REFERENCE`. It has no `.git` directory — it is a snapshot, so there
is no history to migrate, only behaviour.

## Measured inventory

| Measure | Value |
| --- | --- |
| Files | 1,565 (71 MB) |
| Python | 266 files, 44,395 LOC |
| Tests | 64 files, 5,085 LOC pytest |
| Test result | **394 passed, 0 skipped** (see [baseline](#test-baseline)) |
| Frontend | one file, `ui_app.html`, 896 KB / 2,395 lines |
| HTTP API | 136 distinct `/api/*` routes |
| Documentation | 217 markdown files |
| SQLite databases | 3 application + 10 demo |
| Launchers | 19 Windows `.bat` scripts |

### Largest modules

```
ui_server.py           2,185    HTTP server + routing + request handlers
full_simulation.py     1,631    multi-world simulation engine
dotaznik.py            1,604    questionnaire / respondent engine
pipeline.py            1,496    sampling, budget guard, checkpoint/resume
worker_job.py          1,096    job execution for every stage kind
dimension_catalog.py     798    persona dimension catalogue
research_designer.py     756    brief-first research design
data_library.py          650    source ingestion → evidence → dimensions
dispozice.py             630
claude_code_provider.py  618    Claude Code CLI transport
fullsim_learning.py      614
persona_depth.py         601
project_store.py         596    the durable project graph
provider_auth.py         587
sociomap.py              565    relation matrices, unfolding, layout
```

## Runtime shape

Single-process, single-user, localhost. `ThreadingHTTPServer` with a hand-written
`BaseHTTPRequestHandler`, dispatching 136 routes through `if`/`elif` chains on
path prefixes. Started by `.bat` scripts that detect or bootstrap a bundled
Python. No authentication, no concept of a user or a tenant, a writable current
working directory assumed throughout.

The frontend is one 896 KB HTML file containing 176 script blocks, ~1,040
functions and 4,944 `div`s, with element ids suffixed by build number
(`anthKey1790`, `assistantDrawer1791`, `demoSubAudience1795`). It is a functional
reference, not code to salvage.

## What is genuinely good

These parts are well designed and their *concepts* survive the migration intact.

### `project_pipeline.py` — the fingerprint contract

The most valuable module in the prototype. `stage_input_payload()` defines, per
stage, exactly which project fields materially affect it. That payload is
fingerprinted, and the fingerprint decides whether an artifact can be reused.

Two subtleties that are easy to destroy and expensive to lose:

- **Provider transport is deliberately excluded** from the fingerprint, so
  switching provider preserves completed artifacts.
- **Model is included only where it changes generated content** (fieldwork,
  analysis), not everywhere.

`impact_preview()` maps changed fields to the earliest affected stage; everything
upstream is preserved, that stage and everything downstream is invalidated. A few
fields (`provider`, `preferred_provider`, `provider_policy`, `model`) map to
`None` and invalidate nothing.

**Ported** to `aia_core.domain.pipeline` with byte-level parity tests.

### `project_store.py` — the durable graph

11 tables implementing `Project → immutable Revision → Stage → Artifact` with
content-hash deduplication, per-key changed-field detection, and the
carry-forward rule that copies completed upstream stages into a new revision.
Artifact writes use temp file → `fsync` → atomic rename → SHA256 verify →
registry commit, and a stage is never marked complete before its artifact is
committed.

**Ported** to `aia_core.domain.project` + `aia_core.infrastructure`.

### `job_store.py` — a real durable queue

10 tables with leases, heartbeats, idempotency keys, `max_attempts`,
`cancel_requested`, cost reservations, approvals and cron-style schedules. This is
proper job-queue design that happens to be implemented on SQLite. The design
survives; only the storage engine changes.

**Phase 3.** Port the schema and semantics; do not redesign.

### `workflow_engine.py` — the canonical research DAG

`STANDARD` is a 24-node list giving each node its kind, interaction mode,
dependencies, stage and artifact target. Two details matter: `preflight` is
`review_if_warning` rather than `auto`, and analysis is **eight** separate
durable nodes so a quota pause resumes mid-analysis.

**Phase 3.** Carry over as data.

### `ai_router.py` / `provider_runtime.py` — explicit provider behaviour

Structured output against JSON schemas, schema strictification, automatic
substitution of retired model ids against what an account can actually see, and a
10-way error classification. No silent fallback.

**Domain rules ported** to `aia_core.domain.providers`; the transport layer is
Phase 4.

### `PRODUCT_POLICY.json` and `DATA_CONTRACT_v17.json`

The methodology encoded as machine-readable data rather than prose: permitted
evidence roles, sample-size limits, signal budgets, scenario rules
(`linear_interpolation_allowed: false`), provider policy, demo constraints,
Sociomapa rules (`manual_drag: visual_override_only_never_mutates_raw_results`).

**Phase 6.** These become first-class backend rules, not prompt text.

## What is accidental and should not survive

| Area | Reason |
| --- | --- |
| `ThreadingHTTPServer` + hand-rolled routing | 136 routes in `if`/`elif` chains; no validation, no schema, no docs |
| `ui_app.html` | One 896 KB file with build-number-suffixed ids |
| SQLite as the application store | Single-writer; blocks concurrent workers and multi-instance deploys |
| Filesystem artifact paths | Not shareable between processes, lost on redeploy, unbacked |
| 19 Windows `.bat` launchers, bundled Python installer | Replaced by containers and CI |
| `legacy_job_dispatch.py`, `LEGACY_STAGE_MAP` | Compatibility shims for pre-17.8 jobs |
| `anthropic_compat.py`, `spawn_env.py`, `system_fingerprint.py`, `portability_check.py` | Local-machine and SDK-version workarounds |
| Czech code identifiers | `dotaznik`, `dispozice`, `navrh`, `kalibrace`, `vystupy`, `osobnost`, `biografie`. Czech stays in UI copy and population column names only |
| Duplicate feature generations | e.g. `report.py` / `client_report_v2.py` / `final_client_report.py`; four generations of interactive Sociomapa acceptance |
| One-space indentation, dense one-line functions | Style, not behaviour |

## Test baseline

Verified on 2026-09-21, Python 3.14.6, macOS, in a clean virtualenv:

```
394 passed in 67.73s
```

- **0 failures, 0 skipped** once `python-pptx` is installed.
- **Finding:** `output_pack.py` imports `pptx`, but `python-pptx` is **not
  declared in `requirements.txt`**. On a clean install
  `tests/test_release_core.py::test_client_exports_hide_internal` fails with
  `ModuleNotFoundError: No module named 'pptx'`. This is a genuine packaging bug
  in the prototype, not a test problem.
- **No test requires provider credentials.** The suite is fully hermetic, which
  makes it usable as a characterization harness.
- Tests are named by build number (`test_*_1790.py`) and are release-gate style.
  Many assert on implementation details, so behavioural equivalents are written
  rather than the originals being ported verbatim.

## Latent bugs found during the audit

Found by writing parity tests against the prototype. Both are fixed in the port
and documented as deliberate deviations in
[parity-matrix.md](parity-matrix.md).

1. **`impact_preview` raises `ValueError` on a cross-pipeline field.** Changing
   `scenario` on a research project maps to `SCENARIO_CONTRACT`, which is not a
   research stage; `ids.index()` then raises, and the exception escapes through
   `project_store._save_normalized` — the project save path. Reachable.

2. **`api_budget_check` reports more remaining budget than the cap.** Negatives
   are clamped when computing `projected_usd` but not `remaining_usd`, so a spend
   of `-3.0` against a $10 cap reports **$13 remaining**. The allow/deny decision
   is unaffected, but the figure is shown to users and cost dashboards.

## Data assets

| Asset | Detail |
| --- | --- |
| Population panel | `FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz`, **18,766 rows × 400 columns**, Czech census-anchored |
| Architecture | `population anchor → same-person core → whole-donor thematic blocks → labeled calibrated/modelled backgrounds` |
| Key columns | `panel_row_id`, `vek`, `pohlavi`, `kraj`, `nuts2`, `population_cell`, `vaha_kalibrovana`, `core_donor_id`, `core_match_quality`, `vzdelani_isced`, `prijem_decile` |
| Weights | default `vaha_strukturalni_2025`; census 2021 `vaha_kalibrovana`; party benchmark has its own explicit contract |
| Demo library | 33 MB, 10 complete demos each with `PROJECT.json`, `DATABASE.sqlite`, `RESPONDENTS.csv`, `RESULTS.xlsx`, `WORLDS.json`, `PROVENANCE.json`, `REPORT.docx`, `SHA256SUMS.txt` |

**Note on a legacy inconsistency:** `PRODUCT_POLICY.json` gives
`production_panel: v17_4_0` at the top level but
`data_core.production_panel: v17_1_2`. `DATA_CONTRACT_v17.json` says `v17_4_0`.
The migration should treat `v17_4_0` as authoritative and resolve the stale key.

## Methodology constraints that must survive

From `DATA_CONTRACT_v17.json`, `PRODUCT_POLICY.json` and
`KNOWN_LIMITATIONS.md`. These are product requirements, not caveats to tidy away:

- `same_person_core: true`, `cross_block_same_person: false` — cross-block
  relationships are **not** same-person truth, and latent cross-block claims fail
  closed.
- `external_predictive_holdout: EXTERNAL_HOLDOUT_PENDING_LIVE_T1_T3_NOT_RUN` —
  external predictive certification is `NOT_VALIDATED`. A distribution build must
  not fake these results.
- `independent_dimension_imputation_allowed: false`.
- Modelled background is allowed but **must be labeled**.
- Brand-specific claims **require** brand-specific background.
- Scenario output is a **delta**; absolute level claims are not allowed;
  `linear_interpolation_allowed: false` — variants are independently modelled.
- `invent_missing_truth: false` — a missing validation anchor is not fabricated.
- Licensing without clearance metadata is `REVIEW_REQUIRED`.
- Automated consulting reports have an evidence/QA gate and still require human
  sign-off before external delivery.
- Special Audience catalogue is deliberately `COMING SOON` in the UI.
- Progress is real elapsed time and heartbeat; percentages are not invented.
