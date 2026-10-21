# ADR 0041 — The Lead's conversation and context: five memory tiers, a budgeted context with a manifest, compaction that keeps decisions, and message operations as new turns

**Status:** Proposed — 2026-10-20. Not accepted until the product owner says so. The coordinator
relayed the owner's answers to all six of its questions (PM status page, 2026-10-20 22:39-22:48
UTC: Q25 a, Q26 a, Q27 a, Q28 a, Q29 a, Q30 a); they are written in as relayed, to be confirmed when
the owner accepts this ADR.
**Amends** [ADR 0026](0026-research-lead-proposes-a-person-decides.md) decision 2 (the context's
layers get budgets and a manifest; the conversation layer's rolling summary is specified and built),
decision 8 (`study_lead_turns` gains three columns; queued messages are stored) and its
*Consequences* ("streaming not decided": decided by D-39, the transport is specified here).
**Builds on**, by reference to PR #512 (`chore/mvp-adrs @ 4502017`, all Proposed): ADR 0029 (the
operation log and per-change accept), ADR 0030 (the Lead's files over time; a Lead is its
researcher's alone), ADR 0039 (the study context file), ADR 0040 (the web lookup and its
continuation turn) and ADR 0035 (report edits).
**Leaves unchanged** the closed `LeadOutput`, "the Lead calls no tool", the governed model gateway as
the only model path, the number rule, the privacy of turns, the wallet and spend gates, and the
96 KB context bound.
**Date:** 2026-10-20.
**Plan:** [lead-conversation](../../../.planning/plans/lead-conversation.md).
**Evidence:** [`.planning/evidence/lead-chat-capabilities.md`](../../../.planning/evidence/lead-chat-capabilities.md)
(what exists, what is planned, the gap table against Open WebUI and current practice).

## Context

The product owner asked that the Lead have "the correct capabilities a chat-centric software would
have, from session memories to context management", with Open WebUI as the reference.

The Lead has a sound core (the evidence file, §1.1): durable worker turns, a frozen and hashed
context, a closed output, private per-researcher sessions, reviewed memory for anything that crosses
clients. Its conversation handling is thin:

- **It forgets, by count.** The conversation layer is the newest 12 turns; everything older is
  counted as `omitted_turns` and gone (`domain/research_lead.py:121,796-827 @ 237fd0a`). ADR 0026
  decision 2 promised "a rolling summary of older turns, stored as an artifact"; none was built. In a
  study that runs for weeks, the Lead loses why the brief changed, what the client said and which
  proposals the researcher refused.
- **One bound, no budget.** Only the whole context (96 KB), knowledge (20 KB of titles), notes
  (40 / 16 KB) and runs (5) are bounded. A large design squeezes the conversation out; nothing says
  which layer cost what.
- **What it saw is not shown.** The pane says one line, "Vidí: <stage> · pracovní kopie studie"
  (`LeadPane.tsx:227 @ 237fd0a`), while the stored context knows exactly what was sent and omitted.
