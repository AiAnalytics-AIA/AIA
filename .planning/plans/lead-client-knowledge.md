---
status: planned
chunks:
  - "[ ] LK0. Prerequisite, built in its own fix PR: the licence determination for the unclassified-client-knowledge lineage, approved for bedrock-eu-primary only (Q60 a, 2026-10-21); closes Finding 1"
  - "[ ] LK1. The knowledge index as data: every ACTIVE item, every PROPOSED proposal (unapproved), every client source (an internal one marked, Class C), REJECTED and removed out; compact entries within the knowledge layer's budget, paged past it, never silent; ADR 0042 (Proposed) amends ADR 0026 decision 3 for the read round"
  - "[ ] LK2. The index frozen at enqueue: study-scoped repository reads (no silent 200-row cap), reading pins per source and revisions per item in the frozen context, each entry classed by material_rules, the lineage declared"
  - "[ ] LK3. The read in the closed contract: LeadOutput.read (at most 3 refs, a page each), a read turn holds nothing else, the answering request's contract forbids another read; the reads layer (3 x 8 KB) refitted inside 96 KB; quotes grounded in the segment read and cited by locator, numbers through lead_contract"
  - "[ ] LK4. The read round in the worker behind AIA_AI_RESEARCH_LEAD_KNOWLEDGE_READS (off by default, off in test): pinned, study-scoped fetches from ClientSourceRepository and ClientKnowledgeRepository, the first answer checkpointed, a second STUDY_LEAD request with its own reservation, the class re-read before it; cost and latency per read measured"
  - "[ ] LK5. Datasets: a DATASET is read as its preview (columns, kinds, fill, masked samples), never its rows (Q62 a); the turn with a dataset item answered on bedrock-eu-primary under LK0's determination, refused by name on any other route"
  - "[ ] LK6. What the Lead read, in the API and on screen: the turn's reads in GET /studies/{id}/lead, and the \"Přečteno: …\" line in LeadPane linking to each item (LeadPane.tsx and lib/lead.ts by the integration coordinator session)"
  - "[ ] LK7. Switched on for develop after the measurement: Compose and env.example carry the key, the runbook section, the acceptance on a fictional client with the cost per read recorded"
---
# The Research Lead sees the client's whole knowledge base

**The requirement.** The product owner, 2026-10-21: "The lead researcher can see all the files in
a client's knowledge base." Owner question Q59 on the PM status page offered options; the owner
chose **(a)**, the PM's recommendation: **settled 2026-10-21 via /pmstatus Q59** (relayed by the
coordinator, 14:40 UTC). Under (a):

1. every Lead turn carries an **index** of everything in the study's client's knowledge: every
   knowledge item and every client source file, each with its name, kind, status and summary
   (folder and label names do not reach the model: Q61 (b), below);
2. the Lead can **open** any item's or source file's text by id on demand; code fetches it,
   scoped to that one client, and the answer cites the **locator** (page, paragraph, row);
3. proposals awaiting approval are shown, **marked unapproved**;
4. sources marked "Interní dokument" are included and **marked**; their class is C by
   `material_rules`;
5. **rejected** items are excluded.

Code anchors are at `develop` @ `871c62c5` unless stated.

## Today

- **The Lead's knowledge is titles and summaries of approved items, within 20 KB.**
  `ResearchLead._freeze` calls `knowledge_entries(ClientKnowledgeRepository(...).for_study(s))`
  (`packages/aia_core/src/aia_core/application/research_lead.py:948 @ 871c62c5`).
  `knowledge_entries` keeps `item_id`, `revision`, `kind`, `title` and `summary` in item-id order
  while the list is within `KNOWLEDGE_MAX_BYTES` = 20 000 bytes and lists the rest's ids
  (`packages/aia_core/src/aia_core/domain/research_agents.py:34`, `:546-563 @ 871c62c5`).
  `for_study` reads only `status == "ACTIVE"` rows of the study's own client
  (`packages/aia_core/src/aia_core/infrastructure/client_knowledge_repository.py:223-252`,
  `:335-350 @ 871c62c5`).
