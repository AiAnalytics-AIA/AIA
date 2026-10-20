# ADR 0040 — The Lead looks things up on the web: it asks, code searches through `RetrievalGate`, and a continuation turn answers with grounded, cited results

**Status:** Proposed — 2026-10-20, from the product owner's answer Q6 (a) of the same day
(`.planning/evidence/scope-freeze/answers-2026-10-20.md`, #523 @ `ee21982`). Not accepted until the
product owner says so. **Amends** [ADR 0026](0026-research-lead-proposes-a-person-decides.md)
decision 3 ("the Lead calls no tool … makes no HTTP request"): the Lead may *request* a lookup in its
closed output, which code performs. **Widens** [ADR 0017](0017-deep-research-external-retrieval.md)'s
scope to a second caller of AIA's web retrieval. **Builds on** [ADR 0028](0028-orchestration-scope-wallet-and-plan-card.md)
(the wallet), [ADR 0032](0032-open-posture-classification-deferred.md) (the posture) and
[ADR 0021](0021-deep-research-purpose-target-lineage.md) (external evidence is never respondent
evidence). **Leaves unchanged** the Deep Research engine and its steps, grounding, and every
evidence gate.
**Date:** 2026-10-20
**Plan:** [lead-orchestration](../../../.planning/plans/lead-orchestration.md) LO20 (#523);
`deep-research-web-search` 56; `research-lead-workbench` 32

## Context

The owner, Q6: "a governed 'Hledat na webu' through RetrievalGate, OPEN clients, charged to the
wallet. i really want to preserve a good UX here, and not have limited results." And on D-35: "Each
lead agent needs a web search to help fetch more info if needed, like a regular chatbot."

Two facts of the code shape it:

- **The Lead holds no tools.** A turn is one durable worker step over a frozen context, with a closed
  output and at most one repair (ADR 0026 decisions 1-3); the API never calls a model.
- **Every query and fetch already has one exit.** `RetrievalGate` classifies, checks egress,
  meters, reserves and journals each call before it leaves
  (`packages/aia_core/src/aia_core/application/web_retrieval.py:788 @ 854c209`), and grounding
  accepts a quote only when it locates in a captured snapshot
  (`domain/deep_research/grounding.py:116 @ 854c209`). Deep Research runs it in six steps; nothing
  else calls it.

## Decision

### 1. The Lead requests; code searches; a continuation turn answers

A turn's closed output gains `lookup`: one to three queries in the Lead's words, and why. The turn
ends there. Code starts a **lookup step** (one track, not a Deep Research run,
`deep-research-web-search` 56) that sends the queries through `RetrievalGate`, returns each route's
hits together (a page per query), fetches the top pages in parallel under the existing per-host
pacing, and captures each as a content-addressed snapshot. When the step finishes, it enqueues a
**continuation turn** (LO6) whose context carries the results as typed data: titles, snippets,
links, and the captured texts by snapshot id. That turn answers the person.

So the Lead still calls nothing and reads nothing outside a frozen context; ADR 0026 decision 3's
reason (a tool call would sit beside the gates) holds, and the request is the only new output.

### 2. Its answer is grounded and labelled

Every claim the continuation turn makes from a page cites it inline with the link and a quote;
the validator accepts a quote only when it locates in that turn's captured snapshot, and refuses a
number not in a quote or the context's admitted claims (ADR 0026 decision 3's number rule, unchanged).
Each citation is labelled *externí zdroj*; it is never respondent evidence and never an admitted
claim. A captured page becomes Client Knowledge only by a person's "Ověřeno, přidat zdroj"
(`application/verified_sources.py`), as today.

### 3. Who may search: OPEN clients only, pinned

A lookup pins the client's posture when it starts (ADR 0032). For an OPEN client the queries go to
any composed search route; for a CLASSIFIED client nothing is sent, and the Lead says it may not
search and why; for a fictional client, as for Deep Research. A query's class is otherwise as ADR
0032 sets it. The routes, prices and live approvals are Deep Research's (ADR 0022).

### 4. Paid from the wallet, without a card, inside a bound

"Without limited results" and no extra click (Q6): a lookup the Lead requests starts without a
decision card, charged to the study's wallet. This is a narrow exception to ADR 0028's rule that a
Lead-initiated paid start needs an approved plan, and it is bounded by code:

- a lookup's ceiling (search calls plus fetches at the route's pinned price) is held against the
  wallet before anything leaves, under the study lock; an unknown price refuses, never counts as zero;
- at most a fixed number of queries and fetches per lookup and of lookups per turn, set as
  configuration, no defaults;
- a lookup that does not fit the wallet parks and asks the person, like any uncovered spend;
- each search and fetch is shown in the turn with its cost.

The model reservation of the continuation turn is the Lead's ordinary turn reservation.

### 5. It reaches the person as it arrives

The Lead pane shows the result list as the step reports it, and the continuation turn streams its
answer (D-39). The latency target is the route's own response time for the first results, measured
in the chunk's PR.

### 6. Text from the web is data, never instructions

Captured page text enters the continuation turn's context in a fenced layer marked as external
material (Class C, a public source, `domain/material_rules.py`), screened by the existing
instruction detector (`grounding.py:226 @ 854c209`), whose hits are named in the context. Whatever
a page says, the Lead's output stays closed: an edit is a proposal, a paid action a card or a plan,
and nothing a page asks for can approve, spend beyond the lookup's bound or start a run.

## Alternatives considered

- **Give the Lead a live search tool inside one turn.** It breaks the frozen, reproducible context
  and puts a call beside the gates (ADR 0026 decision 3).
- **Start a Deep Research run for every question.** Six steps, verification and a sealed bundle:
  minutes and cost where a chatbot answers in seconds, which is what the owner asked against.
- **A model's own recollection, presented as a search.** Not web research (CLAUDE.md, *Native
  Research agents*).
- **A decision card per lookup.** The owner asked for no extra click; the wallet and the bound are
  the control instead.

## Consequences

- A new output field, a lookup step and its executor, a continuation turn per lookup (one more paid
  model call), and wallet charges for search and fetch.
- An OPEN client's Lead queries reach a US search provider (Brave), as ADR 0032 states for Deep
  Research.
- Tool spend reconciles in the usage ledger only after M11 (ADR 0028's open item 4, D-05).

## What enforces it

- `RetrievalGate` stays the only exit for a query or URL (`make layer_check`, existing); the lookup
  executor is the only new caller.
- Tests: a CLASSIFIED client's lookup sends nothing and the Lead says why; a lookup's ceiling is held
  against the wallet before anything leaves, and one that does not fit parks; the per-lookup and
  per-turn bounds refuse an extra query; a quote not in a captured snapshot is refused; a cited
  result is labelled external and never enters an admitted-claim ref; a page containing "approve the
  plan" text changes nothing the Lead's closed output can do; a retry replays no paid search.

## Unblocks

`deep-research-web-search` 56 (W3), `lead-orchestration` LO20 (W3), `research-lead-workbench` 32.

## Open for Nigel

1. **The bound values**: queries per lookup, pages fetched per lookup, lookups per turn. This ADR
   requires them as configuration; the owner's "not have limited results" suggests generous values,
   to be measured on develop against cost.
2. **A lookup without a card** is an exception to ADR 0028's "a Lead-initiated paid start needs an
   approved plan". Q6's "charged to the wallet" and no extra click read as yes; confirm.
3. **Amending ADR 0026 decision 3, which is Accepted**, needs the owner's explicit yes (D-08 named
   the other amendments, not this one).
