# ADR 0005 — Centralised LLM gateway with capability-based model selection

**Status:** Proposed. To be confirmed before Phase 4 implementation begins.
**Date:** 2026-09-21

## Context

The prototype calls providers from `ai_router.py`, which already does the hard
parts well: JSON-schema structured output, schema strictification, substitution of
retired model ids against what an account can actually see, and a ten-way error
classification. But provider model names are threaded through the codebase, so
choosing a model is a decision made at hundreds of call sites.

Three providers are in play: the Claude Code subscription (flat rate), the Claude
API and the OpenAI API (both metered). Workflows must not care which.

## Decision

**Workflows request a logical capability, never a provider model name.**

```
FAST_EXTRACTION     cheap, high-volume, structured extraction
RESEARCH_REASONING  long-context synthesis and study design
REPORT_WRITING      long-form prose in Czech
CRITIC              adversarial review of another agent's output
SIMULATION          respondent and world simulation
EMBEDDING           vector embedding for retrieval
```

A `ModelRegistry` maps a capability to a concrete `(provider, model)` under a
`ModelPolicy`, and an `LLMGateway` performs the call. The gateway is the only
component that imports a provider SDK.

```
Workflow step
  -> requests capability RESEARCH_REASONING
  -> ModelPolicy + ModelRegistry resolve (provider, model)
  -> LLMGateway performs the call
  -> AIUsageEvent written before the result is returned
```

This buys three things:

1. **A model swap is a configuration change**, not a code change across the
   codebase. When a model is retired — which the prototype already handles
   reactively — the registry is the single place to update.
2. **Cost policy becomes expressible.** "Use the cheap model for extraction on
   this study" is a policy, not a refactor.
3. **Provenance stays honest.** The resolved provider and model are recorded per
   call, so a finding can always name what produced it.

### Gateway implementation: LiteLLM, tentatively

**LiteLLM** is the current recommended direction for the transport layer, giving
one interface across Anthropic and OpenAI.

It is **not yet decided**, because of a specific risk: the prototype's
`ai_router.py` contains behaviour we are contractually committed to preserving —
no silent fallback, the ten-way error classification, quota parking distinguished
from failure, and retired-model substitution. A library that retries or falls back
on our behalf would break the product's central provider rule. Before adopting
LiteLLM, verify that:

- automatic fallback can be **fully disabled**, not merely configured;
- its error taxonomy can be mapped onto ours without losing the quota/capacity
  distinction, since we park rather than retry on quota;
- token and cost figures are exposed per call, including cached-token counts;
- the Claude Code subscription CLI runtime can live behind the same interface, as
  it is not an HTTP API.

If any of those fail, implement the gateway directly over the provider SDKs and
port `ai_router.py` behind the interface. The interface is the decision; the
library behind it is an implementation detail we should not pay a behavioural
price for.

## Alternatives considered

**Direct SDK calls per provider.** What the prototype does. Rejected: it is what
spread model names through the code, and it duplicates the error taxonomy.

**A managed gateway service.** Rejected for now: research data and client briefs
would transit a third party, and the residency question is unresolved.

**Provider-native routing.** Rejected: it would put fallback behaviour outside
our control, and disabling silent fallback is a product requirement.

## Consequences

- Domain code cannot name a model, which makes some debugging less direct; the
  resolved model is recorded on every `AIUsageEvent` to compensate.
- The registry becomes a critical configuration surface and needs its own tests
  for capability coverage.
- A capability with no configured model must fail closed, not fall back to
  "whatever is available".

## Revisit when

- LiteLLM's fallback behaviour is verified against the four points above.
- A provider is added or removed.
- Cached-token pricing changes materially enough to affect capability mapping.
