---
status: done
chunks:
  - "[x] 1. Decision document"
  - "[x] 2. Integration rule; layer_check"
  - "[x] 3. Agent status on coordination/agent-status"
---
# Sociomap methodology sign-off package (D6 / OI-16)

**Status:** done — awaiting the methodology owner's decision (D6) · **Owner:** sociomapa-deterministic · **Started:** 2026-09-22

## Problem

`AIA_SOCIOMAP_V1` carries four values that are AIA engineering declarations,
not recovered reference methodology. Nothing yet stops an engineering preset
from becoming client methodology by default — an API, worker or UI could pick
it up silently, and a map could ship to a client whose methodology nobody who
owns methodology ever approved.

## Approach

One owner-facing decision document, one entry per declaration, with the
reference evidence, the gap, the consequence, the real alternatives and an
approval field. Plus the integration rule that separates *computable* from
*client-deliverable*, recorded in the engine document and enforced mechanically
where it can be today: `AIA_SOCIOMAP_V1` may not be referenced outside the
Sociomap domain package, its tests and its golden tool.

No Sociomapping mathematics changes. No further reverse engineering of OI-13,
OI-14 or OI-15 — they are archive-acquisition dependencies.

## Trade-off accepted

The client-deliverable gate is specified, not built: the policy registry it
reads belongs to integration-architecture and product policy, not to this
context.

## Chunks

- [x] 1. Decision document `docs/architecture/sociomapa-methodology-decision.md`
- [x] 2. Integration rule in `sociomapa-deterministic-engine.md`; `layer_check`
      rule forbidding `AIA_SOCIOMAP_V1` outside the Sociomap package; OI-17 for
      the cross-context gate; PROGRESS / OI-16 point at the decision document
- [x] 3. `.agent-status/sociomapa-deterministic.md` on `coordination/agent-status`

## Review outcome

Not yet reviewed. The decision itself is D6's, not a code review's. The `layer_check`
rule was verified to fail on a probe file importing the preset into `apps/api`,
and to pass without it.
