# Analysis of a native research run

How a completed research run's artifacts become the eight analysis modules, what an
outcome is when stored, and how a reader gets it back. The plan, with the reference
mapping and the decisions owed, is
[`.planning/plans/evidence-backed-analysis.md`](../../.planning/plans/evidence-backed-analysis.md).

**State:** the contract, the inputs and the reconstruction exist in `aia_core`; the
executor is in PR B. Nothing is registered in the production worker, added to the
research template, deployed or enabled.

## The rule

A model drafts one module; the evidence gate decides; only admitted claims reach a
result (`domain/analysis/`, `application/analysis.py`, unchanged). This document is
about what surrounds that rule for a *native* run -- one AIA executed itself, whose
respondents are simulated.

**Internal fictional interpretation is produced. Client-facing evidence is refused.**
Every native run's respondents are simulated (`NON_EVIDENCE_ORIGINS` holds every
`DataOrigin`), so every module runs for the `INTERNAL` surface, is labelled so, and is
read only by the Study's researchers -- the treatment the internal Sociomap already
has (ADR 0016 decision 6).

## Inputs: `domain/analysis/native.py`

The run's compiled specification and its aggregate become:

- **An evidence table.** Per item (a question, or one object of a tracked set): valid
  n, effective n, and each share (`pct:<answer>`), or the mean and top-two-box of a
  scale. Values, decimals and 95 % intervals are the aggregate's, copied. Support is the
  unit's donor support re-assessed by `assess_support` (which also needs 50 valid
  answers, so it is never looser). A row is **removed, keeping only why**, when support
  is suppressed, when the unit's fidelity rule refuses the question (`REFUSE`: absolute
  willingness to pay or market size), or when an estimate has no interval containing
  it. Every row is `MODELED`, `AGGREGATE`, carries the modelled-value disclosure and the
  dataset's origin. Open-answer verbatims and the Sociomap are not evidence.
- **A field policy.** The Study's own questions have no dictionary entry, so
  `domain/evidence/instrument.py` declares them: one fixed policy
  (`aia-instrument-evidence-1`) for items answered by simulated respondents -- modelled,
  aggregate only, individual value modelled, never a measured fact, and `INTERNAL_ONLY`.
  Its status is an `InstrumentStatus`, never one of the dictionary's 22, so no dictionary
  can declare one. Any other origin has no policy and refuses.
- **A joint status.** A native run has no population panel, so no `CORE_JOINT_STATUS`
  certificate: `load_joint_status(None)` answers `MISSING`, which permits nothing
  client-facing. Validation is `None`, so every result says `METHOD_STATUS_PENDING`.
- **Research questions**, from the Design Revision as the unit reads them:
  `research_plan.research_questions`, else `objectives`, else `goal`, at most eight.

**Client-facing claims are refused three independent ways**: the claim gate's
`FIELD_INTERNAL_ONLY` (whatever the certificate or origin), `SYNTHETIC_DATA_ORIGIN`,
and the missing certificate. The preflight (`native_preflight`) refuses the surface,
an empty table and a research-questions module with no question before anything is
reserved or sent.

## The request: `domain/analysis/harness.py`

One agent, `aia.analysis.module`, on `RESEARCH_REASONING`, output contract
`AnalysisDraft`, **no gateway schema repair**. A schema failure returns to the runner as
an `InvalidStructuredOutput`, which the gate refuses and the next turn shows the model,
so a module makes at most `1 + MAX_REPAIRS = 3` calls, each a turn the runner counted.
Class C only when the operator declared the client fictional **and** every respondent is
simulated; otherwise Class A, which the approved route refuses. Lineage is the dataset's,
as its artifact recorded it (`dataset_material`); an undeclared lineage is refused by the
gateway. The harness frame tells the model it interprets simulated respondents on a
stated surface; it is versioned and fingerprinted, and enforces nothing the gate does not.

## The stored outcome: `domain/analysis/artifact.py`

`research_analysis_module`, contract **`aia-analysis-module-artifact-1`**, on the Study's
owned design project (read only through the run, ADR 0016):

