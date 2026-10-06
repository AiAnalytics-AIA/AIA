# ADR 0021 — Deep Research serves two methodological checkpoints: purpose, typed target and frozen lineage around a frozen engine

**Status:** Proposed — develop (2026-10-06). Implemented on `feature/dr-purpose-lineage`
([plan](../../../.planning/plans/deep-research-purpose-lineage.md); AIA-83, parent AIA-81).
**Amends** the lifecycle reading of [ADR 0017](0017-deep-research-external-retrieval.md):
Deep Research is not one stage pinned only to a Design Revision; its retrieval, grounding and
evidence decisions stand unchanged. **Builds on** [ADR 0007](0007-deterministic-tools.md) (no LLM
for deterministic computation), [ADR 0016](0016-research-execution-and-model-transmission.md)
(runs and their artifacts found only through the Study) and
[ADR 0019](0019-two-roles-and-human-ai-gates.md) (gate 1: a person applies an AI proposal).
**Date:** 2026-10-06

## Context

The engine is mature. After PR #166 it plans, investigates with agents and a lead, fans tracks out
across workers, climbs an acquisition ladder, verifies independently, grounds every finding in a
captured snapshot, scores confidence by code, recovers a released track without sending a call
twice, and seals an `EvidenceBundle`. All of it was built as **one operation**: a
`DeepResearchRequest` frozen around a Design Revision (`domain/deep_research/contracts.py:236-263
@ 579b7ab`), enqueued by `DeepResearchRuns.start` under the key
`deep_research:{revision}:{request fingerprint}` (`application/deep_research.py:226-228 @ 579b7ab`),
sealed into a bundle that carries the same design lineage (`bundle.py:112-142`).

AIA's methodology needs it at two different points, and a run could not say which:

```
Study / proposed design
        ↓
DESIGN_RESEARCH                 ← context, constructs, benchmarks, gaps → proposals
        ↓
human-reviewed proposals → a new Design Revision (gate 1)
        ↓
Research Design / Questionnaire / Audience / Dimensions / Sample Plan
        ↓
METHODOLOGY FREEZE
        ↓
Population / Fieldwork → deterministic Aggregation / Validation / Analysis
        ↓
deterministic Sociomapping
        ↓
INTERPRETATION_RESEARCH         ← corroborate, challenge, benchmark, explain
        ↓
evidence-aware Report → human review / approval → Delivery
```

Deep Research is a governed evidence service used at two checkpoints, not an eighth stage.

## Decision

1. **Two purposes, explicit.** `DeepResearchPurpose` (`domain/deep_research/integration.py`):

   - **`DESIGN_RESEARCH`** runs before the methodology freeze. It may research market and category
     context, terminology, regulation, hypotheses, established constructs, possible questionnaire
     topics, audience definitions, analytical dimensions, benchmarks and evidence gaps. Its
     authority is **advisory**: it may produce *proposals*; it may not write the Research Design,
     Questionnaire, Audience, Dimensions or Sample Plan. A person accepts, modifies or rejects a
     proposal into a new, explicit Design Revision (ADR 0019 gate 1); only that revision is
     research truth.
   - **`INTERPRETATION_RESEARCH`** runs only against immutable research outputs that already exist.
     It may corroborate, challenge or benchmark a result, research an anomaly or an unexpected
     segment, contextualise a Sociomap relationship, and identify explanations, contradictions and
     gaps. It has **no** authority over the deterministic chain: respondent and population data,
     bindings, weights, aggregates, calculated dimensions, validation, statistics, segment
     membership, canonical Sociomap coordinates, geometry, terrain and object relationships, and
     deterministic findings are never changed.

   This is code, not prompt wording: `authority_of(purpose)` lists what each may propose and
   write — its own `deep_research_*` evidence artifacts, nothing else; `require_may_write` refuses
   a design or any `DETERMINISTIC_ARTIFACT_TYPES` for both; the module refuses to import beside an
   engine whose artifact types overlap them; and `layer_check` keeps the Deep Research executors,
   domain and service from naming any writer of a design, a Study's working content or a research
   run's results.