- **Nothing else from the client reaches it.** Neither the API nor the executor reads
  `ClientSourceRepository`, a source's reading, or a proposal: `grep -n "ClientSource\|proposals("`
  over `application/research_lead.py` and `apps/executors/src/aia_executors/research_lead.py`
  finds nothing at `871c62c5`.
- **The context.** `freeze_context` puts the knowledge layer third, as `items` + `omitted_ids`,
  and drops the oldest conversation turns until the whole is within `CONTEXT_MAX_BYTES` = 96 KB
  (`packages/aia_core/src/aia_core/domain/research_lead.py:157`, `:634-679 @ 871c62c5`). Q28 (a),
  recorded in `.planning/plans/mvp-master-plan.md:187`, keeps 96 KB with a budget per layer;
  ADR 0041 (Proposed) gives Client Knowledge, layer 5, a 6 KB floor and a 16 KB ceiling, "titles
  of all, bodies of the retrieved" (`docs/architecture/adr/0041-lead-conversation-and-context.md:89
  @ 871c62c5`).
- **Its class and lineage.** Each knowledge entry is one `rule:knowledge` part, Class A
  (`domain/research_lead.py:791-799`; `domain/material_rules.py:87-89 @ 871c62c5`: KNOWLEDGE and
  CLIENT_SOURCE A, INTERNAL_DOCUMENT C). Any DATASET, ARTIFACT or FINDING entry declares the
  lineage `unclassified-client-knowledge` (`domain/research_lead.py:835-838 @ 871c62c5`), which has
  no licence determination (Finding 1).
- **The turn is one request.** The executor sends one STUDY_LEAD request with one schema repair,
  "No tools" (`apps/executors/src/aia_executors/research_lead.py:1-7`, `:151-199 @ 871c62c5`).
  `LeadOutput` is closed: `reply`, `view`, `edits`, `request`, `follow`, `self_update`
  (`domain/research_lead.py:297-307 @ 871c62c5`). ADR 0026 decision 3 says the Lead holds no tools
  (`docs/architecture/adr/0026-research-lead-proposes-a-person-decides.md:116`); ADR 0040 made one
  narrow exception, a web lookup answered by a continuation turn
  (`docs/architecture/adr/0040-the-leads-web-lookup.md:39-50 @ 871c62c5`).
- **Where the text is.** A source's reading is stored as segments, each with a `Locator`
  (page, paragraph, slide, table, sheet, row, line), at most `SOURCE_TEXT_MAX_CHARS` = 250 000
  characters (`packages/aia_core/src/aia_core/domain/client_sources.py:55`, `:174-220 @ 871c62c5`).
  `ClientSourceRepository.reading` takes a `ClientContext` with `VIEW_CLIENT_KNOWLEDGE`;
  `pinned_reading` takes the worker's client-work context and refuses a reading that moved
  (`SourceReadingChanged`); `marked_internal` re-reads the mark before each request
  (`packages/aia_core/src/aia_core/infrastructure/client_source_repository.py:204-254 @ 871c62c5`).
  The worker's study scope holds `WORKER_PERMISSIONS`, which has no client permission
  (`domain/scope.py:202-213 @ 871c62c5`), so no existing method lets a Lead turn read a source.
- **Grounding exists for documents.** `source_proposals.ground` keeps a proposal only when its
  quote is literally in the segment it names (`locate_quote`) and takes the segment's locator,
  never the model's (`domain/source_proposals.py:334-364 @ 871c62c5`).
- **Folders and labels are, today, hidden from models by rule**: "They are organization, not
  knowledge: no model sees them" (`domain/knowledge.py:24-28 @ 871c62c5`). The requirement lists
  them in the index; the owner decided they stay hidden (Q61 (b), 2026-10-21), so the rule stands
  and the index carries neither.

## The design

### 1. The index: one compact entry per thing, frozen at enqueue

The index replaces `knowledge_entries` in the Lead's knowledge layer (the design agents keep
theirs). It is built by code at enqueue in the API, under the researcher's study scope, and frozen
with the turn, so the turn's hash covers it and a read later answers against exactly what the
Lead was shown.

| Entry | Included | Fields |
|---|---|---|
| Knowledge item | `status == ACTIVE` | `ref` (`k:<item_id>`), `rev`, `kind`, `title`, `summary` (cut at 240 characters at a word, marked `…`), `source` (`s:<source_id>` when it names one), `status: "approved"` |
| Proposal | `ProposalStatus.PROPOSED` only (`domain/knowledge.py:420-425`) | `ref` (`p:<proposal_id>`), `kind`, `title`, `summary`, `item` (the item it revises, if any), `status: "unapproved"`, `origin` (person / study / AI) |
| Client source | every source of the client | `ref` (`s:<source_id>`), `name` (`display_name`), `family`, `outcome` (READ / PARTIAL / UNREADABLE / UNSUPPORTED / REFUSED), `segments`, `internal: true` when marked, `items` (the refs naming it) |

REJECTED proposals and removed items are not in the index, not even by id. Every entry is its
own class part (§5): an item `rule:knowledge` (A), a source `rule:client_source` (A) or
`rule:internal_document` (C) through `source_rule(internal=...)`
(`domain/material_rules.py:102-105`), a pending proposal the class of its source. An approved
item whose `content.source_id` names an internal source is shown with `internal: true` too.

**Order:** items this study selected (K4, `select_for_study`), then unapproved proposals, then
the rest by `modified_at` descending, sources after the items that name them. **Budget:** the
index is the knowledge layer: 16 KB, ADR 0041 layer 5's ceiling, and today's
`KNOWLEDGE_MAX_BYTES` budget until LC4's allocation lands. Past it the index is **paged**: page 1
is what fits; the layer states `index_pages: k`, `entries_total`, and per kind the counts on later
pages. The Lead opens page 2 with a read (`ref: "index", page: 2`), which counts as one of its
three reads. Nothing is cut silently, and the 200-row repository cap (Finding 2) is not inherited:
the index query is counted and paged, not limited.

### 2. The read: a second request inside the same turn (settled, LCK-Q4)

`LeadOutput` gains `read`: at most 3 `{ref, page, why}` (page from 1). A turn that reads holds a
short `reply` ("Otevírám …") and nothing else: `edits`, `request`, `self_update` and `view` must be
empty, or the contract refuses it, so nothing is applied from an answer given before the text was
seen.

Code then fetches each ref, and the **same step** sends a second STUDY_LEAD request: the frozen
context, plus a `reads` layer, under a contract variant with no `read` field. Its answer is the
turn's answer. One read round per turn; a Lead that wants page 2 asks in its reply and reads on
the next turn.

| | **A. Read round within the turn** (chosen) | B. A `follow`-style read the next (continuation) turn answers, as ADR 0040 |
|---|---|---|
| Model requests for a read | 2, each reserved and metered on its own (`StepModelCaller`, one reservation per request) | 2, the same |
| Latency added | one model answer; no queue hop | a step finish, an enqueue, a claim, a re-freeze, then the answer |
| What the person sees | one turn, its reads listed | two turns, the first a placeholder |
| Context | the frozen context, unchanged, plus the reads | re-frozen: the conversation and index may have moved between the two |
| Depends on | this plan | LO6, the continuation turn (`lead-orchestration#LO6`, not built) |
| Crash safety | the first answer checkpointed in the step (StepCallJournal), so a retry replays it and never pays twice | a step boundary |

