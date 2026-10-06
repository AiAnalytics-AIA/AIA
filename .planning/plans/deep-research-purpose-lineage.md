---
status: done
chunks:
  - "[x] 1. ADR 0021 and this plan: two purposes, typed targets, frozen lineage, the frozen engine"
  - "[x] 2. Domain: DeepResearchPurpose, ResearchTargetRef, FrozenLineage, DeepResearchRunSpec, provenance, authority"
  - "[x] 3. Application: design freeze, interpretation freeze, orchestration identity, retry, legacy read, provenance"
  - "[x] 4. API: purpose, target and lineage on a run; the provenance route; the legacy start shape kept"
  - "[x] 5. Tests: golden pre-Step-1 compatibility, identity, scope, lineage, methodology boundary, round trip"
  - "[x] 6. Documentation: PR #166's follow-up, the plan re-cut, open items, stale architecture text"
---
# Deep Research — purpose, target and frozen lineage (AIA-83, Step 1)

**Status:** done (on its pull request) · **Parent:** AIA-81 · **Base:** `develop` @ `579b7ab` (PR #166 merged)
**Decides:** [ADR 0021](../../docs/architecture/adr/0021-deep-research-purpose-target-lineage.md)

## Why

Deep Research was built as one standalone operation: a `DeepResearchRequest` frozen around a
Design Revision, run, and sealed into an `EvidenceBundle`. AIA's methodology uses it at two
checkpoints instead: before the methodology freeze, to inform the design
(`DESIGN_RESEARCH`), and after the deterministic results, to interpret them
(`INTERPRETATION_RESEARCH`). A run must say durably *why* it runs, *what* it researches, and
*which immutable AIA state* it is anchored to — without reopening the engine PR #166 finished.

## Approach

An outer orchestration envelope around the frozen engine, never inside it:

```
DeepResearchRunSpec                     (domain/deep_research/integration.py)
├── contract_version  aia-deep-research-run-spec-1
├── purpose           DeepResearchPurpose
├── target            ResearchTargetRef  (closed, discriminated)
├── lineage           FrozenLineage      (exact artifacts and their SHA256)
├── title             presentation only, not identity
└── engine_request    DeepResearchRequest   (unchanged; its fingerprint unchanged)
```

- **Identity.** `run_spec.fingerprint()` covers contract, purpose, target, lineage and the engine
  request's fingerprint; it is the run's idempotency key. The engine's own fingerprints (request,
  track) are untouched, so a design run and an interpretation run over the same engine input are
  two runs that share engine work.
- **Storage.** The spec (without the engine request, already the plan step's input) is stored in
  `workflow_runs.metadata_json`; no migration. Provenance is assembled from durable state: the
  spec, the publish step's bundle artifact id and row SHA256, and the bundle's own seal.
- **Targets** are only identifiers that exist: Design Revision (`REV-…`); a question's or a battery
  object's result in a run's `research_aggregate`; an analysis module (`AnalysisModuleId`); a
  battery's `research_sociomap`, one of its objects, or a pair of them. No segment target (no
  segment identifier exists, `research_aggregate.py:18-19`), no Sociomap region (none exist), no
  analysis finding id (findings carry none). Each is added when the domain has the identifier.
- **Lineage** pins the producing research run's `compile`, `run`, `aggregate` and target step
  outputs (node, `ART-…`, type, SHA256, read and verified) and the Design Revision it executed
  (id, number, content SHA256). A newer result is a different run and so a different lineage.
- **Authority.** Neither purpose may mutate the design or the deterministic chain; the engine's
  artifact types are checked disjoint from the deterministic ones at import; a layer check keeps
  Deep Research code from the design writer.
- **Legacy.** A run without `integration_contract` reads as `legacy-unversioned`, purpose null;
  history is not rewritten. The deployed start shape (no `purpose`) is a new `DESIGN_RESEARCH`
  run, recorded `purpose_source: legacy_default`.

## Not in this plan

Executing Interpretation Research: until chunk 30 derives its mission from the target, the
enqueue boundary refuses its spec (OI-88); the result-side start route comes with it; the Research Lens; the
report evidence graph; the operator screen; any engine change (retrieval, ladder, investigators,
lead, fan-out, verification, grounding, confidence, bundle).

## Findings

- **OI-85 was stale.** Chunk 7 of the web-search plan (#144) fixed it; the reproduction now
  returns `MEASURE_NOT_IN_SOURCE` (re-run on `579b7ab`). Closed in `open-items.md`.
- **OI-86** (closed by #166), the released planned track that resent its calls, and **OI-87**, the
  model-slot lease hypothesis, are filed from #166's record; **OI-88** is this step's own
  limitation: Interpretation Research is frozen, never enqueued, until chunk 30.
- **Stale "not registered" text.** `application/deep_research.py`'s docstring, `CLAUDE.md`,
  `deep-research.md` and `research-journey.md` said nothing was registered or executed; the
  executors are in the default registry and the API route calls the service (#92). Corrected here.

## Doc follow-up

Applied in this PR itself (it is the architecture synchronisation PR the owner asked for).
