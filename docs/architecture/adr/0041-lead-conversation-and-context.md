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
class rule. The sum of floors fits `CONTEXT_MAX_BYTES` (96 KB, unchanged); unused bytes go, in
order, to the verbatim conversation, then to retrieved items. The table is code in `domain/`, and
its values are proposed here, to be set from LO14's measurement:

| # | Layer | Floor | Ceiling | Over the ceiling |
|---|---|---|---|---|
| 1 | Prompt pin | as pinned | 12 KB | refuse the turn (a prompt never truncates) |
| 2 | Lead files (name, SOUL, USER) | 6 KB | 6 KB | cannot happen: the files' own bounds |
| 3 | Lead notes | 4 KB | 12 KB | relevance-ranked (decision 5), then newest; omitted ids named |
| 4 | Study context file (ADR 0039) | 8 KB | 16 KB | ADR 0039 decision 4: oldest history lines, then oldest notes, named |
| 5 | Client Knowledge | 6 KB | 16 KB | titles of all, bodies of the retrieved (decision 5); omitted ids named |
| 6 | Design and stage state (LO7) | 12 KB | 32 KB | the focused stage verbatim, the others as an outline of item ids and titles, named |
| 7 | Runs and results (LO8 `ResultsContext`) | 4 KB | 16 KB | LO8's own bound |
| 8 | Pinned items (decision 6) | 0 | 8 KB | refuse the pin when it is made, never at the turn |
| 9 | View and the message(s) | as written | 12 KB | cannot happen: message bounds; queued messages, decision 7 |
| 10 | Conversation memory (M3): digest, kept facts, summaries | 6 KB | 16 KB | oldest blocks rolled up; oldest unpinned facts to retrieval; the digest's oldest decisions to one line each; all named |
| 11 | Conversation, verbatim | 8 KB | what is left | oldest first, **only turns a summary covers**, else decision 4's fallback |

**Results enter once, then as references.** A continuation turn's typed results (LO6) and a
lookup's captured texts (ADR 0040) are verbatim in the turn that answers them; later turns carry
them as references (snapshot, artifact or run id) with the answer's citations, the lightest form of
compaction, as context editing clears old tool results elsewhere. Retrieval (decision 5) may bring
one back.

Layer 11 drops only turns already covered by a summary. When compaction has not caught up (switched
off, failed or behind), it drops the oldest uncovered turns as today, and the manifest says
`summary_lag` with the count; it is never silent.

### 3. Every turn stores a manifest, and the person can read it

The frozen context already sits in the step's input. Beside it the turn stores a **manifest**:
per layer, its bytes, floor and ceiling, the ids included, the ids omitted and why
(`over_budget`, `not_relevant`, `forgotten`, `class_refused`), its class and the source of the
class (a rule or an operator); and the turn's total, its class, the study context file's version,
the summary's id and the turns it covers.

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
2. **Kept facts (*Držená fakta*), grounded.** Statements the conversation established that are not
   ledger decisions: "the client wants the report in English", "region is not a quota", "the
   pilot is in Brno". The compaction step proposes them; each must carry a quote that code locates,
   verbatim, in a person's message of the turn it names (the Deep Research grounding rule, ADR 0017,
   applied to the conversation). A fact without a locatable quote is refused. Kept facts are never
   compacted: a later fact may supersede one by naming it, and the researcher can pin, correct or
   retire any (in place, decision 11). Bounded (40 facts, 300 characters each); over the bound the
   oldest unpinned facts move to retrieval, named in the manifest.
3. **Hierarchical summaries, each line referenced.** Turns are summarised in fixed blocks of eight
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

**Its other rules.**

- **Not research truth:** labelled *shrnutí konverzace*; never a source of the study context file,
  knowledge or a report.
- **Correctable in place:** the researcher rewrites a summary or a fact inline in "Co Vedoucí vidí";
  a person's revision (`created_by = person`) is kept as written, and later roll-ups build on it.
- **Paid and switched:** `AIA_AI_RESEARCH_LEAD_COMPACTION_ENABLED` (off by default, on for develop
  once measured), with its own `…_MAX_OUTPUT_TOKENS` and `…_RESERVATION_USD`, charged to the wallet
  like a turn and shown with its cost. It names `ModelCapability.STUDY_LEAD_SUMMARY`, bound to the
  light model where one is configured. Off, the digest, the kept facts already accepted and the named
  drop are what remains.
- **Measured:** the chunk's PR reports a recall test on a recorded 60-turn conversation (every
  digest decision and every kept fact present in turn 61's context; the turns behind a summary
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
and the stage:

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
into layer 8 on every turn until unpinned, and is refused when made if layer 8 cannot hold it. A
pinned item keeps its own class; a pin never copies text between clients.

### 7. Message operations are new turns; history is never rewritten

`study_lead_turns` stays append-only and gains three nullable columns: `parent_turn_id` (the turn
this one answers or follows), `replaces_turn_id` (the turn it supersedes) and `status` for a
person's message (`queued`, `answered`, `withdrawn`). The table holds a tree; the MVP's interface
shows the current path with superseded turns collapsed.

- **Queued messages are stored at once.** A message posted while a turn runs is a stored turn,
  `queued`, visible in every tab; the next turn answers all queued messages together, in order, and
  marks them `answered`. Each stays its own turn with its own text, never merged into one prompt. `LeadBusy` is retired for messages (a greeting still waits). A queued
  message can be withdrawn (`withdrawn`, never deleted) before its turn starts.
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

- Three nullable columns on `study_lead_turns`, one feedback table, one manifest per turn (in the
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
  refused; a roll-up keeps its children's references.
- The recall test (decision 4, *Measured*): on a recorded 60-turn conversation, turn 61's context
  holds every digest decision and every kept fact, and a message naming a summarised subject brings
  back the referenced turns verbatim.
- Application tests: a queued message posted from a second tab is answered by the next turn; a
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