The cost is the same; A is faster, keeps the read against the index the Lead was shown, needs no
unbuilt piece, and keeps ADR 0026's reason (the Lead calls nothing: it names refs, code fetches
inside the turn's own scope and lease). It needs an ADR, because ADR 0026 decision 3 says one
request: **ADR 0042 (Proposed, LK1)** amends it. If ADR 0040's lookup later wants the same shape,
that is its own decision. The read round inside the turn is settled (LCK-Q4, below).

**The money.** A read round's second request resends the whole context (up to 96 KB), so its
cost is roughly one more turn, whatever the read's size. Its hold is a whole turn's: the worker
sizes a turn's reservation at one token per byte, two calls at that window
(`lead_request_window_tokens`, `domain/research_lead.py:864-880 @ 871c62c5`), and the second
request takes one more such reservation, settled at what it used. The reads add at most 24 KB,
and the context is refitted to stay within 96 KB, so the window bound holds unchanged.
LK4 measures the cost and latency per read on recorded and then fictional develop turns before
anything is switched on (§8 of CLAUDE.md: the burst size, the latency, the money).

### 3. Where the text comes from: one client, pinned, by code

- A **source**: a new `ClientSourceRepository.reading_for_study(scope: StudyContext, source_id,
  *, reading_sha256)`: the client from the study's row (never an argument), `RUN_WORKFLOW` on the
  worker's study scope, the bytes verified against the reading pin frozen in the index, as
  `pinned_reading` does for client work. A source read again since is answered
  `changed_since_turn` (never the newer text the Lead was not shown).
