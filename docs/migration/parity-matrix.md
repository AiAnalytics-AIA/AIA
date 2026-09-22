# Parity matrix

Old versus new behaviour, and the evidence for each claim.

**Parity levels**

| Level | Meaning |
| --- | --- |
| ✅ **Verified** | Automated tests compare this implementation against the prototype on shared fixtures, and pass |
| ◐ **Partial** | Implemented and tested behaviourally, but not compared against the prototype |
| ○ **Not started** | No implementation |
| ⚠ **Deviation** | Intentionally differs from the prototype; documented and tested below |

Parity tests live in `packages/aia_core/tests/test_pipeline_parity.py` and
`test_providers_parity.py`. They import the prototype from
`AIA_LEGACY_REFERENCE` and skip cleanly when it is absent, so a normal clone
stays green while a migration engineer gets the comparison.

Run them: `make test-parity`

## Authoritative reference

Reference interpretation is owned by the private repository
**`AiAnalytics-AIA/AIA-reference`** (tag
`reference-18.6.6-gemo-2026-09-11-v1`), which carries the full capability map,
methodology ledger, subsystem contracts and 11 executable golden fixtures. See
[reference-source.md](reference-source.md).

## Complete module inventory

This table covers the modules whose behaviour has a parity claim. It is **not**
a complete inventory, and treating it as one is how 85 of the prototype's 191
modules ended up with no recorded disposition.

For the exhaustive list -- every module, with an explicit port / drop /
dev-tool / data-pipeline decision and the phase that owns it -- see
[module-inventory.md](module-inventory.md), enforced by
`packages/aia_core/tests/test_module_inventory.py`.

## Migration inventory

