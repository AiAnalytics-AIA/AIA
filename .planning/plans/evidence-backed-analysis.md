---
status: in-progress
chunks:
  - "[x] 0. This plan"
  - "[x] 1. Instrument items as evidence fields: evidence/instrument.py"
  - "[x] 2. Native evidence and inputs: analysis/native.py"
  - "[x] 3. Harness: analysis/harness.py"
  - "[x] 4. Artifact contract and graph spec: analysis/artifact.py, analysis/steps.py"
  - "[x] 5. Scoped sources and reconstruction: application/analysis_results.py (PR A, #76)"
  - "[ ] 6. Executor: aia_executors/analysis.py over the real worker and recorded Bedrock"
  - "[ ] 7. Decision-table parity against the vendored evidence_validator.py (M17)"
  - "[ ] 8. Documents, and the Doc follow-up for the shared files (PR B, #80)"
---
# Evidence-backed analysis of native research runs

**Owner:** analysis (Job 3) · **Started:** 2026-09-27

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

- [x] 0. This plan, and a PROGRESS row until #89 retired that file. — docs only
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
      tests: `test_analysis_results.py` (20; SQLite and PostgreSQL 16), upstream steps driven
      through the real workflow repository. Sources are identified by content
      (`ModuleSources.content`), as the research steps reuse them: an identical earlier
      revision's specification, and -- after an edit outside the questionnaire -- the
      earlier run's dataset and aggregate. Both were refused until
      `test_a_specification_reused_from_an_identical_revision_is_the_runs_own` and
      `test_an_aggregate_reused_over_the_same_questionnaire_is_the_runs_own` (**PR A ends
      here**)
- [ ] 6. Executor: `aia_executors/analysis.py`, generator with turn checkpoints, config,
      registry; real worker over recorded Bedrock: complete, blocked after 3 calls,
      schema failure counted, client-facing and unconfigured and Class A refused with no
      call, uncertain → recovery without resend, cancel between turns, budget park, retry
      reuse, changed research questions rerun, recovery replays checkpoints. — code + tests
- [ ] 7. Decision-table parity against the vendored `evidence_validator.py` (M17). — tests +
      parity matrix
