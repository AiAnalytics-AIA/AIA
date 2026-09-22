# Reference module inventory

Every Python module in the NPC Panel prototype, with an explicit decision
about its fate. **This file exists because prose was not enough.**

[parity-matrix.md](parity-matrix.md) names the significant modules in prose,
and that is how 85 of 191 modules ended up with no recorded disposition --
among them `factual_layer`, `tier_gate`, `holdout_registry`, `uncertainty`,
`validation_status` and `budget_guard`, which are the modules that
*implement* the epistemic and budget rules
[`docs/product/README.md`](../product/README.md) claims AIA enforces. The
rules were written down; the code realising them was never enumerated.

A module with no disposition is a module nobody decided to keep or drop.
`packages/aia_core/tests/test_module_inventory.py` fails the build if the
reference contains one, so omission can no longer be silent. The machine-
readable source of truth is [module-dispositions.json](module-dispositions.json).

**Scope.** 191 modules, 39,086 LOC. Excludes the prototype's own test suite,
`__pycache__` and the bundled `demo_library` payloads (data, not behaviour).

## How to read the LOC figures

Reference LOC measures **how much prototype behaviour a phase covers**, not
how much production code it takes. The 1,295 reference LOC reimplemented so
far became 10,743 lines of production source and 9,063 of tests, because the
replacements are transactional, typed, multi-tenant and tested. So "3% of
reference LOC" means 3% of the *behaviour surface*, not 3% of the effort.

## Dispositions

| Disposition | Meaning | Modules | LOC |
| --- | --- | --- | --- |
| `port` | Reimplemented in production, in the phase shown | 152 | 34,922 |
| `data-pipeline` | Offline panel build; becomes a versioned reproducible data pipeline, not app runtime | 5 | 487 |
| `dev-tool` | Local diagnostic or release check; replaced by CI, health endpoints and CloudWatch | 22 | 1,555 |
| `drop` | Not carried forward; reason recorded per module | 12 | 2,122 |

## Ports by phase

| Phase | Scope | Modules | LOC | Done | State |
| --- | --- | --- | --- | --- | --- |
| 2 | Foundation, scope, artifacts | 4 | 866 | 4 | ✅ complete |
| 3 | Durable workflow engine | 6 | 853 | 3 | ◐ 3 of 6 |
| 4 | AI runtime and cost | 10 | 3,261 | 0 | ○ not started |
| 5 | Research engine | 42 | 13,152 | 0 | ○ not started |
| 6 | Analysis, governance and reports | 43 | 4,538 | 0 | ○ not started |
| 7 | Simulation | 6 | 2,852 | 0 | ○ not started |
| 8 | Data Library and population | 29 | 5,017 | 0 | ○ not started |
| 9 | Sociomapa and modul VÝZKUM | 11 | 2,198 | 0 | ○ not started |
| 10 | HTTP surface | 1 | 2,185 | 0 | ◐ 19 of 136 paths |

**Reimplemented so far:** 7 modules, 1,295 of
39,086 reference LOC (3% of the behaviour surface).
`ui_server.py` is partial: 19 of its 136 HTTP paths exist.

Phase 3 is the engine, not the dispatch: `job_store`, `workflow_engine` and
`cost_controller` are reimplemented and verified under real PostgreSQL
contention, but `scheduler`, `worker_daemon` and `project_artifact_sync` are
still to build, so no worker process runs yet.

The work so far deliberately took the *load-bearing* modules first -- the
fingerprint contract, provider policy, the durable graph and the workflow
engine. Those are the ones every later phase depends on, and the ones where a
wrong answer corrupts artifact reuse or lies about money.

## Phase 2 — Foundation, scope, artifacts

| | Module | LOC | Context | Disposition note |
| --- | --- | --- | --- | --- |
| ✅ | `project_store.py` | 596 | pipeline | Reimplemented as ProjectRepository + domain.project; behavioural tests |
| ✅ | `project_pipeline.py` | 158 | pipeline | Reimplemented; fingerprint parity verified byte-identical |
| ✅ | `artifact_store.py` | 65 | artifacts | Reimplemented as ArtifactStore protocol + 3 backends |
| ✅ | `provider_runtime.py` | 47 | ai-runtime | Reimplemented as domain.providers; parity verified |

