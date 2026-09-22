# Architecture decision records

One file per decision that would be expensive to reverse or surprising to
inherit. Each records the decision, the alternatives, and what would make us
revisit it.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-python-fastapi-backend.md) | Keep the validated Python domain engine; FastAPI for the API | Accepted |
| [0002](0002-postgresql-authoritative-store.md) | PostgreSQL is the authoritative store; SQS is dispatch only | Accepted |
| [0003](0003-cognito-identity-boundary.md) | Cognito federated to Google Workspace for authentication; authorization stays in AIA | Accepted |
| [0004](0004-client-study-isolation.md) | Client and Study as hard isolation boundaries with injected scope | Accepted |
| [0005](0005-llm-gateway.md) | Centralised LLM gateway; capability-based model selection | **Proposed** |
| [0006](0006-langgraph-agent-execution.md) | LangGraph for agent reasoning, AIA owns the outer workflow | Accepted — constrained use |
| [0007](0007-deterministic-tools.md) | No LLM for deterministic analytical computation | Accepted |
| [0008](0008-eu-data-residency.md) | EU data residency; Bedrock `eu-central-1` is the only inference path | Accepted |

## Status meanings

- **Accepted** — implemented, or committed to and being implemented.
- **Proposed** — the direction is agreed but the choice is not yet locked by
  code. Revisit before the phase that depends on it starts.
- **Superseded** — replaced; the replacing ADR is named.

## Numbering note

ADRs 0005 and 0006 were communicated with their numbers transposed. In this
repository the LLM gateway is **0005** and LangGraph is **0006**. Each file
repeats this note; the table above is authoritative.