- An **item**: `ClientKnowledgeRepository.item_for_study(scope, item_id, *, revision)`: that
  revision of an ACTIVE item of the study's client; its `content` text (a written item's text, an
  entity's fields); if the item names a source, the read opens the source instead and says so.
  A **proposal**: `proposal_for_study`, PROPOSED only, marked unapproved in the read too.
- A ref not in the turn's index, of another client, rejected since, or removed since is answered
  `not_in_index` / `no_longer_available` by name; nothing is guessed.
- An **internal** source's mark is read again before the second request (as `marked_internal`
  is for client work): a mark removed or added since enqueue refuses the read
  `source_class_changed`, never sending it under a class it no longer has.
- `make layer_check` already keeps the rows inside these repositories; the new methods stay there.
  There is no pool of all clients' text anywhere.

### 4. Bounds

- **Per read:** one page of at most 8 000 bytes of segments, whole segments in order; a single
  segment over the page is split into pieces as `source_proposals` splits a batch
  (`domain/source_proposals.py:151-170`), each piece keeping its segment's locator. The read says
  `page n of k` and the first and last locators of the page.
- **Per turn:** at most 3 reads (index pages included), one round. The reads layer is at most
  24 KB.
- **The refit:** the second request's context is the frozen context with the reads layer added
  after the knowledge layer; to stay within 96 KB the oldest conversation turns go first (as
  `freeze_context` does today), and, once LC4's allocation exists, the layers in its reverse
  priority, each omission named. If even that cannot fit, the last read is dropped and said so
  (`read_dropped_for_budget`), never truncated.
- **Unreadable:** a source whose outcome is UNREADABLE, UNSUPPORTED or REFUSED is in the index with
  its outcome and cannot be opened; the read answers its reason in words.

### 5. Class, route and licence