## Phase 3 — Durable workflow engine

| | Module | LOC | Context | Disposition note |
| --- | --- | --- | --- | --- |
| ✅ | `job_store.py` | 295 | workflow | Reimplemented as WorkflowRun/StepRun/StepAttempt; verified under PG contention |
| ○ | `project_artifact_sync.py` | 180 | artifacts | Sub-artifact registration from engine outputs |
| ○ | `scheduler.py` | 127 | workflow | Dispatch + reconciler; SQS-backed worker process still to build |
| ○ | `worker_daemon.py` | 117 | workflow | Dispatch + reconciler; SQS-backed worker process still to build |
| ✅ | `workflow_engine.py` | 99 | workflow | Reimplemented as WorkflowRun/StepRun/StepAttempt; verified under PG contention |
| ✅ | `cost_controller.py` | 35 | workflow | Reimplemented as WorkflowRun/StepRun/StepAttempt; verified under PG contention |

## Phase 4 — AI runtime and cost

| | Module | LOC | Context | Disposition note |
| --- | --- | --- | --- | --- |
| ○ | `worker_job.py` | 1096 | workflow | Stage execution body; drives one pipeline node |
| ○ | `claude_code_provider.py` | 618 | ai-runtime | Becomes a ModelGateway adapter behind AIA's own protocol (ADR 0006) |
| ○ | `provider_auth.py` | 587 | ai-runtime | Credential handling moves to Secrets Manager + KMS; no local keystore |
| ○ | `ai_router.py` | 512 | ai-runtime | Becomes a ModelGateway adapter behind AIA's own protocol (ADR 0006) |
| ○ | `runtime_config.py` | 156 | ai-runtime | Capability/policy metadata for user-facing AI actions |
| ○ | `ai_runtime_audit.py` | 72 | ai-runtime | Usage ledger and audit of model calls |
| ○ | `budget_guard.py` | 63 | cost | Pre-run cost/time estimation and the hard per-run spend cap |
| ○ | `ai_runtime.py` | 58 | ai-runtime | Capability/policy metadata for user-facing AI actions |
| ○ | `cost_estimator.py` | 54 | cost | Pre-run cost/time estimation and the hard per-run spend cap |
| ○ | `ai_execution_context.py` | 45 | ai-runtime | Capability/policy metadata for user-facing AI actions |

## Phase 5 — Research engine