- **A message typed while the Lead works lives in one tab's memory** (`LeadPane.tsx:30,93 @
  237fd0a`); the server refuses it (`LeadBusy`, `application/research_lead.py:421-424 @ 237fd0a`).
- **No regenerate, no edit-and-resend, no per-turn cost, no feedback.**

Mature chat products solve these with the same small set of patterns (evidence, §2): a session
store separate from long-term memory; compaction that replaces old turns with a summary instead of
dropping them; retrieval instead of truncation; a visible context; messages as a tree so regenerate
and edit never destroy history. AIA needs them under constraints no general chat product has: data
classes by rule, EU residency, numbers only as ledger refs, a person deciding every structural
change, private turns, sealed Leads, and every paid call inside the wallet.

## Decision

### 1. Five memory tiers, each with one writer rule

| Tier | What | Scope and privacy | Who writes | Class by rule |
|---|---|---|---|---|
| **M1 Turn context** | The frozen context of one turn (ADR 0026 decision 2), with its manifest (decision 3) | That turn | Code, at enqueue | Most restrictive of its layers |
| **M2 Conversation** | `study_lead_turns`: the person's messages and the Lead's turns | One researcher in one study; nobody else reads it (ADR 0030 decision 5) | The person (a message); the worker (a Lead turn) | Each Lead turn the class it was sent as; a message Class B (`material_rules.py`) |
| **M3 Conversation memory** | The *decision digest* and the *summary* (decision 4) | As M2: private, sealed with the Lead | Digest: code. Summary: a model step, correctable by the person | Digest: the class of what it names. Summary: the most restrictive class of the turns it covers |
| **M4 The Lead's own memory** | Name, SOUL, USER, personal and client notes, their revisions and signals (ADR 0026 *Accepted with* 6, ADR 0030) | The researcher, across studies; a client note only in that client's studies | The person; the Lead proposes, and what reaches every client needs a yes | Personal Class C; client note Class A |
| **M5 Shared memory** | The study context file (ADR 0039) and approved Client Knowledge | Every member who opens the study / the client | Code (facts); a person accepts notes and knowledge | ADR 0039 decision 5; knowledge Class A |

Two rules hold across tiers:

- **Nothing moves from a private tier to a shared tier without a person.** A turn's content reaches
  M5 only as a proposal the person accepts (a study note, ADR 0039; a knowledge proposal; a verified
  source). A summary is never a source of the study context file.
- **A client's material never enters a tier that crosses clients.** M4's personal files keep ADR
  0030 decision 3's check (no client name, no number). M3 is per study, so a summary of a Class A
  conversation stays in that study.

### 2. The context is assembled by a pipeline of layers, each with a budget

`freeze_context` becomes a pipeline over a declared table of layers. Each layer has an order, a
**floor** (bytes it always gets when it has content), a **ceiling**, a **policy when over**, and a
class rule. The sum of floors fits `CONTEXT_MAX_BYTES` (96 KB, unchanged). Bytes above the floors
are allocated by the second pass below, in its one declared order, with the verbatim conversation
last. The table is code in `domain/`, and
its values are proposed here, to be set from LO14's measurement:

| # | Layer | Floor | Ceiling | Over the ceiling |
|---|---|---|---|---|
| 1 | Prompt pin | as pinned | 12 KB | refuse the turn (a prompt never truncates) |
| 2 | Lead files (name, SOUL, USER) | 6 KB | 6 KB | cannot happen for a file admitted under the byte bounds below; an older file over them is shortened at its last whole paragraph within the bound, named (`lead_file_shortened`), and the researcher is told |
| 3 | Lead notes | 4 KB | 12 KB | relevance-ranked (decision 5), then newest; omitted ids named |
| 4 | Study context file (ADR 0039) | 8 KB | 16 KB | ADR 0039 decision 4: oldest history lines, then oldest notes, named |
| 5 | Client Knowledge | 6 KB | 16 KB | titles of all, bodies of the retrieved (decision 5); omitted ids named |
| 6 | Design and stage state (LO7) | 12 KB | 32 KB | the focused stage verbatim, the others as an outline of item ids and titles, named |
| 7 | Runs and results (LO8 `ResultsContext`) | 4 KB | 16 KB | LO8's own bound |
| 8 | Pinned items (decision 6) | the accepted pins' bytes | 8 KB | refuse the pin when it is made; an accepted pin is reserved in the floor pass, never dropped at a turn |
| 9 | View and the message(s) | as written | 12 KB | queued messages oldest first while they fit; the rest answered by a follow-on turn, named (decision 7) |
| 10 | Conversation memory (M3): digest, kept facts, summaries | 10 KB | 16 KB | the digest within its share (5-8 KB, scaling with the layer's allocation) by decision 4's order, older decisions counted with their ledger range (decision 3); oldest blocks rolled up; oldest unpinned facts to retrieval; all named |
| 11 | Conversation, verbatim (active path only, decision 7) | 8 KB | what is left | oldest first, **only turns a summary covers**, else decision 4's fallback |

**The allocation is global, in two passes, so the total cannot exceed 96 KB.** The ceilings sum to
more than 96 KB on purpose, because most layers are small most of the time. `freeze_context`
therefore never adds layers up and checks afterwards. It allocates:

1. **Floors first.** Each layer gets the smaller of its content and its floor. The floors sum to at
   most 90 KB: prompt 12, files 6, notes 4, study file 8, knowledge 6, design 12, results 4, pins
   up to 8 (every accepted pin, reserved), message 12, memory 10, verbatim 8. That leaves at least
   6 KB.
2. **The remainder in a fixed priority order.** Each layer in turn takes what it still needs, up to
   its ceiling, until the 96 KB is spent:
   design (6) → study file (4) → results (7) → pins (8) → conversation memory (10) → knowledge (5)
   → notes (3) → verbatim conversation (11), which takes whatever is left.

A layer whose content exceeds its allocation applies its own over-ceiling policy to that
allocation, not to its nominal ceiling. A layer is therefore shortened by its own named rule, never
by another layer's growth. The conversation never falls below its floor while it has content, and a
context of individually valid layers is never refused. The order is the proposed default and is
recorded in the manifest beside each layer's allocation. It is tuned with the budget values after
LO14.

**Results enter once, then as references.** A continuation turn's typed results (LO6) and a
lookup's captured texts (ADR 0040) are verbatim in the turn that answers them; later turns carry
them as references (snapshot, artifact or run id) with the answer's citations, the lightest form of
compaction, as context editing clears old tool results elsewhere. Retrieval (decision 5) may bring
one back.

**The Lead's files are bounded in bytes, not only characters.** Today's limits are 2,000 characters
for SOUL and USER and 40 for the name (`domain/research_lead.py:123-126 @ 237fd0a`), which in
four-byte characters could exceed the layer. Hatching and every self-update therefore also refuse
the following, by name (`lead_file_too_large`), never truncating:
- SOUL over 2,800 bytes of UTF-8;
- USER over 2,800 bytes;
- a name over 160 bytes.

With the JSON framing, layer 2 then fits its 6 KB.

Layer 11 drops only turns already covered by a summary. When compaction has not caught up (switched
off, failed or behind), it drops the oldest uncovered turns as today, and the manifest says
`summary_lag` with the count; it is never silent.

### 3. Every turn stores a manifest, and the person can read it

The frozen context already sits in the step's input. Beside it the turn stores a **manifest**:
per layer, its bytes, floor and ceiling, the ids included, the ids omitted and why
(`over_budget`, `not_relevant`, `forgotten`, `class_refused`), its class and the source of the
class (a rule or an operator); and the turn's total, its class, the study context file's version,
the summary's id and the turns it covers.

**The manifest is bounded by the number of layers, never by the length of the history.** Per layer
it lists at most 50 included and 50 omitted ids. Beyond that it stores counts, by reason, and a
**range**: the source (ledger, turns, knowledge, notes) and the first and last id or sequence
number, as of the revisions the turn froze. "Co Vedoucí vidí" pages the omitted items from the
source table through that range (`GET …/manifest/omitted?layer=&after=`), under the caller's own
scope. A turn's stored manifest stays a few kilobytes however long the study runs, and nothing it
summarises by count is unreachable.

The pane's one-line *Vidí* becomes a chip that opens **"Co Vedoucí vidí"**: the manifest of the
last turn in words, layer by layer, with what was left out. It reads stored data and costs nothing.
It shows the summary's text and lets the researcher correct it (decision 4). This is the person's
answer to "why did the Lead not know X".

### 4. Compaction is grounded and hierarchical: nothing decisive is lost, and every summary line points back to its turns

The product owner chose a decision digest plus a model summary (Q25 a, 2026-10-20) and asked that
the approach be innovative and "best preserve the context properly". That is a requirement here:
compaction may shorten the dialogue, but it may not lose a decision or an agreed fact, and every
shortened line can be expanded back to the turns it came from. Conversation memory (M3) has four
parts, from exact to approximate:

1. **The decision digest, by code, always.** A deterministic projection of what was *decided* in
   this conversation, from the approval ledger and the turns: edits accepted or dismissed (by item),
   cards approved or left, notes kept or forgotten, self-updates accepted or refused, lookups run,
   feedback given, each with its turn id. No model, no cost, never summarised.
   **It is bounded in context and complete in the ledger.**
   - **Its record is the ledger.** The digest is a view of the approval ledger rows, which are
     immutable, so no decision is ever lost. What is bounded is how much of it a turn carries.
   - **Each line is exact and short:** at most 200 bytes, with the item, the decision, the turn id
     and the ledger row id.
   - **Its share of layer 10 scales with the layer's allocation.**
     - **Range:** from 5 KB at the layer's 10 KB floor to 8 KB at 16 KB, linearly.
     - **Group caps:** the caps below are the 8 KB values. They scale by the same factor (5/8 at the
       floor), except group 4's 256 bytes, which stay fixed.
     - **The rest of the layer:** after the digest, the remaining bytes go to kept facts first, then
       summaries.

     So a large design that takes the whole remainder still leaves memory a compliant allocation:
     a 5 KB digest and 5 KB for facts and summaries.
   - **The groups.** Each group has its own cap and a deterministic order inside it, so no group
     can starve the others:

     | Group | Cap | Order inside the group |
     |---|---|---|
     | 1. Decisions on items the message, focus or a pin names | 4 KB | Items in the order they are named, then the newest 3 decisions per item, newest first; the rest counted per item |
     | 2. Undecided proposals on the active path (decision 7) | 2 KB | Newest first, one pointer line each |
     | 3. The latest decision per other item | whatever groups 1 and 2 left | Newest first |
     | 4. Counts per kind | 256 bytes, always reserved | "14 older edit decisions, 3 cards" |

     A group under its cap leaves its bytes to group 3.
   - **Nothing is rewritten, and every omission has a source to page from.**
     - A decision left out of groups 1 or 3 is counted, and the manifest records its **ledger
       range** (decision 3).
     - An undecided proposal left out of group 2 lives in a turn's output, not the ledger. The
       manifest records the **turn range** that holds it.
     - Both page through "Co Vedoucí vidí".
     - Retrieval (decision 5) brings a decision back exactly when its item is named, and the newest
       omitted undecided proposals when the message names their stage.
2. **Kept facts (*Držená fakta*), grounded.** Statements the conversation established that are not
   ledger decisions: "the client wants the report in English", "region is not a quota", "the
   pilot is in Brno". The compaction step proposes them; each must carry a quote that code locates,
   verbatim, in a person's message of the turn it names (the Deep Research grounding rule, ADR 0017,
   applied to the conversation). A fact without a locatable quote is refused. Kept facts are never
   compacted: a later fact may supersede one by naming it, and the researcher can pin, correct or
   retire any (in place, decision 11). Bounded (40 facts, 300 characters each); over the bound the
   oldest unpinned facts move to retrieval, named in the manifest.
3. **Hierarchical summaries, each line referenced.** Active turns (decision 7) older than the two
   newest active exchanges are summarised in fixed blocks of eight
   *after* the reply, by a follow-on step `research_lead_compact`, so the person never waits.
   - A **block summary** covers one block. Every sentence ends with the turn ids it rests on
     (`[t12, t14]`), each within the block.
   - When block summaries exceed their share of layer 10, the oldest are rolled up into an **episode
     summary**, whose sentences reference the block summaries; episodes roll up the same way. Three
     levels at most.
   - The context carries the newest episode, the newest blocks and the verbatim tail: a rolling
     window over a tree, so the cost of a turn does not grow with the study's age.
   - Each is an artifact `research_lead_summary` of the Lead's run: level, the turn range, the child
     summary ids, the input hash, the prompt pin, its class and its cost.
4. **Verbatim, always reachable.** Covered turns stay in `study_lead_turns`. Retrieval (decision 5)
   follows the references: a summary sentence that matches the new message brings back the turns it
   names, verbatim, before any lexical search of the rest. The summaries are an index into the
   record, not a replacement for it.

**The preservation check.** Code accepts a new summary only when:

- every sentence references at least one turn (or child summary) within its range, and every turn of
  the range is referenced by some sentence or by a digest line, so no turn is silently skipped;
- every number appears in the referenced turns' text (`lead_contract` over that text);
- its class is the most restrictive class of the covered turns, by rule, and it goes only to a route
  approved for that class;
- it does not restate a decision differently from the digest (a sentence naming an item the digest
  decided must carry that decision's turn).

A summary that fails is refused, the previous level stays in force, and the manifest reports
`summary_lag` with the uncovered turns. The digest and kept facts do not depend on a model, so a
refused or switched-off summary loses no decision.

**What a summary dropped is indexed, not trusted away.** No check can prove that a model kept every
preference or constraint a person stated, and the kept-fact proposals come from the same model. So
compaction makes no such claim. Instead, code records what each summary left out, and makes
exactly that the first thing retrieval looks for:

- **The uncovered-terms index.** When a summary is accepted, code computes each covered person
  message's *uncovered terms*: its content words that appear neither in the summary sentences
  referencing that turn nor in its kept facts. Words are accent-folded and stemmed by the
  project-memory matcher, `domain/project_memory.py`. The index is stored with the summary
  artifact. This is deterministic, needs no model and costs nothing.
- **Retrieval keyed on the gaps.** When a new message, its focus or a pin matches a turn's uncovered
  term, that turn comes back verbatim, ahead of every other retrieval (decision 5, step 0). A
  constraint the summary dropped therefore returns the moment the conversation touches it again.
- **Coverage is measured and floored.** The manifest reports each summary's coverage, the share of
  its person-message content words it kept. A summary below 60 % is refused like any other failure
  (`summary_lag`). The threshold is tuned by LC13's recall test.
- **Covered turns are never unreachable.** A covered turn leaves layer 11, never the store or the
  index. The researcher can see its uncovered terms in "Co Vedoucí vidí" and promote any to a kept
  fact in place.

**Its other rules.**

- **Not research truth:** labelled *shrnutí konverzace*; never a source of the study context file,
  knowledge or a report.
- **Correctable in place, references kept.** The researcher rewrites a summary or a fact inline in
  "Co Vedoucí vidí". A person's revision (`created_by = person`) passes the same preservation
  check as a model's, except the coverage floor:
  - **Each sentence keeps its references.** They show as fixed chips the person can move or remove
    but cannot type. A sentence left without any is refused in place, with the reason.
  - **Deleted sentences.** A turn that loses its last referencing sentence must still be referenced
    by another sentence or a digest line. Otherwise its words go back into the uncovered-terms
    index, which is recomputed for the revision, and retrieval still finds it.
  - **Numbers.** The number rule applies.
  - **Later roll-ups build on the revision,** so every summary sentence stays expandable to its
    turns.
- **Paid and switched:** `AIA_AI_RESEARCH_LEAD_COMPACTION_ENABLED` (off by default, on for develop
  once measured), with its own `…_MAX_OUTPUT_TOKENS` and `…_RESERVATION_USD`, charged to the wallet
  like a turn and shown with its cost. It names `ModelCapability.STUDY_LEAD_SUMMARY`, bound to the
  light model where one is configured. Off, the digest, the kept facts already accepted and the named
  drop are what remains.
- **Measured:** the chunk's PR reports a recall test on a recorded 60-turn conversation (every
  kept fact in turn 61's context, every digest decision in it or reachable through the manifest's ledger range and retrieved
  when its item is named; the turns behind a summary
  sentence retrieved when the message names its subject), and the cost per block.
- **"Začít od čistého stolu"** (after the MVP): the researcher sets a boundary; turns before it enter
  the Lead's context only through M3.

Why this shape: rolling summaries alone (Letta, Open WebUI's checkpoint, server-side compaction
APIs) drift, because each summary is a summary of a summary and nothing checks what it dropped.
Here the parts that must not drift (decisions, agreed facts) never pass through a summary at all;
the summaries that remain are grounded line by line in the turns, checked by code, correctable by
the person, and reversible through their references.

### 5. Retrieval is code at enqueue, recorded, lexical first

The Lead calls no tool (ADR 0026 decision 3), so retrieval happens where the context is frozen.
At enqueue, code ranks with the accent-folded matcher project memory already uses
(`domain/project_memory.py:76,169 @ 237fd0a`) against the message, the focus, the queued messages
and the stage, in this order:

- **step 0: turns whose uncovered terms match** (decision 4), verbatim, ahead of everything else;
- **step 1: the turns behind a matching summary sentence**, following its references;
- **past turns** of this conversation that a summary covers (layer 11's spare bytes);
- **Client Knowledge bodies** beyond the titles (layer 5);
- **notes** (layer 3), instead of the newest 40.

Each retrieved item is in the manifest with its score's reason. Embeddings (an EU embedding route,
`pgvector` in PostgreSQL per ADR 0002) are after the MVP and need their own ADR: an embedding is
model output over Class A material and a new egress. A Lead-requested recall (the Lead asks, a
continuation turn answers, as ADR 0040's lookup) is the path if retrieval at enqueue proves too
coarse; it is not built now.

### 6. Pins

A researcher pins a turn, a knowledge item, a note or an artifact element (through the `@` of
`research-lead-workbench#16`) to the conversation. A pin is the researcher's own (M2 privacy), goes
into layer 8 on every turn until unpinned, and is refused when made if layer 8 cannot hold it.
Accepted pins are reserved in the floor pass (decision 2), so no higher-priority layer can take
their bytes and a pin that was accepted is never dropped at a turn. A pinned item that grows (a
knowledge item revised) is re-checked against layer 8 when it changes. If it no longer fits, the
researcher is told and the pin stays at its pinned revision. A
pinned item keeps its own class; a pin never copies text between clients.

