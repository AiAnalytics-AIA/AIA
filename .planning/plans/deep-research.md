# Deep Research — a governed research swarm over Client Knowledge and the web

**Status:** planned — chunk 0 (this plan, ADR 0017 *Proposed*) only · **Owner:** research-engine +
ai-runtime · **Started:** 2026-09-25 · **Base:** `develop` @ `b3bd42f`
**Decided by:** the data owner, 2026-09-25 (DR-1, DR-3, DR-4 below; DR-2 and DR-5 still open).
**Follows:** the Agent Runtime Foundation (PROGRESS *Next*) — this is the first multi-agent workload
on it, and chunks 1–7 do not wait for it.

## Problem

`DEEP_RESEARCH` is the second stage of both lifecycles (`domain/pipeline.py:103` @ `b3bd42f`) with
a declared fingerprint contract (`pipeline.py:254-261`), but nothing in AIA executes it: the
`research` workflow starts at `compile` (`domain/workflow_templates.py:62-65`) and no executor
registers a deep-research kind. On develop a researcher still gets it from 18.6.6, and what 18.6.6
does is narrow:

- **One topic string, web only.** `run_dual_research` sends a topic plus the survey questions to
  two sequential agents with the provider's server-side web search, capped at 3–12 sources each
  (`legacy/npc-panel-18.6.6/app/research_context.py:390-459`, `data_library.py:432-452`). The
  client's own knowledge is never consulted, and the study's tracked objects are never a unit of
  research.
- **Quality is self-reported.** `source_quality` is the agent's own 0..1 guess, and it decides
  acceptance (`research_context.py:345`, threshold 0.55; single-agent acceptance at ≥ 0.90,
  `:375-377`). *Unknown scored as good* (CLAUDE.md §8).
- **Nothing proves a claim is in its source.** Consensus is lexical similarity between two agents'
  paraphrases (`:360`, ≥ 0.42) — two agents can agree on the same hallucination.

What it gets right, and what must survive: **the anti-leakage quarantine**. Evidence that reports
the answer to a survey question is logged but never becomes respondent context, by agent label
*and* by a deterministic second-line screen (`research_context.py:198`, `:313-332`, `:342-344`).
Accepted evidence becomes fieldwork prompt context (`bundle_to_kontext`, `:499-512`), so a leaked
published outcome makes the synthetic panel look accurate while predicting nothing.

The data owner's ask (2026-09-25): research driven by the study's research objects, over the
client's internal knowledge **and** the internet, as wide and deep as the budget allows.

## What stands in the way (verified @ `b3bd42f`)

1. **No tool may reach outside AIA.** `ToolEffect` has only `PURE` and `READS_STUDY_DATA`
   (`domain/ai_tools.py:105-117`); a metered external tool "cannot be registered, rather than
   being registered and uncounted".
2. **The provider cannot search for us.** Claude's server-side `web_search` / `web_fetch` are not
   offered on Amazon Bedrock (Claude API platform-availability table, checked 2026-09-25), and
   Bedrock is AIA's EU route (ADR 0010). AIA must own search and fetch as registered tools. This is
   also the better shape: every outbound query crosses AIA's egress decision and ledger instead of
   leaving invisibly from inside a provider.
3. **Client material may not reach any model yet.** Every route is Class C only until D6; licence
   eligibility is a separate gate (ADR 0016 §5, `domain/licence.py:129-142`), and panel-derived
   datasets are *not approved* for any provider.
4. **Objects arrive after the stage.** Tracked objects are a design/questionnaire input
   (`pipeline.py:145`, `IMPACT_ROOTS["tracked_objects"] = "QUESTIONNAIRE"`), while `DEEP_RESEARCH`
   precedes `RESEARCH_DESIGN`.

## Decisions