| | Module | LOC | Context | Disposition note |
| --- | --- | --- | --- | --- |
| ○ | `dotaznik.py` | 1604 | questionnaire | Sequential questionnaire engine — core research runtime |
| ○ | `pipeline.py` | 1496 | respondents | Respondent sampling and generation pipeline |
| ○ | `dimension_catalog.py` | 798 | respondents | Latent dispositions, personality, biography, response style, behaviour layers |
| ○ | `research_designer.py` | 756 | research-design | Guided research design and dual-agent research context |
| ○ | `dispozice.py` | 630 | respondents | Latent dispositions, personality, biography, response style, behaviour layers |
| ○ | `persona_depth.py` | 601 | respondents | Latent dispositions, personality, biography, response style, behaviour layers |
| ○ | `research_context.py` | 512 | research-design | Guided research design and dual-agent research context |
| ○ | `research_project.py` | 498 | research-design | Guided research design and dual-agent research context |
| ○ | `respondent_dialogue.py` | 390 | results | Grounded and explicitly-simulated respondent dialogue |
| ○ | `segment.py` | 359 | audience | Segment engine and orchestration |
| ○ | `audience_registry.py` | 346 | audience | Audience definition, sufficiency, registry and AI-assisted discovery |
| ○ | `audience_dimensions.py` | 345 | audience | Audience definition, sufficiency, registry and AI-assisted discovery |
| ○ | `persona_grounded.py` | 318 | respondents | Latent dispositions, personality, biography, response style, behaviour layers |
| ○ | `run.py` | 312 | orchestration | CLI orchestrators; become API/worker entrypoints |
| ○ | `import_dotaznik.py` | 294 | questionnaire | Sequential questionnaire engine — core research runtime |
| ○ | `qc.py` | 273 | analysis | Post-run QC and pricing analysis helpers |
| ○ | `audience.py` | 268 | audience | Audience definition, sufficiency, registry and AI-assisted discovery |
| ○ | `osobnost.py` | 268 | respondents | Latent dispositions, personality, biography, response style, behaviour layers |
| ○ | `research_copilot.py` | 256 | research-design | Optional research-design copilot surface |
| ○ | `factual_layer.py` | 201 | respondents | Deterministic factual layer — panel facts must never be re-invented by an LLM |
| ○ | `navrh.py` | 201 | questionnaire | Sequential questionnaire engine — core research runtime |
| ○ | `project_engine.py` | 187 | respondents | Respondent sampling and generation pipeline |
| ○ | `mrp.py` | 185 | respondents | Raking / IPF weighting and competitor-inspired adjustment mechanisms |
| ○ | `conditional_engine.py` | 177 | questionnaire | Conditional calibration engine and its diagnostics |
| ○ | `representative_sampling.py` | 173 | respondents | Respondent sampling and generation pipeline |
| ○ | `audience_strategist.py` | 150 | audience | Audience definition, sufficiency, registry and AI-assisted discovery |
| ○ | `pricing_engine.py` | 147 | analysis | Post-run QC and pricing analysis helpers |
| ○ | `kontext.py` | 145 | respondents | Shared survey runtime context; never implicitly injected |
| ○ | `filter_syntax.py` | 141 | questionnaire | Deterministic instrument library, static lint, filter normalisation |
| ○ | `behavior.py` | 126 | respondents | Latent dispositions, personality, biography, response style, behaviour layers |
| ○ | `instrument_library.py` | 125 | questionnaire | Deterministic instrument library, static lint, filter normalisation |
| ○ | `survey_lint.py` | 118 | questionnaire | Deterministic instrument library, static lint, filter normalisation |
| ○ | `styly.py` | 117 | respondents | Latent dispositions, personality, biography, response style, behaviour layers |
| ○ | `segment_orchestration.py` | 115 | audience | Segment engine and orchestration |
| ○ | `biografie.py` | 108 | respondents | Latent dispositions, personality, biography, response style, behaviour layers |
| ○ | `kalibrace.py` | 102 | respondents | Raking / IPF weighting and competitor-inspired adjustment mechanisms |
| ○ | `conditional_validation.py` | 96 | questionnaire | Conditional calibration engine and its diagnostics |
| ○ | `project_intake.py` | 80 | research-design | Guided research design and dual-agent research context |
| ○ | `npc.py` | 65 | orchestration | CLI orchestrators; become API/worker entrypoints |
| ○ | `audience_selector.py` | 49 | audience | Audience definition, sufficiency, registry and AI-assisted discovery |
| ○ | `audience_profile.py` | 11 | audience | Audience definition, sufficiency, registry and AI-assisted discovery |
| ○ | `task_conditions.py` | 9 | respondents | Shared survey runtime context; never implicitly injected |

## Phase 6 — Analysis, governance and reports