- [ ] 8. Documents: `docs/architecture/analysis.md` and the parity matrix on the branch; what
      ARCHITECTURE, the CLAUDE map, AGENTS, open items and the overview need goes under
      *Doc follow-up* below (#89); draft PRs. (**PR B**: chunks 6–8, stacked on PR A)

## Decisions owed (not engineering)

- **ANL-1** Approve (or replace) the instrument evidence policy v1 for internal use, and
  decide whether any instrument evidence may ever be client-facing, and on what origin.
- **ANL-2** Should support that is `INDICATIVE` (or a thin run) pause analysis for a person
  (`donor_qc`'s `review_if_warning`)?
- **ANL-3** Port `qc.kontrola` with its thresholds as warnings, as gates, or not at all.

## Findings

None open. Building PR B against this contract found two defects in it: a reused
specification and a reused aggregate, each refused as not the run's own. Codex found three
more, two on #76 and one on #80. The fix for #80's is on this branch too: in `1caa26f`, a
corrupt source is refused by its reason, without its storage key
(`test_a_corrupt_source_is_refused_by_reason_without_its_storage_key`). Each was reproduced
by a test that failed first, then fixed here. The first four are listed with their tests
under *Chunks* (5) and *Review outcome*. PR A closes and changes no existing OI.

## Doc follow-up

What the shared documents need once this feature merges. Until #89 its branches made these
edits themselves; the docs PR applies them now. The text is exact.

### PR A (#76)

**`CLAUDE.md` § 2, the map.** Under `domain/evidence/`, after `admission.py`:

```text
      instrument.py         A Study's own questionnaire items as evidence fields: declared
                            from the run's record, modelled, aggregate only, INTERNAL_ONLY
```

Under `domain/analysis/`, after the `analysis/` line itself:

```text
      native.py             A native run's specification + aggregate -> evidence table,
                            instrument policy, MISSING certificate; research questions; preflight
      harness.py            One module turn = one governed request: agent aia.analysis.module,
                            no gateway schema repair (<= 3 calls a module), Class C/A, lineage
      artifact.py           The stored outcome (aia-analysis-module-artifact-1), turn
                            checkpoints, reuse keys; no claim is ever stored
      steps.py              The eight analysis nodes as data, for the research template
```

Under `application/`, after `analysis.py`:

```text
    analysis_results.py     A native run's analysis: its sources in scope, one module prepared,
                            outcomes reconstructed by re-admission (the reader Job 4 uses)
```

**`ARCHITECTURE.md`.** In the table of companion documents, after
`ai-step-executor-contract.md`:

```markdown
| [analysis.md](docs/architecture/analysis.md) | A native run's analysis: evidence from its artifacts, the stored outcome, reconstruction by re-admission |
```

In the `layer_check` table, after *a joint status is issued only by its loader*. The rule
itself is already in `tools/layer_check.sh`:

```markdown
| the API, worker and executors never build field policy or a joint status (no `FieldPolicyBook(`, `FieldPolicy(`, `load_joint_status(`, instrument declaration or dictionary loader in `apps/`) | A permissive policy book for a questionnaire, or a certificate for a run with no panel, presented as the authority a claim rests on |
```

In § 4, after the research Sociomap bullet, the one that ends "…which refuses it and fails
closed on a missing status.":

```markdown
- **A native run's analysis is internal, and an outcome is re-admitted whenever it is
  read** ([analysis.md](docs/architecture/analysis.md)). The Study's own questionnaire
  items become evidence fields only from what the run recorded
  (`domain/evidence/instrument.py`): modelled, aggregate only, `INTERNAL_ONLY`, which the
  claim gate refuses client-facing whatever the certificate or origin says. A run with no
  panel has no certificate, and says so (`MISSING`). A stored module outcome holds the
  accepted draft, never claims: `application/analysis_results.py` rebuilds the evidence
  from the run's own artifacts, requires every fingerprint to match and puts the draft
  through the gate again, so a file cannot mint an `AdmittedClaim`.
```

**`docs/architecture/README.md`**, in the companion table, after
`ai-step-executor-contract.md`:

```markdown
| [analysis.md](analysis.md) | A native run's analysis: evidence from its artifacts, the stored outcome, reconstruction by re-admission |
```

**`.planning/overview.md`.** A row for #76 in *Open pull requests*, from its description.
Nothing else: this feature's status is the front-matter above.

## Review outcome

Filled in when the plan is archived. Findings so far:

- **Codex on #76 @ `986a55e`, two P2s, each reproduced before its fix.**
  1. A source whose bytes pass their hash but hold another shape (not an object, or a
     specification this system cannot read) raised `AttributeError` or `ValidationError`
     out of `native_sources`, so a reader got an exception, not a refusal. Now it is
     refused as `specification_shape` or `aggregate_shape`, and an earlier specification
     of another shape is simply not the run's (`aggregate_lineage`). Beside it, the same
     class of escape in `_reconstruct`: an evidence adapter's refusal left the API as
     `NativeEvidenceRefused`, and is now `evidence_refused`. Tests in
     `test_analysis_results.py`: `test_a_source_of_another_shape_is_refused_not_raised`,
     `test_an_earlier_specification_of_another_shape_is_not_the_runs`,
     `test_a_source_that_became_another_shape_refuses_the_reconstruction` and
     `test_evidence_the_adapter_now_refuses_refuses_the_reconstruction`.
  2. A specification that names the run's revision was never compared with the
     revision's content. When this system's compiler produced it, it is now compiled
     again and compared (`design_revision`). Another compiler's cannot be, and a run
     parked across a deploy must still be read, so it is held to the revision it
     records. Tests: `test_a_specification_compiled_from_other_content_is_refused_whatever_it_records`
     and `test_another_compilers_specification_is_held_to_the_revision_it_records`.
