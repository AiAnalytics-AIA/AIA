# ADR 0008 — EU data residency and the egress boundary

**Status:** Accepted. Frozen invariant; enforcement implemented in
`aia_core.domain.residency`.
**Date:** 2026-09-22

## Context

AIA produces paid research for European clients. Client material arrives under
confidentiality terms and frequently under data protection obligations that
constrain where it may be processed and what a processor may do with it.

This was previously carried in `security.md` as a decision the team still owed.
That was wrong twice over: the decision had in fact been made, and while it sat in
a "decisions needed" list nothing in the code could enforce it. A residency
requirement that exists only in prose is a requirement that will be broken by the
first convenient integration.

This ADR records the invariant. It selects **no vendor, region or hosting
product** — see *What this ADR does not decide*.

## Decision

**All processing of client-derived material obeys EU residency rules, and the
egress boundary fails closed.**

"Client-derived material" is deliberately broad, because residency is broken at
the edges rather than in the obvious place:

- client source data and uploaded datasets
- generated artifacts and deliverables
- backups and snapshots of either
- retrieval indexes and embeddings built over client material
- caches holding client material
- logs and traces carrying client information
- AI inference over identifiable or confidential client material

### Fail closed

The boundary refuses anything it cannot positively justify. A rule that permits
what it has not been told about permits everything, because the case nobody
configured is exactly the case that leaks. Concretely:

- **Unclassified material does not leave AIA.** Absence of a classification is a
  refusal, not a default to "internal".
- **No approved route means no egress.** There is no fallback provider.
- **An unknown route id is a refusal, not a substitution.** Silently using a
  different route is the residency face of the product's no-silent-fallback rule.
- **An under-specified route is refusable.** `ResidencyZone.UNKNOWN` exists so
  that "we did not write down where this runs" is representable and denied,
  instead of being modelled as probably fine.
- **A denial is a hard stop.** `EgressDenied` carries no suggested or fallback
  route, exactly as `BudgetDecision` carries no `suggested_provider`.

### An outbound call needs trusted information

Egress is authorised from an issued `StudyContext`, the data classification, the
residency policy and the approved route. The context can only be produced by the
authorization layer, so a model, an agent, a tool argument or a request body
cannot assert whose data a call carries. The worst a compromised tool can do is
fail.

### Data classes

| Class | What it is | What it requires |
| --- | --- | --- |
| **A — client confidential** | Raw client documents, row-level datasets, personal data, NDA material | A route explicitly approved for Class A, with confirmed EU processing, contractual exclusion from training and a specified retention period. **Never an arbitrary direct provider API.** |
| **B — derived / aggregate client information** | Aggregates, segment profiles, summaries computed from client material | An approved EU-processing route with the same contractual and retention controls |
| **C — internal / non-client** | Methodology text, public sources, prompts carrying no client information | Broader approved routes permitted, including non-EU ones. Still requires an approved route, and still records provenance and cost attribution |

Two properties of this table are load-bearing:

**Approval is per class, not per provider.** The same provider, over the same
transport, under the same terms, approved for aggregates, is still refused raw
client data. Approval is a statement about what an operator agreed to, and it does
not generalise on its own.

**Residency is not only geography.** Material processed in the EU but used to
train a provider's model, or retained for an unspecified period, has left the
client's control as surely as material processed elsewhere. Classes A and B
therefore require training exclusion and a specified retention period in addition
to the zone.

## What this ADR does not decide

It records an invariant. It does **not** select:

- a provider, managed inference service or model host;
- a permanent cloud region;
- a compute service;
- a hosted search, retrieval or embedding product;
- any vendor pricing or commercial arrangement.

Those are implementation choices, each needing its own record, each judged against
this ADR rather than allowed to modify it. Declaring an approved route is how an
implementation states that it *meets* these constraints; the route does not get to
redefine them.

This distinction matters because it is the one that erodes. A proposal to make the
system depend on one vendor's regional offering was circulating as though it were
the residency decision. It is not: it would be one possible way of satisfying the
residency decision, and adopting it would mean writing a vendor ADR that says so
and can be revisited without reopening the invariant.

## Alternatives considered

**Leave residency as a deployment concern.** Rejected. It would be enforced by
whoever configured the environment, differently each time, with no test that could
fail. The classes and the boundary exist so the rule is checkable.

**Encrypt and send anywhere.** Rejected for Class A and B: inference requires
plaintext at the provider, so encryption in transit does not address the question
this ADR is about.

**One global allowlist of providers.** Rejected. A provider is not a route: the
same provider reached over a different transport, account or region is a different
residency answer and must be a separate, separately approved route.

## Consequences

- Every outbound call site must classify what it is sending. This is deliberate
  friction at exactly the moment the question should be asked.
- A capability with no approved route for a study's data class cannot run, and
  `EgressPolicy.routes_for` exists so that is discoverable before a study starts
  rather than mid-pipeline.
- Adding a provider is an operator act with a recorded justification, not a
  configuration convenience.
- Some otherwise attractive tools will be unusable for Class A work. That is the
  decision, not a side effect of it.

## Revisit when

- A client's contract imposes a stricter requirement than these classes express.
- The legal basis changes materially.
- A new class of material appears that none of A, B or C describes — in which case
  the default is the most restrictive, and the burden is on the exception.