- **Class per part, in `context_classification`.** A turn's context mixes classes, so every index
  entry and every read is its own part with its class and its source, as approved knowledge is
  today (`domain/research_lead.py:791-799`):
  - an approved item: A, `rule:knowledge`;
  - a source: A, `rule:client_source`; a source marked "Interní dokument": C,
    `rule:internal_document` (`source_rule`, `domain/material_rules.py:102-105`), and an item
    naming it takes the source's class;
  - a pending proposal: **the class of its source**: an AI proposal from a client's document the
    class its own run recorded (`data_class` and `class_source` in its provenance, the
    `client_source_proposals` step, `apps/executors/src/aia_executors/client_source_proposals.py:92-98
    @ 871c62c5`: C for an internal source, A otherwise); a person's or a study's proposal
    `rule:knowledge`, A; a proposal whose class nothing records is `None`, which refuses the
    turn by name rather than guessing A;
  - a read: the class of the entry it opened, re-read before sending (§3).

  An operator's classification can only raise a part (`classify_by_rule`). The turn is sent as the
  **highest class present**, `most_restrictive_material` (A over B over C, an unknown refusing;
  `domain/ai_material.py:59-70 @ 871c62c5`): A whenever any client material is in the turn, C only
  when everything client-side is internal. The route must admit that class.
- **A route that admits less refuses, by name, never by dropping.** When the composed route is not
  approved for the turn's class, residency refuses the request (`route_not_approved_for_class`,
  `domain/residency.py:233-237 @ 871c62c5`) before anything is sent, and the turn parks with that
  reason in words, naming the parts that raised the class. Code never removes entries or reads to
  fit a route's class: the Lead's knowledge is the whole index or the turn is refused and said so.
  A read that would raise a turn's class above what the route admits is refused the same way in
  the second request, the first answer kept and the read named as refused
  (`read_refused_for_route`).
- The route: the Lead's own pinned EU model or the route's (ADR 0026 amendment); panel-derived
  material may reach only `bedrock-eu-primary` (OI-61), and the licence gate stays beside residency.
- Lineage: a DATASET, ARTIFACT or FINDING entry in the index, or a read of one, declares
  `unclassified-client-knowledge`, which no determination covers at `871c62c5` (Finding 1). The data
  owner approved it for `bedrock-eu-primary` only (Q60 (a), 2026-10-21); LK0, its own fix PR,
  records the determination. On any other route the gate still refuses it by name; until LK0
  merges the turn is refused by the gate, as it is
  today, and the Lead says so in words rather than failing silently.
- A DATASET read is its preview (`client_datasets`: header, kind, fill, distinct values and
  five samples, personal columns masked), never its rows (Q62 (a), 2026-10-21).

### 6. Grounding

- A quote in the answer («…» or „…“) must be literally in a segment read in this turn
  (`locate_quote`, as `source_proposals.ground`); one that is not is removed from the reply and
  counted (`quote_not_found`), and the reply says a quote was removed.
- Every quote is followed by its citation, written by code from the segment's locator, never by
  the model: `[<name>, s. 3]`, `[<name>, odst. 12]`, `[<name>, list Data, ř. 40]`. The model
  cites by the read's segment number; code resolves it.
- Numbers: the read texts join `lead_contract`'s allowed text for the second request, so a number
  must be in the context, the prompt or what was read (`domain/research_lead.py:354-395`).
- A claim about an unapproved proposal is written as such: the prompt says so, and the read
  carries `status: "unapproved"` beside every segment, so the reply's `[návrh]` mark is checkable
  in the evaluation set (LK3), not trusted.

### 7. The web