| # | Decision | By |
|---|---|---|
| DR-1 | **Research objects are both** the research questions (`research_plan.research_questions`) **and** the tracked objects (brands, products, entities). | Data owner, 2026-09-25 |
| DR-2 | **Web egress: "the one that brings the best results."** Interpreted inside the frozen residency invariant (ADR 0008) as **tiered queries**, below: queries may carry client context for quality, and that makes them Class B, so they travel only over a search route approved for Class B. **Open:** which search provider(s) and whether any is EU-approved; until then only Class C queries go out. | Data owner (intent) · **route choice open** |
| DR-3 | **Client Knowledge to the model: target Bedrock EU for Class A and B** (D6). Built now against recorded fixtures; live when D6 approves the route. | Data owner, 2026-09-25 |
| DR-4 | **Outputs: all of** Research Design input, respondent context, Client Knowledge proposals, a cited research report — **plus a fifth the data owner named "something else" without saying what.** | Data owner, 2026-09-25 · **fifth open** |
| DR-5 | **Default run budget and the depth presets** ("go ham" is bounded by money, never by a hidden cap). Proposed: three presets priced by `CostPreset` before start; the researcher can extend a parked run. | **Open** |

## Approach

### One workflow type, runnable at any Design Revision, incremental by track

A new workflow type `deep_research`, Study-scoped like `research` (ADR 0016 §7), pinned to a
Design Revision: the brief, the research questions and whatever objects exist at that revision.
Research is split into **tracks** — one per (subject × channel), where a subject is a research
question, a tracked object, or an object × question cross — and **each track is fingerprinted**.
This resolves the stage-order problem without moving the stage:

- **Pass 1, at `DEEP_RESEARCH`:** the brief-time revision; subjects are the questions plus any
  objects the brief or Client Knowledge `ENTITY` items already name. Feeds Research Design.
- **Pass 2, after Research Design fixes the objects:** the same workflow on the newer revision.
  Tracks whose fingerprint is unchanged are **reused, not re-bought**; only new or changed objects
  are researched.

Rejected: moving `DEEP_RESEARCH` after `RESEARCH_DESIGN` (the design then loses its evidence) and a
second stage id (a lifecycle change for both pipelines, a parity break with the reference's 13
stages, for what track reuse already gives).

### The graph

```
plan ──▶ investigate ──▶ merge ──▶ verify ──▶ synthesize ──▶ publish
 │         │ (tracks, in parallel inside the step, checkpointed per track)
 │         ├─ internal investigators  — Client Knowledge tools only, no web
 │         └─ web investigators       — web_search / web_fetch only, no knowledge tools
 └─ deterministic coverage check: every question × object cell has a track, or the plan is refused
```

`investigate` is **one step** whose executor schedules tracks with bounded parallelism, a
checkpoint per completed track and a ledger row per call. Resume skips checkpointed tracks. This
fits ADR 0006 (a graph must not outlive its attempt) and the worker's existing checkpoint and
heartbeat seams without teaching the engine dynamic fan-out. Cost of that choice: one long
attempt. The Agent Runtime Foundation may replace the in-step scheduler with child steps; the track
contract does not change.

### Who does what — models choose, code decides (ADR 0007)

| Role | Capability | Sees | May call | Emits (strict schema) |
|---|---|---|---|---|
| Planner | `RESEARCH_REASONING` | brief, questions, objects, a Client Knowledge index | nothing | `ResearchPlan`: tracks, sub-questions, query intents |
| Internal investigator | `RESEARCH_REASONING` | its track + retrieved items | `knowledge_search`, `knowledge_read` | `EvidenceItem`s citing `item_id@revision` |
| Web investigator | `FAST_EXTRACTION`/`RESEARCH_REASONING` | its track + a Class B study digest | `web_search`, `web_fetch` | `EvidenceItem`s citing a stored page snapshot |
| Verifier | `CRITIC` | one claim + its source excerpt | nothing | supported / unsupported / overstated |
| Synthesizer | `REPORT_WRITING` | **accepted evidence only**, never raw pages | nothing | Czech research brief; every number cites an evidence id |

Deterministic, in `domain/deep_research/` (stdlib + Pydantic, no I/O):

- **Anti-leakage screen** — the legacy rule ported **exactly** (`research_context.py:313-332`),
  plus the agent's label; **re-run at fieldwork compile against the final questionnaire**, because
  pass 1 only saw research questions. A quarantined item never becomes respondent context.
- **Citation grounding** — a web claim is admissible only if its quoted excerpt occurs in the
  stored snapshot of the page it cites (normalised whitespace). This replaces "two agents agree"
  as the primary acceptance signal; the verifier judges whether the excerpt *supports* the claim.
