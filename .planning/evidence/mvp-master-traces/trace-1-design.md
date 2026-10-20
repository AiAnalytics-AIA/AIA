# Trace 1: the DESIGN stages (Brief, Design, Questionnaire)

Read-only audit of `/home/user/AIA`, branch `chore/mvp-master-plan`, HEAD `f7e80bb9`.
**Every `file:line` below is @ f7e80bb9** (the HEAD I read). Statuses: EXISTS, PARTIAL, MISSING, CONTRADICTION.
A claim marked ◇ is a hypothesis: I did not open the code it rests on, or I inferred it.

Method: read CLAUDE.md, `mvp-development-plan.md`, `mvp-target-architecture.md`, `mvp-cohesion.md`,
`research-lead-workbench.md`, `mvp-acceptance.md`, ADR 0026 (decisions 2-5), then followed each capability
through web, API, application, domain, repository, worker and back. Two small read-only Python probes ran from
`/tmp` against `domain/design_items.py` (stdlib only, no bytecode written); their output is quoted where used.

Plan facts used throughout (verified against `plans.json` and the plan file):
- `research-lead-workbench` has 15 open chunks of 26 (`research-lead-workbench.md:3-29`). None of them is
  "shared edit vocabulary", "operations log", "presence", "change feed" or "per-change accept". Chunk 16 reads
  "Pointing at the artifact: the Vidí chip, the target button and @ over every artifact's elements" (line 20) and
  chunk 17 reads "Questionnaire artifact, its proposal shown in it (where chunk 7 lands)" (line 21): neither carries
  the F11 decisions that `mvp-cohesion.md:641-645` says they must.
- `mvp-development-plan.md:136` marks the same work "**New**" for S1 in W1 and says "New means the chunk is added
  to that plan before the wave starts" (line 119). No plan file has it yet.
- None of M1 `workspace_edit_ops`, M2 `study_presence`, M6 `proposal_change_decisions` exists in
  `tables.py` or `migrations/` (grep over `migrations` and `packages/aia_core/src`: no hit). Migration head is
  `57eaa96a5538` (chain `7b3c32892aa9` -> `c7e9a1b3d5f2` -> `57eaa96a5538`), 47 files, as the plan says.

---------------------------------------------------------------------------------------------------------

## 1. A person edits the working copy by hand (save with base revision, stale refusal, revisions, history)

**Verdict.** The single-author path is solid and tested. Everything that makes it multi-author, attributable,
undoable or visible as history is planned but unbuilt, and the plan files do not carry it.

| link | status | anchor or plan chunk |
|---|---|---|
| Stage editors change a client-side `ResearchProject` and autosave after 1.8 s | EXISTS | `apps/web/src/research/store.ts:14, 168-188`; 33 `store.update(` call sites in 9 files; editing logic is ~1,900 lines in `research/{questionnaire,plan,plan-edit,brief,persona,audience,trace}.ts` with 18.6.6 parity tests |
| Save names the revision it was edited from | EXISTS | `store.ts:206-211`; `apps/api/src/aia_api/routers/workspace.py:479-488, 2043-2085` (`PUT /studies/{id}/workspace/content`) |
| Server serialises saves under the Study row lock and refuses a stale base whole | EXISTS | `packages/aia_core/src/aia_core/infrastructure/study_workspace_repository.py:125-138, 234-273` (`stale_revision`, line 268-273); test `apps/api/tests/test_client_api.py:483` |
| Immutable revisions with dedupe, author and reason | EXISTS | `study_workspace_repository.py:212-218, 283`; `tables.py:167` (`ProjectRevisionRow`) |
| What a person sees after a refused save | PARTIAL | `store.ts:229-231, 175-181, 260-266, 323`: the copy is frozen ("conflict"), typed work stays on screen, the person is told to copy it and reload. No merge, no notice that another person saved before the person saves (no poll, no feed: grep for `setInterval` / ops / presence in `apps/web/src` finds only run and report polls) |
| History route | PARTIAL | `workspace.py:2088-2104` (`GET …/workspace/revisions`) lists revision, reason, author, hash. `apps/web/src/lib/api.ts:798-898` (`workspace` object) has no `revisions` call: the route has no consumer. V3 "Historie" tab is chunk 15, unticked (`research-lead-workbench.md:19`) |
| Read an older working revision's content over HTTP | MISSING | `study_workspace_repository.py:187` `at_revision` is called only by application code (`proposal_accept.py:86, 149`, `study_design_repository.py:170, 229`, `design_reuse.py:189`, executor `research_agents.py:93`); no route. Chunk 15's "revision stepper" needs one; no plan names it: NONE |
| Per-revision attribution: person vs Lead vs accepted proposal vs import | PARTIAL | only `created_by` plus a free `reason` string (`autosave`, `lead_edit_accepted`, `ai_proposal_accepted`, `design_research_accepted`, `questionnaire_import`, `brief_attachments`); no operation, so no "what changed" and no inverse |
| Undo of a person's own edit | MISSING | no route; the Lead's "Vrátit" is browser memory only (`Workbench.tsx:176-177, 356, 386-392`: `autoList(memory)` is display state, lost on reload). Planned: `inverse` column of `workspace_edit_ops` (`mvp-target-architecture.md:83`), M1, S1 W1, no plan chunk |
| Operations log, item-level merge on save | MISSING | `workspace_edit_ops` / `apply_edit_ops` absent from code; plan: `mvp-development-plan.md:136, 193` ("**New**", M1), `mvp-target-architecture.md:64-108`; no chunk in `research-lead-workbench.md` or any plan file |
| "One vocabulary written once": person's operations and the Lead's are the same | PARTIAL | the Lead's vocabulary is 8 ops (`domain/research_lead.py:157-310`); a person's editing is 1,900 lines of TypeScript with parity fixtures to 18.6.6's JavaScript. Moving it to a server `domain/edit_ops.py` means re-proving those parity cases in Python. No chunk sizes this; `mvp-development-plan.md:110` lists `domain/edit_ops.py` ◇ as a name to confirm |
| Whole-copy `PUT …/workspace/content` after `apply_edit_ops` exists | CONTRADICTION | `mvp-target-architecture.md:109-110` "that route stays for whole-copy writes (an import, a migration)" against `:98-100` "a lock on Set 1 and the declared Sociomap rating question refuses an operation unless it carries an unlock" and `:411` "the working copy is written only by `apply_edit_ops`". A whole-copy write bypasses the lock and leaves no operation. Until every one of the 33 call sites is converted, the PUT is the path every edit takes |
| What a whole-copy write puts in the ops log / change feed | MISSING | not specified: `source` check list is `ui, lead_turn, proposal_accept, undo` (`:79`), with no import, reuse, migration, Design Research accept, or "whole copy" value. A feed built from the ops would be silent about those revisions. Owner: NONE |
| Lock on Set 1 and the Sociomap rating question | MISSING | see capability 7 row "Sociomap declarations editor": nothing in `apps/web/src` sets `sociomap_rating` or `context_objects` (grep: zero hits), so the lock has nothing to lock in the product UI |

