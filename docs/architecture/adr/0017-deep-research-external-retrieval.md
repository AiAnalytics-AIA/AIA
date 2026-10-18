# ADR 0017 — Deep Research: AIA-owned web retrieval, tiered query egress, and grounding as the acceptance rule

**Status:** Proposed — develop (data owner's DR-1, DR-3, DR-4, 2026-09-25; DR-2 route choice and
DR-5 open). Amended 2026-09-27 by the recorded/offline implementation (§ Amendments); decision 4
amended 2026-10-18 by the topic gate and the student-thesis rule (D4).
Builds on [ADR 0005](0005-llm-gateway.md) (one model call path), [ADR 0006](0006-langgraph-agent-execution.md)
(a graph never outlives its attempt), [ADR 0007](0007-deterministic-tools.md) (models choose, code
computes), [ADR 0008](0008-eu-data-residency.md) (the egress boundary), [ADR 0010](0010-bedrock-eu-inference-route.md)
(Bedrock as the EU route), [ADR 0015](0015-client-first-product-interface.md) (Client Knowledge) and
[ADR 0016](0016-research-execution-and-model-transmission.md) (the licence gate).
**Date:** 2026-09-25 · **Plan:** [`.planning/plans/deep-research.md`](../../../.planning/plans/deep-research.md)

## Context

The `DEEP_RESEARCH` stage has no AIA executor. 18.6.6 fills it with a web-only, topic-string search
by two agents using the provider's server-side web search, accepting findings on the agent's own
quality score and on lexical agreement between agents (`legacy/npc-panel-18.6.6/app/research_context.py:335-387`
@ `b3bd42f`). The data owner wants research driven by the study's research questions and tracked
objects, over the client's own knowledge and the internet, as far as the budget allows.

Three facts decide the shape:

- Claude's server-side web search and fetch are not offered on Amazon Bedrock, AIA's EU route.
- `ToolEffect` cannot express a tool that leaves AIA or costs money (`domain/ai_tools.py:105-117`).
- A search query built from a client brief is client-derived material; residency is frozen
  (ADR 0008) and a refusal is never a reroute (`domain/residency.py:159-169`).

## Decision

1. **AIA owns web search and fetch as registered tools**, under a new
   `ToolEffect.EXTERNAL_RETRIEVAL`. Registration requires a declared route and a meter. Every call
   is classified, authorised by `evaluate_egress` for its class on that route, reserved and written
   to the usage ledger before it leaves, exactly like a model call. Provider-native browsing is not
   used even where a provider offers it: it would leave AIA without a per-query egress decision.

2. **Queries are classified by code, per query** — Class A (overlaps Class A text the run has read)
   is refused; Class B carries a client-identity or confidential term from the data owner's list
   (client name and aliases, study codename, Client Knowledge `ENTITY`/`TERM` items marked
   confidential); anything else is Class C. A query leaves only over a search route approved for
   its class. The model's own claim about a query's class is not an input.

3. **Channels are separated by tool grant.** Agents reading Client Knowledge hold no web tools;
   agents searching the web hold no knowledge, proposal or write tools. Web content is untrusted
   data: it reaches the synthesizer only as evidence that passed the gates below.

