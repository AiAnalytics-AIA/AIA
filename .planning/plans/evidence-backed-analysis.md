# Evidence-backed analysis of native research runs

**Status:** in progress · **Owner:** analysis (Job 3) · **Started:** 2026-09-27

Chunk 5 of [research-agent-workflows.md](research-agent-workflows.md), in the analysis
half; the report half is [report-docx.md](report-docx.md) R10–R11 (Job 4).

## Problem

A native research run stops at `aggregate` and `sociomap`. The eight analysis modules
(`domain/analysis/`) and the evidence-gated runner (`application/analysis.py`) exist, but
nothing turns a run's artifacts into their inputs, nothing calls a model for them, and
nothing stores or reloads their outcome. Three facts decide the shape:

- **No production code builds an `EvidenceRow`** (`grep -rn "EvidenceRow(" packages apps`
  outside tests is empty @ `ceee2dc`). The admission gate was written for population
  fields; a native run's numbers are answers to the Study's own questionnaire.
- **A questionnaire item has no field policy.** The dictionary covers the 400 panel
  fields; a survey answer is a runtime column with no entry, which the gate refuses
  (`FIELD_UNDECLARED`, `domain/evidence/claims.py:187-190`). So today no native number can
  be admitted on any surface.
- **Every native run is fictional.** `NON_EVIDENCE_ORIGINS` holds every `DataOrigin`
  (`domain/fieldwork.py:66-68`), and the gate refuses them client-facing
  (`admission.py:245-252`); there is no population panel, so there is no
  `CORE_JOINT_STATUS` certificate either.

## Approach

**Internal fictional interpretation is produced; client-facing evidence is refused.** The
same shape as the research Sociomap (computed, `INTERNAL_ONLY`, ADR 0016 decision 6).

1. **Instrument items become declared evidence fields**
   (`domain/evidence/instrument.py`). An item answered by simulated respondents gets one
   fixed, versioned policy (`aia-instrument-evidence-1`): modelled, aggregate only,
   individual value modelled, never a measured fact, internal analysis only. It is
   derived from facts the run records (the Design Revision's items, the dataset's origin),
   never from a dictionary, so no population dictionary can declare one. Any other origin
   has no policy and refuses.
2. **Native evidence from native artifacts** (`domain/analysis/native.py`): the compiled
   specification and the aggregate become an `EvidenceTable` — one row per
   share, mean, top-two-box, n and effective n — with the unit's own donor support, AIA's
   `assess_support`, the bootstrap interval, the fidelity rating (`REFUSE` removes a
   question), and the dataset's origin. Basis is always `MODELED`. The joint status is the
   honest *missing* certificate (`load_joint_status(None)`); validation is `None`, so every
   result is stamped `METHOD_STATUS_PENDING`.
3. **A deterministic preflight** blocks a module before any reservation: no citable
   evidence, client-facing on fictional data, research questions module with no question.
4. **One harness over `StepModelCaller`** (`domain/analysis/harness.py`): `RESEARCH_REASONING`,
   output contract `AnalysisDraft`, **zero gateway schema repairs**. A schema failure
   returns to the runner as an invalid draft, which its own repair loop handles, so a module
   makes at most `1 + MAX_REPAIRS = 3` calls. Class C only for a declared-fictional client
   with fictional respondents; otherwise Class A, which the approved route refuses.
5. **One recoverable step per module** (`aia_executors/analysis.py`, kind
   `research_analysis`): reuse on the full input fingerprint, a checkpoint per model turn
   (a retry replays recorded turns and never pays twice for them), `COMPLETED` and `BLOCKED`
   both stored as outcomes, provider failures left to the worker's recovery rules.
6. **A versioned artifact and a reconstruction API** (`domain/analysis/artifact.py`,
   `application/analysis_results.py`). The artifact stores the accepted draft, never
   claims; reconstruction re-reads the run's sources in scope, rebuilds the evidence,
   re-checks every fingerprint and re-admits the draft through the gate, so stored JSON
   cannot mint an `AdmittedClaim`.