- **Source scoring** — from declared tables (official statistics and regulators, peer-reviewed,
  industry, media, forum, unknown), recency and geography; the agent's `source_quality` is
  recorded and ignored. An unclassifiable source scores lowest, never neutral.
- **Merge** — canonical URL and claim-similarity dedupe (ported), independent-confirmation
  bonus, per-reason quarantine (`target_outcome_overlap`, `ungrounded_excerpt`,
  `low_source_quality`, `unsupported_by_verifier`, `no_independent_confirmation`).
- **Coverage matrix and stop rule** — "go ham" means: keep opening sub-tracks while (a) the
  reservation has room, (b) some question × object cell is below its depth target, and (c) the
  last *k* calls in the track still produced newly accepted evidence (saturation). Whichever ends
  first ends the track; the reason is recorded.
- **Budget allocator** — splits the run reservation across tracks; a track that exhausts its share
  parks, the run parks `AWAITING_BUDGET` with everything so far kept, and *extend budget* resumes.

### The two new tool families

**`knowledge_search` / `knowledge_read`** — `READS_STUDY_DATA` over
`ClientKnowledgeRepository.for_study` (`infrastructure/client_knowledge_repository.py:166`), so a
study sees what its study grant sees (ADR 0015 §7). The result's data class comes from the item
kind: `DOCUMENT`/`DATASET` → Class A, approved `FACT`/`FINDING`/`TERM` → Class B. A `DATASET` item
carries its lineage, so the licence gate refuses panel-derived material at the next model call —
no special case in the tools.

**`web_search` / `web_fetch`** — a new `ToolEffect.EXTERNAL_RETRIEVAL`. Registering one requires a
declared route and a meter; every invocation:

1. **classifies the query** deterministically (below) and asks `evaluate_egress` for that class on
   the search route — refused is refused, never rerouted (`residency.py:159-169`);
2. **reserves and ledgers** the call like a model call (a tool row in the usage ledger);
3. `web_fetch` only: public `http(s)` hosts only (no private, link-local or metadata addresses,
   resolved and re-checked after redirects), size and content-type caps, and a **content-addressed
   snapshot in `ArtifactStore`** so every citation stays checkable after the page changes;
4. returns page content marked **untrusted**. Web investigators hold no write, propose or
   knowledge tools, their output is a strict schema, and the synthesizer never sees raw pages — a
   prompt injection in a page can at worst produce an evidence item that then fails grounding or
   verification.

### Tiered queries (DR-2)

Web investigators get a **Class B study digest** (the brief and objects, summarised — not raw
documents) because that is what makes queries good. Their model calls are therefore Class B
(Bedrock EU, D6). Each query is then classified by code, not by the model:

- **Class A — refused.** It shares a long n-gram with any Class A text the run has read.
- **Class B** — it contains a client-identity or confidential term: the client's name and aliases,
  the study codename, and Client Knowledge `ENTITY`/`TERM` items marked confidential.
- **Class C** — otherwise. Public market terms and competitors' public brand names are Class C.

A query goes out only over a search route approved for its class. With no Class B search route
configured, Class B queries are refused and recorded; the agent may rephrase, and the rephrasing is
classified again. What counts as confidential is the data owner's list, not a model's judgement.

### Outputs (DR-4)

1. **Evidence bundle** (`deep_research_bundle`, hashed): accepted and quarantined items with
   reasons, coverage matrix, per-track stop reasons, quality status, full provenance. Its id joins
   the `RESEARCH_DESIGN` stage inputs — **a fingerprint migration** (`pipeline.py:376-389`), so
   re-running research reopens the design and nothing upstream.
2. **Respondent context** — accepted `context_only` items as context blocks (the legacy
   `bundle_to_kontext` shape), evidence role `EXTERNAL_CONTEXT`, re-screened at compile. Never a
   measured claim: the evidence gate refuses it as a number source for results.
3. **Client Knowledge proposals** — `SOURCE` and `FACT`/`FINDING` proposals through
   `propose_from_study` (`client_knowledge_repository.py:299`), deduplicated against existing
   items, origin `deep_research`, never self-approved.