4. **Grounding is the acceptance rule.** A web claim is admissible only when its quoted excerpt
   occurs in the content-addressed snapshot of the page it cites (stored in `ArtifactStore`), and a
   critic agent judges the excerpt to support the claim. Source quality comes from declared tables,
   never from the agent's self-report; an unclassifiable source scores lowest.

   *Amended 2026-10-18 (owner's D4 on evaluation finding F1,
   [research-integrity-report](../../../.planning/plans/research-integrity-report.md) chunk 10):*
   grounding, a credible host and the critic are not enough, because none of them reads the topic
   a finding was searched for -- a mortgage thesis on an academic host was accepted for a
   current-account topic. The merge therefore also applies a **topic gate**, after the source
   score and before dedupe (`domain/deep_research/topicality.py`, `aia-dr-topicality-1`, carried
   in `aia-merge-3`): an object's finding must name its object in the quote or source title, by
   its distinguishing words together and never by one word of a longer name; a quote or title
   naming a sibling concept of a declared family (retail-banking products; the run's tracked
   objects) and none of the topic's own is set aside, unless it names a kind of the topic's (a
   mortgage under a loan topic); a question's finding must share two of the topic's words (all of
   them when it has fewer).
   Deterministic, no model; the investigator's claim never decides the first two rules. A
   finding that fails is quarantined `off_topic`, one whose topic leaves nothing to judge by
   `topic_undetermined`, the evidence kept in the bundle either way.
   Shared words are not shared meaning: population, place, period and what a sentence says
   remain the reader's to check.
   Anchors, all `@ 94744de` under `packages/aia_core/src/aia_core/domain/deep_research/`: the
   order is `merge.py:282` (score), `:299` (topic), `:320` (dedupe), each topic refusal kept with
   its evidence (`:299-313`); `aia-dr-topicality-1` is `topicality.py:103`, carried by
   `merge.py:86-88`; the object named is `topicality.py:593-606`, the concept swap `:607-617`
   (families `:436`), two shared words `:618-639` (`SHARED_TERMS` `:129`), and only the last reads
   the claim (`:626`; the first two read the quote and title, `:601`, `:611`). Tests:
   `test_deep_research_merge.py::test_an_off_topic_copy_is_set_aside_before_dedupe_and_never_stands_in_for_its_twin`,
   `::test_a_source_is_scored_before_its_topic_and_unknown_topics_are_never_accepted`,
   `::test_the_merge_rules_carry_the_topic_rules`;
   `test_deep_research_topicality.py::test_an_object_finding_names_its_object_in_the_quote_or_the_title`,
   `::test_a_word_of_a_longer_name_names_no_tracked_object`,
   `::test_a_mortgage_thesis_does_not_support_a_current_account_topic`,
   `::test_a_kind_of_the_topics_concept_is_no_swap`,
   `::test_the_runs_tracked_objects_are_one_family`,
   `::test_a_question_finding_shares_two_words_of_its_topic`,
   `::test_nothing_to_judge_by_is_undetermined_never_on_topic`.

   *Amended 2026-10-18 (D4, the same plan, chunk 11):* a credible host is not a credible document
   -- a university's host scored a bachelor thesis in its information system as an academic
   institution and the review accepted it. Before the source score (after a retraction), the
   merge therefore types each web finding's source by declared rules
   (`domain/deep_research/document_types.py`, `aia-document-types-1`, carried in `aia-merge-3`): a
   whole host that is a thesis register, an archive prefix on a declared university host, a path
   segment or a title segment that names the genre, on any host but an encyclopedia's
   (`wikipedia.org`, whose article on a genre bears its name). A source so typed is a **student
   thesis** (doctoral dissertations included in this version), and its finding is quarantined
   `student_thesis`, the evidence kept. Client Knowledge is never typed. The source table, its
   approval (ADR 0022) and every pin are unchanged: a thesis on an approved host is refused as a
   retracted work on one is. A thesis no rule declares, whose title does not name its genre, is
   still accepted; repository hosts (`dspace.*`, `.edu`) are not declared, and a DOI is no
   document type.
   Anchors, all `@ 94744de` under `packages/aia_core/src/aia_core/domain/deep_research/`: the
   order is `merge.py:247` (retraction), `:266-267` (thesis), `:282` (score), the thesis kept
   with its evidence (`:270-278`); Client Knowledge untyped is `merge.py:215`;
   `aia-document-types-1` is `document_types.py:78`; the encyclopedia first,
   `document_types.py:191-192` (`ENCYCLOPEDIAS` `:82`), then registers `:84`, archive prefixes
   `:87-92`, path segments `:94-102` and title phrases `:105-122`, in that order (`:188-224`).
   `git diff 3b8fd98 94744de` touches neither `sources.py` nor `settings.py`. Tests:
   `test_deep_research_merge.py::test_a_retraction_is_named_before_a_thesis_and_a_thesis_before_its_score_and_topic`,
   `::test_a_student_thesis_is_quarantined_by_name_and_kept_as_a_lead`,
   `::test_client_knowledge_is_never_typed`;
   `test_deep_research_document_types.py::test_every_page_of_a_thesis_register_is_a_thesis`,
   `::test_a_thesis_archive_on_a_declared_university_host_is_a_thesis`,
   `::test_a_path_segment_that_names_the_genre_is_a_thesis`,
   `::test_a_title_segment_that_names_the_genre_is_a_thesis`,
   `::test_an_encyclopedia_article_on_the_genre_is_not_a_thesis`,
   `::test_the_coverage_limits_stay_undetermined`.

5. **The legacy anti-leakage quarantine is kept exactly** and re-run at fieldwork compile against
   the final questionnaire. Quarantined evidence never becomes respondent context; accepted
   evidence enters fieldwork only as `EXTERNAL_CONTEXT`, never as a measured claim.

6. **Research is split into fingerprinted tracks** (question, object, or cross; internal or web) in
   one `deep_research` workflow type pinned to a Design Revision, so a later revision that adds
   objects researches only what changed. Tracks run in parallel inside one step, checkpointed per
   track; the run stops each track on budget, depth target or saturation, and records which.

