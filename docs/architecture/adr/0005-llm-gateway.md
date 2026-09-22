# ADR 0005 — AIA defines the model gateway contract; providers sit underneath

**Status:** **Proposed.** The `ModelGateway` contract below is the decision.
LiteLLM remains **unaccepted** pending the four conditions.
**Date:** 2026-09-21

> **Numbering note.** The decision keeping LiteLLM unaccepted was communicated as
> "ADR 0006". In this repository the LLM gateway is **0005** and LangGraph is
> [0006](0006-langgraph-agent-execution.md).

## Context

The prototype's `ai_router.py` already does the hard parts: JSON-schema structured
output, schema strictification, substitution of retired model ids against what an
account can actually see, and a ten-way error classification. But provider model
names are threaded through the codebase, so choosing a model is a decision made at
hundreds of call sites.

More importantly, the reference runtime has behaviour that matters **more than
provider convenience**:

```
no silent fallback
10-way error taxonomy
quota parking ≠ failure
provider capacity ≠ failure
explicit provider switching
budget semantics
uncertain paid-call recovery
```

A gateway library that helpfully performs retry, fallback, load balancing, model
substitution or provider substitution could violate AIA's methodology and
accounting **without technically failing**. For a system that bills client studies
and makes research claims, that is unacceptable.

## Decision

**AIA defines the semantics. A provider library may later implement transport.**

The inversion is the point. Not: *LiteLLM defines provider semantics and AIA
adapts around them.*

### The contract

```python
class ModelGateway(Protocol):
    async def invoke(
        self,
        request: ModelRequest,
        context: ExecutionContext,
    ) -> ModelResult: ...
```

`ModelRequest` carries:

| Field | Why |
| --- | --- |
| `capability` | Logical capability, not a model name |
| `policy_version` | Which model policy resolved this; changes results |
| `data_classification` | Governs which providers may see the payload at all |
| `requested_provider` | Explicit choice, when a user made one |
| `requested_model` | Explicit pin, for a reproducible run |
| `fallback_policy` | **Explicitly authorised** fallback, or none. Never implicit |
| `budget_reservation_id` | Ties the call to a reservation, so a crash is reconcilable |

`ModelResult` carries:

| Field | Why |
| --- | --- |
| `resolved_provider`, `resolved_model` | What actually produced the output |
| `provider_request_id` | **Essential**: lets a possibly-billed call be reconciled after a worker dies |
| `usage` | Input, output and cached tokens where available |
| `actual_cost` | For the authoritative ledger |
| `finish_reason` | Distinguishes truncation from completion |
| `latency` | Observability |
| `provenance` | Prompt version, runtime version, timestamps |

### Capabilities, not model names

```
FAST_EXTRACTION     cheap, high-volume, structured extraction
RESEARCH_REASONING  long-context synthesis and study design
REPORT_WRITING      long-form prose in Czech
CRITIC              adversarial review of another agent's output
SIMULATION          respondent and world simulation
EMBEDDING           vector embedding for retrieval
```

A `ModelRegistry` maps a capability to a concrete `(provider, model)` under a
`ModelPolicy`. A capability with no configured model **fails closed** — it does
not fall back to "whatever is available".

### Providers underneath

```
ModelGateway                  <- AIA owns this contract
├── AnthropicAdapter
├── OpenAIAdapter
├── BedrockAdapter
└── potentially LiteLLMAdapter <- one option among several, not the interface
```

Three thin provider adapters is entirely reasonable at this scale: five users, not
five million requests per minute. Writing them keeps the semantics ours.

## Conditions before LiteLLM can be Accepted

All four must be proved:

1. **Automatic retries can be completely disabled**, or made compatible with
   AIA's attempt and reservation model. A retry we did not record is an attempt
   that does not exist in `StepAttempt`.
2. **Fallback and model substitution cannot occur unless AIA explicitly
   authorises it.** Not "is configured off by default" — cannot occur.
3. **Complete provider error information survives normalization**, enough to
   drive the ten-way taxonomy. Collapsing quota, capacity and authentication into
   one "error" destroys the distinction between parking and failing.
4. **Usage, provider request ids and cost metadata are exposed accurately enough
   to reconcile a possibly-billed call after worker failure.** Without a provider
   request id, `SETTLED_UNCERTAIN` can never be resolved to a fact.

If any is shaky, do not use it. The adapters are cheap; the semantics are not.

## Alternatives considered

**Direct SDK calls per provider with no gateway.** What the prototype does.
Rejected: it spread model names through the code and duplicated the error
taxonomy.

**A managed gateway service.** Rejected for now: client briefs and research data
would transit a third party, and residency is unresolved. `data_classification`
exists on `ModelRequest` partly so this stays decidable per call.

## Consequences

- Domain code cannot name a model, making some debugging less direct. The
  resolved provider and model are on every `AIUsageEvent` to compensate.
- The registry is a critical configuration surface and needs tests for capability
  coverage.
- `provider_request_id` must be captured even on failure paths, because that is
  exactly when it is needed.

## Revisit when

- The four conditions have been tested against a real LiteLLM version, with the
  result recorded here.
- A provider is added or removed.
- Cached-token pricing changes materially enough to affect capability mapping.
