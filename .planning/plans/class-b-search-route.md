---
status: planned
chunks:
  - "[ ] 0. (after the MVP) The owner chooses and contracts the provider: an EU processing agreement and a written answer on storing results"
  - "[ ] 1. (after the MVP) The provider's route, composed beside Brave's and approved for Class B"
  - "[ ] 2. (after the MVP) The ADR 0022 live sign-off for the route"
  - "[ ] 3. (after the MVP) A design's class for Deep Research decided by rule once a Class B route exists (no operator step), Class C routes refusing it"
  - "[ ] 4. (after the MVP) A recorded double and a journey test: a Class B query reaches only the Class B route"
  - "[ ] 5. (after the MVP) Operator activation on develop (with deep-research-web-search 27)"
  - "[ ] 6. (after the MVP) The class of a derived query: content decides, not derivation (owner, 2026-10-19): aia-query-classifier-2, the ADR 0017 and 0008 amendment, then the rule enforced by code"
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
3. **Classification (mandatory: it does not wait for a Class B route).** The plan step classifies a
   design by `MaterialRule.DESIGN` (Class B, raised and never lowered by an operator), exactly as
   `ai_fieldwork.py` does, instead of by an operator's exact-bytes record alone. Today
   `plan.py:163-174` returns `egress_unclassified_material` for an edited design with no record,
   before any query reaches the classifier of chunk 6, so without this chunk no real-client design
   can reach Brave. A design no rule can classify still parks. Test: an edited design runs its web
   tracks without an operator record; this supersedes OI-129's second sentence (the owner's decision
   of 2026-10-19, recorded in ADR 0008's amendment).
4. **Journey.** `test_deep_research_journey.py` with a recorded Class B route: Class C routes refuse
   the Class B query, the Class B route accepts it, nothing is sent twice.
5. **Activation.** The develop host's switches and the provider credential, an operator's act,
   verified by the live Deep Research run of the acceptance study (`mvp-acceptance-harness`).

6. **Derived-query class: content decides, not derivation (the owner's decision, 2026-10-19).**
   `aia-query-classifier-2` in `classification.py`. The context-class floor of
   `aia-query-classifier-1` ("nothing lowers a class") is removed. A query's class is the most
   restrictive of: (1) a client term (the client's and study's names and slugs, every non-public
   ENTITY or TERM, matched across case, diacritics, transliteration and spacing) → at least B, as
   today; (2) a run of five words shared with any text the run holds, which takes **that text's
   effective class**: A for raw client knowledge (SOURCE, DOCUMENT, DATASET, ARTIFACT kinds, as
   `knowledge_access.py` classes them) and for a design an operator raised to A, and an A query never
   leaves, as today; B (**new**) for derived knowledge (FACT, FINDING, TERM, ENTITY, DIMENSION,
   AUDIENCE), the design by rule and the study's own messages. The overlap buckets are built from each
   frozen text's own class, never from a category's example, so a paste from raw client knowledge or
   from an A-raised design is never downgraded to B. A query that trips none is Class C and may go to
   a Class C route. A paraphrase passes; a paste does not. The class is computed by code from the
   query's text and the texts the run holds, never from anything the model declares.
   **Residual risk, accepted by the owner:** the Codex review of #497 was right that a model can
   paraphrase a confidential launch or pricing question with none of these tokens, and the paraphrase
   is still Class B intent; Brave (US-based, query logs up to 90 days) will see which topics a client
   is researching. Kept as mitigations: every query is journaled and visible in the run; a per-client
   switch to turn derived search off and a zero-retention plan are available and not built.
   **Tests:** a client-named query stays at least B and a Class C route refuses it; a verbatim run of
   five words from the design is B and refused by a Class C route; a verbatim run from a client
   document, from raw client knowledge and from an operator-raised design is A and never leaves
   (each case separately); a verbatim run from derived knowledge is B; a paraphrase with no checked token is Class C and reaches the Class
   C route; a model that declares its own query public changes nothing. The tests of
   `aia-query-classifier-1` that assert "a paraphrase keeps the class of what it was written from" are
   **replaced** by these, each citing this decision; the cases that are still true (the client-named
   query, the verbatim paste) keep their assertions. Nothing ships until the amendment (ADR 0017
   decision 2, ADR 0008's class table) is recorded in the docs PR; if the data-owner role is held by
   someone other than the owner, they confirm it before activation on a real client.

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

## Deferred (2026-10-19)

The owner: "all these classifications, honestly lets get rid of them for now and build them later."
Every chunk here, the Class B provider and the classifier redesign alike, is **after the MVP**. The MVP
uses one flag per client instead (`deep-research-web-search` 53, the open posture). Chunk 6's content
rule (client terms and a five-word run shared with a text of its own effective class) and the two
review findings it collected, that a paraphrase keeps its intent and that overlap buckets must use each
text's own class, are kept as the **starting point** of the redesign, not as a contract.
See `mvp-development-plan.md` § Reach.