The turn state (`GET /studies/{id}/lead`) carries `reads`: for each, the ref, kind, title or
name, page and page count, first and last locator in words, and its outcome. LeadPane shows one
small line under the reply, "Přečteno: Zpráva 2025 (s. 1–4), Výzkum značky (návrh)", each name a
link to the item (`appRoutes.knowledgeItem`; a source without an item to the client's Data area),
an unread ref named with its reason. **LeadPane.tsx and lib/lead.ts are owned by the integration
coordinator session**: LK6 delivers the API field, its words (`readsLine`, a pure function with
tests) and the journey assertions, and hands the LeadPane edit to that session rather than editing
those files from this plan's branch.

### 8. The kill switch

`AIA_AI_RESEARCH_LEAD_KNOWLEDGE_READS` (off by default, off in test, off on develop until LK7), in
the worker beside `AIA_AI_RESEARCH_LEAD_ENABLED`. Off: the index is still frozen (it costs no
request), the prompt says the Lead cannot open files, and a turn that names a read anyway is
answered from the first request with the reads dropped and said ("Otevírání souborů je vypnuto").
A typed `AIA_AI_RESEARCH_LEAD_KNOWLEDGE_READS` with any other value stops the worker by name.

## Chunks

Each chunk is one PR, with its tests, and adds a step to
`tools/ui_workbench/lead_journey.mjs` run at **1440, 1100, 768 and 390 px** on the scripted Lead
(`ScriptedLeadExecutor`, `apps/executors/src/aia_executors/workbench.py:129 @ 871c62c5`) with
**zero paid jobs** asserted. The journey runs at 1440 alone today (`lead_journey.mjs:46`); LK1
loops it over the four widths. Below 1100 px the Lead's compact drawer is decided but not built
(MVPQ-11, `research-lead-workbench` 26): until it lands, the 768 and 390 px steps assert what the
classic layout serves and no overflow, and they assert the drawer once it exists.

**LK0. Prerequisite: the licence determination (built in its own fix PR).** Finding 1 is a live
defect, so the determination Q60 (a) settled, `unclassified-client-knowledge` approved for
`bedrock-eu-primary` only, recorded in `licence_determinations.py` with the decider and date, ships
on its own fix PR now, not under this plan. This plan's chunks LK2, LK4 and LK5 build on it; its
tick here records that PR once merged. It is the one chunk without a journey step: it is a
policy record, tested by the licence gate's own tests.

**LK1. The index as data, and ADR 0042.** `domain/lead_knowledge.py`: `IndexEntry` (item,
proposal, source), `knowledge_index(items, proposals, sources, selected)` in the
order and budget of §1, `index_page(n)`, each entry's `MaterialRule`. ADR 0042 (Proposed): the
read round as an amendment of ADR 0026 decision 3, its bounds and its relation to ADR 0040.
*The owner, 2026-10-25 (ADR-0042 (a), the audit page, relayed by coordinator 3): accept ADR 0042 when LK1 writes it; his note: the
Lead should retrieve and search relevant documents, "like claude projects / chatgpt folders".*
Tests: REJECTED never present; no folder or label name in any entry (Q61 (b)); PROPOSED marked unapproved; an internal source C and its item
marked; summaries cut at a word; a 500-entry client paged with counts and no entry lost across
pages; the bytes of page 1 within 16 KB. Journey: the scripted greeting names the index's counts
("V knihovně klienta vidím 12 položek, 2 návrhy, 5 souborů") at the four widths.

**LK2. The index frozen at enqueue.** `ClientKnowledgeRepository.index_for_study(StudyContext)`
(ACTIVE items, never their folder or label names (Q61 (b)), PROPOSED proposals; counted, not limited at 200) and
`ClientSourceRepository.sources_for_study(StudyContext)` (each with its reading pin and internal
mark), both taking the client from the study's row; `_freeze` builds the index in place of
`knowledge_entries`; `context_classification` emits one part per entry by its rule; the lineage
declared per §5. Tests: another client's items, proposals and sources never in the index (two
clients, one organization); a 201st item present (Finding 2); the turn's context hash covers the
index; `context_classification` names one part per entry with its class and source (an internal
source C, an AI proposal from it C, a person's proposal A, a proposal with no recorded class
`None`); a turn's class with only internal material is C, with any client material A; a route
approved for C alone refuses an A turn as `route_not_approved_for_class` with every entry still in
the context, nothing dropped. Journey: a
fictional client with an internal source and a pending proposal; the greeting counts them.

