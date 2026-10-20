# ADR 0032 — Open posture: one declared flag per client replaces classification for Deep Research's web in the MVP

**Status:** Proposed — 2026-10-20, recording the product owner's decision of 2026-10-19 (#500).
Not accepted until the product owner says so. **Amends** [ADR 0008](0008-eu-data-residency.md), a
frozen invariant, for Deep Research's web egress only, and its addendum of 2026-10-19 item 1
(operator-only classification of a design, OI-129) for an OPEN client. **Builds on**
[ADR 0017](0017-deep-research-external-retrieval.md) (a query inherits its class),
[ADR 0021](0021-deep-research-purpose-target-lineage.md) and
[ADR 0022](0022-deep-research-settings-are-approved-data.md) (a run pins its settings at enqueue).
**Leaves unchanged** the EU residency of models and storage, the model gateway and
`domain/material_rules.py` for every model call, the licence gate, grounding, verification and
every evidence gate.
**Date:** 2026-10-20. **Amended 2026-10-20** with the product owner's recorded answers D-08 and D-17
(`.planning/evidence/scope-freeze/answers-2026-10-20.md`, #523 @ `ee21982`); still Proposed.
**Plan:** [deep-research-web-search](../../../.planning/plans/deep-research-web-search.md) 53 (§ Open
posture), 51, 52; migration M10

## Context

Deep Research asks for a class in six places: the plan step's `classify_material`
(`apps/executors/src/aia_executors/deep_research/plan.py:163 @ 854c209`) and five `classify_query`
calls in the retrieval gate (`packages/aia_core/src/aia_core/application/web_retrieval.py:788, 882,
1177, 1275, 1365 @ 854c209`). Every live web route is Class C only, a design is Class B by rule, and
ADR 0008's addendum keeps Deep Research on operator-only classification of a design's exact bytes.
So every run on an edited design parks `egress_unclassified_material`, and a query written from a
real design can reach no route. The route list is wider than people were told (Wikipedia, Brave,
fetch from any public host, six connectors and Common Crawl, `mvp-development-plan.md` §1); the
class is what blocks it.

The owner, 2026-10-19: "all these classifications, honestly lets get rid of them for now and build
them later. theyre a huge blocker in general and we can better design it, once we have a fully
functioning mvp." And on reach: "i never want to hear that this limitation exists." Brave stays the
search route (US-based, query logs up to 90 days, `.planning/plans/deep-research-web-search.md:502 @ 854c209`); the
classifier redesign (`aia-query-classifier-2`) is deferred, not built.

## Decision

### 1. Every client declares a posture: `CLASSIFIED` (the default) or `OPEN`

`clients.data_posture` (M10), with who set it and when. Only an organization OWNER or ADMIN sets it
(`PUT /clients/{id}/data-posture`); every change is audited and shown on the client's profile. It
is set on the client's Profil → Pravidla, beside the wallet ceiling (the product owner, 2026-10-20,
D-17).
Marking a client OPEN is **the organization's statement that this client's material may be used in
public search queries**. It is a positive, recorded justification, which is what ADR 0008's
"refuses anything it cannot positively justify" asks for; the default stays closed.

### 2. A run pins its client's posture at enqueue

The posture is written into the run's engine request at enqueue, beside ADR 0022's settings pin, so
a retry re-freezes it from the request, never from the client row. A client switched mid-run changes
nothing for that run; a retry copies the original's posture.

### 3. OPEN lowers the class of web egress only

For an OPEN run, the plan step's web gate and the five query classifications take the posture in
place of a class: queries and fetches may go to any composed route (Brave, the connectors, Common
Crawl, the crawler) inside ADR 0022's approved settings. The journal records `posture: OPEN` where
it recorded a class, so every query that left says on what authority.

The one `design_class` field that today serves both search egress and model requests is split: the
**query** class follows the posture, the **model request** keeps the design's rule class (B), so a
model route approved for C alone still refuses it. `fictional_client` stays derived from the
operator's record, never from the posture (`plan.py:175-178 @ 854c209`).

### 4. CLASSIFIED is exactly today

`aia-query-classifier-1` is untouched. A run on an edited design with no operator record fails
whole with `egress_unclassified_material` (`plan.py:166-174 @ 854c209`). **A real, confidential
client left CLASSIFIED gets no web search in the MVP.** Operator-declared fictional clients behave as
before.

### 5. The deferral and the redesign note

Classification of search material is redesigned after the MVP, starting from `class-b-search-route`
6's content rule and the review findings it collected. Until then, this flag is the only control.

## Alternatives considered

- **Build `aia-query-classifier-2` first** (a content rule, three review rounds of findings). Deferred
  by the owner: it held the MVP's reach for a design that is not settled.
- **Default every client to OPEN.** Rejected: confidential clients exist, and a default nobody chose
  is not a justification.
- **Read the posture from the client row at each query.** A run would change posture mid-flight;
  pinned like the settings, it cannot.
- **A Class B EU route (Linkup) instead.** The post-MVP contract door (`class-b-search-route` 0-6);
  see *Open for Nigel*, 1.

## Consequences

- **What it costs, stated:** an OPEN client's queries and fetches carry no confidentiality check,
  and Brave sees everything an OPEN client's design makes a researcher search for, names included.
- **What it does not loosen:** grounding (a quote must be in a captured source), adversarial
  verification, the evidence gate, and the residency of models and storage. Reach changes where the
  engine may look, not what it may claim.
- A real client's web research waits for the redesign unless an OWNER or ADMIN marks it OPEN.

## What enforces it

- Tests (chunk 53): an OPEN client's edited design runs its web tracks with no operator record; a
  CLASSIFIED client's still fails `egress_unclassified_material`; a retry keeps the original's
  posture; a mid-run switch changes nothing for the run; a model request in an OPEN run still carries
  the design's rule class; only OWNER or ADMIN may set the posture, audited, a second organization's
  client 404.
- `make layer_check`: `data_posture` written only by the client repository's setter.
- The Reach panel (chunk 52) states each run's posture, read from the composition and the run.

## Unblocks

`deep-research-web-search` 53 (W0 decision, W1 code), 51 and 54's activation for OPEN clients, gate
I-R, and AC-11's first half.

## Open for Nigel

1. **Which route is the release route.** `overview.md` MVP-27 says live Deep Research uses "a search
   provider approved for Class B under an EU processing agreement, contracted before release" (Linkup
   the candidate); `mvp-development-plan.md` §1 says the route is Brave for an OPEN client and the
   Class B route is after the MVP. Both are dated 2026-10-19. This ADR follows the development plan;
   MVP-27 and AC-11's wording would change (its Doc follow-up already proposes it).
2. ~~"Frozen" retrieval.~~ Yes: CLAUDE.md §2's and ADR 0021's wording changes, as a docs follow-up,
   when this ADR is accepted (D-08, a).
3. ~~Amending ADR 0008.~~ Yes, recorded in ADR 0008's amendments when this ADR is accepted (D-08, a).
