# ADR 0006 — LangGraph for agent reasoning; AIA owns the workflow

**Status:** **Accepted — constrained use.** Decided 2026-09-21.
**Date:** 2026-09-21

> **Numbering note.** The decision approving LangGraph was communicated as
> "ADR 0005". In this repository LangGraph is **0006** and the LLM gateway is
> [0005](0005-llm-gateway.md). The content is unchanged; only the file numbers
> differ from that message.

## Decision

LangGraph is accepted as the **agent-internal orchestration framework**. It is
**not** AIA's authoritative workflow engine.

> **LangGraph is an implementation detail of eligible agent steps. AIA's workflow
> engine and PostgreSQL remain the system of record for durable business workflow
> state.**

## The boundary

```
AIA Workflow Engine
PostgreSQL-owned durable state
│
├── WorkflowRun
├── StepRun
├── StepAttempt
├── Gates / approvals
├── Reservations / budget
├── Artifacts
└── Recovery
        │
        ▼
   Agent Step
        │
        ▼
    LangGraph
        │
        ├── reasoning
        ├── tool selection
        ├── model call
        └── internal agent checkpoint
```

AIA owns anything with business meaning. LangGraph owns reasoning topology inside
one agent step.

## What LangGraph must never be authoritative for

This list is the decision. Each item, if it lived in LangGraph, would produce the
state nobody can debug: half a failed run in PostgreSQL tables and the other half
only interpretable through a framework checkpoint.

1. Whether a study is waiting for a gate approval.
2. Whether a paid call is `SETTLED_UNCERTAIN`.
3. Whether a study exceeded its budget.
4. Which client and study own a run.
5. Whether a step is eligible to retry.
6. Artifact lineage.
7. Human approval state.

## Operational rules that follow

- **A LangGraph run must not outlive a `StepAttempt`.** If an attempt fails, the
  attempt is recorded and a new attempt starts a new graph.
- **LangGraph state is not the record that a step completed.** The `StepRun` row
  is.
- **An approval gate is not a graph interrupt.** It is a `WAITING_GATE` state in
  AIA's machine, because it may last days and must survive a deploy.
- **Cost is not aggregated from LangGraph.** Every model call writes an
  `AIUsageEvent`; that ledger is authoritative.
- **LangGraph state is debugging information, not evidence.** It is not an
  artifact and is not part of provenance.

LangGraph's in-memory checkpointing may be used *within* one attempt, to avoid
repeating tool calls after a recoverable error inside the loop.

## Alternatives considered

**LangGraph for the whole pipeline, including durability.** Rejected. The 13-stage
lifecycle, revisions, artifact reuse by input fingerprint, per-study budgets and
approval gates are product concepts with contractual behaviour, described by the
prototype's 394 tests in our semantics rather than a framework's.

**No agent framework: hand-written reasoning loops.** What the prototype does, and
retained as the fallback. The boundary above means only the inside of a step would
change, so a swap is cheap.

## Consequences

- Two layers of retry exist: LangGraph's inside an attempt, and AIA's across
  attempts. Their interaction needs explicit tests, particularly that a quota
  error inside the graph surfaces as a park rather than being retried internally.
- Agent steps must be safe to restart from the beginning, because that is what
  AIA will do.
- If anyone reaches for LangGraph's checkpointer to solve a durability problem,
  the boundary is being eroded and this ADR is being violated.
