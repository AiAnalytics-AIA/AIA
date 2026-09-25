# ADR 0016 — Research execution: a workflow run pinned to a Design Revision, a fieldwork boundary, and a fail-closed model-transmission rule

**Status:** Accepted — develop (data owner's decisions D1–D3 and design ingestion, 2026-09-25).
Builds on [ADR 0002](0002-postgresql-authoritative-store.md) (the workflow engine),
[ADR 0005](0005-llm-gateway.md) (one model call path), [ADR 0006](0006-langgraph-agent-execution.md)
(AIA owns the workflow), [ADR 0007](0007-deterministic-tools.md) (no LLM for deterministic
computation), [ADR 0008](0008-eu-data-residency.md) (the egress boundary) and
[ADR 0015](0015-client-first-product-interface.md) (Client → Study → stages).
**Date:** 2026-09-25

## Context

After ADR 0015 a researcher designs a study in AIA but runs it in 18.6.6: the Run, Progress and
Results stages hand off to `/classic`. Three facts at `develop` @ `4ad5f66` stand in the way:

- AIA's only workflow type is `develop_snapshot` (`domain/workflow_templates.py:34`).
- A run is pinned to an AIA project revision (`workflow_runs.project_id`, `tables.py:830`), while
  the stages' working content lives in the unit's store behind `study_workspaces` (OI-58).
- The reference's research pipeline is AI end to end at its edges (design help, fieldwork,
  interpretation, report) and deterministic statistics in between: *"the model interprets numbers;
  it does not produce them"* (AIA-reference `inference-document.md:71-77`). Even fieldwork's model
  output is a per-question probability distribution; code draws the answer.

The next PR is the Agent Runtime Foundation (Study → AgentRun → AIA Orchestrator → ModelGateway →
Bedrock). This ADR fixes the seam that PR plugs into, so that it adds executors rather than
redesigning execution. It also records a licensing constraint on that runtime before the runtime
exists: the reference leaves open whether panel-derived microdata (PIAAC, ISSP) may be sent to any
model provider (`open-decisions.md` D3).

## Decision

1. **A research run is a workflow run pinned to a Design Revision.** The browser submits the design
   it holds; AIA validates it against the authenticated Study (research kind, open, `EDIT_STUDY`)
   and stores it as an immutable revision of the Study's own design project (`study_designs`: one
   per research Study, found only through the Study). The revision's `revision_id` is the **Design
   Revision ID**; content is deduplicated by hash, and a later edit is a new revision. A run names a
   Design Revision ID explicitly and executes exactly that content. The browser supplies content,
   never authority: no route takes a client, organization or unit project id, and nothing finds a
   Study by a unit id.

2. **One `research` workflow type, with the reference's node keys.** PR C's graph is
   `compile → preflight → fieldwork → aggregate → sociomap`. Later nodes (`donor_qc`, battery
   gates, segments, `analysis_*`, `interpret`, `verify`, `alignment`, `report`, `delivery`) join the
   same type as their executors land. A run's state is the engine's canonical state
   (`WorkflowRunStatus`); the product groups it for people (queued, running, waiting, completed,
   failed, cancelled) without inventing states or percentages.

3. **Steps are deterministic tools.** Each method is a pure function in `aia_core` with typed input
   and output: run by a step executor today, registered in `ToolRegistry` for agents tomorrow, the
   same function either way. Methods are ported from the vendored unit's own code and pinned to
   fixtures captured by running that code; where exactness is impossible the difference is recorded,
   never silent.

4. **Fieldwork is a boundary.** The `fieldwork` step produces a **fieldwork dataset** (respondent
   rows with weights, donor ids and answers) from a declared **source**, and every later step reads
   only that dataset. Sources:
   - `ai_runtime` — the AI respondent engine (Agent Runtime PR). Until it exists, the step **parks**
     the run in an explicit waiting-for-AI-runtime state that no timer resumes; downstream steps stay
     blocked, and nothing is fabricated.
   - `synthetic_fixture` — a fictional dataset for tests and the workbench. It exists only in the
     test/workbench composition: the production executor registry never provides it, a run records
     its source at creation and the worker refuses a source it does not provide, every artifact
     derived from it carries `data_origin = SYNTHETIC_FIXTURE`, and nothing from it can become a
     client-facing claim.

5. **Model transmission fails closed on licence (D3).** Two things are kept apart:
   - the **engineering rule** (code, in the egress boundary of ADR 0008): material may be sent to a
     model provider only when every dataset it derives from has a determination that explicitly
     approves that provider. Unknown lineage, an unknown dataset, or a determination that is missing,
     pending or refused all mean **no transmission**. Material must declare its lineage; an
     undeclared lineage is refused like unclassified material.
   - the **determination** (policy data, owned by the data owner and legal): per dataset, whether
     transmission to which providers is approved, by whom, when and on what basis. Today every
     panel-derived source — PIAAC, ISSP, the Czech population panel and anything computed from its
     rows — is *not approved* for any provider, Bedrock included. Approval changes the
     determination; it does not change code.

6. **The execution API is Study-scoped.** Under `/api/v1/studies/{study_id}/`:
   `design/revisions` (submit, list, get), `research/runs` (start, list), `research/runs/{run_id}`
   (state), `…/cancel`, `…/retry`, `…/artifacts/{artifact_id}`. Every route resolves the Study
   through `ScopeResolver` first: out of scope is 404, in scope without the permission is 403.
   Start is idempotent per client request and per Design Revision; retry starts a new run linked to
   the one it retries. Cost and usage fields require `VIEW_COSTS`.

## Alternatives considered

- **Start 18.6.6's run from AIA and mirror its state.** Reaches a real report soonest, but the unit
  becomes the orchestrator, the run needs AI anyway, and state lives outside AIA's audit, budget and
  provenance. Rejected.
- **Let the API fetch the design from the unit.** Keeps the browser out, but adds a server→unit
  dependency that OI-58 must then remove. Rejected in favour of browser submission under AIA scope.
- **Fixture data on develop so the chain completes there too.** Makes develop look finished while
  proving nothing about real fieldwork, and breaks the reference's rule that production never
  silently uses fixtures. Rejected (D1).
- **A per-call licence check inside each future agent.** Every new agent would have to remember it.
  Rejected: the rule sits at the one egress boundary every call already crosses.

## Consequences

- The Agent Runtime PR adds executor kinds and the `ai_runtime` fieldwork source; it does not touch
  the run, revision, API or UI contracts.
- AI fieldwork cannot go live against the Czech panel until the D3 determination changes. It can be
  built and tested on synthetic or explicitly cleared data.
- Until OI-58, the unit store keeps the editing copy; AIA holds the revisions that ran. The design
  project is where the editing copy moves when OI-58 lands.
- Porting brings the vendored unit's numerics into a stdlib-only domain (ARCHITECTURE.md §2); a
  method that depends on NumPy's random stream needs a faithful pure-Python generator or a recorded
  intentional difference (the same question as PROGRESS D11 for simulation).

## Revisit when

The D3 determination changes; a second fieldwork source (client datasets) is needed; or the Agent
Runtime needs a step shape this ADR does not allow.