### 7. Message operations are new turns; history is never rewritten

`study_lead_turns` stays append-only, and its rows stay immutable (the `before_update` guard,
`infrastructure/tables.py:815-818 @ 237fd0a`). It gains two nullable columns, written when the
row is inserted and never after:
- `parent_turn_id`: the turn this one answers or follows;
- `replaces_turn_id`: the turn it supersedes.

What a Lead turn answered is recorded exactly, not as a high-water mark. **`study_lead_turn_answers`**
is append-only, holding (`lead_turn_id`, `person_turn_id`). It is inserted in the same transaction
as the Lead turn, with one row per message the turn was actually sent, and is scoped like the turns.

**A message's queue position** is the `sequence_no` of the root of its `replaces_turn_id` chain. An
edit therefore keeps the original's place in the queue, whatever `sequence_no` the edit itself gets.

A message's state is derived, never stored:
- **queued:** a person message that no `study_lead_turn_answers` row names, that no later row
  names by `replaces_turn_id` (an edited message is replaced by its edit, which takes its place in
  the queue) and that no `withdrawal` names;
- **answered:** a message that a `study_lead_turn_answers` row of an **active** Lead turn names:
  exactly the messages that turn was sent, so a deferred message is never answered by position. A
  replaced or withdrawn message is never sent and never named. When a Lead turn becomes inactive
  (below), every still-active message it answered is queued again, in its queue position. So an
  edit-and-resend of one of two co-answered messages requeues the other, and the replacement turn
  answers both;