| | Module | LOC | Context | Disposition note |
| --- | --- | --- | --- | --- |
| ○ | `report.py` | 448 | reports | Report composition and export packs |
| ○ | `result_context.py` | 335 | results | Post-run external verification and contextual calibration |
| ○ | `validation_gate.py` | 277 | governance | Fail-closed evidence and predictive-validity gates |
| ○ | `benchmark.py` | 274 | governance | Benchmarks, drift guard and controlled ablation experiments |
| ○ | `holdout_protocol.py` | 218 | governance | Blind-human holdout: protocol, registry, preregistration workflow |
| ○ | `analysis_agent.py` | 216 | analysis | Eight independently durable analysis modules |
| ○ | `uncertainty.py` | 199 | statistics | Donor-aware weighted uncertainty; Kish effective N; bootstrap intervals |
| ○ | `client_report_v2.py` | 160 | reports | Report composition and export packs |
| ○ | `persona_calibration.py` | 158 | statistics | Calibration layers, kept separate from respondent microdata |
| ○ | `report_html.py` | 140 | reports | Report composition and export packs |
| ○ | `holdout_registry.py` | 137 | governance | Blind-human holdout: protocol, registry, preregistration workflow |
| ○ | `reality_alignment.py` | 122 | results | Post-run external verification and contextual calibration |
| ○ | `legal_gate.py` | 116 | governance | Source-use / licensing governance adapter |
| ○ | `persona_ablation.py` | 112 | governance | Benchmarks, drift guard and controlled ablation experiments |
| ○ | `validation_diagnostics.py` | 107 | statistics | Validation diagnostics and paired-question statistics |
| ○ | `system_fingerprint.py` | 101 | governance | Validation state machine bound to an immutable system fingerprint |
| ○ | `validace.py` | 98 | statistics | Validation diagnostics and paired-question statistics |
| ○ | `product_policy.py` | 95 | governance | Methodology contract as enforced backend rules |
| ○ | `provenance.py` | 84 | governance | Methodology contract as enforced backend rules |
| ○ | `output_pack.py` | 80 | reports | Report composition and export packs |
| ○ | `tier_gate.py` | 75 | governance | Fail-closed evidence and predictive-validity gates |
| ○ | `validation_stats.py` | 75 | statistics | Donor-aware weighted uncertainty; Kish effective N; bootstrap intervals |
| ○ | `validation_workflow.py` | 69 | governance | Blind-human holdout: protocol, registry, preregistration workflow |
| ○ | `fidelity.py` | 62 | governance | Fail-closed evidence and predictive-validity gates |
| ○ | `survey_experiments.py` | 62 | governance | Benchmarks, drift guard and controlled ablation experiments |
| ○ | `evidence_validator.py` | 60 | governance | Fail-closed evidence and predictive-validity gates |
| ○ | `final_client_report.py` | 59 | reports | Report composition and export packs |
| ○ | `manifest.py` | 58 | governance | Methodology contract as enforced backend rules |
| ○ | `ensemble.py` | 54 | statistics | Donor-aware weighted uncertainty; Kish effective N; bootstrap intervals |
| ○ | `evaluation.py` | 50 | statistics | Validation diagnostics and paired-question statistics |
| ○ | `cross_survey.py` | 49 | governance | Benchmarks, drift guard and controlled ablation experiments |
| ○ | `output_calibration.py` | 48 | statistics | Calibration layers, kept separate from respondent microdata |
| ○ | `model_drift.py` | 43 | governance | Benchmarks, drift guard and controlled ablation experiments |
| ○ | `reality_alignment_acceptance.py` | 43 | results | Post-run external verification and contextual calibration |
| ○ | `pdf_targets.py` | 39 | reports | Report composition and export packs |
| ○ | `anchor_registry.py` | 38 | governance | Known-truth anchors, campaign background (brand knowledge fails closed) |
| ○ | `research_arena.py` | 34 | governance | Benchmarks, drift guard and controlled ablation experiments |
| ○ | `dispersion_calibration.py` | 32 | statistics | Calibration layers, kept separate from respondent microdata |
| ○ | `validation_status.py` | 30 | governance | Validation state machine bound to an immutable system fingerprint |
| ○ | `effective_evidence_audit.py` | 29 | governance | Effective-evidence audit of dimensions beyond basic demographics |
| ○ | `smoke_validation.py` | 23 | governance | Validation state machine bound to an immutable system fingerprint |
| ○ | `campaign_background.py` | 17 | governance | Known-truth anchors, campaign background (brand knowledge fails closed) |
| ○ | `data_contract.py` | 12 | governance | Methodology contract as enforced backend rules |

## Phase 7 — Simulation