| Legacy component | Responsibility | New component | Status | Parity | Notes |
| --- | --- | --- | --- | --- | --- |
| `project_pipeline.RESEARCH_STAGES` / `SIMULATION_STAGES` | Stage lists + Czech labels | `aia_core.domain.pipeline` | Done | ✅ | Ids, order and labels identical |
| `project_pipeline.STAGE_STATUSES` | Stage state set | `StageStatus` enum | Done | ✅ | Exact set equality asserted |
| `project_pipeline.IMPACT_ROOTS` | Field → root stage | `IMPACT_ROOTS` | Done | ✅ | Dict equality asserted |
| `project_pipeline.stage_input_payload` | **The fingerprint contract** | `stage_input_payload` | Done | ✅ | Byte-identical for all 13 stages, both pipelines |
| `project_pipeline.stage_fingerprint` | Reuse key | `stage_fingerprint` | Done | ✅ | Hash-identical |
| `project_pipeline.fingerprint` | Stable SHA256 | `fingerprint` | Done | ✅ | Identical incl. nested, unicode, unserialisable |
| `project_pipeline.impact_preview` | Invalidation rule | `impact_preview` | Done | ✅ ⚠ | Identical for all in-pipeline fields; one deviation (D1) |
| `project_pipeline.resolve_stage` | Cross-pipeline routing | `resolve_stage` | Done | ✅ | Identical across the full probe matrix |
| `project_store._save_normalized` | Revision + carry-forward | `domain.project.plan_save` | Done | ◐ | Behaviourally tested; not yet diffed against the prototype's SQLite |
| `project_store` (11 tables) | Durable graph | `infrastructure.tables` | Done | ◐ | PostgreSQL; schema redesigned, semantics preserved |
| `project_store.create_project` | Project creation | `ProjectRepository.create` | Done | ◐ | Czech default titles and policy widening preserved |
| `project_store.list/trash/restore` | Portfolio + trash | `ProjectRepository` | Done | ◐ | Tenant scoping added |
| `provider_runtime.LIVE_PROVIDERS` / `POLICIES` | Provider identity | `Provider`, `ProviderPolicy` | Done | ✅ | Internal ids and policy names identical |
| `provider_runtime.UI_LABELS` | Display names | `ui_label` | Done | ✅ | `anthropic` → "Claude API" preserved |
| `provider_runtime.normalize_live_provider` | Alias normalisation | `normalize_provider` | Done | ✅ | All 15 spellings identical |
| `provider_runtime.normalize_policy` | Policy normalisation | `normalize_policy` | Done | ✅ | Identical incl. fallback |
| `provider_runtime.policy_for_provider` | Implied policy | `policy_for_provider` | Done | ✅ | Identical |
| `provider_runtime.provider_for_stage` | Stage provider resolution | `provider_for_stage` | Done | ✅ ⚠ | Identical across 700-case matrix for known input; one deviation (D2) |
| `provider_runtime.api_budget_check` | Budget enforcement | `check_budget` | Done | ✅ ⚠ | Decision identical incl. boundary; one deviation (D3) |
| `ui_server.py` (136 routes) | HTTP API | `apps/api` routers | ◐ 8 routes | ◐ | Projects only; 128 routes still to migrate |
| `ui_app.html` | Frontend | `apps/web` | ○ | ○ | Reference UI only; not salvaged |
| `artifact_store.py` | Artifact bytes | `infrastructure.storage` (S3 / filesystem / memory) | Done | ◐ | Three backends, identical key validation and hash verification |
| `job_store.py` (10 tables) | Durable queue | `WorkflowRun`/`StepRun`/`StepAttempt` + `WorkflowRepository` | Done | ◐ | Redesigned into two-level state; append-only attempts. Verified under real PostgreSQL contention |
| `workflow_engine.STANDARD` | 24-node research DAG | `domain.workflow.StepDefinition` + `validate_dag` | Done | ◐ | DAG validated at definition time; dependency gating on `SUCCEEDED` |
| `worker_job.py` | Stage execution | Phase 4 | ○ | ○ | Engine exists; the step body that calls a provider does not |
| `ai_router.py` | Provider transport | Phase 4 | ○ | ○ | Largely portable behind an interface |
| `claude_code_provider.py` | Claude Code CLI | Phase 4 | ○ | ○ | |
| `cost_controller.py` | Reservations | `WorkflowRepository.reserve_budget` | Done | ◐ | Blocking `FOR UPDATE` on the study row; concurrent-overspend regression test |
| `dotaznik.py`, `pipeline.py` | Questionnaire + respondents | Phase 5 | ○ | ○ | Needs seeded parity tests |
| `research_designer.py` | Research design | Phase 5 | ○ | ○ | |
| `analysis_agent.py` | 8 analysis modules | Phase 6 | ○ | ○ | |
| `validation_gate.py`, `evidence_validator.py`, `holdout_protocol.py`, `legal_gate.py` | Governance | Phase 6 | ○ | ○ | **Must fail closed** where the prototype does |
| `PRODUCT_POLICY.json`, `DATA_CONTRACT_v17.json` | Methodology contract | Phase 6 | ○ | ○ | Become enforced backend rules |
| `client_report_v2.py`, `output_pack.py` | Reports and exports | Phase 6 | ○ | ○ | |
| `full_simulation.py`, `scenario_compiler.py` | Simulation | Phase 7 | ○ | ○ | Seeded reproduction required |
| `data_library.py`, `society_insights.py` | Data Library | Phase 8 | ○ | ○ | Approval ordering must hold |
| `population_context.py`, `donor_fusion.py`, `core_joint.py` | Population | Phase 8 | ○ | ○ | 18,766 × 400 panel |
| `sociomap.py` (+ `ui_app.html` `*66` terrain, normaliser, object metrics) | Sociomapa core | `aia_core.domain.sociomap` | Done (core) | ◐ | ✅ against golden fixtures F1–F3, F5–F7, F9; F8 partial (OI-14); layout **not** at parity — the legacy Python and R algorithms are refused (OI-13, OI-15) and an AIA algorithm is declared instead. Deviations S1–S6 in `docs/architecture/sociomapa-deterministic-engine.md` §8 |
| `visualization_lab.py`, segments, comparison, object manager | Sociomapa modes | Phase 9 | ○ | ○ | Numerical parity required |
| 19 `.bat` launchers, `launcher_bootstrap.py` | Windows startup | — | Dropped | n/a | Replaced by containers + CI |
| `legacy_job_dispatch.py`, `LEGACY_STAGE_MAP` | Pre-17.8 compatibility | — | Dropped | n/a | Remove after Phase 3 |
| `anthropic_compat.py`, `spawn_env.py`, `portability_check.py` | Local-machine shims | — | Dropped | n/a | |
| `src/server.js` (this repo) | Fastify login stub | `apps/api` | Retained | n/a | 44 lines, no domain logic. Holds the only existing login path; remove once the auth seam is filled |