## Alternatives considered

- **Provider-native web search on the Claude API or another platform.** Best-in-class browsing,
  but not on the EU route, and queries leave without AIA's egress decision or ledger. Rejected.
- **Declassify every query to Class C.** Simplest egress story, weaker research. Kept as the
  fallback posture while no Class B search route is approved, not as the design.
- **Two-agent lexical consensus as the acceptance rule (the reference).** Two agents can agree on
  the same invention. Kept as a confirmation bonus, replaced as the gate by grounding.
- **Move `DEEP_RESEARCH` after `RESEARCH_DESIGN`.** The design would lose its evidence. Rejected
  for track reuse across revisions.

## Consequences

- The usage ledger records tool calls as well as model calls; the generalized metered ledger
  (PROGRESS *Next* #2) and D11 must accommodate them.
- The `RESEARCH_DESIGN` stage fingerprint gains the evidence bundle id — a fingerprint migration.
- Live runs need a search provider route (DR-2). ADR 0010 is accepted for fictional Class C on
  develop only (AR-2, 2026-09-26); any client material, and so any Class B query or model call,
  needs D6. Everything else is buildable and testable offline on recorded doubles.
- ~~`research.deep_research` becomes its own parity-matrix capability~~ — the matrix is fixed at
  the reference's 78 capabilities; the leakage screen and merge are gated EXACT under
  `research.design`, which owns `research_context.py` (amendment 6).

## Amendments — 2026-09-27, the recorded/offline implementation

What building it on today's runtime changed. Each keeps the decision's intent and says what is
different and why; the contracts are in [deep-research.md](../deep-research.md).

1. **Decision 1: retrieval is code-called, and `EXTERNAL_RETRIEVAL` is not registered yet.** The
   gateway makes one call and one schema repair; there is no model tool loop, and adding one is a
   shared gateway change. So models *propose* queries in a strict schema and code sends them
   through classification, egress, a tool reservation and a journal. `ToolRegistry` keeps its two
   effects: its own rule forbids registering a metered external tool before the generalized ledger
   exists. The reserve / dispatching / outcome contract for tools is defined
   (`domain/deep_research/tooling.py`); a route with a price is refused until tool spend is held
   against the study's budget.
2. **Decision 2: a query's class is inherited, never inferred down.** Class = the most restrictive
   of the proposing call's context, a client-term match, and a five-word run shared with Class A
   text. Keywords can only raise a class, so a paraphrase of a client's brief without the names is
   still the client's brief. "Anything else is Class C" is replaced: a query written from a Class A
   context is Class A. A design is Class C only for an operator-declared fictional client.
3. **Decision 3: channels are separated by construction, not only by tool grant.** The web query
   proposer is never shown Client Knowledge; internal retrieval is deterministic over the
   knowledge frozen at enqueue; no agent holds any tool.
4. **Decision 4: grounding is exact and narrower.** The cited source must be one the same track
   retrieved; every number in the claim must be in the quote; a source containing
   prompt-injection text is quarantined as a source.
5. **Decision 5: the leakage rule bars, it does not discard.** A finding that reports a target
   outcome stays in the bundle as alignment evidence for the researcher and is barred from
   respondent context for good; respondent context is built at compile against the final
   questionnaire, which re-screens everything else.
6. **Consequences: parity.** Gated under `research.design`
   (`research.design/deep-research-leakage-merge`), not as a new capability.
7. **Decision 6: checkpoints are artifacts.** A completed track is an artifact whose input
   fingerprint is the track fingerprint; `ArtifactRepository.find_reusable` is both the per-track
   checkpoint and the cross-pass reuse. The fingerprint excludes the other subjects, so a pass that
   adds an object re-buys only that object's tracks.
8. **Decision 6, further: only completed work is reusable.** A track a gate refused, or one an
   uncertain tool call cut short, is stored for its own run alone (a resumed step finds it; no
   other run can), as are the plan and the review records. A refused track reused after its gate
   opened would never be researched.
9. **Decision 1, further: what a tool call is charged is decided in the gate, never in AIA's
   favour.** A provider that answered is charged the route's price, error or not; a failure that
   sent nothing is free; an uncertain call and a page refused after its dispatch are charged the
   ceiling. Recorded routes have no price, so nothing moves today.
10. **Decision 2, further: no model is paid to write a query that cannot leave.** The planner is
    not asked when retrieval does not exist, when the design's class is A, or when the route or
    its metering would refuse every query; the web tracks are blocked with the gate named.

## Revisit when

A search route is approved for Class B; D6 is decided; the Agent Runtime Foundation offers dynamic
child steps; or evaluation shows grounding rejects a material share of genuinely supported claims.
