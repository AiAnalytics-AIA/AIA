---
status: planned
chunks:
  - "[ ] 0. The owner chooses and contracts the provider: an EU processing agreement and a written answer on storing results"
  - "[ ] 1. The provider's route, composed beside Brave's and approved for Class B"
  - "[ ] 2. The ADR 0022 live sign-off for the route"
  - "[ ] 3. A design's class for Deep Research decided by rule once a Class B route exists (no operator step), Class C routes refusing it"
  - "[ ] 4. A recorded double and a journey test: a Class B query reaches only the Class B route"
  - "[ ] 5. Operator activation on develop (with deep-research-web-search 27)"
---
# A Class B search route for live Deep Research

Track F of the MVP roadmap (`overview.md` § MVP roadmap, #493). Written 2026-10-19 from MVP-27 and
`mvp-cohesion.md` F1 and F7 (#496). **Owner: a chat session for chunks 1-4; chunk 0 and 5 are the
product owner's and an operator's.**

## Decisions this plan carries

MVP-27: live Deep Research uses the full study design (DR-2b). Queries may carry the Class B
design, so they go only to a search provider **approved for Class B under an EU processing
agreement**, contracted before release. Brave and Wikipedia stay Class C. Candidate: Linkup.
(MVP-9, Brave as the release route, is superseded.)

## The owner's answer on breadth, and what it leaves open

On 2026-10-19 the owner answered `mvp-cohesion.md` F1: Deep Research "should take that whole design
and use it to find as much relevant data as possible"; an operator step after each design edit is
not wanted. **This plan builds only (a): one or more routes approved for Class B, so every query
carries the design's class.** Whether *derived* queries may also reach Class C routes (Wikipedia,
Brave, Common Crawl) is a separate decision: it needs a rule that lowers a derived query's class,
which ADR 0017 forbids ("never lowered by keywords") and OI-129 declined on the same day. It is
the owner's and the data owner's; until answered, Class C routes receive Class C queries only.

## What exists

- Routes declare the classes they accept: Brave and the recorded route
  `approved_for=frozenset({DataClass.CLASS_C_INTERNAL})`
  (`apps/executors/src/aia_executors/deep_research_live.py:115 @ 085abe0`,
  `deep_research_recorded.py:69`); the refusal is `RetrievalGate.refusal_for_class`
  (`packages/aia_core/src/aia_core/application/web_retrieval.py:618-632 @ 085abe0`).
- The plan step classifies a design by an operator's exact-bytes record alone
  (`apps/executors/src/aia_executors/deep_research/plan.py:163 @ 085abe0`, `classify_material`);
  OI-129 (`.planning/open-items.md:4121`) recorded that, and a run on an edited design parks.
  The Lead, the design jobs and the respondents classify by rule (`domain/material_rules.py`).
- A priced live route runs only under a pin recording the sign-off
  (`sign_off_routes()`, ADR 0022).

## Chunks

0. **Provider.** The owner chooses and contracts an EU provider approved for Class B, with the
   processing agreement and a written answer on storing results (the open DR-2 question for Brave).
   Output: the provider, its terms and its price, recorded in `overview.md`.
1. **Route.** An adapter behind the existing search protocol, composed in `deep_research_live.py`
   beside Brave's, credential by reference (never kept or logged), `approved_for` Class B, priced
   per request and held against the study's budget like any priced call.
2. **Sign-off.** `sign_off_routes()` names it; Settings → Deep Research approves every live setting
   it needs (ADR 0022). Test: the route refuses to run without the pin.
3. **Classification.** With a Class B route composed, the plan step classifies a design by
   `MaterialRule.DESIGN` (Class B, raised and never lowered by an operator), exactly as
   `ai_fieldwork.py` does. A design no rule can classify still parks. Test: an edited design runs
   its web tracks without an operator record; this supersedes OI-129's second sentence and needs the
   owner's recorded confirmation in OI-129 / ADR 0008 first.
4. **Journey.** `test_deep_research_journey.py` with a recorded Class B route: Class C routes refuse
   the Class B query, the Class B route accepts it, nothing is sent twice.
5. **Activation.** The develop host's switches and the provider credential, an operator's act,
   verified by the live Deep Research run of the acceptance study (`mvp-acceptance-harness`).

## Depends on / feeds

Needs the provider contract (chunk 0, blocks 1-5 live) and chunk 3's confirmation. Feeds AC-11 and
integration gate I-4 (`mvp-cohesion.md` §4). `deep-research-web-search` 1 (sign-off) and 27
(activation) are the same work from the other side: tick them from this plan's chunks 2 and 5.

## Open

- Derived queries on Class C routes (above).
- Whether more than one Class B route is wanted ("as much data as possible").

## Doc follow-up

`ARCHITECTURE.md` §4 (Deep Research's classification regime), ADR 0008 amendment, `overview.md`
(MVP-27 beside OI-129).
