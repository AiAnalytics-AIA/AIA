---
status: planned
chunks:
  - "[ ] 0. The owner chooses and contracts the provider: an EU processing agreement and a written answer on storing results"
  - "[ ] 1. The provider's route, composed beside Brave's and approved for Class B"
  - "[ ] 2. The ADR 0022 live sign-off for the route"
  - "[ ] 3. A design's class for Deep Research decided by rule once a Class B route exists (no operator step), Class C routes refusing it"
  - "[ ] 4. A recorded double and a journey test: a Class B query reaches only the Class B route"
  - "[ ] 5. Operator activation on develop (with deep-research-web-search 27)"
  - "[ ] 6. The class of a derived query: an ADR 0017 and 0008 amendment, the data owner's confirmation, then a rule enforced by code"
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

## The owner's answer on breadth, and what it requires

On 2026-10-19 the owner answered `mvp-cohesion.md` F1: Deep Research "should take that whole design
and use it to find as much relevant data as possible"; an operator step after each design edit is
not wanted; and **queries derived from the design may reach Class C routes** (Wikipedia, Brave,
Common Crawl). Chunks 1-5 build the Class B route and classify the design itself by rule.
**Chunk 6 is the part that reverses an existing rule**: ADR 0017 says a query's class is never
lowered by keywords, and OI-129 declined a class of its own for a derived query on the same day. So
chunk 6 starts with paper, not code (an amendment to ADR 0017 and ADR 0008, and the data owner's
confirmation, because the licence and residency gates are theirs), and its mechanism is enforced
by **code**, never by a prompt or a model's own claim about a query.

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

6. **Derived-query class: by provenance, never by a negative text test.** A query is Class C only
   when code can **prove** its content comes from a Class C source. Two candidate provenances, to
   be chosen in the amendment: (a) a fixed query template filled only from a list of public terms a
   person has declared public; (b) a query set a person has seen and marked public before it is
   sent (a card, consistent with MVP-13). Everything else stays Class B and only a Class B route may
   receive it. **A test that finds no client term, named entity or verbatim design text is not
   enough** (Codex review of #497, accepted): a model can paraphrase a confidential launch or
   pricing question with none of those tokens, and the paraphrase is still Class B intent. Tests: a
   paraphrase of a Class B question that keeps no checked token stays Class B and a Class C route
   refuses it; a template over declared-public terms is Class C and reaches Wikipedia; a model
   cannot lower its own query's class. Nothing here ships until the amendment is accepted.

## Depends on / feeds

Needs the provider contract (chunk 0, blocks 1-5 live), chunk 3's confirmation and, for chunk 6, the amendment. Feeds AC-11 and
integration gate I-4 (`mvp-cohesion.md` §4). `deep-research-web-search` 1 (sign-off) and 27
(activation) are the same work from the other side: tick them from this plan's chunks 2 and 5.

## Open

- ~~Which provenance chunk 6 uses~~ **decided 2026-10-19, the owner:** content decides, not
  derivation (client terms, and a five-word run shared with Class A or B text); no approval step.
  Who confirms it: the owner; the data owner too if that is another person.
- Whether more than one Class B route is wanted ("as much data as possible").

## Doc follow-up

`ARCHITECTURE.md` §4 (Deep Research's classification regime), ADR 0008 amendment, `overview.md`
(MVP-27 beside OI-129).

## Reordered (2026-10-19)

The owner decided to go with Brave, a Class C route, for live Deep Research. Chunk 6 (the class of a
derived query) is therefore **first**: `aia-query-classifier-2` drops the context-class floor of
`classification.py` (the owner's rule: derived is fine, pasted is not) and adds Class B text to the
five-word overlap check; the tests that encode "nothing lowers a class" are replaced by tests of the
new rule, each citing this decision, and the old rule's cases that are still true (a client-named query,
a verbatim paste) stay as they are. Chunks 0-5 (the Class B provider and its route) are **optional and
later**: they add a route for queries the content test refuses. See `mvp-development-plan.md` § Reach.