| | Module | LOC | Context | Disposition note |
| --- | --- | --- | --- | --- |
| ○ | `full_simulation.py` | 1631 | simulation | Simulation lab, learning layer, multi-variant orchestration |
| ○ | `fullsim_learning.py` | 614 | simulation | Simulation lab, learning layer, multi-variant orchestration |
| ○ | `simulation_batch.py` | 219 | simulation | Simulation lab, learning layer, multi-variant orchestration |
| ○ | `simulation_context.py` | 198 | simulation | Simulation lab, learning layer, multi-variant orchestration |
| ○ | `scenario_compiler.py` | 166 | simulation | Scenario contracts and the append-only scenario resolution log |
| ○ | `scenario_truth_log.py` | 24 | simulation | Scenario contracts and the append-only scenario resolution log |

## Phase 8 — Data Library and population

| | Module | LOC | Context | Disposition note |
| --- | --- | --- | --- | --- |
| ○ | `data_library.py` | 650 | data-library | Source ingestion → evidence proposal → approval → materialisation |
| ○ | `npc_tools/npc_fetch.py` | 426 | data-library | Panel QC, provenance, authenticity lint and source acquisition tools |
| ○ | `project_memory.py` | 404 | data-library | Cross-project knowledge retrieval (a documented product capability) |
| ○ | `population_context.py` | 341 | population | Population core: joint structure, donor fusion, subpanels, context |
| ○ | `npc_tools/npc_validate.py` | 340 | data-library | Panel QC, provenance, authenticity lint and source acquisition tools |
| ○ | `demo_showcase.py` | 324 | data-library | Read-only bundled demo project library |
| ○ | `society_insights.py` | 276 | data-library | Source ingestion → evidence proposal → approval → materialisation |
| ○ | `npc_tools/npc_provenance.py` | 267 | data-library | Panel QC, provenance, authenticity lint and source acquisition tools |
| ○ | `npc_tools/npc_lint.py` | 264 | data-library | Panel QC, provenance, authenticity lint and source acquisition tools |
| ○ | `library_system_catalog.py` | 225 | data-library | Source ingestion → evidence proposal → approval → materialisation |
| ○ | `npc_ingest/realism.py` | 181 | data-library | Ingest subsystem: routing, harmonisation, leakage, realism, versioning |
| ○ | `npc_ingest/versioning.py` | 143 | data-library | Ingest subsystem: routing, harmonisation, leakage, realism, versioning |
| ○ | `employment_bridge.py` | 131 | population | PIAAC 2023 employment bridge |
| ○ | `donor_fusion.py` | 125 | population | Population core: joint structure, donor fusion, subpanels, context |
| ○ | `npc_ingest/registry.py` | 125 | data-library | Ingest subsystem: routing, harmonisation, leakage, realism, versioning |
| ○ | `results_registry.py` | 117 | results | Run/results history and reusable question bank |
| ○ | `npc_ingest/manager.py` | 111 | data-library | Ingest subsystem: routing, harmonisation, leakage, realism, versioning |
| ○ | `npc_ingest/response_bank.py` | 109 | data-library | Ingest subsystem: routing, harmonisation, leakage, realism, versioning |
| ○ | `core_joint.py` | 106 | population | Population core: joint structure, donor fusion, subpanels, context |
| ○ | `run_store.py` | 80 | results | Run/results history and reusable question bank |
| ○ | `domain_readiness.py` | 68 | population | Readiness diagnostics for the integrated population core |
| ○ | `population_subpanels.py` | 53 | population | Population core: joint structure, donor fusion, subpanels, context |
| ○ | `ingest_automation.py` | 38 | data-library | Ingest subsystem: routing, harmonisation, leakage, realism, versioning |
| ○ | `library_batch_import.py` | 35 | data-library | Source ingestion → evidence proposal → approval → materialisation |
| ○ | `npc_ingest/leakage.py` | 25 | data-library | Ingest subsystem: routing, harmonisation, leakage, realism, versioning |
| ○ | `npc_ingest/harmonization.py` | 24 | data-library | Ingest subsystem: routing, harmonisation, leakage, realism, versioning |
| ○ | `npc_ingest/router.py` | 22 | data-library | Ingest subsystem: routing, harmonisation, leakage, realism, versioning |
| ○ | `npc_ingest/__init__.py` | 6 | data-library | Ingest subsystem: routing, harmonisation, leakage, realism, versioning |
| ○ | `npc_tools/__init__.py` | 1 | data-library | Panel QC, provenance, authenticity lint and source acquisition tools |

