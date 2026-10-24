---
status: planned
chunks:
  - "[ ] LC0. ADR 0041 accepted by the product owner (Proposed in this plan's PR): the relayed answers Q25-Q30 confirmed"
  - "[x] LC1. The layer table and the manifest: freeze_context as a pipeline over declared layers (order, floor, ceiling, over-policy, class rule), today's values first, a manifest stored per turn"
  - "[x] LC2. Co Vedoucí vidí: the Vidí chip opens the last turn's manifest in words, layer by layer, with what was left out and why"
  - "[x] LC3. The decision digest: a code-built record of what this conversation decided (edits, cards, notes, self-updates, lookups) in the conversation-memory layer, never dropped"
  - "[ ] LC4. Budgets enforced: ADR 0041's floors, ceilings and two-pass global allocation, the design layer's five-step shortening ladder, spare bytes to the verbatim conversation, every omission named"
  - "[ ] LC5. Queued messages stored on the server: immutable rows, queued / answered / withdrawn derived (an exact study_lead_turn_answers relation, a withdrawal row, queue position kept through an edit), bounded in bytes and count, a follow-on turn for what layer 9 cannot hold, LeadBusy retired for messages, visible in every tab"
  - "[x] LC5a. (opened as a draft during the feature freeze at Nigel's word, 2026-10-22) The server's queue: a message posted while a turn runs is stored at once, bounded (8 KB, 5 queued), answered by the next turn while layer 9 fits, the rest deferred and named; study_lead_turn_answers; withdraw; the web's queue retired"
  - "[ ] LC5b. Edit a queued message as a replacement keeping its place, and requeue what an inactive turn answered (with LC10's replaces_turn_id and active path)"
  - "[ ] LC6. Cost, model and class on every Lead turn, from the usage ledger and the composition digest"
  - "[ ] LC7. Grounded hierarchical compaction: research_lead_compact after the reply, block summaries of eight turns with a turn reference on every sentence, episode roll-ups (three levels at most), the preservation check, the coverage floor and the uncovered-terms index, STUDY_LEAD_SUMMARY, AIA_AI_RESEARCH_LEAD_COMPACTION_ENABLED and its two keys, summary_lag"
  - "[ ] LC7a. Kept facts (Držená fakta): proposed by the compaction step, each with a quote located verbatim in its named turn, never compacted, superseded only by name, 40 x 300 characters"
  - "[ ] LC8. Summaries and kept facts corrected, pinned or retired in place by the researcher; a person's revision later roll-ups build on"
  - "[ ] LC9. Retrieval at enqueue: the turns behind a matching summary sentence first, then covered turns, knowledge bodies and notes ranked by the project-memory matcher, recorded in the manifest"
  - "[ ] LC10. Regenerate, edit-and-resend and retry as replacement turns: parent_turn_id, replaces_turn_id, superseded_turn refusals"
  - "[ ] LC11. Pins: a turn, knowledge item, note or artifact element pinned to the conversation, its own layer, refused when made if it cannot fit"
  - "[ ] LC12. Feedback: pomohlo / nepomohlo with a closed reason per Lead turn, private, an evaluation export by prompt version, an ADR 0030 signal by id"
  - "[ ] LC13. The long-conversation journey and the recall test: 60 recorded turns, every kept fact in turn 61's context and every digest decision in it or reachable through the manifest's ledger range, a summarised subject's turns retrieved verbatim, the manifest naming omissions, a queued message from a second tab, a regenerate, zero unintended paid jobs"
  - "[ ] LC14. After the MVP: one's own conversations listed on Můj Vedoucí and a lexical search over one's own turns"
  - "[ ] LC15. After the MVP: export of one's own conversation as Markdown, each turn's class shown, audited"
  - "[ ] LC16. After the MVP: branch navigation over replaced turns, and Začít od čistého stolu"
  - "[ ] LC17. After the MVP, own ADR: semantic retrieval (an EU embedding route, pgvector), or a Lead-requested recall on ADR 0040's continuation pattern"
  - "[ ] LC18. After the MVP: personal prompt templates in the / list beside the command registry"
  - "[x] LC19. Day dividers in every time-only feed: Dnes, Včera, the weekday and date within the past week, else the date; the viewer's local day; an unknown moment shows none"
---
# The Lead's conversation and context

The chat-centric capabilities the product owner asked for on 2026-10-20 (22:25 UTC): session memory,
context management, and the message operations of a mature chat product, built inside ADR 0026's
closed output and the governed gateway. Architecture:
[ADR 0041](../../docs/architecture/adr/0041-lead-conversation-and-context.md) (Proposed). Evidence
and the gap table: [`evidence/lead-chat-capabilities.md`](../evidence/lead-chat-capabilities.md).