---------------------------------------------------------------------------------------------------------

## 2. The Research Lead proposes an edit and a person accepts it

**Verdict.** Two accept routes work end to end on the server (Lead edits, agent jobs) plus a third (Design
Research). The server never tells the Lead what was accepted, never gives it readiness, and the item-level
stale rule is defeated by any later Design Revision submit.

| link | status | anchor or plan chunk |
|---|---|---|
| Person message -> `research_lead` worker step -> closed `LeadOutput` | EXISTS | `application/research_lead.py:385` `post`; `domain/research_lead.py:412` `LeadOutput` (reply, view<=3, edits<=12, one request, follow, self_update) |
| Lead edit vocabulary | PARTIAL | `domain/research_lead.py:157-170` (8 text fields only: title, goal, decision_use, 4 `briefing.*`, `plan.problem_summary`), plan lists, question add/edit/remove, `set_n`. Cannot touch tracked sets, comparisons, sections, routing, scales, audience, dimensions, options of a battery. Target adds move/merge/section/set/route/scale/comparison ops: MISSING, no chunk |
| Changing the vocabulary changes the model's structured-output contract | MISSING | `EditOp` is a closed discriminated union (`research_lead.py:299-308`) bound into `lead_contract` and the pinned prompt (`LEAD_PROMPT_VERSION`, `:110`); extending it needs a prompt/harness version bump, a new `is_text_edit` ruling per op (`:314-346`) and a parity decision with `lib/lead.ts applyLeadEdit`. Not in any chunk: NONE |
| Lead edit accepted one by one through the gate | EXISTS | `routers/lead.py:402` `POST …/lead/turns/{turn_id}/edits`; `application/research_lead.py:504-618` (`indices`, ledger row per edit, one save at 594-601) |
| Lead edit stale rule | PARTIAL | `application/research_lead.py:561-562` refuses the whole accept unless `base_revision == current`; `:563-566` (auto only) also refuses when the turn's frozen revision is not current. No item-level check: an accepted edit is applied over whatever is now in the item |
| Lead edit accept writes the Design Revision | PARTIAL | it does not: `research_lead.py:594-601` saves the working copy only. Agent accept does (`proposal_accept.py:151-156`). So the head Design Revision lags the working copy until the next submit |
| Lead prepares a paid design job; person approves; started on a fresh Design Revision | EXISTS | `application/research_lead.py:678-759` (spend limit 720-734, `_submit_design` 737-741, `ResearchAgentJobs.start` 742, ledger 747-754) |
| Direct agent-job start has no spend-limit check | MISSING | `application/research.py:1311-1407` never reads `spend_confirm_usd`; `routers/research.py:2735-2754` is open to any `EDIT_STUDY`+`RUN_WORKFLOW`. Planned fix: `mvp-development-plan.md:127` (W0, S1) and `mvp-cohesion.md:223-225`; not a chunk in `research-lead-workbench.md` (its F1, lines 179-186, still says "observation, not yet a defect") |
| Worker records the items a proposal touches | EXISTS | `apps/executors/src/aia_executors/research_agents.py:77-97, 203, 342-347` (`touched_items`) |
| The touched items reach the browser | MISSING | grep for `touched_items` in `routers/research.py`, `lib/api.ts`, `research/*.ts`, `components/rehome/research/*.tsx`: none. The web draws its own diff by text (`research/proposal-diff.ts`). Needed by per-change accept (cap. 3); no plan names it |
| Agent-job accept in one transaction (stale rule, merge, working revision, Design Revision, ledger) | EXISTS | `application/research.py:1585-1647`; `application/proposal_accept.py:92-157`; `routers/research.py:2889-2918`; tests `apps/executors/tests/test_research_agent_executor.py:858, 947` |
| "A pending proposal goes stale only when an edit touches an item it changes" | CONTRADICTION | ADR 0026 decision 5 heading (`docs/architecture/adr/0026-…:201`) against `proposal_accept.py:117-118` and ADR line "the head Design Revision has moved (today's `submit_if_current` check, kept)": every submit (`research.py:1311` job start via `useResearchAgents.tsx:106, 164`, rebuild, run start `ExecutionSteps.tsx:645-657`, Deep Research start `DeepResearchPanel.tsx:88`, Lead approval `research_lead.py:737`) moves the head and makes every other pending proposal `design_moved`, whatever items it touches. Under the V3 model (Lead starts jobs often) one approval kills the other stage's pending proposal, which has to be rebuilt (a paid call) |
| Visiting the Run stage creates a Design Revision | PARTIAL | `ExecutionSteps.tsx:643-657` `submitWorkingDesign(…, "run")` on mount: a read-only visit moves the head (same effect as the row above) |
| Design Revision snapshot covers content and analysis | CONTRADICTION | ADR 0026 decision 5 says the server checks "the submitted content and analysis are that working revision's"; `study_design_repository.py:168-174` and `lib/api.ts:1203` submit and hash `content` only. Plan lists live in both documents (`research_lead.py:1233-1254` writes both), so a run executes the content copy only. Affects the wording of the target test "head's content equals the working copy's" |
| Target invariant "after any accept the head's content equals the working copy's" | CONTRADICTION | `mvp-target-architecture.md:180-183` against `application/research_lead.py:594-601` (Lead accept saves without submitting) and every autosave. True only for a proposal accept. Reword to "after a proposal accept" |
| Lead is told what the person did with its edits and proposals | MISSING | `_conversation` (`application/research_lead.py:895-912`) passes reply text and data class only; edit decisions are in the turn view (`:263-283`) but not in the frozen context. Agent-job proposal state is not in context either. M7 signals (W2, `mvp-target-architecture.md:186-203`) cover only undo/reject of Lead proposals, not accepts or agent-job outcomes |
| Lead's context holds readiness, question outlook, "what changed since I last answered", the stage contract | CONTRADICTION | ADR 0026 decision 2 (items 4 and 6, status Accepted) against `domain/research_lead.py:803-819` (layers: prompt, lead, knowledge, study, design, runs, view, conversation) and `application/research_lead.py:876-881` (design layer = revision numbers, content, analysis). `lead_commands.py` does not exist. Chunk 11 builds the command registry; no chunk builds the readiness or the diff layer: NONE |
| Agent proposal shown inline in the artifact | PARTIAL | reviewed in `ProposalReview.tsx` (stage top) via `useResearchAgents.tsx:89-150`; chunk 7 (inline in the V3 artifact, coverage gained/lost/kept) unticked (`research-lead-workbench.md:11`) |
| Model route for every design job and Lead turn | CONTRADICTION | `mvp-development-plan.md:77-79` says only a design job "whose study has approved knowledge (Class A by rule)" parks on the Class-C-only route. `domain/research_agents.py:675-686` classes the design itself Class B, a Lead message is Class B (`research_lead.py:20-24`) and `deploy/develop/README.md:400-405` says "each of those parks". So on develop every design worker and every Lead turn parks until the W0 operator step, not only the knowledge-bearing ones |
| Design size ceiling for the design workers and the Lead | PARTIAL ◇ | design jobs: hard `ValueError` over 64,000 bytes (`research_agents.py:32, 581-582`); Lead: 96 KB with only conversation droppable (`research_lead.py:782-826`); `design_research.py` guards an accept that would exceed it. A brief attachment contributes up to 6,000 characters (`domain/attachments.py:43, 149`), eight per pick (`research/brief.ts:59`), no total cap. Reproduction (not run): attach a dozen long PDFs, then start any design job |