**LK3. The read in the closed contract.** `LeadOutput.read`; the read-turn validator (§2); the
answer contract without `read`; `reads_layer(results)` and `read_context(frozen, results)`
refitting to 96 KB with every omission named; `ground_quotes` and code-written citations from
locators (§6); `lead_contract` over the read texts. Tests: a read turn with an edit refused; four
reads refused; a quote not in the read removed and counted; a citation written from the segment,
never the model's locator; a number only in the read accepted, one in no read refused; a too-large
fourth page dropped by name. Journey: none paid; the scripted Lead's script gains a read whose
answer the journey reads at the four widths.

**LK4. The read round in the worker.** `reading_for_study`, `item_for_study`,
`proposal_for_study` (§3); `ResearchLeadExecutor._answer` runs the round behind the switch: the
first answer checkpointed, the fetches, the class re-read, the second request with its own
reservation, its usage in the ledger; `ScriptedLeadExecutor` follows the same path without a
model. Tests: a retry after the first answer replays it and sends one request, not two; a ref of
another client `not_in_index`; a reading changed since enqueue `changed_since_turn`; an internal
mark removed mid-turn `source_class_changed` and nothing sent; switch off, reads dropped and said;
a malformed switch stops the worker. Measured on recorded exchanges and stated in the PR: requests,
input bytes and tokens per read round, added latency, USD at the Lead model's configured prices.
Journey: a read opened at the four widths; zero paid jobs.

**LK5. Datasets.** A DATASET read is its preview (§5; Q62 (a)), never a row. Tests: a personal
column's samples masked in the read; no read returns a dataset row segment; a turn with an approved
DATASET item answered on `bedrock-eu-primary` (LK0) and refused by name on another route. Journey:
a fictional dataset opened as its preview at the four widths.

**LK6. What the Lead read, in the API and on screen.** `reads` in the turn state and OpenAPI;
`readsLine(turn)` in words (pure, Vitest); the "Přečteno: …" line in LeadPane by the integration
coordinator session (§7). Tests: the API's reads from the step output; an unread ref with its
reason; `readsLine` for item, proposal, source, page range and a dropped read. Journey: the line
visible under the reply, each link opening the item (`?item=`) or the Data area, at the four
widths; zero paid jobs.

**LK7. On for develop.** After LK4's measurement: `AIA_AI_RESEARCH_LEAD_KNOWLEDGE_READS` in
`deploy/develop/docker-compose.yml` and `env.example`; a runbook section (what it does, its cost
per read, how to turn it off); the acceptance on a fictional develop client: index, a read of a
document, a page 2 on the next turn, an internal source read as C, cost per read recorded. The
paid develop acceptance needs the owner's authorization, as `ai-research-activation`'s did.

## Owner questions

- **Q59 — what the Lead sees of a client's knowledge.** Settled 2026-10-21 via /pmstatus Q59:
  **(a)**, an index of everything every turn and reads on demand, as above.
- **LCK-Q1 = Q61 — folder and label names reach the model.** Settled 2026-10-21 via /pmstatus Q61:
  **(b)**, neither reaches the model, against this plan's recommendation of (a). The index carries
  each item's name, kind, status, summary and internal mark only; the rule "no model sees them"
  (`domain/knowledge.py:24-28`) stays as written.
- **LCK-Q2 = Q62 — what a DATASET read contains.** Settled 2026-10-21 via /pmstatus Q62: **(a)**,
  its preview only: columns, kinds, fill and five samples, personal columns masked, never rows.
- **LCK-Q3 = Q60 — the licence lineage of client knowledge (the data owner).** Settled 2026-10-21,
  14:51 UTC, via /pmstatus Q60: **(a)**, `unclassified-client-knowledge` approved for
  `bedrock-eu-primary` only. Built as LK0 in its own fix PR (Finding 1).
- **LCK-Q4 — the read round inside the turn.** Settled 2026-10-21 by the PM within Q59 (a): the
  second request runs inside the same step (§2, A); ADR 0042 stays Proposed until accepted. ADR 0040
  is unchanged by it.

## Findings