**Owner: S1** (the Lead's lane, as `lead-orchestration`). Every chunk is open. Written during the
scope freeze: nothing here is in the MVP until the owner accepts ADR 0041 and the baseline admits
it (LC0).

## Folded in, not duplicated

This plan adds what no plan has. Where a capability is already planned, the chunk stays where it
is and gains an acceptance condition from ADR 0041:

| Existing chunk | Stays the owner of | ADR 0041 adds to its acceptance |
|---|---|---|
| `lead-orchestration#LO6` continuation turn | waking the Lead on finished work | the continuation turn is a turn with `parent_turn_id` = the turn that asked; it reads the manifest's budgets |
| `lead-orchestration#LO7` context layers | readiness, outlook, changes, execution state, pending proposals | each new layer is a row of LC1's table with a floor, ceiling and over-policy |
| `lead-orchestration#LO8` `ResultsContext` | the results layer and its bound | its bound is layer 7's ceiling; its omissions appear in the manifest |
| `lead-orchestration#LO9d` stage workers' inputs | each worker's own context | the worker's context records a manifest in the same shape (one reader for both) |
| `lead-orchestration#LO10` 96 KB vs 64 KB | the clean error | unchanged; LC4's budgets make the Lead's side predictable |
| `lead-orchestration#LO11` the Lead over time | signals, proposed self-updates, file revisions, sealing | LC12's *nepomohlo* writes a signal by id; sealing covers summaries and feedback |
| `lead-orchestration#LO14` cost per turn | measuring it and the kill switch | LC6 shows it per turn; the measurement sets ADR 0041's budget values |
| `lead-orchestration#LO17` stop | cancelling a turn and a plan | the partial text is kept as *Zastaveno vámi* and is not a turn (ADR 0041 decision 7) |
| `lead-orchestration#LO18` streaming, file, unprompted comments | all three | its streaming is built to ADR 0041 decision 8: reply-only preview, held-back numbers, SSE over the run feed, resume by cursor |
| `lead-orchestration#LO19` study context file | the file | it is layer 4 with ADR 0041's floor and ceiling; a summary is never its source |
| `lead-orchestration#LO20` web lookup | the lookup and its bounds | its results enter a layer with a ceiling, and the lookup's cost has its own line (LC6) |
| `research-lead-workbench#11` command registry | the registry | the `/` list in the composer reads it (LC18 adds personal templates after the MVP) |
| `research-lead-workbench#12` workbench journey | the four widths and keyboard | ADR 0041 decision 11's keyboard map is in its assertions |
| `research-lead-workbench#16` pointing and `@` | the chip, target button and `@` | the Vidí chip opens LC2; `@` can pin (LC11) |
| `research-lead-workbench#26` compact Lead | every width | LC2 and LC5 work in the drawer |
| `research-lead-workbench#29` conversation controls (D-38; plan @ `ec1265a`, #523) | the UI: older-message paging, copy, edit and resend, ArrowUp to edit the last message, a queued message's send-now and edit | its edit and resend creates replacement turns under LC10's rule (refused once the replaced turn's output is decided); its queue is LC5's server queue, so a queued message is edited or withdrawn on the server and visible in every tab; send-now stops the running turn (LO17) and starts one that answers the queue. LC5 and LC10 own the server side |

## Waves

Waves are `mvp-execution-contracts.md`'s; the row these chunks join is the docs PR's to add.

- **W1** (with E10, after LO7's first layer): LC1, LC2, LC3, LC5, LC6. No model call; all
  deterministic or a read of stored data.
- **W2** (with LO19, after LC1): LC4, LC7, LC7a, LC8, LC9, LC10, LC11.
- **W3** (with LO18): LC12, LC13.
- **After the MVP:** LC14-LC18.

## Chunks

**LC0. ADR 0041 accepted.** The coordinator relayed the owner's answers from the PM status page
(2026-10-20 22:39-22:42 UTC): Q25 (a) the digest plus a model summary, "ensure we are using an
innovative approach, and that we ensure we best preserve the context properly"; Q26 (a) feedback in
the MVP; Q27 (a) queued messages on the server, answered together; Q28 (a) 96 KB with per-layer
budgets; Q30 (a) regenerate and edit-and-resend in the MVP. They are written into ADR 0041 and these
chunks, to be confirmed when the owner accepts it. Q29 (a), relayed at 22:48 UTC: no separate
threads; the study is the thread, with pinned items (LC11) instead, and branching after the MVP
(LC16). The
amendments to ADR 0026 decisions 2 and 8 are recorded in the docs PR. Test: none (a decision).

**LC1. The layer table and the manifest.** Saving or activating a version of `aia.research.lead`
refuses one whose serialized `PromptPin` exceeds 12 KB (`prompt_too_large_for_lead`, byte count in
the editor). Hatching and self-update gain byte bounds on the Lead's
files (SOUL and USER 2,800 bytes, name 160, refused as `lead_file_too_large`); an older file over
them is shortened at a paragraph boundary, named `lead_file_shortened`. `domain/research_lead.py`: a `LeadLayer` table and
`freeze_context` as a pipeline over it, carrying today's bounds unchanged (12 turns, 20 KB knowledge,
40 / 16 KB notes, 5 runs); a `ContextManifest` (per layer bytes, floor, ceiling, included ids,
omitted ids with reason (at most 50 each per layer, beyond that counts and a source range), allocation, class and class source; totals; context file version and summary id when
they exist) stored in the step input beside the context and hashed with it. Tests: the same inputs
give the same manifest; a 12,000-character prompt of multibyte text is refused at activation, not at
a turn; every omitted id is listed with a reason or lies in the stored range; a
manifest after 1,000 decisions is the same size as after 100; today's turns freeze byte-identical
contexts (a regression fixture).

*As built (LC1):*
- `domain/lead_context.py` declares `LEAD_LAYERS` (today's bounds, in `freeze_context`'s order) and
  `context_manifest(context, classification=None)`:
  - per layer: bytes, bound, over-policy, included and omitted ids (at most 50 each, the rest
    counted);
  - `bounded_bytes` beside `bytes`: a ceiling bounds the notes or the items, not the whole layer
    entry, so the manifest never shows a valid turn as over;
  - each layer's class from the turn's `context_classification`, through `PART_LAYERS`.
- The manifest is a reading of the frozen context, so it is stored beside the context and **not**
  hashed with it; the context, its hash and the turn's identity do not move (the existing
  `freeze_context` tests stay green unchanged).
- Where it is stored: the worker writes it into the turn artifact's provenance
  (`context_manifest`), with classes. For a turn that never reached the worker (parked, failed),
  LC2 computes it from the stored step input's context, since it is a pure reading of it; no
  second copy is stored.
- `RUNS_IN_CONTEXT` moved from the application to the domain, so the table can name it.
- The prompt bound is `PromptSlot.max_pin_bytes` on the Lead's slot (12 KB, measured with the
  largest framing a stored version carries). It is refused on save and on activation as
  `too_large_for_context`, the message naming the byte count.
