# The Lead as a chat-centric product: what it has, what is planned, what a mature chat product has

Written 2026-10-20 for the product owner's request of 22:25 UTC: *"We designed the Lead research
around the chat-centric approach; we took inspiration from Open WebUI. But we need to ensure we have
the correct capabilities a chat-centric software would have, from session memories to context
management. Let's ensure the architecture is designed for this."*

Read-only evidence. It changes no plan; the proposal it leads to is
[ADR 0041](../../docs/architecture/adr/0041-lead-conversation-and-context.md) (Proposed) and
[`plans/lead-conversation.md`](../plans/lead-conversation.md).

**Anchors.** Code `@ 237fd0a` (`origin/develop`, 2026-10-20). Plans `@ ec1265a`
(`chore/scope-baseline`, PR #523, the baseline awaiting the owner's signature). ADRs 0028-0040
`@ 4502017` (`chore/mvp-adrs`, PR #512, all Proposed). This file copies none of them; it cites.
Open WebUI is cited by URL (docs.openwebui.com and github.com/open-webui/open-webui, read
2026-10-20); a claim marked *unverified* was not confirmed in a primary source.

---

## 1. What the Lead has today, and what is already planned

### 1.1 Built (code @ 237fd0a)

| Capability | What exists | Anchor |
|---|---|---|
| One conversation per researcher per study | `study_lead_turns`, append-only; key is (`study_id`, `user_id`); `sequence_no` per pair; no conversation table | `infrastructure/tables.py:758 @ 237fd0a`; ADR 0026 decision 8 |
| Privacy of turns | Every read filters by the caller's `user_id` | `infrastructure/study_lead_repository.py:54-73 @ 237fd0a` (`_mine`) |
| A turn is a durable worker step | `research_lead` run, one `research_lead_turn` step, reservation, checkpoint, one schema repair; the API calls no model | `application/research_lead.py:385-470 @ 237fd0a`; `apps/executors/src/aia_executors/research_lead.py:150-230 @ 237fd0a` |
| Closed output | `LeadOutput`: `reply` (≤ 4,000 chars), `view` (≤ 3), `edits` (≤ 12), one `request`, `follow` (≤ 3 suggestions), `self_update` | `domain/research_lead.py:412-422 @ 237fd0a` |
| Numbers only from context | `lead_contract` refuses a reply with a number not in the frozen context (sign, exponent) | `domain/research_lead.py:435-500 @ 237fd0a` |
| Frozen, hashed context | Eight layers in fixed order (prompt, lead, knowledge, study, design, runs, view, conversation), canonical JSON, `context_sha256` in the run metadata | `domain/research_lead.py:782-827 @ 237fd0a`; `application/research_lead.py:829-892 @ 237fd0a` |
| Context bound | 96 KB total (`CONTEXT_MAX_BYTES`); conversation = the newest 12 turns (`HISTORY_TURNS`) of the 50 read, the oldest of those dropped first while over 96 KB; `omitted_turns` counts them; refused by name with none left to drop | `domain/research_lead.py:116,121,782-827 @ 237fd0a`; `application/research_lead.py:425 @ 237fd0a` |
| Per-layer bounds (some) | Knowledge 20 KB, titles and summaries only, omitted ids named; notes 40 / 16 KB; runs 5 | `domain/research_agents.py:33,545-562 @ 237fd0a`; `domain/research_lead.py:128-129,766-779 @ 237fd0a`; `application/research_lead.py:106 @ 237fd0a` |
| Data class per turn | Each layer classed by rule; most restrictive wins; unknown refuses; prior Lead replies carry the class they were sent as | `domain/research_lead.py:876-965 @ 237fd0a`; `application/research_lead.py:895-919 @ 237fd0a` |
| Long-term memory: the Lead's files | `researcher_leads` (name, SOUL ≤ 2,000, USER ≤ 2,000), revisions in `researcher_lead_revisions` | `infrastructure/tables.py:821,861 @ 237fd0a`; `domain/research_lead.py:123-126 @ 237fd0a` |
| Long-term memory: notes | `researcher_lead_memories`, `personal` or `client` scope, ≤ 300 chars; the Lead proposes ≤ 2 per turn; forget sets `forgotten_at` (nothing deleted); a client note loads only in that client's studies (by query) | `infrastructure/tables.py:897 @ 237fd0a`; `domain/research_lead.py:384-410 @ 237fd0a`; `infrastructure/researcher_lead_repository.py:135-185 @ 237fd0a` |
| Memory write review | What would reach every client (personal note, SOUL, USER, name) waits for the researcher's yes ("Pamatovat si"); a client note applies with the turn | `application/research_lead.py:620-676 @ 237fd0a` (`decide_self_update`); `domain/research_lead.py:617-648 @ 237fd0a` (`split_self_update`) |
| File revisions | Written on every change; **no reader** (`revisions()` has no caller) | `infrastructure/researcher_lead_repository.py:187 @ 237fd0a`; LO11 |
| Edits as change blocks, gated | Accept/dismiss per edit in one transaction, ledger `lead_edit`; text edits auto-accepted when the researcher's toggle is on, with Vrátit; stale turn refused | `application/research_lead.py:504-618 @ 237fd0a` |
| Prepared paid work | One decision card; a design job approved on the server under the spend check; other kinds open their stage | `application/research_lead.py:678-760 @ 237fd0a` |
| Greeting | One greeting per 8 h; the Lead row lock makes two tabs start one | `application/research_lead.py:104,407-420 @ 237fd0a` |
| One turn in flight | A second post while a turn holds is refused (`LeadBusy`); the **browser** queues messages and drains them one at a time; a refused one is held for "Zkusit znovu" | `application/research_lead.py:122,421-424 @ 237fd0a`; `apps/web/src/components/workbench/LeadPane.tsx:30,93-100,183-188,238 @ 237fd0a` |
| Transport | Whole turns, polled every 1.5 s (`GET /lead`); no streaming | `LeadPane.tsx:22,137 @ 237fd0a`; ADR 0026 *Consequences* ("Not decided here: streaming") |
| What the Lead sees, in words | One line: "Vidí: <stage> · pracovní kopie studie · <focus>" | `LeadPane.tsx:227 @ 237fd0a` |
| Pointing | The focus picker sends one item id with the message | `LeadPane.tsx:60,244 @ 237fd0a`; `domain/research_lead.py:176 @ 237fd0a` (`FOCUS_ID`) |
| Cost | Per job on its activity card; **not per Lead turn** | `LeadPane.tsx:393 @ 237fd0a` |
| Routes | `GET /studies/{id}/lead`, `POST …/lead/turns`, `…/edits`, `…/self-update`, `…/request`; `GET/POST /lead`, `PUT /lead/preferences` | `apps/api/src/aia_api/routers/lead.py:350-445 @ 237fd0a` |

**A promise not kept.** ADR 0026 decision 2 layer 7 says the conversation layer is "a rolling summary
of older turns, stored as an artifact of the Lead's run" plus the newest turns verbatim. No summary
exists: `freeze_context` keeps the newest 12 turns and counts the rest as omitted
(`domain/research_lead.py:796-827 @ 237fd0a`). A study conversation longer than 12 turns therefore
forgets its beginning, named but lost. This is the largest single gap and the reason ADR 0041 exists.

### 1.2 Planned (plans @ ec1265a, ADRs @ 4502017)

| Planned | Where | What it adds to the conversation |
|---|---|---|
| Wake on finished work | `lead-orchestration#LO6` (W1) | A finished step enqueues a continuation turn with typed results; turns stop being person-started only |
| Context layers | `lead-orchestration#LO7` (W1) | Readiness, outlook, what changed since the last turn, other people's changes, execution state, pending proposals |
| Results context | `lead-orchestration#LO8` (W1) | `ResultsContext` typed, classed, bounded; the read-tool decision against ADR 0026 decision 3 |
| Stage workers' inputs | `lead-orchestration#LO9d` (W2) | Each worker reads upstream accepted items, readiness, earlier dismissals, Deep Research findings, bounded with omissions named |
| Card bound to its revision; 96 KB vs 64 KB | `lead-orchestration#LO10` (W1) | A clean error where the Lead's context meets an agent's limit |
| The Lead over time | `lead-orchestration#LO11` (W2); ADR 0030 | Signals by id, proposed self-updates approved each, revision reader and restore, sealing on departure |
| Stop | `lead-orchestration#LO17` (W1); D-18 | Esc cancels a running turn; "Zastavit plán" |
| Streaming, file in composer, unprompted comments | `lead-orchestration#LO18` (W3); D-39 | Streamed text; a file kept by the existing paths; a paid comment after a pause |
| Study context file | `lead-orchestration#LO19` (W2); ADR 0039 | Code-built facts plus accepted "Poznámky ke studii", versioned, frozen per turn, shown as *Kontext studie* |
| Web lookup | `lead-orchestration#LO20` (W3); ADR 0040 | `lookup` output, a lookup step, a continuation turn with cited results; 3 queries, 5 pages, 2 lookups per turn |
| Report edits | ADR 0035; `report-delivery#RD6` | Lead edits a stored report; suggestions or direct rewrites per researcher |
| Operation log, per-change accept, undo | ADR 0029; `working-copy-edit-ops` | The one write path the Lead's edits go through |
| Pointing and @ | `research-lead-workbench#16` | The Vidí chip, the target button, `@` over every artifact's element |
| Command registry | `research-lead-workbench#11`; `lead-orchestration#LO9a` | The workers the Lead may call, one row each |
| Compact Lead at every width | `research-lead-workbench#26`, `#27` | Drawer or stacked layout under 1,100 px; switch-off stated |
| Cost per turn, kill switch | `lead-orchestration#LO14` | Measured cost per turn and an `AIA_LEAD_*` budget line |
| Workbench journey incl. keyboard | `research-lead-workbench#12` | Four widths, keyboard, focus modes |

Nothing planned covers: summarisation or compaction of the conversation, retrieval over a long
conversation or over knowledge beyond 20 KB of titles, a per-layer budget table, a
"what the Lead can see" panel beyond one line, regenerate, edit-and-resend, branching, server-side
queueing, conversation search or export, threads within a study, a prompt or template library,
slash commands, per-turn feedback, and per-turn usage display.

---

## 2. What a mature chat-centric product has

Open WebUI's sources were read on GitHub (`open-webui/open-webui @ 91ea4e3`, 2026-10-16;
`open-webui/docs @ cd7fbd8`), because the docs site itself was not reachable from this session.
Code links below are `OW:<path>#L<n>`, which stands for
`https://github.com/open-webui/open-webui/blob/91ea4e3/<path>#L<n>`. Docs links are
`docs.openwebui.com/<path>`, and each matches a file read in the docs repository.

Other products were read as follows:
- **Anthropic** (compaction, context editing, the memory tool, the context-engineering guidance):
  read directly from platform.claude.com and anthropic.com.
- **LibreChat and LangGraph:** read from their documentation repositories.
- **ChatGPT memory, Claude app memory, Letta and OpenAI Conversations:** search results only. These
  are marked *(snippets)*.

The patterns that recur across products are the checklist:

1. **Messages form a tree.**
   - Open WebUI's `history.messages` holds `{id, parentId, childrenIds}` with a `currentId` leaf
     (`OW:backend/open_webui/models/chats.py`).
   - Editing a message or regenerating an answer adds a sibling; nothing is overwritten
     (`OW:src/lib/components/chat/Chat.svelte#L4575-L4630`).
   - The sibling switcher shows "n/total".
   - Only the active path is sent to the model.
2. **The session is kept apart from long-term memory.**
   - LangGraph: a thread checkpoint keyed by `thread_id`, and a `Store` keyed by a namespace tuple
     (docs.langchain.com/oss/python/concepts/memory).
   - Letta: core, recall and archival memory *(snippets)*.
   - Open WebUI: chats, plus a per-user `memory` table that is embedded for retrieval
     (`OW:backend/open_webui/models/memories.py`).
3. **Memory can be scoped to a project.**
   - Claude: per-project memory spaces *(snippets)*.
   - ChatGPT: project-only memory (openai.com/academy/projects).
   - Open WebUI: folders carry a system prompt and knowledge
     (docs.openwebui.com/features/chat-conversations/chat-features/conversation-organization).
4. **Old turns are compacted, not dropped.**
   - Open WebUI (opt-in) summarises the oldest ~60 % at about 80k tokens, always cuts at a user
     message, keeps the summary as a checkpoint (`chat_message.context_summary`) and rebuilds the
     fixed layers after compaction (docs.openwebui.com/troubleshooting/context-window).
   - Anthropic offers server compaction (`compact_20260112`; on-demand `compact-2026-09-04`)
     (platform.claude.com/docs/en/build-with-claude/compaction).
   - Anthropic also offers context editing, which clears old tool results as the "lightest touch"
     (platform.claude.com/docs/en/build-with-claude/context-editing).
5. **The user can see the context.**
   - Open WebUI exposes `context_usage {tokens, threshold, percent}` and the `/status` and
     `/compact` commands.
   - LibreChat's gauge splits usage into dialogue, tool results, instructions and cost
     (librechat.ai/docs/configuration/token_usage).
   - Letta has a context-window viewer *(snippets)*.
6. **Retrieval replaces truncation.**
   - Open WebUI attaches knowledge with `#`, offers hybrid BM25 + vector search and reranking, and
     stores citations in the message's `sources` (docs.openwebui.com/features/chat-conversations/rag).
   - Anthropic's guidance: retrieve just in time (anthropic.com/engineering/effective-context-engineering-for-ai-agents).
7. **Memory writes are visible and editable.**
   - The Claude app lets the user view and edit its memory summary *(snippets)*.
   - Anthropic's memory tool is a file directory with caps; its guidance is to strip sensitive data
     and expire stale files (platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool).
   - LibreChat keeps extraction opt-in and lets the user switch memory off per chat
     (librechat.ai/docs/features/memory).
8. **The answer persists on the server, whoever is watching.** Open WebUI writes the final message
   itself and reloads from storage after a reconnect (`OW:backend/open_webui/utils/middleware.py#L3875`;
   `OW:src/lib/components/chat/Chat.svelte#L1889-L1909`).
9. **Messages typed while the model works are queued**, with send-now, edit and delete
   (docs.openwebui.com/features/chat-conversations/chat-features/message-queue).
10. **Feedback carries a snapshot of its conversation.** Ratings on sibling answers feed an
    Elo-based evaluation (`OW:backend/open_webui/models/feedbacks.py#L20-L30`;
    docs.openwebui.com/features/administration/evaluation).
11. **Commands and mentions.**
    - `/` opens prompts with typed variables, and prompts keep a version history with rollback
      (docs.openwebui.com/features/workspace/prompts).
    - `@` mentions a model or context, `#` knowledge, `$` a skill.
12. **The model is chosen under governance.** Model presets bundle a prompt, knowledge and tools,
    and per-group access decides who may use them (docs.openwebui.com/features/workspace/models).

What goes wrong in practice, and which part of AIA's design answers each failure:

- **Silent truncation.**
  - Open WebUI cuts injected memory to `[:2000]` characters with no marker
    (`OW:backend/open_webui/utils/memory.py#L397-L404`).
  - Its compaction skips silently when it finds no cut point.
  - OpenAI's `truncation:"auto"` drops the earliest items *(snippets)*.
  - *In AIA: a manifest per turn and named omissions.*
- **Memory written without review.** Open WebUI's background review rewrites memory every 10 turns
  without asking. *In AIA: ADR 0026 and ADR 0030's yes for anything that crosses clients.*
- **Compaction the transcript cannot see.** Open WebUI shows only a toast. *In AIA: "Co Vedoucí
  vidí" and the summary shown in it.*
- **Queued messages merged into one prompt, in browser memory only.** Authorship blurs and a reload
  loses them. *In AIA: queued messages stored on the server, kept as separate turns, answered
  together.*
- **Admins can read every chat by default** (`ENABLE_ADMIN_CHAT_ACCESS=True`,
  docs.openwebui.com/reference/env-configuration). *In AIA: never (D-32 to D-34, ADR 0030
  decision 5).*
- **Streaming state that is not persisted**, while persisting every chunk is flagged as a
  production risk. *In AIA: deltas batched into the run feed; the validated output is the record.*

## 3. The gap table

**Columns:**
- **AIA now:** the code at 237fd0a.
- **Planned:** a plan chunk at ec1265a, or `—`.
- **Constraint:** the AIA rule the design must keep.
- **Rec.:** **MVP**, **After** (after the MVP) or **Never**, with the chunk of
  [`lead-conversation`](../plans/lead-conversation.md) or of an existing plan.

**Abbreviations in the cells:**
- **DC:** data classes A/B/C by `material_rules.py`.
- **EU:** EU residency.
- **NUM:** numbers stay ledger refs (the number rule).
- **PD:** a person decides every structural change (ADR 0026).
- **PRIV:** turns are private to their researcher (D-32 to D-34).
- **SEAL:** the Lead is sealed when its member leaves (Q14).
- **$:** the wallet and spend gates.
- **IN:** the owner's input rule (edit in place, no full-screen text boxes).

### Conversation lifecycle

| Capability | Open WebUI | AIA now | Planned | Constraint | Rec. |
|---|---|---|---|---|---|
| Thread per unit of work | A chat, inside folders that act as projects | One conversation per researcher per study | — | PRIV; the study is the unit | **Never** for several threads per study in the MVP: the study is the thread (ADR 0041 decision 10) |
| History list across one's conversations | Sidebar, pinned, folders, unread | None | — | PRIV | **After**, LC14 |
| Search across conversations | Cmd+K over titles and messages, all words must match | None | — | PRIV, DC | **After**, LC14: lexical, one's own turns only |
| Rename and auto-title | A task model titles the chat | The study's name | — | — | **Never**: the title is the study's |
| Archive | Per chat | Follows the study | — | — | Already done (with the study) |
| Delete | By the user, gated by permission | None; append-only | LO11 / Q14: sealed, then deleted at retention end | Audit, SEAL | **Never** by the author; deletion only at retention end |
| Share | Snapshot links, live "Allow replies" | None | — | PRIV | **Never**. The path to share is a study note a person accepts (ADR 0039) |
| Export / import | JSON; ChatGPT import | None | — | DC, PRIV | **After**, LC15: export one's own conversation, class shown on each turn, audited. Import **Never** |
| Temporary chat | Never saved; can be enforced per role | None | — | Audit | **Never**: every turn is a paid, audited step |

### Message operations

| Capability | Open WebUI | AIA now | Planned | Constraint | Rec. |
|---|---|---|---|---|---|
| Streaming | Socket.IO deltas; partly persisted | Whole turns, polled every 1.5 s | LO18 (W3), D-39 | NUM: an unchecked number must not show; the API calls no model | **MVP**, LO18 built to ADR 0041 decision 8: only the reply previews, numbers held back until checked, SSE over the run feed |
| Stop mid-generation | `POST /api/tasks/chat/{id}/stop`; Esc | None | LO17 (W1) | $: the reservation settles | **MVP**, LO17. Partial text is kept as *Zastaveno vámi* and does not count as a turn |
| Retry on error | Error saved on the message; the user regenerates | "Zkusit znovu" for a message the server refused; a parked turn shows its reason | — | An uncertain call is never replayed | **MVP**, LC10: a replacement turn |
| Regenerate | A sibling answer | None | — | PD: decided output stays decided; $ | **MVP**, LC10: refused once any of the turn's output is decided |
| Edit and resend | A new branch | None | — | IN: edited in place in the thread | **MVP**, LC10 |
| Branch / fork navigation | Sibling switcher; fork copies the history | None | — | Append-only | **After**, LC16. The data comes in the MVP (`parent_turn_id`, `replaces_turn_id`) |
| Queued messages | Queued in the browser, merged into one prompt, lost on reload | Queued in one tab's memory; the server refuses with `LeadBusy` | — | PRIV; visible in every tab | **MVP**, LC5: stored on the server, kept as separate turns, answered together |
| Continue a cut-off answer | `continueResponse` | — | — | Closed output | **Never**: the output is validated whole |
| Resume after reload | Reloads from the database; no mid-stream replay | The turn is durable; the poll resumes | — | — | **MVP** with LO18: SSE resumes from its cursor |

### Memory

| Capability | Open WebUI | AIA now | Planned | Constraint | Rec. |
|---|---|---|---|---|---|
| Working context per turn | Assembled by middleware, not stored | Frozen and hashed per turn | — | DC, EU | Already done; LC1 adds the manifest |
| Session memory (the conversation) | The chat tree | `study_lead_turns`, the newest 12 turns | — | PRIV | **MVP**: LC3 (decision digest), LC7 (summary) |
| Long-term memory (the assistant's own) | `memory` table; model tools and background review write it | SOUL, USER and notes; the Lead proposes, and changes that cross clients need a yes | LO11 (W2): signals, revision reader, restore | DC (C personal, A client), SEAL | **MVP**, LO11 as planned |
| Per-project memory | Folder prompt and knowledge; Claude and ChatGPT keep per-project memory | Client notes load only in that client's studies | LO19 (W2), ADR 0039 | DC; facts by code, notes accepted by a person | **MVP**, LO19 as planned. It is layer 4 of ADR 0041 |
| Cross-client memory and its privacy | User-scoped; admins can read every chat by default | Personal notes only; the prompt forbids client facts; the person sees every note | ADR 0030 decision 3: code refuses a client name or number in a personal file | DC, PRIV | **MVP**, LO11. No admin read, ever |
| Memory write review | None (written by tools and background review) | Yes for whatever crosses clients; a client note applies with its turn | LO11 | PD | Already done; keep it |
| Forget | Delete, clear all | `forgotten_at`; nothing is deleted | — | Audit | Already done |
| Rollback | — | Revisions are written but nobody reads them | LO11 | — | **MVP**, LO11 |

### Context management

| Capability | Open WebUI | AIA now | Planned | Constraint | Rec. |
|---|---|---|---|---|---|
| Token budget per layer | None (memory cut by characters); LibreChat's gauge | One 96 KB total; some layers bounded | — | DC per layer | **MVP**, LC1 + LC4: a declared layer table with floors, ceilings and an over-ceiling rule per layer |
| Summarise and compact old turns | Opt-in checkpoint, about 60/40, cut at a user turn | None. ADR 0026 promised a rolling summary that was never built (F1) | — | NUM, DC, PRIV; never silently lossy; $ | **MVP**, LC3 + LC7: a code digest of decisions, plus a model summary after the reply behind a switch, with `summary_lag` named when it falls behind |
| Retrieval over history and knowledge | Hybrid search, top-k, citations | Knowledge as titles only (20 KB); no history beyond the window | LO8 (results), LO9d (workers) | DC; no new egress for the MVP | **MVP**, LC9: lexical retrieval at enqueue. **After**, LC17: embeddings, with their own ADR (EU embedding route, pgvector) |
| Clearing old tool results | Anthropic `clear_tool_uses` | n/a (no tools) | LO20's results reach a continuation turn | — | **MVP**, by rule in ADR 0041: a lookup's captured texts reach later turns only as references |
| Pinned items | — (folder knowledge comes closest) | Focus on one item, for one message | `research-lead-workbench#16` (`@`) | PRIV; a pin never copies text between clients | **MVP**, LC11 |
| "What the Lead can see" panel | `context_usage`, `/status`; compaction shows only a toast | One line, "Vidí: …" | `research-lead-workbench#16` (the chip) | — | **MVP**, LC1 + LC2: "Co Vedoucí vidí", from the stored manifest |
| Citations back to sources | `sources` stored on the message | Numbers must be admitted claims; not linked in the reply | LO20 (web, inline) | NUM; external sources labelled *externí zdroj* | **MVP**, partly: LO20 for web sources and LO8 for results. Linking knowledge, notes and turns is **After** |

### Files, tools and artifacts

| Capability | Open WebUI | AIA now | Planned | Constraint | Rec. |
|---|---|---|---|---|---|
| Attachments in chat | Upload, then RAG or the whole document | None in the composer (files go in through Přidat podklady) | LO18 (W3) | DC (a client source is A) | **MVP**, LO18: the file is kept by the existing paths and the Lead reads it through retrieval (LC9) |
| Tool calls shown in the thread | Collapsible items; Allow/Deny; `ask_user` | Job activity cards, decision cards | LO4 (plan card), `research-lead-workbench#23` | PD, $ | **MVP** as planned |
| Artifacts / canvas | HTML/SVG side panel | The workbench's artifact pane | `research-lead-workbench` 15-22 | — | Already done as the workbench |

### Commands, model choice, usage, feedback

| Capability | Open WebUI | AIA now | Planned | Constraint | Rec. |
|---|---|---|---|---|---|
| Prompt and template library | `/` prompts with variables and versions | The pinned Lead prompt (ADR 0020) | — | DC (personal templates are Class C) | **After**, LC18 |
| Slash commands | `/compact`, `/status`, `/model`, prompts | None | Command registry `research-lead-workbench#11`; typed chat start LO5 | PD: the server matches a typed command | **MVP** through #11 and LO5: `/` lists the registry |
| Mentions | `@` model or context, `#` knowledge | The focus picker | `research-lead-workbench#16` | PRIV | **MVP**, #16. LC11 lets an `@` pin |
| Model and route choice | `/model`, presets, group RBAC | Fixed per deployment (`STUDY_LEAD`), refused by class | LO12b/c (composition record) | DC, EU, licence | **Never** a per-conversation picker. **MVP**: show which model answered (LC6) |
| Usage and cost per turn | Raw usage in a tooltip; no cost figure | Cost per job, not per turn | LO14 (measured) | $: an unknown cost is never shown as 0 | **MVP**, LC6 |
| Feedback and ratings | Thumbs with a reason and a snapshot; Elo arena | None | ADR 0030 signals (LO11) | PRIV; the export carries no text | **MVP** (small), LC12. This is a decision for Nigel |

### Concurrency, resilience, access

| Capability | Open WebUI | AIA now | Planned | Constraint | Rec. |
|---|---|---|---|---|---|
| Two tabs | Live read-state; the queue is lost | A lock gives one greeting; the queue lives in one tab | — | — | **MVP**, LC5 |
| Two researchers | Shared folders, live replies | Separate private sessions | LO7 (other people's changes), LO19 (shared file) | PRIV | **MVP** as planned |
| Offline and resume | Reload from the database | A durable step; the poll resumes | LO18 | — | **MVP** with LO18 |
| Accessibility | Accessibility mode, UI scale; no live-region spec found (unverified) | Inherits the workbench | `research-lead-workbench#12`, `#26` | — | **MVP**: one polite announcement per finished reply (ADR 0041 decision 11) |
| Keyboard | Rebindable; Esc stops, ↑ edits, Cmd+R regenerates | Enter sends | LO17 (Esc), #12 | IN | **MVP**: ADR 0041 decision 11's key map, asserted in #12 |

### What the gaps come to

**For the MVP, five gaps are not in any plan:**
1. compaction, as a digest plus a summary;
2. per-layer budgets with a manifest, and the panel that shows it;
3. queued messages stored on the server;
4. regenerate, edit-and-resend and retry as replacement turns;
5. cost per turn and feedback.

They are LC1-LC13.

**Already planned, and given acceptance conditions by ADR 0041:**
- streaming (LO18);
- stop (LO17);
- the study context file (LO19);
- the Lead over time (LO11);
- commands and mentions (#11, #16).

**Never:** sharing turns, admin reads, temporary chats, a per-conversation model picker, deleting
turns, several threads per study in the MVP.