1. **A Lead turn with any approved DATASET, ARTIFACT or FINDING item is refused by the licence
   gate.** Anchor: `packages/aia_core/src/aia_core/domain/research_lead.py:835-838 @ 871c62c5`
   declares `DataLineage.of("unclassified-client-knowledge")`; `licence.py:158-163` refuses a
   dataset with no determination (`dataset_unknown`); `licence_determinations.py` records only the
   panel datasets and the synthetic fixture. Reproduction (run 2026-10-21 on `871c62c5`):
   `recorded_policy().authorise(lineage=DataLineage.of("unclassified-client-knowledge"),
   route=<bedrock-eu-primary>)` raises `LicenceDenied` with reason `dataset_unknown`. Consequence:
   once a client has one approved dataset item, every Lead turn in every one of its studies parks
   with "Vedoucí výzkumu čeká na povolenou trasu nebo licenci"
   (`apps/executors/src/aia_executors/research_lead.py:186-195`); the design agents share it
   (`domain/research_agents.py:690-691`). Smallest fix: the data owner's determination (Q60 (a), LK0)
   recorded in `licence_determinations.py`. Test that would have caught it: a Lead turn's request
   with an approved DATASET item through `GovernedModelGateway` preflight on the develop route.
2. **Hypothesis (not reproduced here; no database in this session): items past the 200th
   disappear from the Lead's knowledge silently.** Anchor:
   `infrastructure/client_knowledge_repository.py:86` (`_MAX_RESULTS = 200`) and `:249-251`
   (`.limit(_MAX_RESULTS)`) under `for_study`; `knowledge_entries` lists omitted ids only for the
   byte cap (`domain/research_agents.py:546-563 @ 871c62c5`). Consequence: a client with 201
   approved items gives the Lead 200 and no sign of the rest. Reproduction to run: a repository
   test adding 201 ACTIVE items and asserting `for_study` returns 201. Fix: LK2's counted, paged
   index; the design agents' snapshot keeps its own `knowledge_retrieval_limit: 200`
   (`domain/research_agents.py:579`), which states the cap at least.

## Coordination

- `lead-conversation` LC1/LC4 (ADR 0041, Proposed) own the layer table and the allocation; this
  plan's index is layer 5 within its 16 KB ceiling, and the reads layer is a refit of the second
  request only, named in LC1's manifest when both exist. LC9's retrieval of "knowledge bodies" at
  enqueue overlaps the read: with this plan the bodies come by the Lead's read, and LC9 ranks the
  index's order. Neither plan edits the other's file.
- `lead-orchestration` LO8 decides "a read tool against ADR 0026 decision 3" for results; ADR 0042
  is the knowledge case of that question and should be read beside LO8.
- LeadPane.tsx and lib/lead.ts: the integration coordinator session.

## Doc follow-up

For the docs PR after each chunk merges (no feature PR edits these files):

- `CLAUDE.md` § 2, `application/` `research_lead.py`: "the turn's knowledge layer is the
  client's index (items, unapproved proposals, sources, an internal one marked; rejected out),
  paged past 16 KB; the Lead reads up to three refs a turn, pinned, by code, behind
  AIA_AI_RESEARCH_LEAD_KNOWLEDGE_READS (off by default)". `domain/` gains `lead_knowledge.py`;
  `infrastructure/client_source_repository.py` gains `reading_for_study`;
  `client_knowledge_repository.py` gains `index_for_study`, `item_for_study`,
  `proposal_for_study`. The workbench line under LeadPane: "Přečteno: …".
- `ARCHITECTURE.md`: the Lead's read round as the second exception to "the Lead holds no tools",
  beside ADR 0040.
- `docs/architecture/adr/README.md`: ADR 0042, Proposed.
- `.planning/open-items.md`: Findings 1 and 2, with OI numbers; Finding 1 closed by LK0's fix PR once it merges.
- `AGENTS.md`: anything non-obvious the read round's checkpointing teaches (LK4).