- **withdrawn:** a person message named by a later row of kind `withdrawal` (`parent_turn_id` = the
  message).

The table holds a tree. **The active path** is the one predicate that freezing, retrieval,
compaction and the digest all use. A turn is active when:

- no later row names it by `replaces_turn_id`, and no `withdrawal` names it;
- the turn its `parent_turn_id` names is active;
- for a Lead turn, every person message it answers is still active when the turn is read. A Lead
  turn answering a message later replaced by an edit-and-resend is therefore inactive with it.

Inactive turns stay stored. The interface shows them collapsed, and the researcher can open them.
They never enter layer 11, the retrieval candidates, a summary block or the digest's undecided
group. Their undecided output is refused as `superseded_turn`.

**Compaction stays out of the replaceable window.** Regenerate and edit-and-resend act only on the
newest exchange (decision 7). Compaction covers only turns older than the two newest active
exchanges, so a covered turn can never be superseded afterwards.

- **Queued messages are stored at once.** A message posted while a turn runs is a stored turn,
  visible in every tab. The next turn answers the queued messages in order. Each stays its own
  turn with its own text and is never merged into one prompt. `LeadBusy` is retired for messages; a
  greeting still waits. A queued message can be withdrawn before its turn starts, or edited, which
  appends a replacement with `replaces_turn_id`.