2. **Purpose, target and lineage are three things.** The *purpose* says why. The *target*
   (`ResearchTargetRef`, a closed discriminated union) says what was asked about. The *lineage*
   (`FrozenLineage`) says which immutable state the answer is valid for. They are never collapsed.

   Targets use only identifiers that exist: `DESIGN_REVISION` (`REV-…`); `RESULT_QUESTION` and
   `RESULT_BATTERY_OBJECT` in a run's `research_aggregate`; `ANALYSIS_MODULE`
   (`AnalysisModuleId`); `SOCIOMAP`, `SOCIOMAP_OBJECT`, `SOCIOMAP_RELATIONSHIP` (a battery of a
   run's `research_sociomap`; the relation matrix is symmetric, so a pair has one identity in
   sorted order). **Not targets yet:** segments (no segment identifier exists;
   `research_aggregate.py:18-19`), Sociomap regions (none exist), analysis findings (findings carry
   no id). Each becomes a new variant when the domain has the identifier.

   Lineage pins a target's containing artifacts. Design lineage is the revision's id, number and
   content SHA256. Interpretation lineage is the producing research run, the Design Revision it
   executed, and its `compile`, `run`, `aggregate` and target-node outputs, each `(node, ART-…,
   type, SHA256)` — read and hash-verified at freeze. A target is never "the latest": a newer
   result is another research run, another lineage, another identity.

3. **An envelope around the frozen engine, not a change inside it.**

   ```
   DeepResearchRunSpec                       orchestration identity
   ├── contract_version  aia-deep-research-run-spec-1
   ├── purpose · target · lineage
   ├── title             presentation only, never identity
   └── engine_request    DeepResearchRequest   unchanged; its fingerprint unchanged
   ```

   `DeepResearchRequest`, its fingerprint, `HARNESS_VERSION` and the `EvidenceBundle` and its seal
   are untouched: a harness version moves when the method moves, and this is not that. The spec's
   fingerprint — contract, purpose, target, lineage and the engine request's fingerprint — keys the
   run (`deep_research:spec:{fingerprint}`). **Orchestration identity is not engine-work reuse
   identity:** every step's fingerprint stays the engine request's, so a design run and an
   interpretation run over the same engine input are two runs that share the engine's reusable
   tracks, snapshots and verifications.

4. **Durable provenance without touching the bundle.** The spec (purpose, target, lineage, its
   fingerprint, how the purpose was stated, the title) is stored in the run's metadata; the engine
   request stays the plan step's input. `DeepResearchProvenance` is assembled from durable state —
   the stored spec, re-checked against its fingerprint, and the publish step's bundle artifact id,
   its row SHA256 and the bundle's own seal. `resolve_lineage` re-reads every pin and fails on any
   difference. No migration: `workflow_runs.metadata_json` holds it.

5. **History is not rewritten.** A run stored before this contract reads
   `integration_contract: legacy-unversioned`, with no purpose, target or lineage; nothing is
   back-filled. The deployed start shape, which names no purpose, starts a *new* `DESIGN_RESEARCH`
   run and records `purpose_source: LEGACY_DEFAULT` — a compatibility rule for new requests only.