## Phase 9 — Sociomapa and modul VÝZKUM

| | Module | LOC | Context | Disposition note |
| --- | --- | --- | --- | --- |
| ○ | `sociomap.py` | 565 | sociomapa | Preference map and segmentation — numerical parity required |
| ○ | `visualization_lab.py` | 286 | sociomapa | Preference map and segmentation — numerical parity required |
| ○ | `study_contract.py` | 271 | sociomapa | modul VÝZKUM: data contract, dataset conversion, engine, export, validity |
| ○ | `segment_intelligence.py` | 245 | sociomapa | Preference map and segmentation — numerical parity required |
| ○ | `study_export.py` | 245 | sociomapa | modul VÝZKUM: data contract, dataset conversion, engine, export, validity |
| ○ | `study_validation.py` | 182 | sociomapa | modul VÝZKUM: data contract, dataset conversion, engine, export, validity |
| ○ | `study_validity.py` | 140 | sociomapa | modul VÝZKUM: data contract, dataset conversion, engine, export, validity |
| ○ | `study_dataset.py` | 117 | sociomapa | modul VÝZKUM: data contract, dataset conversion, engine, export, validity |
| ○ | `study_engine.py` | 95 | sociomapa | modul VÝZKUM: data contract, dataset conversion, engine, export, validity |
| ○ | `typology_reference.py` | 36 | sociomapa | modul VÝZKUM: data contract, dataset conversion, engine, export, validity |
| ○ | `study_cli.py` | 16 | sociomapa | modul VÝZKUM: data contract, dataset conversion, engine, export, validity |

## Phase 10 — HTTP surface

| | Module | LOC | Context | Disposition note |
| --- | --- | --- | --- | --- |
| ◐ | `ui_server.py` | 2185 | api | 136 HTTP paths; 19 ported so far. Source of the API contract |

## Not ported — `data-pipeline`

| Module | LOC | Context | Reason |
| --- | --- | --- | --- |
| `build_wp_artifacts_v17_1.py` | 160 | population | Offline panel build/rebuild script; becomes a versioned reproducible data pipeline, not app runtime |
| `BUILD_MARKETING_LATENT_v17_1.py` | 112 | population | Offline panel build/rebuild script; becomes a versioned reproducible data pipeline, not app runtime |
| `validate_v17.py` | 88 | population | Offline panel build/rebuild script; becomes a versioned reproducible data pipeline, not app runtime |
| `rebuild_social_network_gender_v17_4.py` | 73 | population | Offline panel build/rebuild script; becomes a versioned reproducible data pipeline, not app runtime |
| `audit_reference/legacy_build_scripts/patch_version_v17_1.py` | 54 | population | Offline panel build/rebuild script; becomes a versioned reproducible data pipeline, not app runtime |

## Not ported — `dev-tool`