## Documented deviations

Each is a place where the prototype's behaviour is wrong rather than merely ugly.
Each is tested, including an assertion that the *legacy* behaviour is still what
we think it is — so if the prototype changes, the test tells us to revisit.

### D1 — `impact_preview` no longer crashes on a cross-pipeline field

**Prototype:** changing `scenario` on a research project maps to
`SCENARIO_CONTRACT`, which is not in `RESEARCH_STAGES`. `ids.index(root)` raises
`ValueError: list.index(x): x not in list`, and the exception escapes through
`project_store._save_normalized` — the project save path. The same happens for
`questionnaire` on a simulation project.

**Now:** the root is resolved through `STAGE_EQUIVALENTS` — the mechanism this
codebase already uses for cross-pipeline routing — and dropped if it still does
not resolve. `scenario` on a research project reopens `RESEARCH_DESIGN`.

**Why not preserve it:** faithfully reproducing a crash in a save path is not
fidelity. `STAGE_EQUIVALENTS` exists precisely because the codebase knows
cross-pipeline routing happens.

**Tests:** `test_cross_pipeline_field_crashes_legacy_but_not_us`,
`test_cross_pipeline_field_reverse_direction`.

### D2 — an unrecognised stage override no longer overrides policy

**Prototype:** `provider_for_stage` accepted any truthy `stage_override` and
normalised an unrecognised one to Claude Code. So a typo on a project pinned to
`CLAUDE_API_ONLY` silently moved that stage onto the subscription runtime,
changing both cost and provenance.

**Now:** only a recognised override is honoured; otherwise the policy decides.

**Why not preserve it:** `workflow_engine` already emits a `CONFIG_NORMALIZED`
warning for unsupported provider overrides, so normalise-and-warn is the
documented intent — not break-the-policy. Silently retargeting a provider is
exactly what the no-silent-fallback rule forbids.

**Tests:** `test_unknown_stage_override_no_longer_breaks_policy`,
`test_unknown_stage_override_falls_back_to_policy`.

### D3 — negative cost records no longer inflate remaining budget

**Prototype:** `api_budget_check` clamped negatives when computing
`projected_usd` but not `remaining_usd`. A spend of `-3.0` against a $10 cap
reported **$13 remaining** — more headroom than the cap permits.

**Now:** clamping is consistent; reported headroom never exceeds the cap. The
allow/deny decision is unchanged, and parity on the decision is still asserted.

**Why not preserve it:** the figure is surfaced to users and cost dashboards.

**Tests:** `test_negative_cost_records_do_not_inflate_remaining_budget`.

## Deliberate improvements (not behaviour changes)

| Area | Prototype | Now | Rationale |
| --- | --- | --- | --- |
| Timestamps | Naive local-time strings | Aware UTC | Audit ordering was ambiguous across timezones |
| Foreign keys | SQLite, unenforced | Enforced; `PRAGMA foreign_keys=ON` on SQLite | Prototype silently accepted FK violations and skipped cascades |
| Tenant scoping | None | Repository unconstructable without an org | The prototype has no tenant concept at all |
| Missing vs forbidden | n/a | 404 for both | A 403 would disclose that another tenant's project exists |
| Fingerprint exposure | n/a | 12-char prefix only | Clients should not depend on cache internals |
| Error responses | Ad hoc | One `{code, message, details, request_id}` shape | |
| Secret handling | n/a | Redaction by key name and value shape | |
| Packaging | `python-pptx` undeclared | Declared where used | Prototype fails on a clean install |

## Reference weaknesses

Defects found in the prototype are catalogued in
[reference-weaknesses.md](reference-weaknesses.md), including the undeclared
`python-pptx` dependency (W1) that makes the advertised test baseline unreachable
from a clean install. The reference is **not** modified to make our environment
look clean; workarounds are applied on our side and recorded there.

## Baseline

Prototype suite, verified 2026-09-21 on Python 3.14.6: **394 passed, 0 skipped**
(after installing the undeclared `python-pptx`). Fully hermetic — no test needs
provider credentials.

New suite: **168 passed** — 99 in `packages/aia_core` (of which 29 are parity
against the prototype) and 69 in `apps/api`. Ruff clean, `mypy --strict` clean.