- **The queue is bounded in bytes, never truncated.**
  - **Per message:** a message is at most `MESSAGE_MAX_BYTES` of UTF-8, 8 KB, on top of today's
    4,000 characters. A post over it is refused (422 `message_too_long`).
  - **Per queue:** at most 5 messages, so a sixth post is refused (409 `lead_queue_full`).
  - **Per turn:** a turn takes queued messages, oldest first, while they fit layer 9's 12 KB
    ceiling. Queue position, as defined above, sets the order. The turn's answer rows name exactly
    the messages taken. If any remain, a follow-on turn is
    enqueued at once to answer them, and the manifest names them (`queued_deferred`).

  So layer 9 cannot overflow, and no message is cut or lost.
- **Regenerate** the newest Lead turn: a new Lead turn with `replaces_turn_id`, from a fresh
  freeze. Allowed only while none of the replaced turn's edits, cards or self-updates has been
  decided; its undecided ones are refused afterwards as `superseded_turn`. Paid like any turn.
- **Edit and resend** the newest person message, edited in place in the thread: a new person turn
  replacing it and a new Lead turn; the same rule on decided output.
- **Retry** a failed or parked turn: a regenerate with the park reason shown; an uncertain model
  call is never replayed automatically (the step's own rule).
- **Stop** (LO17): cancels the running step; its partial text is kept as *Zastaveno vámi* and is
  not a turn of the conversation; nothing it proposed exists.
- **Branch navigation** (sibling arrows over replaced turns) is after the MVP; the data already
  holds it.

### 8. Streaming is a preview of the reply; the validated output replaces it

D-39 put streaming in. The API has no model path, so tokens travel through the run's event feed:

- the worker writes `lead_reply_delta` events (about every 250 ms or 200 characters) for the
  `reply` field only, behind `AIA_AI_STEP_EVENTS`' measured write path;
- the API serves `GET /studies/{id}/lead/stream?since=` as Server-Sent Events over that feed, and
  the browser falls back to today's poll; a reload resumes from its cursor;
- the preview is marked *koncept* until the output validates. A digit sequence is held back until
  its number is complete and found in the turn's allowed numbers; one that is not stops the preview
  at that point ("Ověřuji…"). The validated reply replaces the preview; a refused one is repaired as
  today, and the preview never stands as the answer;
- `view`, `edits`, `request`, `lookup` and `self_update` appear only after validation, never
  streamed.

### 9. Cost, model and feedback on each turn

- Each Lead turn shows a quiet line: tokens in and out, USD, the model that answered and the
  class it was sent as, from the usage ledger and the composition digest (LO12c), with compaction
  and lookup costs as their own lines.
- The model is not chosen per conversation. The route and binding are the deployment's
  (`STUDY_LEAD`, ADR 0026 amendment), refused by class as today.
- **Feedback:** a person may mark a Lead turn *pomohlo* / *nepomohlo* with a closed reason
  (`wrong_fact`, `ignored_context`, `bad_edit`, `too_long`, `other`) and optional text. It is stored
  per turn and researcher, private as M2, keyed by prompt pin, and read by an evaluation export for
  the prompt's owner as counts by reason and prompt version, never the text. A *nepomohlo* writes an
  ADR 0030 signal by id. It changes no file by itself.

### 10. Lifecycle, search and export

- One conversation per researcher per study stays (ADR 0026 decision 8): the study is the thread.
  No separate threads within a study (Q29 a, relayed): pinned items (decision 6) serve where a
  topical thread would; branch navigation comes after the MVP (decision 7).
- Archive follows the study; seal and deletion follow the Lead (ADR 0030 decision 5, Q14).
- After the MVP: a list of one's own conversations on *Můj Vedoucí*, a lexical search over one's own
  turns across the studies one can open, and an export of one's own conversation as Markdown with
  each turn's class, audited.

### 11. The interface follows the owner's input rule

Messages, summaries, notes and pins are edited in place, in the thread or the panel, never in a
full-screen text box. The keyboard map: Enter sends, Shift+Enter a new line, Esc stops a turn
(LO17), ↑ in an empty composer edits the last message, `/` opens the command list
(`research-lead-workbench#11`), `@` points (`#16`). A streamed reply is announced once when it
completes (a polite live region), never per token.

## What stays out

- **Tool calls by the Lead.** Retrieval, lookups and jobs stay code steps around a closed output.
- **A model picker** in the conversation; **temporary, unlogged chats**; **sharing a turn** with
  another person (the path to share is a study note a person accepts).
- **Memory written without review** where it crosses clients.
- **Deleting a turn** by its author. Append-only; sealed and deleted only at the Lead's retention end.
- **A summary as a source** of anything shared.
- **Embeddings and a vector store** in the MVP.

## Alternatives considered

- **Keep dropping old turns, raise the window.** The Lead model's window is large, but every byte is
  paid on every turn, and a longer drop horizon still drops. Rejected: cost grows with the study's
  age and the loss is only delayed.
- **Summary only, no digest.** A model summary can omit or soften a decision. The digest is free and
  exact for exactly the things that must not be lost. Rejected.
- **Compaction before the reply, in the same step.** Adds a model call to the person's wait on every
  long conversation. Rejected for a follow-on step with the named fallback.
- **Retrieval as a Lead tool.** Breaks ADR 0026 decision 3 and costs a second turn each time.
  Deferred, with ADR 0040's continuation pattern named as the path.
- **Threads within a study, as Open WebUI's chats.** The study is the unit of work and the Lead's
  memory tiers are organised around it; a second thread splits what the Lead knows. Deferred until
  use shows the need.
- **Editing history in place** (overwrite the message and the answer). Breaks the audit and the
  decisions recorded against a turn. Rejected for replacement turns.
- **Stream the whole structured output.** Edits and cards before validation would show proposals
  that may not exist. Rejected: only the reply previews.

## Consequences

- Two nullable columns on `study_lead_turns`, set on insert and never updated, a `withdrawal`
  turn kind and an append-only `study_lead_turn_answers` relation; one feedback table, one manifest per turn (in the
  step's stored input), one artifact type, one capability, one switch with two keys.
- The Lead remembers a long study's decisions exactly and its dialogue approximately, and says
  which.
- Every turn can answer "what did the Lead see", in words, from stored data.
- Compaction is a paid call the Lead did not make before; bounded by its reservation, off by
  default, measured before it is on.
- The streamed preview is less fluent than a general chat product's around numbers; that is the
  price of the number rule.

## What enforces it

- Domain tests: the budget table's floors fit 96 KB; each layer's over-ceiling policy names what it
  dropped; layer 11 drops covered turns first and records `summary_lag` otherwise; the digest is the
  same for the same ledger; a summary with a number not in its covered turns is refused; its class is
  the covered turns' most restrictive; a summary sentence without a turn reference, or a range with
  an unreferenced turn, is refused; a kept fact whose quote does not locate in its named turn is
  refused; a roll-up keeps its children's references; a constraint a summary left out is in its
  turn's uncovered terms and brings that turn back verbatim when named; a summary under the
  coverage floor is refused; with every layer at its ceiling an accepted pin is still whole; an
  edited queued message sends only its edit, keeps the original's queue position, and its original
  is never marked answered; a message deferred behind a large edited one stays unanswered; with the
  design taking the whole remainder, layer 10 at its 10 KB floor holds a 5 KB digest within its
  scaled group caps; after a
  regenerate or an edit-and-resend the next turn's context, retrieval candidates, summaries and
  digest hold no superseded turn; a person's correction that leaves a sentence without a reference
  is refused, and a turn it un-references returns to the uncovered-terms index; 40 decisions on one
  named item and 60 undecided proposals keep the digest within 8 KB, every group within its cap,
  each omission pageable from its ledger or turn range.
- The recall test (decision 4, *Measured*): on a recorded 60-turn conversation, turn 61's context
  holds every kept fact and every digest decision, either in context or reachable through the
  manifest's ledger range and retrieved exactly when its item is named; a message naming a summarised subject
  brings back the referenced turns verbatim.
- Application tests: no `study_lead_turns` row is ever updated (the `before_update` guard stays);
  a message over 8 KB of UTF-8 is refused; a sixth queued message is refused; queued messages over
  layer 9 are answered by a follow-on turn named in the manifest; the digest of 500 decisions stays
  within its share, its manifest stays bounded (counts and a range), and every omitted decision
  pages from that range; a queued message posted
  from a second tab is answered by the next turn; a
  regenerate after a decided edit is refused; a superseded turn's card is refused; the manifest
  lists every omitted id; feedback by another researcher is refused; a sealed Lead refuses every
  operation here.
- Web tests: the preview holds back an unadmitted number; "Co Vedoucí vidí" renders a stored
  manifest; the summary is corrected in place.
- `make layer_check`: the summary artifact and feedback only through their repositories; no model
  path in the API for streaming.

## Unblocks

`lead-conversation` LC1-LC13 (MVP) and LC14-LC18 (after); gives LO7, LO8, LO17, LO18, LO19 and LO20
the budget table, the manifest and the stream they each need.

## Open for Nigel

Answers relayed by the coordinator from the PM status page (2026-10-20 22:39-22:48 UTC), written in
and to be confirmed on acceptance. Nothing is left open.

- **Q25 (a), compaction:** the code digest plus a model summary, with the note "ensure we are using
  an innovative approach, and that we ensure we best preserve the context properly". Decision 4
  answers the note: the digest, grounded kept facts, hierarchical summaries with references, and the
  preservation check.
- **Q26 (a), feedback:** in the MVP. Decision 9.
- **Q27 (a), queued messages:** stored on the server and answered together. Decision 7.
- **Q28 (a), the 96 KB total:** kept, with a budget per layer. Decision 2.
- **Q30 (a), regenerate and edit-and-resend:** in the MVP. Decision 7.
- **Q29 (a), threads within a study:** none. The study is the thread, with pinned items instead, and
  branching comes after the MVP. Decisions 6, 7 and 10.