---------------------------------------------------------------------------------------------------------

## 3. Per-change accept of part of a proposal (planned, new)

**Verdict.** The primitive is there (a `touched=` subset parameter, per-edit accept for Lead edits, per-item
accept for Design Research). The planned agent-job version is a third mechanism beside those two, with no plan
chunk, no web control, and an identity problem for what a "change" is.

| link | status | anchor or plan chunk |
|---|---|---|
| Server merge takes a subset of items | EXISTS | `proposal_accept.py:101, 133, 141` (`touched` parameter); `domain/design_items.py:397` `merge_items`. Only caller that passes it passes the worker's full recorded set (`research.py:1630-1632`) |
| Lead edits are already decided one by one | EXISTS | `application/research_lead.py:509, 538-618`; web `Workbench.tsx` `decide(…, keys)` |
| Design Research already accepts chosen items | EXISTS | `application/design_research.py:95-157` (`item_ids`, ledger `record_design_research_acceptance(selection_id, item_ids)`). A second per-item pattern, own ledger subject, different owner (S2 owns `deep_research`; S1 owns `proposal_accept`) |
| Agent-job accept with `change_ids`, `proposal_change_decisions`, `ACCEPTED_IN_PART` | MISSING | no hit for `change_ids` / `proposal_change_decisions` / `ACCEPTED_IN_PART` in code (only the word inside `test_research_lead.py:170` `text_edit_ops`); `domain/research_agents.py:871-905` `ProposalState` has four values. Plan: `mvp-development-plan.md:136, 198` (M6), `mvp-target-architecture.md:171-184`; no plan-file chunk |
| Web control to pick changes | CONTRADICTION | `research-lane-redesign.md:8` (done) "accepted per item or all", against its own progress note `:87-89` ("the decision stays one for the whole proposal -- accept per item would change the gate-1 contract") and `ProposalReview.tsx:1-9, 147-152` (one `onDecision(true)`). The done plan overstates; the code is whole-proposal |
| Identity of a "change" | PARTIAL | the server unit is `ItemKey`; the web draws changes by text lists (`ProposalReview.tsx:77-121`). Probe on `design_items.py`: adding a question to a section yields `['content:question:qa', 'content:section:s1']` (section's own value embeds its question-key list, `design_items.py:221-231`); an RQ reword yields two keys (`content:research_question:jak často?` removed, `…pijete?` added) and the same again under `analysis:` because plan lists are dual-homed. One visible change is 2-4 keys; `change_id` is undefined in `mvp-target-architecture.md:171-184` |
| Coupled changes can be split | MISSING | `domain/research_lead.py:315-325` documents the coupling (questionnaire items and comparisons name an RQ by text, so renaming one unlinks what measures it). Per-change accept can take the RQ reword and refuse the questionnaire links, producing a dangling link that only readiness WARNs on (`research_trace.py:353`). No grouping or dependency rule in any doc: NONE |
| Ledger shape for partial accept | PARTIAL | one `ai_proposal` row per job (`research.py:1636-1646`, `workflow_repository.py:2414`); M3 adds seven subject types and none for a change (`mvp-development-plan.md:192`), consistent with "one ledger row", but `proposal_change_decisions.decision_id` then repeats one id for every change; fine, but `proposal_state` after a partial accept must also read the new table |
| Target route name | CONTRADICTION | `mvp-target-architecture.md:268` `POST agent-jobs/{id}/accept`; real route `…/research/agent-jobs/{run_id}/accept` (`routers/research.py:2889`) and Design Research and Lead accepts live on other routes the table does not name |
| Stale handling after a partial accept | PARTIAL | remaining changes become `REJECTED`/`DROPPED_STALE` by default (`mvp-target-architecture.md:175-176`, "open to change"); consistent with head-moves-on-accept (`proposal_accept.py:117-118`), so "accept the rest later" is impossible by construction. The owner's open sub-question (`mvp-cohesion.md:363-364`) is answered by the code, not by a decision |

---------------------------------------------------------------------------------------------------------

## 4. Two researchers on one study (presence, change feed, shared working copy, edit-operations log)

**Verdict.** The shared working copy and per-researcher Lead exist. Presence, feed, merge and the Lead's
awareness of the other person are all unbuilt; two statements of F12 contradict the privacy of Lead turns.

| link | status | anchor or plan chunk |
|---|---|---|
| One working copy per study | EXISTS | `study_workspace_repository.py:112-118` (`_row` by study) |
| One Lead conversation per researcher | EXISTS | `study_lead_repository.py:1-6`; `application/research_lead.py:373-383` (`_completed`: the caller's own turn) |
| Item-level merge instead of whole refusal | MISSING | M1 (above). Today a second autosave is refused whole (`study_workspace_repository.py:268-273`) and the frozen browser copy needs a manual reload (`store.ts:229-231`) |
| Presence (`study_presence`, 5 s heartbeat, 20 s expiry) | MISSING | `mvp-target-architecture.md:110-116`, `mvp-development-plan.md:136, 194` (M2); no code, no plan chunk |
| Change feed `GET workspace/ops?since=` and the browser poll | MISSING | `mvp-target-architecture.md:115, 263`; nothing polls the working copy today (grep, cap. 1) |
| The Lead's context includes other people's changes since its last turn, with author | MISSING | `mvp-cohesion.md:400-401` (F12.4) and ADR 0026 decision 2 item 4; absent from `mvp-target-architecture.md` §3.2 (which defines only the route), from `mvp-development-plan.md` W1, from every chunk, and from `freeze_context` (`domain/research_lead.py:803-819`). Owner: NONE |
| Proposals belong to the study, visible to all members as change blocks "labelled with who asked" | CONTRADICTION | `mvp-cohesion.md:402-405` (F12.5) against `study_lead_repository.py:1-6` ("nobody reads another's turns"), `mvp-cohesion.md:476-479` (turns stay private) and `application/research_lead.py:373-383`. A Lead's pending edits and request cards live in its turn and are therefore private; only agent-job proposals are study-level (`application/research.py:1444-1454` `jobs`). Say which of the two wins for Lead edits |
| Who may accept a proposal another person's Lead prepared | PARTIAL | agent-job and Design Research accepts check no author (`research.py:1603-1605`, `design_research.py:110-112`): works. Lead turn edits and request: own turns only (`research_lead.py:373-383`): cannot be accepted by anyone else, despite `mvp-cohesion.md:419-422` "any member who holds the accept permission" |
| Accept needs the browser's revision to equal the current one | PARTIAL | `proposal_accept.py:125-131` (`stale_revision`): with a second person autosaving, an accept by the first is refused whole although no item overlaps. The web turns only `stale_proposal` into a message (`useResearchAgents.tsx:123-129` `staleDetails`); `stale_revision` falls through as a thrown error |
| One person's submit kills the other's pending proposals | PARTIAL | head moves on any submit (cap. 2 row): researcher B approving any job or opening Kontrola makes researcher A's pending questionnaire proposal `design_moved` |
| Two people adding questions to one section merge cleanly (exit I-1: "merges or conflicts on one item only") | PARTIAL | probe: two different added questions in section `s1` give intersecting item sets `['content:section:s1']` (`design_items.py:221-231`). The conflict key of the planned log, `(item_key, field)` (`mvp-target-architecture.md:87`), is undefined for `question_add` (item = new question or the section?). Section reorder is no item at all (`design_items.py:36, 312` "order is no item"; probe: swapping two sections gives `[]`), so `section_move` has no item key and can never conflict |
| Brief attachments added by two people at once | PARTIAL | `briefing.attachments` is one item (`design_items.py:259-261`: each `briefing.<sub>`, so `briefing.attachments` is the whole list), so two uploads conflict on the field |
| Spend is the study's; approval cards go to the preparing person | EXISTS | `application/research_lead.py:678-759` (ledger names the approving person) |

---------------------------------------------------------------------------------------------------------

## 5. Pointing at an element with @ or the target button (stable ids, revision)

**Verdict.** Pointing works for whole questions, sections, brief fields and plan blocks. It cannot name an RQ,
objective, hypothesis, option, tracked set or comparison, carries no revision, and takes one reference.

| link | status | anchor or plan chunk |
|---|---|---|
| Click-to-pick maps an element to a target id | EXISTS | `apps/web/src/lib/lead.ts:341-365` `targetOfElement` (`qedit_`, `qblock_`, `brief-`, `plan-*`); the picking in `Workbench.tsx:185-207` is as cited by the plan (`research-lead-workbench.md:101`) ◇ not re-opened |
| Server accepts a focus on four kinds only | EXISTS | `domain/research_lead.py:176` `FOCUS_ID` (`question|section|brief|plan` + `[A-Za-z0-9_.-]{1,80}`); `application/research_lead.py:776-788` |
| Lead's own `focus` view op | PARTIAL | `domain/research_lead.py:197-202` any `kind:id`; the web resolves only the four kinds (`lib/lead.ts:301-313`); the Lead prompt's example `plan:research_questions` (`research_lead.py:707`) is not in `focusSelector`'s map and falls back to `plan-understanding` |
| Brief field ids line up with the Lead's edit fields | PARTIAL | edit fields are `briefing.situation` etc. (`research_lead.py:157-170`); DOM ids are `brief-goal`, `brief-type`, `brief-context`, `brief-files`, and `brief-<field>` for context inputs (`BriefStep.tsx:118-124, 138, 304-318`); `brief:decision_use` and `brief:title` have no element ◇ (not every context field name checked) |
| Stable id for questions | EXISTS ◇ | `mvp-cohesion.md:350-352` cites `research/questionnaire.ts:144, 186-196` (not re-opened); section fallback is positional: `design_items.py:190` (`f"#{i}"`), `QuestionnaireStep.tsx:656` (`qblock_${sec.id || si}`) |
| Stable id for objectives, research questions, hypotheses, options, battery objects | MISSING | keyed by normalised text (`design_items.py:120-172`); tracked sets by `id` only when present, else title (`:166-172`, docstring: "a plan's set carries no id today"); `FOCUS_ID` cannot even encode a text key. F11.3's "a stable id, the number a label" therefore holds for questions and sections only. Plan: none (chunk 16/18 say "any element") |
| Pointer carries the revision it was made on | PARTIAL | `application/research_lead.py:782-785` stores `{id, label}`; the turn row carries `workspace_revision` and `design_revision_id` (`study_lead_repository.py:_to_domain`), so a turn is bound but a later render of the chip is not. Chunk 16 does not mention it (`research-lead-workbench.md:20`) |
| Lead's prose cites "Q9" as a chip that re-renders ("Q9, now Q7") | MISSING | `mvp-cohesion.md:366-368` flags it as a consequence "the decision does not yet cover"; no chunk, no output-contract field for a typed reference (`LeadOutput`, `research_lead.py:412-423`): NONE |
| Several references in one message | MISSING | `focus` is one object (`application/research_lead.py:776-785`); chunk 16 silent |
| `@` list over the current and other stages | MISSING | chunk 16 (`research-lead-workbench.md:20`), unticked |
| `data-aia` registry / "AI interaction contract" per artifact | MISSING | ADR 0026 decision 4 (Accepted); `data-aia` appears only on Lead-pane elements (`Workbench.tsx:509, 542`, `LeadPane.tsx:392, 438, 448`), stage screens use `id=`; chunk 14 (view vocabulary, unticked) is the nearest owner but does not name the contract |

---------------------------------------------------------------------------------------------------------

## 6. Brief attachments and the questionnaire file import

**Verdict.** Both are built, one-way, and client-orchestrated. Neither is wired to the planned edit
vocabulary, client sources, history or the Lead's context bound.

| link | status | anchor or plan chunk |
|---|---|---|
| Upload files into the Brief (8 per pick), then record them by autosave | EXISTS | `BriefStep.tsx:366-405`; `routers/workspace.py:2124-2163`; `study_workspace_repository.py:489-540` (needs saved content, `not_saved`) |
| Text excerpt (6,000 chars) rides the design | EXISTS | `domain/attachments.py:43, 149`; `material_rules.py:10, 75`; `research_agents.py:672-674` (Class B by rule) |
| Download, hash-verified, octet-stream | EXISTS | `routers/workspace.py:2166-2202`; `study_workspace_repository.py:541-555`; test `test_client_api.py:639, 667` |
| Bytes survive a failed record or a removal | PARTIAL | the artifact is stored before the brief records it (`attach` 489-540); a stale save loses the record and leaves an orphan; removing the record from the Brief deletes nothing: I found no code that deletes an attachment's bytes (only `storage.py:336, 364`). The delete path required before production (`mvp-target-architecture.md:433`) must reach these |
| Same bytes classified differently by entry point | PARTIAL | as a Brief attachment: Class B (design); as a client source: Class A, or C when marked "Interní dokument" (CLAUDE.md map, `material_rules.py`). A person can bypass a source's class by attaching the file to the Brief instead. Intentional per the owner's 2026-10-19 rule, but no doc states the consequence |
| Brief materials pick a client dataset and open a data contract (F19) | MISSING | no source picker in the research stages (grep `SourcePicker|source_id` in `components/rehome/research`: none); plan: `client-data-in-analysis` chunk 2 (planned, 0 of 8 in `plans.json`) |
| Contract between Brief attachments and client sources | MISSING | a dataset reference must be added to `brief_signature` in Python (`design_items.py:523-548`) and TypeScript (`research/model.ts` `briefFingerprint`) in lockstep, kept out of `design_material` (`research_agents.py:535-542`) and out of `briefing.attachments` item semantics. Owner: NONE |
| Questionnaire template download | EXISTS | `routers/workspace.py:2246-2266` |
| Questionnaire import read server-side | EXISTS | `routers/workspace.py:2205-2243` (EDIT_STUDY, 18.6.6's row rules) |
| Import applied | PARTIAL | `QuestionnaireStep.tsx:355-358` then `research/questionnaire.ts:365-378` replaces **all** sections with the file's; the template has no column for research-question links or Sociomap declarations (`domain/questionnaire_import.py` has no such field), so every link on every replaced question is dropped; no confirmation; revision `questionnaire_import` is the only trace and the history route has no UI |
| Import as an operation | CONTRADICTION | target keeps whole-copy writes for imports (`mvp-target-architecture.md:109-110`) while declaring `apply_edit_ops` the only writer (`:411`) and the lock enforced there (`:98-100`): an import will bypass the lock |

---------------------------------------------------------------------------------------------------------

## 7. Readiness and the research-question trace (`research_trace`, `question_outlook`)

**Verdict.** Complete on the server for a submitted Design Revision and shown on the Run stage. The design
stages and the Lead use a different, client-side reading; the Sociomap declarations the V3 designs show have
no editor.

| link | status | anchor or plan chunk |
|---|---|---|
| Compile + readiness + support forecast + outlook + trace + answerability | EXISTS | `application/research.py:1062-1131` (`readiness`, `outlook`); `domain/question_outlook.py:137`; `domain/research_trace.py:228, 353`; `routers/research.py:1084` `GET …/research/readiness` |
| Answerability gate at start | EXISTS | `application/research.py:187-196` `ResearchQuestionsUnanswerable`; web `AnswerabilityGate.tsx` |
| Readiness available for the working copy | MISSING | the route takes `design_revision_id` only (`research.py:1076-1097`, `lib/api.ts:1213-1214`); the only web caller submits a Design Revision first (`ExecutionSteps.tsx:643-667`). No working-revision mode; no plan chunk (chunk 15's header "readiness" can only use `lane.ts`) |
| Design stages' readiness and coverage | PARTIAL | client-side only: `research/lane.ts:100` `blockers`, `research/trace.ts:27-130` (`researchQuestionsOf`, `danglingLinks`, `proposedTrace`). The Python rule is separate (`research_trace.py`, `research_agents.py` `research_questions_of`); both have their own tests, no shared fixture file found (`trace.test.ts`, `test_research_trace.py`) ◇ |
| The Lead sees readiness, outlook, trace | CONTRADICTION | ADR 0026 decision 2 item 4 against `freeze_context` (cap. 2). `application/research.py:1076` `outlook` is the function the ADR names; nothing calls it for a Lead turn |
| Coverage gained/lost/kept shown in a proposal (chunk 7) | PARTIAL | client `proposedTrace` (`ProposalReview.tsx:59, 123-137`); chunk 7 unticked |
| Coverage under a partial accept | MISSING | trace of "accepted subset" has no definition (cap. 3) |
| Sociomap declarations editor (`sociomap_rating`, `context_objects`) | CONTRADICTION | `research-lead-workbench.md:161` lists "Sociomap declarations" under "Backed by in AIA" for the Design artifact and the Questionnaire artifact shows "locked Sociomap inputs" (line 159), yet `docs/architecture/research-journey.md:417` and `sociomap-formula-corrections.md:1189` say "no screen declares" them and `apps/web/src` has zero hits. Producer of the declaration: nobody (only `domain/research_design.py:484, 562-606` and tests read it). The F13.4 hard lock cannot be built on a field no person can set |
| "Serves no objective" reason and per-item time in the Questionnaire artifact | MISSING | `research-lead-workbench.md:159` admits both ("Missing"); D13 says render "V AIA zatím není"; no backend chunk |

---------------------------------------------------------------------------------------------------------

## 8. Downstream when the design changes after a run exists (`pipeline.py` impact, invalidation, the stage track)

**Verdict.** AC-07 is written as if an impact preview drives reuse for research studies. It does not: the
preview is a pure 18.6.6 function reachable only through the generic project API, which cannot see a study's
owned projects. What really happens is immutable runs plus fingerprint reuse, and nothing on screen says a
run's design is no longer the current one.

| link | status | anchor or plan chunk |
|---|---|---|
| `impact_preview` as a pure function with 18.6.6 parity | EXISTS | `domain/pipeline.py:462-513`; `packages/aia_core/tests/test_pipeline_parity.py:121-237` |
| Computed on every working-copy save | PARTIAL | `domain/project.py:365` runs inside `ProjectRepository` save; `StudyWorkspaceRepository.save` (`study_workspace_repository.py:296-337`) returns only revision and dedupe and never reads `outcome.impact` |
| Exposed to a research study | MISSING | `routers/projects.py:308-340` is a generic `/studies/{id}/projects/{pid}/impact`; owned working and design projects are invisible to it (CLAUDE.md "owner=" rule); `apps/web` has no impact call (grep). AC-07 in `mvp-acceptance.md:82` and `parity-matrix.json:4030` names the mechanism; `mvp-acceptance-harness.md:69` schedules it in the "built" first batch. No research-study test exists: impact tests are `test_projects_api.py`, `test_project_repository.py`, `test_project_revisions.py`, `test_pipeline_parity.py` only |
| What actually reuses stage artifacts | EXISTS | content-fingerprint reuse: `infrastructure/artifact_repository.py:228` `find_reusable`; `executors/analysis.py:674, 730`; tests `apps/executors/tests/test_analysis_executor.py:1098, 1128, 1145`. Not driven by `impact_preview` |
| Run bound to the Design Revision it executed | EXISTS | `application/research.py:479` `start` records the revision; Design Revisions are immutable (`study_design_repository.py:146-216`) |
| Screen says "this run's design is older than the current design" | MISSING | grep in `apps/web/src` for run-vs-head comparison: none; `lib/run-state.ts` has no staleness state; revision only in details (`ResultsWorkspace.tsx:75`). The Lead's `runs` layer carries each run's `design_revision_id` and the design layer the head's (`application/research_lead.py:851-889`) but no instruction or field compares them. Plan: NONE |
| "Stages current with revision n", "changed since", "re-check" (F13.1) | MISSING | `research/lane.ts:22-36` has five tones and compares nothing to a revision; no table or state for "re-check confirmed unchanged" in `mvp-target-architecture.md` §3 or the M-lane; nearest chunk 15 ("revision stepper", `research-lead-workbench.md:19`). Owner: NONE |
| "Accepting always creates a whole revision" (F13.1) | CONTRADICTION | `mvp-cohesion.md:429-431` against the code: a person's hand edits create working revisions only; a Design Revision exists only after job start, run start, Deep Research start or a proposal accept (cap. 2 row). A hand edit has no "accept" act |
| One stage vocabulary | MISSING | five lists: `pipeline.RESEARCH_STAGES` 13 ids (`pipeline.py:101-115`), web `StepKey` 10 (`research/steps.ts:16-17`), workbench 11 (`lib/workbench-stages.ts:9-31`), Lead `Stage` 11 (`research_lead.py:143-155`, `design` vs `plan`, `dimensions` vs `persona`) and `DESIGN_SOURCE_STAGES` (`domain/design.py:45-47`). `IMPACT_ROOTS` has no Sociomap stage and maps all of `research_plan` to `RESEARCH_DESIGN` (`pipeline.py:137-165`), i.e. rewording a hypothesis would "invalidate" everything after Design. Also three item-to-stage maps exist: `IMPACT_ROOTS`, `editStage` (`lib/lead.ts:257-263`) and `design_items` kinds. Owner: NONE |
| Pending proposals and Design Research proposals after a design change | EXISTS | `proposal_accept.py:117-140`; `design_research.py:113-118` (`design_moved`, `lineage_changed`) |
| Old run's reports and artifacts stay valid | EXISTS | runs and their artifacts are immutable and found through the run (CLAUDE.md map, `application/research.py:1242-1260`) |

---------------------------------------------------------------------------------------------------------

## Counts of link rows (from the tables above)

99 link rows in the eight tables (counted by script over the status column): **EXISTS 30, PARTIAL 27, MISSING 29, CONTRADICTION 13.**

| capability | EXISTS | PARTIAL | MISSING | CONTRADICTION |
|---|---|---|---|---|
| 1 hand edit | 4 | 4 | 5 | 1 |
| 2 Lead proposes, person accepts | 5 | 6 | 4 | 5 |
| 3 per-change accept | 3 | 3 | 2 | 2 |
| 4 two researchers | 3 | 5 | 4 | 1 |
| 5 pointing | 3 | 3 | 5 | 0 |
| 6 attachments and import | 5 | 3 | 2 | 1 |
| 7 readiness and trace | 2 | 2 | 3 | 2 |
| 8 downstream of a design change | 5 | 1 | 4 | 1 |

---------------------------------------------------------------------------------------------------------

## (A) GAPS: a link MISSING with no plan owning it

1. **Edit-vocabulary, ops log, presence, change feed and per-change accept have no chunk.** Only `mvp-development-plan.md:136, 193-198` names them ("New"); `research-lead-workbench.md` front-matter has none, and chunks 16 and 17 lack the F11 content (`mvp-cohesion.md:641-645`).
2. **The Lead is never told what a person did with its edits, nor what other people changed, nor readiness/outlook/trace.** ADR 0026 decision 2 (Accepted) lists them; `domain/research_lead.py:803-819` has none; only M7 (W2) touches the reject/undo half.
3. **Stable identity for objectives, research questions, hypotheses, options, battery objects.** Keyed by normalised text (`design_items.py:120-172`); F11.3 and chunk 16 need ids they cannot have; a reword is remove+add and breaks trace links.
4. **No editor for `sociomap_rating` / `context_objects`**, so the F13.4 lock and the V3 "locked Sociomap inputs" have no subject (`research-journey.md:417`, zero web hits).
5. **No working-revision readiness.** `GET research/readiness` needs a submitted Design Revision (`research.py:1076-1097`); the design stages, the V3 header and the Lead have no server reading of the working copy.
6. **No research-study surface for impact or "stage current with revision".** `impact_preview` has no consumer for a study; the run-vs-head comparison and the F13.1 states are unowned; AC-07 as worded cannot be tested.
7. **`touched_items` never reaches the browser** (`research_agents.py:203, 342` writes it; no API/TS reads it), so a web change block cannot name the server item it controls.
8. **Whole-copy writes in the ops log** (PUT content, import, reuse, migration, Design Research accept): not specified; the feed and the lock would skip them.
9. **Brief to client-source contract** (`brief_signature`, `design_items`, `design_material`, delete path for attachment bytes) is unwritten; `client-data-in-analysis` is 0 of 8.
10. **Undo/restore of a person's edit** and a route to read an old working revision: MISSING, no chunk (chunk 15 assumes both).
11. **Dependency between change blocks** (RQ reword vs the questionnaire links that name it) for per-change accept: no rule anywhere.
12. **Lead edit vocabulary extension** needs a prompt/harness version and an `is_text_edit` ruling per op; not sized.

## (B) CONTRADICTIONS

1. **D18 vs target architecture.** `research-lead-workbench.md:141-144` ("structural edits may auto-apply per stage") against `mvp-target-architecture.md:99-100` and `mvp-cohesion.md:359-360` ("text-only operations are the only ones an automatic accept may take"); no per-stage column in M1-M10 (`mvp-development-plan.md:190-201`).
2. **Target-arch internal.** Lock enforced in `apply_edit_ops` (`:98-100`) and "written only by `apply_edit_ops`" (`:411`) against "whole-copy writes stay" (`:109-110`).
3. **Head invariant.** `mvp-target-architecture.md:180-183` (head equals working copy after any accept) against `application/research_lead.py:594-601` (Lead accept saves only).
4. **ADR 0026 decision 5 heading vs its own text and code.** "Goes stale when an edit touches an item" against "head moved ... kept" (`proposal_accept.py:117-118`).
5. **ADR 0026 decision 5 "content and analysis" hashed** vs `study_design_repository.py:168-174` (content only).
6. **ADR 0026 decision 2 (Accepted) vs `freeze_context`** (no readiness, no diff, no stage contract).
7. **`research-lane-redesign.md:8` (done) "accepted per item or all"** vs `:87-89` and `ProposalReview.tsx:1-9`.
8. **F12.5 vs ADR 0026 decision 8 / F14.** Proposals "visible to everyone" against "nobody reads another's turns" (`study_lead_repository.py:1-6`); Lead edits live in turns.
9. **`research-lead-workbench.md:159-161` "Backed by ... Sociomap declarations"** vs `research-journey.md:417` and zero web hits.
10. **`mvp-development-plan.md:77-79` vs `research_agents.py:675-686` / `deploy/develop/README.md:400-405`:** every design job and Lead turn parks on a Class-C-only route, not only knowledge-bearing ones.
11. **F13.1 "accepting always creates a whole revision"** vs code (hand edits create no Design Revision).
12. **AC-07 wording / harness "built first batch"** vs no research-study impact surface (`mvp-acceptance.md:82`, `mvp-acceptance-harness.md:69`).
13. **`mvp-target-architecture.md:268` route name** vs `routers/research.py:2889`.

## (C) INTERFACES crossing plans or sessions with no owner (proposed owner)

1. **Per-item acceptance across three accept routes** (agent job, Design Research `item_ids`, Lead `indices`): one `change` identity and one ledger shape. Proposed owner: S1, with S2 reviewing `design_research.py`.
2. **Stage and item vocabulary** (`pipeline.RESEARCH_STAGES`, `StepKey`, workbench stages, Lead `Stage`, `DESIGN_SOURCE_STAGES`, `IMPACT_ROOTS`, `editStage`, `design_items` kinds): one table, one owner. Proposed owner: S1 (`domain/edit_ops.py` neighbour), consumed by S3's acceptance AC-07.
3. **Brief materials to client sources and the data contract** (`briefing.attachments`, `brief_signature` Python and TypeScript, `design_material`). Proposed owner: S3 writes the contract, S1 adopts it in the Brief artifact.
4. **Readiness on a working revision** shared by the V3 header, the Lead's context and the design stages. Proposed owner: S1 for the route and the Lead layer; S2 keeps `research_trace`/`question_outlook`.
5. **Sociomap declarations** (editor, lock, unlock ledger `sociomap_unlock`) between S1's Questionnaire/Design artifacts and S2's `sociomap-formula-corrections` I2. Proposed owner: S1 builds the editor against S2's declared fields.
6. **Duplicated rules with no shared fixture:** TS `applyLeadEdit` vs Python `apply_edit`; TS `trace.ts` vs Python `research_trace.py`. `design_items` has a shared fixture file (`tests/fixtures/design_items/cases.json`), these do not. Proposed owner: S1.
7. **Ops log versus every other writer of the working copy** (import, reuse `submit_as_working_copy`, Design Research accept, migration). Proposed owner: S1 with S3 (migration lane).
8. **Attachment bytes lifecycle** (orphans, removal, the pre-production delete path). Proposed owner: S3.
9. **Design size ceiling** (64 KB agents, 96 KB Lead, results layer D19 on top, attachments uncapped). Proposed owner: S1.

## What I could not verify

- I did not run the web, the API or any test suite. All behaviour claims are from code reading plus the two stdlib probes on `design_items.py`.
- `research/questionnaire.ts` stable-id claim (ids not renumbered) is the cohesion doc's, not re-opened.
- `Workbench.tsx` picking code (lines 185-207) and the exact set of `brief-*` ids for every context field were not fully read.
- The 64 KB overflow reproduction with many attachments is a hypothesis (◇).
- I did not read the prototypes (`prototypes/research-lead-v3`) beyond the plan's table, so what V3 draws for Brief and Design beyond what `research-lead-workbench.md:157-169` says is not checked.