| Field | Meaning |
| --- | --- |
| `module_id`, `ordinal`, `artifact_name` | Which of the eight (`ANALYSIS_01_EXECUTIVE` …) |
| `outcome` | `COMPLETED` (with `draft`, no violations) or `BLOCKED` (no draft, ≥ 1 violation) |
| `surface`, `labels` | `INTERNAL` today; simulated respondents; internal only |
| `method_status` | Computed by code, never by the model |
| `input_fingerprint` | The domain module fingerprint (`module_input_fingerprint`) |
| `reuse_fingerprint` | The reuse key: module fingerprint + sources by content + harness |
| `draft` | The accepted `AnalysisDraft`. **Never a claim** |
| `violations` | Every reason a blocked module stopped (code, subject, detail) |
| `attempts`, `calls` | Model turns (0 when the preflight blocked) and one record per turn: call id, provider request id, model, route, policy, cost, whether it was replayed from a checkpoint |
| `sources` | The run's specification, dataset and aggregate by id and SHA-256; the Design Revision |
| `evidence`, `authority`, `harness` | Table fingerprint, rows, suppressed refs, origin; policy book and certificate identity, system fingerprint; harness, prompt and schema identity, language, repair bound |
| `produced_by`, `runtime_version` | The run, step, attempt and build that stored it |

Parsing is strict JSON semantics against closed models (`parse_module_artifact`). One
turn's answer is checkpointed as `research_analysis_turn` (`aia-analysis-turn-1`).

## Reading it back: `application/analysis_results.py`

```python
reconstruct_module(session, scope, store, *, run_id, module_id) -> ReconstructedModule
reconstruct_run(session, scope, store, *, run_id) -> RunAnalysis   # .complete: all eight COMPLETED
```

A `ReconstructedModule` holds `result: AnalysisModuleResult | None` (claims minted by the
gate *during reconstruction*), `violations`, the rebuilt `inputs` (whose table carries
the suppressed refs for `EvidenceLedger.from_claims(table=...)`), and the parsed record.
Reconstruction parses the artifact, re-loads the run's sources and requires them to be
the recorded ones by content, rebuilds the inputs, requires every fingerprint, the
harness and the method status to match, and puts a completed module's draft through the
gate again. Content, not names: the research steps reuse artifacts by fingerprint, so a
design edited and edited back runs on the earlier revision's specification, a design
edited only outside its questionnaire (its research questions) reuses the earlier run's
dataset and aggregate, and an outcome reused by such a run keeps the ids, revision and
`produced_by` it was computed under. A source whose bytes pass their hash but hold
another shape -- not an object, or a specification this system cannot read -- is refused
as `specification_shape` or `aggregate_shape`, never raised.
Anything else raises `ReconstructionRefused(reason)`:

| `reason` | When |
| --- | --- |
| `run_not_found` | No such research run in the Study in scope |
| `not_in_run`, `no_outcome` | The run has no such module, or its step has not succeeded |
| `outcome_not_found`, `outcome_invalid`, `outcome_corrupt`, `contract` | The artifact is missing, of another type or status, fails its hash, or breaks the contract |
| `sources_refused`, `sources_moved` | The run's sources cannot be loaded (the message starts with the source's reason: `design_revision`, `aggregate_lineage`, `specification_shape` …), or are not the ones recorded |
| `evidence_refused` | The recorded sources no longer make evidence (a later evidence adapter refuses them) |
| `fingerprint_mismatch` | Evidence, policy, research questions, method status or harness moved |
| `readmission_refused` | The stored draft no longer passes the gate |

Reading needs `VIEW_RESULTS`; an `INTERNAL` outcome needs `EDIT_STUDY` too.

## Where it runs: `domain/analysis/steps.py`

For the workflow integration to add to the `research` template: eight nodes
`analysis_<module>`, kind `research_analysis`, stage `ANALYSIS`, each depending on
`aggregate` **only** (a blocked or failed module strands no other), step input
`{"analysis_module", "analysis_surface"}`, `max_attempts` 3.

## Not here

Run QC (`qc.kontrola`), the `donor_qc` review gate, external verification, reality
alignment and the challenger pass are absent; the plan's reference mapping says which
and why. Decisions owed: ANL-1 (the instrument policy for internal use, and any client
use), ANL-2 (should thin support pause for a person), ANL-3 (the QC thresholds).