4. **Research report** — a cited study artifact; the analysis modules' prose-number coverage check
   applies (every number cites an evidence id); external figures are labelled as external, never
   as panel results. Delivery to a client still needs human sign-off.
5. **The fifth output** — DR-4, open.

### Parity

`research_context.py` is today folded into `research.design` (SEMANTIC, MVP blocker via AC-02,
`docs/migration/parity-matrix.json`). Chunk 2 splits out `research.deep_research`: the leakage
screen and merge rules **EXACT** against fixtures captured by running the vendored unit's own code;
citation grounding, deterministic source scoring and object tracks recorded as **intentional
differences** with their reasons. Research quality itself is SEMANTIC and gets a small graded eval
set, not an equality gate.

## Trade-off accepted

Every web query, page and claim passes code-owned classification, grounding and ledgering, which
makes a run slower and costlier than letting a provider's agent browse freely — in exchange for
research whose every sentence is traceable to a stored source and whose every query was allowed
to leave.

## Chunks

Each lands with code, tests and the documents it changes; chunks 1–7 need no model, no network and
no decision.

- [x] 0. **This plan and ADR 0017** (*Proposed*: the external-retrieval tool effect, owned search
      and fetch, tiered query egress, grounding as the acceptance rule); PROGRESS *Next* and
      *Decisions* DR-1…DR-5.
- [ ] 1. **Domain contracts** — `domain/deep_research/`: `ResearchScope`, `ResearchTrack` (with
      fingerprint), `EvidenceItem`, `QuarantineReason`, `EvidenceBundle` (hashed),
      `QualityStatus`. Strict schemas, no I/O.
- [ ] 2. **Leakage screen and merge, ported EXACT** — fixtures captured from
      `research_context.py` on synthetic inputs; `research.deep_research` in the parity matrix
      with its gate.
- [ ] 3. **Deterministic additions** — citation grounding, source-scoring tables, coverage matrix,
      saturation stop rule, budget allocator.
- [ ] 4. **Tool usage in the ledger** — tool calls as usage rows (extends `ai_usage_events`, one
      migration), one reservation per request as D11 resolved it in the Agent Runtime
      Foundation; coordinated with *Next* #2 (the generalized ledger).
- [ ] 5. **`ToolEffect.EXTERNAL_RETRIEVAL`** in `ToolRegistry`: registration needs a route and a
      meter; invocation runs query classification → egress → reservation → call → ledger. Refusal
      tests: no route, class not approved, lease lost before dispatch.
- [ ] 6. **Query classifier** from Client Knowledge terms, with adversarial tests (aliases,
      diacritics, spacing, transliteration, n-gram leakage from Class A text).
- [ ] 7. **`web_fetch` safety and snapshots** — address checks across redirects, caps, snapshots
      in `ArtifactStore`; search and fetch transports behind protocols with recorded doubles. No
      live network in any test.
- [ ] 8. **Client Knowledge tools** — search and read over `for_study`; data class per kind;
      lineage; a study-only grantee and another client's study both refused.
- [ ] 9. **Agents** — five `AgentDefinition`s with strict output contracts and versioned prompts
      rendered from the enums (the leakage rule, the quarantine reasons); recorded-exchange tests.
- [ ] 10. **The `deep_research` workflow and executor** — plan → investigate → merge → verify →
      synthesize → publish; the track scheduler with checkpoints, bounded parallelism,
      cancellation, parking on budget and capacity; worker tests on a scripted gateway.
- [ ] 11. **Outputs** — the bundle artifact and the `RESEARCH_DESIGN` fingerprint migration;
      knowledge proposals; context blocks with the compile-time re-screen; the report with the
      number-coverage gate.
- [ ] 12. **API and the Deep Research stage screen** — `/api/v1/studies/{study_id}/deep-research/…`
      (start, state, cancel, extend budget, bundle, evidence item); progress in real counts
      (tracks, calls, accepted, quarantined, spend); an evidence browser showing quarantine
      reasons.
- [ ] 13. **Live enablement** — *blocked on DR-2 (a search route) and, for Class B, D6. AR-2
      is resolved: ADR 0010 is accepted for fictional Class C on develop only (2026-09-26)*:
      search route configuration, a Class C smoke run, then Class B once D6 approves.

## Review outcome

Filled in when the plan is archived.