- A new answer whose `self_update` writes SOUL or USER over 2,800 bytes is refused by
  `lead_contract` (`lead_file_too_large`, so the turn's one repair sees why). Only new answers
  are held to it: a turn stored before the bound is read through plain `LeadOutput` as before,
  so its edits and cards stay decidable. A name's 40 characters cannot exceed 160 bytes, so
  names get no byte check.
- **Moved to LC4:**
  - `freeze_context` rebuilt as a pipeline over the table;
  - floors, ceilings, allocation;
  - shortening an older file already over the bounds (`lead_file_shortened`).

  These change what a turn holds; LC1 changes nothing a turn holds.
- **Earlier turns carry no ids in the context**, so the conversation layer reports a count, not ids
  or a range (the range comes with LC5's ids).

**LC2. Co Vedoucí vidí.** `GET /studies/{id}/lead/turns/{turn_id}/manifest` (the caller's own turn
only); the pane's Vidí line becomes the chip that opens it inline in the pane, in Czech, layer by
layer. Omitted items beyond the first 50 page from the source through the stored range (`GET …/manifest/omitted?layer=&after=`). Tests: another researcher's turn is 404; the panel names an omitted knowledge item; it renders
in the compact drawer.

*As built (LC2):*
- **Read, never rebuilt.** `ResearchLead.manifest(turn_id)` reads the context the turn froze from
  its step's input (`WorkflowRepository.step_input(run_id, "turn")`) and passes it to
  `domain/lead_context.manifest_view`. Nothing is recomputed from today's study.
- **Not recorded is said.** Every declared layer is listed in `LEAD_LAYERS` order. A layer the
  frozen context does not hold (a turn before LC3's digest, Design Research off) is
  `recorded: false` with unknown counts (`null`), never an empty layer. A turn whose step holds no
  context is `recorded: false` as a whole.
- **A count only where one was counted.** The digest's layer says what its `left_out` froze.
  Runs and Lead notes keep the newest and drop the rest uncounted (F4), so their
  `omitted_count` is `null`, read "Starší vynechané se nepočítají", never 0 (review on #772).
- **No class in the response.** The class a turn was sent as is not the browser's (`_public`);
  LC6 shows it.
- **Routes:**
  - `GET …/lead/turns/{turn_id}/manifest`;
  - `GET …/lead/turns/{turn_id}/manifest/omitted?layer=&after=`, fifty at a time, from the
    frozen context (`omitted_page`).

  Both serve the caller's own Lead turn only. Another researcher's turn, or a person's, is 404
  `lead_turn_not_found` (tests: application and API).
- **The web:**
  - The Vidí line is a button (`aria-expanded`) once a Lead turn froze a context.
  - `LeadSees.tsx` opens inline under the pane's head, the same in the compact drawer. It
    shows each layer's size against its bound, its items counted in Czech and the ids it left
    out with the reason, and pages the rest (`lib/lead-manifest.ts`, pure).
  - Tests: `LeadPane.test.tsx` (the omitted knowledge item, paging, the drawer, no chip before
    a turn) and `lead-manifest.test.ts`.
- **The Lead's notes stay out of every report path (Q69):** the manifest names a note by its
  `memory_id` only, never its text, and only to its researcher.
- **In a browser:**
  - `lead_journey.mjs` opens the chip and reads the panel.
  - Checked by hand: at 1440, 1100, 768 and 390 px all ten layers are listed, Design Research
    unrecorded, with no page or panel overflow.

**LC3. The decision digest.** A pure projection over the ledger rows and turns of this conversation
(`lead_edit`, `lead_job_request`, `lead_self_update`, plan and lookup rows when they exist), each line
each at most 200 bytes: a decision line with its turn id and ledger row id, an event line (a lookup,
a client note kept with its turn) with its source table and row id, a pointer line (an undecided
proposal) with its turn id and output index and no ledger id. Feedback is not in the digest. It goes in layer 10, within its share, which scales from
5 KB at the layer's 10 KB floor to 8 KB at 16 KB, in ADR 0041 decision 4's four capped groups (the
caps below at 8 KB, scaled with the share, group 4 fixed):
1. decisions on named items (4 KB; per item, the newest 3, newest first);
2. undecided proposals on the active path (2 KB; newest first);
3. the latest decision per other item (what is left);
4. counts (256 bytes, reserved).

A group under its cap leaves its bytes to group 3. A decision left out pages from its ledger range,
an undecided proposal from its turn range, both in the manifest (ADR 0041 decision 3).

Tests:
- the same ledger gives the same digest;
- a dismissed edit from turn 3 is in turn 40's context when its item is named;
- 40 decisions on one named item and 60 undecided proposals keep every group within its cap, and
  each omission pages from its ledger or turn range;
- 500 decisions stay within the digest's share (8 KB, or 5 KB at the layer floor), the stored manifest stays bounded (counts and a range), and every
  omitted decision pages from that range;
- no line is rewritten.

*As built (LC3):*
- `domain/lead_digest.py` is pure:
  - `decision_digest(decided, undecided, named=, share_bytes=)`;
  - `edit_item`, which names an edit's item in the focus's words, so `brief:title`,
    `question:q1` and `sample:n` find their decisions (test: the web's own focus ids). A list
    entry (`plan:plan.hypotheses:<text>`) is named by its text, which no focus id carries: the
    web names an objective, research question or hypothesis by its id. Its decisions reach the
    latest group, never the named one, until LC7 maps list ids to their text.
- The four groups keep their caps: 4 and 2 KB at the full 8 KB share, scaled at a smaller one.
  The latest decisions give way, line by line, until the whole digest, its counts and ranges
  included, fits the share.
- `freeze_context(memory=)` adds the `memory` layer before the conversation.
  `context_classification` classes it as the design (Class B: a list entry's item names its
  text), raised to the class of every turn whose text a line carries
  (`freeze_context(memory_classes=)`, stored as the layer's `turn_classes`); one turn of
  unknown class refuses (ADR 0041 M3: the class of what it names). `LEAD_LAYERS` declares it
  with its 8 KB ceiling.
- A request waits in the digest only when it is a prepared agent job: a run or Deep Research
  card is started from its own screen, never decided through the ledger (test).
- `left_out.by_named_item` counts, per named item, the decisions its three lines left out.
- The application builds it from the ledger's `lead_edit`, `lead_job_request` and
  `lead_self_update` rows on the researcher's own Lead turns, which
  `StudyLeadRepository.lead_turn_ids` reads (ids only, the researcher's own). Another
  researcher's decisions in the same study never enter it (test).
- An edit decided on a turn outside the 50-turn history window has no item. Its output is not
  loaded, so it is a decision line with `item: null`, still exact by ledger row and turn.
- Cost, not measured: each turn reads every Lead ledger row of the study and the researcher's
  turn ids, filtering in Python; both grow with the study. A query joining the ledger to
  `study_lead_turns` on the researcher bounds it; LC4 takes it with the allocation.
  Naming those needs the turns' outputs; LC9's retrieval reads them.
- Group 2's pointers cover the proposals in that window. No ledger range covers older undecided
  proposals, so they are not counted. LC5 brings ids to every turn.
- Event lines (a lookup, a client note kept with its turn) wait for their events. There is no
  lookup yet (LO20), and a kept client note is not a ledger row today.
- The share is the full 8 KB until LC4 allocates layer 10.

**LC4. Budgets enforced.** ADR 0041 decision 2's floors, ceilings and two-pass allocation (floors,
then the remainder in the declared priority order, each layer's over-policy applied to its
allocation); the design layer's
five-step shortening ladder (ADR 0041 decision 2: all verbatim; focused stage verbatim; focused
item and section verbatim; focused item only; `item_over_budget` with at most 50 parts and 2 KB listed by stable part id, the rest paged, so any
part can be focused with `@`), each step
named; spare bytes to the verbatim conversation. Tests: a 60 KB questionnaire at a 12 KB
allocation lands on step 3 or 4 and leaves the conversation its floor; the manifest names every
item it outlined; a single item over the allocation is carried as `item_over_budget` with its parts listed, and
focusing one part carries that part verbatim; floors sum within 96 KB; every layer at 90 % of its ceiling at once still
freezes within 96 KB, with the conversation at its floor and each shortened layer named.

**LC5. Queued messages on the server.** The migration adds `parent_turn_id` (nullable, set on
insert, never updated), a `withdrawal` turn kind and the append-only `study_lead_turn_answers`
(`lead_turn_id`, `person_turn_id`), written with the Lead turn. A message's queue position is the
`sequence_no` at the root of its `replaces_turn_id` chain. Rows stay immutable under the
`before_update` guard; a message's queued, answered or withdrawn state is derived (ADR 0041
decision 7).
- `post` stores a message while a turn runs.
- The worker's next turn takes queued messages in queue-position order while they fit layer 9's
  12 KB, writes one answer row per message it sent, and enqueues a follow-on turn for any left (`queued_deferred`).
- Bounds: `MESSAGE_MAX_BYTES` (8 KB UTF-8, 422 `message_too_long`) and 5 queued at most (409
  `lead_queue_full`).
- A message is withdrawn with `POST …/turns/{id}/withdraw`, which appends a `withdrawal` row; it is
  edited by appending a replacement.
- The web drops its module-level queue for the server's.

Tests:
- with two tabs, a message from each while a turn runs: one turn answers both;
- a withdrawn message is not answered;
- no turn row is ever updated;
- 4,000 four-byte characters are refused by bytes;
- five 8 KB messages are answered by a chain of five turns (one 8 KB message fits layer 9's
  12 KB, two do not), each turn naming the rest as `queued_deferred`, no message cut, each turn
  paid and shown; smaller messages pack into one turn while they fit;
- a sixth queued message is refused;
- a queued message edited before its turn starts: only the edit is sent, the original is neither
  sent nor marked answered;
- a withdrawn message inside an answered range is not shown as answered;
- an early queued message edited after two more were queued keeps its place; when its edit alone
  fills layer 9, the two later messages stay queued and unanswered;
- one Lead turn answers two queued messages, then the newer is edited and resent: the shared turn
  goes inactive, the other message is queued again, and the replacement turn answers both;
- a greeting still waits.

*Split (2026-10-22):* LC5's edit-as-replacement and requeue rest on `replaces_turn_id` and the
active-path predicate, which LC10 introduces; building them twice is waste. **LC5a** is the
queue: storage, bounds, packing, answer rows, deferral, withdrawal and the web. **LC5b** is the
replacement and requeue, with LC10. LC5's tests on edits and inactive turns move to LC5b.
LC5a decisions:
- **What starts the next turn.** ADR 0041 decision 7 says a follow-on turn is enqueued "at once"
  for deferred messages. Two Lead turns of one researcher cannot run at once: the second would
  be frozen without the first's answer. So the next turn is started when the conversation is
  free: by the next post, or by `POST …/lead/turns/queued`, which the pane calls as soon as it
  reads the conversation free with messages still queued (any tab; the researcher's Lead row
  lock makes a second call a no-op). A worker-side follow-on, started when the step finishes,
  is LC5c if a closed tab must not delay a deferred message.
- **Legacy turns.** The migration backfills one answer row per existing Lead message turn for
  the person message at the sequence just before it, which is how `post` stored them. No
  stored message reads as queued after the migration.
- **The view.** One message: `view.message`, as today, so a single message's context is
  unchanged. Several: `view.messages`, each `{turn_id, stage, text, focus}` in queue order and
  never concatenated, with `view.message` null. Deferred ones are named in `view.queued_deferred`
  by turn id. A note in the view says so (`MESSAGES_NOTE`): the fixed prefix is every
  agent's, and the task wording is the editable prompt's. The harness stays
  `aia-research-lead-4`, because a single message's context is byte-identical.

*As built (LC5a):*
- **Migration `7db4e0f96181`:**
  - `study_lead_turn_answers` (append-only, with a `before_update` guard);
  - `study_lead_turns.parent_turn_id`;
  - the kind `withdrawal`, which is the person's, has no text and names its message;
  - the backfill of legacy answers;
  - a downgrade refused while a withdrawal is stored.

  Checked on PostgreSQL 16: upgrade with a backfill of two legacy pairs (a typed command left
  out), `alembic check` with no drift, downgrade base and upgrade head, and the refusal.
- **`StudyLeadRepository`:** `queued()` (derived, in queue order), `answers`, `withdrawn` and
  `record_answers`. `make layer_check` holds the answers table to the repository as it does the
  turns.
- **`ResearchLead`:**
  - `post` stores a message while a turn runs; `LeadBusy` stays for a greeting.
  - `answer_queued` starts the next turn once the conversation is free; `withdraw`.
  - `_start_turn` freezes and queues a turn with `take_queued` (domain) and writes its answer
    rows.
  - A turn parked on the budget and superseded by a message has its messages answered by the
    new turn, with the new one, in order: they are no longer only history.
- **Bounds:** `MESSAGE_MAX_BYTES` 8 KB (422 `message_too_long`), `QUEUE_MAX` 5 (409
  `lead_queue_full`) and `MESSAGES_MAX_BYTES` 12 KiB (layer 9).
- **API:** `POST …/lead/turns/queued` (201 with the turn, 200 with none) and
  `POST …/turns/{id}/withdraw` (409 `lead_message_not_queued`, 404 for anyone else's). A turn
  answers `queued`, `withdrawn` and `answers`.
- **The web:**
  - The pane posts at once; the server queues.
  - Its local list holds only a post in flight or one the server did not take.
  - The composer's queue shows what waits on the server, and withdraws it.
  - The conversation leaves out what waits or was withdrawn.
  - A free Lead with messages waiting is asked once per set (any tab).
- **Tests:**
  - application, on SQLite and PostgreSQL: two tabs answered by one turn; a withdrawal; bytes
    and count; five 8 KB messages chained; small ones packed;
  - API: the queue end to end;
  - domain: `take_queued` and the classification of each message;
  - web: `LeadPane.test.tsx`.

*Review of LC5a (independent, before the PR).*

Fixed, each with a test:
- **The pane's ask key.** It now includes the newest Lead turn's id and status. Keyed on the
  waiting set alone, a message waiting behind a turn parked on the budget was never asked about
  again after the budget was lifted and the turn answered.
- **A waiting message's focus is checked again** against the copy its turn is frozen with. One
  another tab removed is left out; the message is still sent (the race of Codex on #624).
- **Only a busy Lead's queue fills up.** A free Lead answers what waits together with the new
  message.
- **Smaller fixes:**
  - a superseded turn's messages are read by id, not from the newest 50 rows;
  - `withdraw` needs an open study;
  - the downgrade also refuses while an answer row exists that the backfill would not write
    again (checked on PostgreSQL).

Left, as findings:
- **F5.** A batch answered by a turn that then failed or parked for a reason other than the
  budget is answered by that turn and never sent again: up to five messages, where one was
  before (`application/research_lead.py`, `_start_turn`). Smallest fix: LC10's retry, which
  regenerates a failed turn; until then the researcher sends again. Test: LC10's.
- **F6.** `state(limit=100)` counts withdrawal rows within its limit, so it can return fewer than
  100 turns. Harmless at today's sizes.
- **F7.** A queued person turn no longer stores `design_revision_id`. Nothing reads it on a
  person turn; the Lead turn that answers it names its revision.
- **F8.** `POST …/lead/turns` takes no idempotency key (`apps/api/src/aia_api/routers/lead.py:574
  @ ddda4d21`; it predates LC5a), so a retry after a lost response stores the message twice, and
  with the queue both copies wait to be answered. Hypothesis until reproduced (the coordinator's
  review of #817). Smallest fix: a client-chosen key on the post, unique per researcher and
  study, answering the stored turn on a repeat. Test: the same key posted twice stores one turn.

**LC6. Cost, model and class per turn.** The turn's usage rows (model, tokens, USD) and class in
`GET …/lead`; a quiet line under each Lead turn; compaction and lookup costs as their own lines.
Tests: a turn with a repair shows both calls' sum; an unknown cost reads *neznámá*, never 0.

**LC7. Grounded hierarchical compaction** (ADR 0041 decision 4). The `research_lead_compact` step
after `research_lead_turn`, once a block of eight uncovered turns is complete. A block summary ends
every sentence with the turn ids it rests on. When block summaries exceed their share of layer 10,
the oldest roll up into an episode summary that references them, three levels at most. Each summary
is a `research_lead_summary` artifact recording its level, range, child ids, input hash, pin, class
and cost. The **preservation check** is pure code in `domain/`:
- every sentence carries a reference within the range;
- every turn of the range is referenced by a sentence or a digest line;
- numbers pass `lead_contract` over the referenced text;
- the class is the strictest of the covered turns;
- no sentence restates a digest decision without its turn;
- coverage of the person messages' content words is at least 60 %.

On acceptance, code stores the **uncovered-terms index** beside the summary: each covered person
message's content words that neither its referencing sentences nor its kept facts contain, folded
and stemmed by the project-memory matcher. LC9 retrieves on it first.

The switches: `ModelCapability.STUDY_LEAD_SUMMARY`; `AIA_AI_RESEARCH_LEAD_COMPACTION_ENABLED` (off by
default), with `…_MAX_OUTPUT_TOKENS` and `…_RESERVATION_USD`, charged to the wallet. The manifest
shows `summary_lag` when compaction is behind or a summary was refused. The PR states the measured
cost (burst, latency, USD per block). Tests:
- a sentence without a reference is refused;
- a range with an unreferenced turn is refused;
- a foreign number is refused;
- a Class A turn makes a Class A summary, which a Class-C route refuses;
- a roll-up keeps its children's references;
- a block closes at eight turns or 2 KB of person text; a block summary over 1.5 KB or an episode
  over 2 KB is repaired once, then refused with `summary_lag`; layer 10 at its floor still holds
  the newest episode and a block;
- with layer 10 full, a retrieved evicted summary is carried in layer 11 ahead of older covered
  turns, never displacing the tail's floor;
- past three levels the oldest episode leaves the context, counted with its range, and a message
  matching one of its sentences brings it back, then its children's turns;
- a constraint stated in turn 5 and left out of the summary is in turn 5's uncovered terms, and a
  later message naming it brings turn 5 back verbatim;
- a summary under 60 % coverage is refused with `summary_lag`;
- with the switch off, the turn freezes with `summary_lag`;
- a failed compaction does not fail the reply.

**LC7a. Kept facts** (ADR 0041 decision 4, part 2). The compaction step's output also carries
proposed facts, each with a quote and a turn id. Code keeps a fact only when its quote locates
verbatim in a person's message of that turn (the grounding rule of `domain/deep_research/grounding.py`,
applied to turns). Facts are never compacted; a later fact supersedes one by naming it. The bound is
40 facts of 300 characters; over it, the oldest unpinned facts move to retrieval, named. Tests:
- a fact whose quote is not in its turn is refused;
- a superseded fact leaves the context with its successor named;
- turn 61 of a 60-turn recording holds every kept fact.

**LC8. Summaries and facts corrected in place, references kept.** References are fixed chips; a
sentence without one is refused in place; a turn left unreferenced returns to the uncovered-terms
index (recomputed); the number rule applies; the coverage floor does not. `PUT …/lead/memory/{id}` (one's own conversation)
corrects, pins or retires a summary or a fact. The person's revision is kept as written and is
audited, and later roll-ups build on it. Tests:
- a corrected summary is in the next turn's context verbatim;
- a correction that leaves a sentence without a reference is refused;
- deleting the only sentence about a turn is accepted (not refused by the every-turn rule) and the
  turn is listed as `unreferenced_by_person`;
- deleting the only sentence about turn 9 puts turn 9's words in the uncovered-terms index;
- a retired fact is not in it;
- numbers in a correction follow the same rule.

**LC9. Retrieval at enqueue.** The order is fixed:
0. turns whose uncovered terms (LC7's index) the message, focus or a pin matches, verbatim;
1. the turns referenced by a summary sentence the message matches, verbatim;
2. then, with the project-memory matcher (`domain/project_memory.py`): the other covered turns,
   knowledge bodies and notes.

Everything retrieved is recorded in the manifest with its reason. Tests:
- a message naming a summarised subject brings back that sentence's turns verbatim;
- a forgotten note is never retrieved;
- another client's note is never retrieved.

**LC10. Regenerate, edit-and-resend, retry, and the active path.** One `active_path` predicate
(ADR 0041 decision 7) used by freezing, retrieval, compaction and the digest; compaction never
covers the two newest active exchanges. Migration: `replaces_turn_id` (set on insert, never updated; `parent_turn_id` comes with LC5).
Routes: `POST …/turns/{id}/regenerate`, `POST …/turns/{id}/resend` (edited text). The replaced turn's
undecided output refused `superseded_turn`. The web edits the message in place and collapses the
replaced turn. Tests: regenerate after an accepted edit is refused; a superseded card's approve is
refused; history keeps both turns; after a regenerate and after an edit-and-resend the next turn's
context, retrieval candidates, summaries and digest hold no superseded turn; a Lead turn answering
a replaced message is inactive.

**LC11. Pins.** `study_lead_pins` (researcher, study, kind, ref, pinned revision, created_at,
removed_at); layer 8, its floor the accepted pins' bytes, reserved in the floor pass. Tests: a pin
over layer 8's ceiling is refused when made; with every other layer at its ceiling an accepted pin
is still in the context whole; a pinned item revised past the bound stays at its pinned revision
and the researcher is told; a removed pin leaves the next context; a pin is not visible to another
researcher.

**LC12. Feedback.** `lead_turn_feedback` (turn, researcher, rating, reason, optional text, prompt
pin); an evaluation export by prompt version (counts by reason, no text); *nepomohlo* writes a
`researcher_lead_signals` row by id (ADR 0030, LO11). Tests: feedback on another researcher's turn
is refused; the export holds no text; a sealed Lead's feedback is unreadable.

**LC13. The long-conversation journey and the recall test.** Extends
`tools/ui_workbench/lead_journey.mjs` with a scripted Lead (no model) over 60 turns:
- recorded compactions: blocks, one roll-up and kept facts;
- every kept fact in turn 61's context, and every digest decision in it or reachable through its
  manifest's ledger range and retrieved when its item is named;
- a message naming a summarised subject retrieves that sentence's turns verbatim;
- the manifest opened;
- a queued message from a second tab;
- a regenerate;
- zero paid jobs.

The recall numbers go in the PR.

**LC14-LC18** are after the MVP and get their own chunk text when admitted.

**LC19. Day dividers** (the product owner, relayed 2026-10-21). The rule:
- A divider stands before the first entry of each calendar day in a feed whose entries show only
  their time: "Dnes", "Včera", otherwise the date ("21. října 2026"), with the weekday before it
  when the day is within the past week ("pondělí 19. října 2026"). Each entry keeps its time.
- The day is the viewer's local calendar day, never UTC; days are counted as calendar dates, so
  a 23- or 25-hour day across a DST change does not move a label.
- An unknown or invalid moment has no day: it shows no divider and breaks none, never "Dnes".
- The divider is text in a heading (or a list item in a list), never colour alone.

*As built (LC19):*
- `apps/web/src/lib/day-label.ts`, pure: `dayKey`, `dayLabel(at, now)`,
  `withDayBreaks(items, at, now)` and `isDayBreak`. Tests across midnight, the week, both DST
  changes of 2026 and invalid moments (`day-label.test.ts`, which runs in Europe/Prague, checked,
  so the DST cases cross the transitions wherever it runs). `lead_journey.mjs` checks the "Dnes"
  heading.
- Wired into the two feeds that show a time alone:
  - `components/workbench/LeadPane.tsx`: the conversation, an `h3.conv__day` before each day
    (test: `LeadPane.test.tsx` "heads each local day of the conversation");
  - `components/rehome/research/StepActivityPanel.tsx`: the live log, a list item marked
    `data-day` (test: `ExecutionSteps.test.tsx` "opens a running step's space").
- In a browser (UI workbench, the scripted Lead, turns backdated to 9, 3 and 1 days): "13. října
  2026", "pondělí 19. října 2026", "Včera", "Dnes" as `h3` at 1440, 1100, 768 and 390 px, no
  page overflow, no paid job; `lead_journey.mjs` passes unchanged.
- Not wired, because they already show the date beside the time: Settings' audit log
  (`settings/ControlPanel`) and Můj Vedoucí's notes and history.

## Findings

- **F4.** Notes past the newest 40, or past 16 KB, leave the Lead's context without being counted:
  `notes_layer` stops silently (`domain/research_lead.py:759-772` on this branch (`:733-746 @ bfe6d15`)), and the context holds
  no `omitted_notes`. LC1's manifest names the bound in words but cannot count what was left. The
  fix is LC4's: the layer carries its omitted count once its bytes may change.

- **F1.** ADR 0026 decision 2 promises "a rolling summary of older turns, stored as an artifact of
  the Lead's run"; none exists. `freeze_context` keeps 12 turns and counts the rest
  (`domain/research_lead.py:121,796-827 @ 237fd0a`). Reproduction: post 13 messages in one study;
  turn 14's stored context has `omitted_turns: 1` and no summary. Consequence: the Lead forgets the
  start of a long study's conversation. Smallest fix: LC3 (digest) then LC7. Test: LC3's "turn 3 in
  turn 40" test.
- **F2.** ADR 0026's *Consequences* says "one conversation per study … shared by everyone who opens
  the study", contradicting its own *Accepted with* 6 and the code (per researcher). Docs only.
- **F3.** File revisions are written but have no reader (`researcher_lead_repository.py:187 @
  237fd0a`); already `lead-orchestration#LO11`.

## Doc follow-up (for the docs PR, not this branch)

- `docs/architecture/adr/README.md`: add ADR 0041 (Proposed).
- `CLAUDE.md` § The map, `domain/research_lead.py`: "the layer table (`LeadLayer`) and
  `ContextManifest`" once LC1 lands; `apps/web/src/components/workbench/` LeadPane: "Co Vedoucí vidí"
  once LC2 lands.
- `mvp-execution-contracts.md`: a row for LC1-LC13 in W1-W3 as above, once LC0 admits them.
- `open-items.md`: F1 and F2 as new OIs.
- `CLAUDE.md` § The map, routers/ `lead`: "GET …/turns/{turn_id}/manifest (what the caller's own
  turn could see, read from its frozen context; a layer it did not record said so) and
  …/manifest/omitted?layer=&after= (the rest of a layer's left-out ids)"; components/workbench/:
  "LeadSees: Co Vedoucí vidí, opened from the Vidí chip".
- The UI standard (`docs/design/aia-design-system-brief.md` § 6, Implementation constraints):
  the LC19 rule as written above, under a heading "Day dividers in a time-only feed", naming
  `lib/day-label.ts` as the one implementation.
