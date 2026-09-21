# ADR 0006 — LangGraph for agent reasoning; AIA owns the outer workflow

**Status:** Proposed. To be confirmed before Phase 4 implementation begins.
**Date:** 2026-09-21

## Context

Some research stages are genuinely agentic: deep research, questionnaire repair,
segment interpretation. They benefit from a reasoning loop with tool use, retries
and branching.

They are also expensive, long-running and must survive a worker restart, which is
exactly what AIA's own durable workflow engine (Phase 3) provides.

## Decision

**LangGraph owns the inside of an agent step. AIA owns everything outside it.**

```
AIA WorkflowRun          durable, PostgreSQL, survives restart
  └── StepRun            one pipeline node
      └── StepAttempt    append-only attempt history
          └── LangGraph execution      agent reasoning, in-memory
              └── LLMGateway / ToolRegistry calls
```

AIA remains the sole owner of: Client, Study, Revision, WorkflowRun, StepRun,
StepAttempt, Budget, Approvals, Artifacts, Costs and audit history.

LangGraph owns only the internal execution graph of one agent's reasoning, and
only for the duration of one attempt.

### The rule this exists to prevent

> **Do not create a second product workflow state system inside LangGraph.**

LangGraph has checkpointers and its own persistence. Using them for product state
would give two systems with independent opinions about whether a stage is
complete, what it cost and who approved it. Every "why did this project stop"
question would then need both answered, and they would eventually disagree.

Concretely:

- A LangGraph run **must not** outlive a `StepAttempt`. If an attempt fails, the
  attempt is recorded and a new one starts a new graph.
- LangGraph state **must not** be the record that a stage completed. The
  `StepRun` row is.
- An approval gate **must not** be a LangGraph interrupt. It is a `WAITING_USER`
  step in AIA's state machine, because it may last days and must survive a
  deploy.
- Cost **must not** be aggregated from LangGraph. Every model call writes an
  `AIUsageEvent`; that ledger is authoritative.

LangGraph's in-memory checkpointing may be used *within* one attempt, to avoid
repeating tool calls after a recoverable error inside the loop.

## Alternatives considered

**LangGraph for the whole pipeline, including durability.** Rejected. The 13-stage
lifecycle, revisions, artifact reuse by input fingerprint, per-study budgets and
approval gates are product concepts with contractual behaviour. Expressing them
in a framework's state model would make them that framework's semantics, and the
prototype's 394 tests describe them in ours.

**No agent framework: hand-written reasoning loops.** Viable, and what the
prototype does. Kept as the fallback if LangGraph's dependency surface or upgrade
cadence proves troublesome, since the boundary above means only the inside of a
step would change.

**A different agent framework.** Not evaluated in depth. The boundary matters far
more than the choice, and it is deliberately narrow enough to make a swap cheap.

## Consequences

- Two layers of retry exist: LangGraph's inside an attempt, and AIA's across
  attempts. Their interaction needs explicit tests, particularly that a quota
  error inside the graph surfaces as a park rather than being retried internally.
- Agent steps must be written so that an interrupted attempt is safe to restart
  from the beginning, because that is what AIA will do.
- LangGraph's state is debugging information, not evidence. It is not an artifact.

## Revisit when

- Phase 4 begins, and at the first agent step that wants a multi-day pause.
- If LangGraph's checkpointer starts being reached for to solve a durability
  problem, that is a signal the boundary is being eroded.
