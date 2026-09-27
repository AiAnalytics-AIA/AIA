# ADR 0005 — AIA defines the model gateway contract; providers sit underneath

**Status:** **two decisions, two statuses. Do not collapse them.**

| Decision | Status |
| --- | --- |
| **A — AIA owns the provider-neutral `ModelGateway` contract and its semantics** | **Accepted** |
| **B — LiteLLM implements the transport underneath it** | **Proposed** — blocked on the seven conditions below |

**Date:** 2026-09-21 · **Reconciled:** 2026-09-22 (Architecture v2.1)

An earlier revision carried a single status of *Proposed* for both, which blocked
the architecture on a vendor question. They are independent: the contract stands
whatever implements it, and that is the entire point of the inversion below. Phase
4 may build against decision A now. Decision B stays open until its conditions are
proved against a real LiteLLM version, and the result recorded here.

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

## Decision A — the gateway contract (Accepted)

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
| `data_lineage` | The datasets the payload was computed from; the licence gate beside residency ([ADR 0016](0016-research-execution-and-model-transmission.md) decision 5) |
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
ModelGateway                <- AIA owns this contract
├── AdapterA                \
├── AdapterB                 |  candidate implementations, none selected here
├── AdapterC                 |  and none named as accepted
└── LiteLLMAdapter          /   one option among several, not the interface
```

The shapes are illustrative. **No provider or hosting product is selected by this
ADR**, and none should be read into it: a route that carries client material must
satisfy [ADR 0008](0008-eu-data-residency.md), and choosing a specific vendor to
satisfy it is a separate decision with its own record.

Two or three thin adapters is entirely reasonable at this scale: five users, not
five million requests per minute. Writing them keeps the semantics ours.

### Implementation (2026-09-22)

Decision A is built. Anchors, all under `packages/aia_core/src/aia_core/`:

| Contract element | Where |
| --- | --- |
| `ModelGateway`, `ExecutionContext`, the step-executor seam | `domain/ai_execution.py` |
| `ModelRequest`, `ModelResult`, `AIUsageEvent`, `ProviderErrorKind`, `FallbackPolicy`, structured-output validation | `domain/ai_contracts.py` |
| `ModelCapability`, `ModelPolicy`, `ModelRegistry` (fails closed) | `domain/ai_models.py` |
| `ToolRegistry` | `domain/ai_tools.py` |
| `GovernedModelGateway` — the semantics | `application/model_gateway.py` |
| Adapters: `AnthropicMessagesAdapter`, `OpenAIChatAdapter`, `ClaudeCodeCliAdapter` | `infrastructure/model_adapters/` |
| Ledger `ai_usage_events`, `AIUsageRepository`, `WorkflowCallJournal` | `infrastructure/` |

Two field-level refinements of the table above, both in the direction of less
trust: `ModelRequest.capability` is derived from its `AgentDefinition` rather than
passed separately, so an agent cannot be invoked under a capability it was not
defined for; and `budget_reservation_id` is checked against the reservation the
*execution context* carries, whose amount comes from the workflow repository and
never from the request.

The adapters are written in-house over AIA's own transport protocols, per the
"two or three thin adapters" consequence below. None imports a provider SDK, and
`make layer_check` now forbids one anywhere in the core or API. They are tested
against recorded exchanges only; **no live call has been made**, and no
provider, route or vendor is selected by them (ADR 0008 still decides that).

## Decision B — LiteLLM (Proposed, not accepted)

LiteLLM remains a candidate implementation of decision A's transport, and nothing
more. It is **not** accepted, and no code may assume it.

All seven conditions must be proved against a real version, with the result
recorded in this file:

1. **Hidden and automatic retries can be completely disabled**, or made compatible
   with AIA's attempt and reservation model. A retry we did not record is an
   attempt that does not exist in `StepAttempt`, and a paid one we did not reserve
   for is money that left without a ledger entry.
2. **Hidden fallback cannot occur.** Not "is configured off by default" — cannot
   occur.
3. **Model substitution cannot occur without AIA authorisation.** A finding
   produced by a different model is a different finding.
4. **Provider substitution cannot occur without AIA authorisation.** A silent move
   from a subscription runtime to a metered API spends a client's money without
   consent.
5. **Quota, capacity and authentication remain distinguishable** after
   normalisation, along with the rest of the ten-way taxonomy. Collapsing them
   into one "error" destroys the distinction between parking and failing, and
   turns a wait into a failed study.
6. **Provider request ids survive**, and token, usage and cost metadata are
   sufficient. Without a provider request id, `SETTLED_UNCERTAIN` can never be
   resolved to a fact.
7. **Uncertain billing can be reconciled** — the end-to-end case, not just the
   presence of the fields: a call dispatched, a worker killed, and the outcome
   determined afterwards from what the library exposes.

If any is shaky, do not use it. The adapters are cheap; the semantics are not.

## Alternatives considered

**Direct SDK calls per provider with no gateway.** What the prototype does.
Rejected: it spread model names through the code and duplicated the error
taxonomy.

**A managed gateway service.** Rejected: client briefs and research data would
transit a third party. Residency is **not** unresolved — it is frozen by
[ADR 0008](0008-eu-data-residency.md), and `data_classification` on `ModelRequest`
is what lets the egress boundary decide per call. A managed gateway would have to
satisfy ADR 0008's constraints as an approved route like any other transport.

## Consequences

- Domain code cannot name a model, making some debugging less direct. The
  resolved provider and model are on every `AIUsageEvent` to compensate.
- The registry is a critical configuration surface and needs tests for capability
  coverage.
- `provider_request_id` must be captured even on failure paths, because that is
  exactly when it is needed.

## Revisit when

- The seven conditions in decision B have been tested against a real LiteLLM
  version, with the result recorded here.
- A provider is added or removed.
- Cached-token pricing changes materially enough to affect capability mapping.