6. **Deep Research is never an input to the canonical Sociomap calculation.** Interpretation
   Research may read the frozen canonical Sociomap. Deep Research and external evidence are never
   inputs to the canonical Sociomap calculation.

   ```
   Canonical Sociomap = approved frozen study evidence + approved deterministic Sociomap methodology
   ```

   The direction matters: reading the map is allowed; writing to it, or into its computation, never
   is. `INTERPRETATION_RESEARCH` may read an exact frozen canonical Sociomap and target a battery,
   one of its objects or a pair of them (`SOCIOMAP`, `SOCIOMAP_OBJECT`, `SOCIOMAP_RELATIONSHIP`),
   pinned by artifact id and SHA256, as context and evidence. What it produces is a **Research
   Lens** — an annotation sidecar holding the target ref, Deep Research provenance, corroboration,
   contradictions, benchmarks, hypotheses, gaps and source evidence — beside the canonical map's
   geometry, objects, relationships, segments and metrics, and it never feeds back into canonical
   coordinates, geometry, relationships, segmentation or deterministic findings
   (`research_sociomap*` is in `DETERMINISTIC_ARTIFACT_TYPES`, which no purpose may write). A map
   that incorporates external research mathematically would be a different, derived artifact with
   its own methodology, version, lineage and label; it never mutates the canonical one. The Lens is
   not built here.

7. **The engine boundary is frozen.** After PR #166 these are a stable boundary: acquisition;
   search, fetch, document and dataset machinery; the investigators; the lead researcher; fan-out;
   the recovery log; per-host politeness; model concurrency; verification; grounding;
   deterministic confidence; and Evidence Bundle production. Lifecycle work integrates around it.
   Changing an internal needs a specific defect or evaluation finding.

**The methodological invariant.** Deep Research helps decide what to measure. Respondents
determine what we observed. Deterministic analysis and Sociomapping determine the computed
structure. Deep Research may then help us understand what that structure may mean. The report may
synthesize all of them, but their provenance is never blurred. *External research may inform what
we ask and how we interpret. It never manufactures respondent evidence and never rewrites
deterministic research truth.*

## Alternatives considered

- **Add purpose and target fields to `DeepResearchRequest`.** Every request fingerprint would move,
  existing idempotency keys and stored replays would break, and two purposes over one engine input
  could no longer share track reuse. Rejected.
- **Put lifecycle semantics into the `EvidenceBundle`.** Every historical seal would need a new
  shape and the bundle would carry orchestration it does not compute. Rejected; the envelope
  references it.
- **A free-form target (`dict` or string).** Unvalidatable, unscoped, unfingerprintable. Rejected.
- **"The latest result" as a target.** A result changes under a running interpretation and the
  evidence silently stops matching what it explains. Rejected: exact artifact or nothing.
- **A second provenance table.** The artifact rows already carry id, type, status and SHA256, and
  run metadata already carries the run's frozen inputs. Rejected as duplication.

## Consequences

- Every new run answers, durably: why it ran, what it researched, which immutable state it rests
  on. The report (evidence families POPULATION/RESPONDENT, DETERMINISTIC, SOCIOMAP, DEEP_RESEARCH,
  CLIENT_KNOWLEDGE) and the Research Lens can cite `DeepResearchProvenance` without reaching
  into the engine.
- **Interpretation Research is frozen, never executed, until chunk 30.** Its target resolution,
  lineage freeze, run-spec construction and provenance contract exist now. Enqueueing is refused
  at the one enqueue boundary (`DeepResearchRuns._enqueue`, `interpretation_not_ready`), and a
  stored interpretation row is never retried. The reason: its engine request would still be the
  design-derived one, so a run would be labelled as interpreting a result while researching the
  design's subjects. Chunk 30 derives the research mission from the exact target, builds the
  engine request from it, and then enables enqueueing together with the result-side route. No
  knowingly mislabelled output exists in AIA.

  | | target resolution | lineage freeze | run spec | provenance contract | enqueue | execute |
  |---|---|---|---|---|---|---|
  | `DESIGN_RESEARCH` | yes | yes | yes | yes | yes | yes |
  | `INTERPRETATION_RESEARCH` (Step 1) | yes | yes | yes | yes | **no** | **no** |
- A start after this ADR over a revision that already had a pre-ADR run is a new run (a new key):
  the honest cost of not pretending the old run was governed.

## Revisit when

A segment, region or finding identifier lands (a new target variant); the Research Lens or the
report evidence graph needs a field the provenance does not carry; or an evaluation finding
requires an engine change behind the frozen boundary.