Rejected: a permissive policy book or a dictionary status stamped on survey items (both
are guesses stamped as authority, A5); blocking every native module until a decision
(the internal path is already accepted for the Sociomap and the user asked for it); a
gateway schema repair per turn (it multiplies with the runner's evidence repairs: up to
six calls a module nobody sees).

## Trade-off accepted

Internal fictional interpretation runs on an AIA-declared instrument policy that no
methodology owner has approved, and in exchange every client-facing path stays refused by
three independent gates until one does.

## Reference mapping (frozen 18.6.6 unit)

All anchors are in `legacy/npc-panel-18.6.6/app/` @ `ceee2dc`.

| Reference behaviour | Anchor | State in AIA |
| --- | --- | --- |
| Evidence table from `vysledky` (distribution, mean, top-2-box) | `analysis_agent.py:25-50` | **Implemented** here: `native.py`, plus n and effective n |
| Research questions: `research_plan.research_questions` → `objectives` → `goal`, ≤ 8 | `analysis_agent.py:12-22` | **Implemented** here, same order and cap |
| Analysis evidence integrity (`validate_analysis`: refs, metrics, values ±0.051, coverage ≥ 0.95, score ≥ 90) | `evidence_validator.py:39-60` | **Implemented, stricter**: `check_analysis_draft` (exact values, 100 % coverage). Decision-table parity: chunk 7 |
| Eight modules in `MODULE_ORDER`, one durable module per job | `analysis_agent.py:124`, `:154-184` | **Implemented**; AIA gates *each* module and repairs it ≤ 2 times. The unit's modular path drafted once, unvalidated, and gated only at assembly (`:186-216`) |
| Repair ≤ 2, `allow_fallback=False`, keep the better-scoring draft | `analysis_agent.py:86-121` | **Implemented** in the runner (from the unit's monolithic `analyze_results`, which the standard workflow does not run); AIA judges each draft alone and has no score |
| Challenger/editor second pass (non-`ECONOMY`) | `analysis_agent.py:84` | **Absent**: only the monolithic path had it |
| Assembly of the eight modules (`interpret`) | `analysis_agent.py:186-216`, `worker_job.py:591-612` | **Reconstruction** returns all eight outcomes; no assembly step (Job 4 composes) |
| Donor support per cell (SUPPRESS / INDICATIVE / REPORTABLE) | `uncertainty.py:114`, ported in `domain/research_aggregate.py` | **Implemented**: the aggregate's donor support, then `assess_support`, which is at least as strict |
| `donor_qc` node, `review_if_warning` | `workflow_engine.py:23`, `worker_job.py:558-566` | Support **implemented** per row; the **human review gate is absent** — decision ANL-2 |
| Fidelity rating (`REFUSE` absolute WTP/market size; AMBER without holdout) | `fidelity.py:22-70` | **Implemented**: `REFUSE` removes the question's rows; AMBER is the pending method status |
| Run QC (`qc.kontrola`: error rate, don't-know share, concentration, straightlining, duplicates, entropy) | `qc.py:70-262` | **Absent** (`analysis.qc` NOT_STARTED); its thresholds are the author's own calibration (`qc.py:24`) — decision ANL-3 |
| Relational batteries as evidence (`battery:<id>`, `map:` metrics) | `analysis_agent.py:66`, `evidence_validator.py:17-23` | **Absent**: map metrics are not allowed metrics, and the Sociomap is `INTERNAL_ONLY` (D6) |
| Background research as context | `analysis_agent.py:66` | **Absent** until Deep Research (Job 5); `external_context` is empty and fingerprinted |
| External verification (`verify`, two web agents) | `result_context.py:196-278`, `worker_job.py:648-686` | **Absent**: needs owned search/fetch (Job 5, DR-2) and a method decision |
| Reality alignment and calibration profile (`alignment`) | `reality_alignment.py:40-90` | **Absent**: needs verification; a calibration rule is a methodology change |
| Holdout validation (`validation_gate.py`, `holdout_*`) | `validation_gate.py:57` | **Absent** (`governance.holdout`); every result says `METHOD_STATUS_PENDING` |

This job completes **interpretation** (the eight modules, internal). It does not complete
validation (only support and suppression), verification or alignment.

## Contracts published for other jobs

- **Artifact** `research_analysis_module`, contract `aia-analysis-module-artifact-1`
  (`domain/analysis/artifact.py`); per-turn checkpoints `research_analysis_turn`.
- **Reconstruction** `application/analysis_results.py`: `reconstruct_module`,
  `reconstruct_run` → `ReconstructedModule` (a fresh `AnalysisModuleResult` or the
  recorded violations). Refusals are `ReconstructionRefused` with a reason code (the table in
  `docs/architecture/analysis.md`).
- **Graph for Job 6** (`domain/analysis/steps.py`): eight nodes `analysis_<module>`, kind
  `research_analysis`, stage `ANALYSIS`, each depending on `aggregate` only (a blocked or
  failed module strands no other), step input `{"analysis_module", "analysis_surface"}`,
  `max_attempts` 3 (turn checkpoints make a retry free for recorded turns).
- **Composition for Job 6 / Job 1**: `analysis_registry(store, build, gateway, config)`;
  `AnalysisConfig` from the AI runtime settings plus an analysis switch, output cap and
  reservation that must cover one call at the model's ceilings. The `ai_runtime.py`
  settings and the production registry are not edited here.

## Chunks

- [x] 0. This plan; PROGRESS row. — docs only
- [x] 1. Instrument items as evidence fields: `evidence/instrument.py`, `InstrumentStatus`
      beside the dictionary's statuses, `FieldPolicy` typed for both, `ClaimRule.INTERNAL_ONLY`
      refused client-facing by the claim gate (`FIELD_INTERNAL_ONLY`); layer rule: no app
      builds a policy book or a joint status (probe-verified to fail). — code + tests:
      `test_evidence_instrument.py` (19); the gate's parity against the reference's
      `field-policy.json` and methodology ledger still holds (`test_evidence_gate_parity.py`,
      8 passed against `AIA-reference` @ `05ef950`)
- [x] 2. Native evidence and inputs: `analysis/native.py` (rows, support, intervals,
      fidelity, suppression, research questions, preflight). — code + tests:
      `test_analysis_native.py` (28), on a compiled design, the fixture dataset and the real
      aggregate
- [x] 3. Harness: `analysis/harness.py` (agent, request per turn, invalid-output marker,
      classification, lineage, identity). — code + tests: `test_analysis_harness.py` (14)
- [x] 4. Artifact contract and graph spec: `analysis/artifact.py`, `analysis/steps.py`. —
      code + tests: `test_analysis_artifact.py` (22), including the eight nodes joining the
      research graph as a valid DAG
- [x] 5. Scoped sources and reconstruction: `application/analysis_results.py`. — code +
      tests: `test_analysis_results.py` (18; SQLite and PostgreSQL 16), upstream steps driven
      through the real workflow repository. Sources are identified by content
      (`ModuleSources.content`): the compile step reuses an identical earlier revision's
      specification, which was refused until
      `test_a_specification_reused_from_an_identical_revision_is_the_runs_own` (**PR A ends
      here**)
- [ ] 6. Executor: `aia_executors/analysis.py`, generator with turn checkpoints, config,
      registry; real worker over recorded Bedrock: complete, blocked after 3 calls,
      schema failure counted, client-facing and unconfigured and Class A refused with no
      call, uncertain → recovery without resend, cancel between turns, budget park, retry
      reuse, changed research questions rerun, recovery replays checkpoints. — code + tests
- [ ] 7. Decision-table parity against the vendored `evidence_validator.py` (M17). — tests +
      parity matrix
- [ ] 8. Documents: ARCHITECTURE §3–4, CLAUDE map, AGENTS, `docs/architecture/analysis.md`,
      open items, PROGRESS; draft PRs. (**PR B**: chunks 6–8, stacked on PR A)

## Decisions owed (not engineering)

- **ANL-1** Approve (or replace) the instrument evidence policy v1 for internal use, and
  decide whether any instrument evidence may ever be client-facing, and on what origin.
- **ANL-2** Should support that is `INDICATIVE` (or a thin run) pause analysis for a person
  (`donor_qc`'s `review_if_warning`)?
- **ANL-3** Port `qc.kontrola` with its thresholds as warnings, as gates, or not at all.

## Review outcome

Filled in when the plan is archived.