| Module | LOC | Context | Reason |
| --- | --- | --- | --- |
| `diagnostika.py` | 209 | operability | Local diagnostic; replaced by CI checks, health endpoints and CloudWatch |
| `doctor.py` | 202 | operability | Local diagnostic; replaced by CI checks, health endpoints and CloudWatch |
| `selftest.py` | 143 | operability | Local diagnostic; replaced by CI checks, health endpoints and CloudWatch |
| `support_bundle.py` | 122 | operability | Local diagnostic; replaced by CI checks, health endpoints and CloudWatch |
| `runtime_diagnostic.py` | 98 | operability | Local diagnostic; replaced by CI checks, health endpoints and CloudWatch |
| `provider_diagnostics.py` | 78 | operability | Local diagnostic; replaced by CI checks, health endpoints and CloudWatch |
| `release_gate.py` | 71 | operability | Release/handoff packaging check; replaced by CI quality gates |
| `ingest_cli.py` | 69 | data-library | Batch ingest CLI; becomes an API + worker path |
| `coherence_audit_v17.py` | 64 | operability | Local diagnostic; replaced by CI checks, health endpoints and CloudWatch |
| `release_integrity.py` | 58 | operability | Release/handoff packaging check; replaced by CI quality gates |
| `NPC_AI_DIAGNOSTIKA.py` | 57 | operability | Local diagnostic; replaced by CI checks, health endpoints and CloudWatch |
| `release_scorecard.py` | 57 | operability | Release/handoff packaging check; replaced by CI quality gates |
| `handoff_verify.py` | 48 | operability | Release/handoff packaging check; replaced by CI quality gates |
| `claude_code_respondent_smoketest.py` | 44 | operability | Smoke test; replaced by the pytest suite and CI startup smoke job |
| `secret_scan.py` | 43 | operability | Release/handoff packaging check; replaced by CI quality gates |
| `claude_code_setup_smoketest.py` | 32 | operability | Smoke test; replaced by the pytest suite and CI startup smoke job |
| `backend_smoketest.py` | 29 | operability | Smoke test; replaced by the pytest suite and CI startup smoke job |
| `golden_path_test.py` | 28 | operability | Smoke test; replaced by the pytest suite and CI startup smoke job |
| `portability_check.py` | 27 | operability | Release/handoff packaging check; replaced by CI quality gates |
| `workflow_report.py` | 27 | operability | Local diagnostic; replaced by CI checks, health endpoints and CloudWatch |
| `live_smoketest.py` | 26 | operability | Smoke test; replaced by the pytest suite and CI startup smoke job |
| `provider_parity.py` | 23 | operability | Smoke test; replaced by the pytest suite and CI startup smoke job |

## Not ported — `drop`

| Module | LOC | Context | Reason |
| --- | --- | --- | --- |
| `prototype_server.py` | 533 | api | Zero-framework local prototype server; superseded by FastAPI |
| `claude_code_setup.py` | 378 | ai-runtime | Local-machine SDK shim; unnecessary server-side |
| `launcher_bootstrap.py` | 378 | runtime | Windows desktop launcher/supervisor; replaced by containers + ECS |
| `legacy_job_dispatch.py` | 230 | workflow | Pre-17.8 compatibility shim |
| `NPC_JEN_CLAUDE_CODE.py` | 227 | ai-runtime | Single-provider mode that disabled the approval queue and reservations; conflicts with no-silent-fallback |
| `desktop_launcher.py` | 116 | runtime | Windows desktop launcher/supervisor; replaced by containers + ECS |
| `project_migration.py` | 83 | pipeline | One-off migration of the prototype's own SQLite store |
| `anthropic_compat.py` | 68 | ai-runtime | Local-machine SDK shim; unnecessary server-side |
| `spawn_env.py` | 36 | runtime | Windows desktop launcher/supervisor; replaced by containers + ECS |
| `env_loader.py` | 32 | runtime | Local .env loader; replaced by typed config + Secrets Manager |
| `edition_config.py` | 25 | runtime | Local .env loader; replaced by typed config + Secrets Manager |
| `research_os_config.py` | 16 | runtime | Local .env loader; replaced by typed config + Secrets Manager |

## Data assets

Not modules, and not yet placed. The prototype carries roughly 70 MB of
payload that the production system needs a deliberate home for:

| Asset | Size | Open question |
| --- | --- | --- |
| `FINALNI_KOMPLETNI_PANEL_v17_*.csv.gz` | 7 MB each | The 18,766 × 400 population panel. S3 with a version pointer, or a seeded fixture? |
| `demo_library/` | 33 MB | Bundled demo projects; product feature or test fixture? |
| `audit_reference/` | 7.3 MB | Validation evidence; must stay auditable |
| `SPECIAL_PANELS/` | 2 MB | Special-audience panels |
| `*_AUDIT_v17*.csv`, `FINAL_SOURCE_CATALOG_v17.csv` | ~2 MB | Provenance and latent-factor audits |

None of this is in the repository, and it should not be committed as-is.
Deciding where it lives is a prerequisite for Phase 8, not a detail.

## Regenerating

The JSON is edited by hand when a disposition changes. The `loc` and
`docstring` fields are descriptive only; the test asserts coverage, not them.
