# Analysis of a native research run

How a completed research run's artifacts become the eight analysis modules, what an
outcome is when stored, and how a reader gets it back. The plan, with the reference
mapping and the decisions owed, is
[`.planning/plans/evidence-backed-analysis.md`](../../.planning/plans/evidence-backed-analysis.md).

**State:** the contract, the inputs, the reconstruction (`aia_core`) and the executor
(`aia_executors/analysis.py`) exist and are tested under the real worker over recorded
Bedrock exchanges. Nothing registers the executor in the production worker, adds the
nodes to the research template, deploys or enables it.

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
as `specification_shape` or `aggregate_shape`, never raised. The specification is also
held to the revision's content: one this system's compiler produced must be exactly the
run's revision compiled again (`compile_design` is deterministic and the revision
immutable), so one that names the run's revision but was compiled from another
questionnaire is refused (`design_revision`). Another compiler's specification cannot be
compiled again here, and a run parked across a deploy must still be read, so it is held
to the revision it records. A source whose bytes fail their hash, or whose object is
gone -- the AI runtime's dataset included, which `dataset_material` reads for its lineage
-- is refused as `source_corrupt`, and the message names no storage key: it reaches a
step's error and a reader. The read has marked the artifact CORRUPT in the caller's
transaction, which keeps that mark only by ending without raising (OI-77).
Anything else raises `ReconstructionRefused(reason)`:

| `reason` | When |
| --- | --- |
| `run_not_found` | No such research run in the Study in scope |
| `not_in_run`, `no_outcome` | The run has no such module, or its step has not succeeded |
| `outcome_not_found`, `outcome_invalid`, `outcome_corrupt`, `contract` | The artifact is missing, of another type or status, fails its hash, or breaks the contract |
| `sources_refused`, `sources_moved` | The run's sources cannot be loaded (the message starts with the source's reason: `design_revision`, `aggregate_lineage`, `source_corrupt`, `specification_shape` …), or are not the ones recorded |
| `evidence_refused` | The recorded sources no longer make evidence (a later evidence adapter refuses them) |
| `fingerprint_mismatch` | Evidence, policy, research questions, method status or harness moved |
| `readmission_refused` | The stored draft no longer passes the gate |

Reading needs `VIEW_RESULTS`; an `INTERNAL` outcome needs `EDIT_STUDY` too.

## Where it runs: `domain/analysis/steps.py`

For the workflow integration to add to the `research` template: eight nodes
`analysis_<module>`, kind `research_analysis`, stage `ANALYSIS`, each depending on
`aggregate` **only**, step input `{"analysis_module", "analysis_surface"}` (no default
surface: a step without one fails), `max_attempts` 3. A gate refusal is an outcome, so a
`BLOCKED` module never stops another. A step that *fails* (a broken upstream, a provider's
permanent refusal) fails the run by the engine's rule (`derive_run_status`: a `FAILED`
step makes the run `FAILED`, and a failed run's other steps are no longer claimed); whether
analysis nodes should be exempt from that is the integration's decision.

## The executor: `aia_executors/analysis.py`

`AnalysisModuleExecutor.execute`, per step:

1. The module and surface from the step input; the run's sources (`native_sources`) and the
   prepared module (`prepare_module`), in one lease-fenced transaction.
2. A stored outcome under the same reuse key is returned (`reused: true`, no call).
3. The deterministic preflight: if it refuses, a `BLOCKED` outcome with 0 calls is stored,
   configured or not.
4. Unconfigured (no gateway and `AnalysisConfig`): the step parks.
5. The runner (`run_analysis_module`) drives the turns. Each turn: stop if cancelled; replay
   a stored `research_analysis_turn` for exactly this request, or check the request fits the
   model window (the first with room for a repair), ask the gateway's preflight once (a
   refusal parks), send it through `StepModelCaller` (one reservation, settled once), and
   store the answer at once. A schema failure is an answer (`SCHEMA_INVALID`); any other
   failure is the worker's.
6. The outcome is stored with its turns as dependencies; the step's output names it.

| Situation | Step ends | `error.reason` |
| --- | --- | --- |
| Preflight refuses (client-facing, no evidence, no question) | `SUCCEEDED`, outcome `BLOCKED`, 0 calls | -- |
| Gate refuses the third draft | `SUCCEEDED`, outcome `BLOCKED`, 3 calls | -- |
| No gateway or configuration | `WAITING_PROVIDER` | `analysis_unconfigured` |
| The gateway would refuse the material (Class A, lineage, capability) | `WAITING_PROVIDER` | the gateway's, e.g. `egress_route_not_approved_for_class` |
| The study's budget cannot hold a turn's reservation | `AWAITING_BUDGET` | -- |
| Quota / throttling | `WAITING_PROVIDER` (resumes after `retry-after`) | the gateway's |
| A call whose outcome is unknown | `RECOVERY_REQUIRED`; a person resumes it, answered turns replay | -- |
| A turn larger than the model window | `FAILED` before any reservation | `context_window_exceeded` |
| Upstream artifacts missing or inconsistent | `FAILED` | `native_sources`' reason |

`AnalysisConfig.from_settings(settings, max_output_tokens=..., reservation_usd=...)` refuses
an output cap above the model's, a reservation below one call at the model's ceilings, and
a policy that does not bind `RESEARCH_REASONING`. Today that capability is bound only with
the design agents' switch (`AIA_AI_RESEARCH_AGENTS_ENABLED`); an analysis switch of its own,
its keys and its registration are the activation work's, not this module's.

## Against the unit's gate

`test_analysis_gate_parity.py` imports the unit's `evidence_validator.py` from the frozen
tree (pinned by SHA-256) and puts the same drafts, over the same aggregate, to both gates.
AIA refuses everything the unit refused, and more: a value not copied exactly, a value
given as text, a number in the prose that no cited claim holds, a claim on a row the
fidelity rule or support removed. It admits two things the unit refused -- a finding that
states no number and cites nothing, and a module with no finding -- and those wait on
decision ANL-4 rather than being called intentional.

## Not here

Run QC (`qc.kontrola`), the `donor_qc` review gate, external verification, reality
alignment and the challenger pass are absent; the plan's reference mapping says which
and why. Decisions owed: ANL-1 (the instrument policy for internal use, and any client
use), ANL-2 (should thin support pause for a person), ANL-3 (the QC thresholds), ANL-4
(must every finding cite evidence).
