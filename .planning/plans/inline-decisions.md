---
status: done
chunks:
  - "[x] 1. Ověřeno, přidat zdroj: a person adds a Deep Research source to the client's knowledge with one inline click"
  - "[x] 2. Auto-accept the Lead's text edits: an opt-in per researcher, off by default, recorded in the ledger as auto"
  - "[x] 3. Tick the plan"
---
# Inline decisions

Two usability decisions of the product owner, 2026-10-19. Both keep ADR 0026's rule: the model
proposes, a person decides. Neither lets a model write anything by itself.

## 1. "Ověřeno, přidat zdroj"

A source Deep Research captured is shown to the researcher with its URL, title and quote: on the
Design Research panel, on the Interpretation Research findings and under each research question's
design evidence. The researcher opens it, reads it, and when it holds, clicks **Ověřeno, přidat
zdroj**. That click is the person's write: a Client Knowledge item of kind `SOURCE`, knowledge at
once (CLAUDE.md, Client Knowledge; ADR 0019 decision 3), through `ClientKnowledgeRepository.add`.

- **Route.** `POST /api/v1/studies/{study_id}/deep-research/runs/{run_id}/sources/{source_ref}/knowledge`
  with `{evidence_id}`. The run is found through the Study, its sealed bundle read and verified,
  and the snapshot (`source_ref`) and the accepted finding citing it (`evidence_id`) must both be
  in it. Nothing the browser sends becomes the item's URL, title or quote: they are the bundle's.
- **What the item carries.** `content`: the URL, the final URL, the title, the quoted passage, the
  snapshot id, the snapshot's text SHA-256, when it was retrieved. `provenance`: the Deep Research
  run, the finding, the snapshot, the person, `verified_by_person: true`.
- **Once per (client, URL).** The client's row is locked, an active `SOURCE` item or a pending
  proposal with the same URL answers `exists` (200) with its id, and nothing is written. The button
  then reads "Už je ve znalostech" and links to the item.
- **Once per address.** A source's address is its URL or its final URL (where a redirect led), on
  either side: the same page reached directly or through another short link is the same source.
- **Permission.** The Study's `EDIT_STUDY` to read the run, the client's propose and approve
  knowledge permissions to write (`add`). Where self-approval is off for the client or for the
  Study (the click is made on the Study), `add` files a proposal instead, and the answer says
  `proposed`.
- **No model adds a source.** Nothing in the worker writes knowledge; the route is a person's.

## 2. Auto-accept the Lead's text edits

ADR 0026: the Lead proposes, a person decides. An explicit standing choice by the researcher is
that decision, so the gate stays the default and the choice is theirs alone.

- `researcher_leads.auto_accept_text_edits` (default false); `PUT /api/v1/lead/preferences`
  sets the caller's own row, audited; `GET /api/v1/lead` carries it.
- **Text edits** change wording and nothing else: `set_text` of `title` or
  `plan.problem_summary`, `list_replace` of `plan.hypotheses`, and
  `question_edit` with `text` and no `options` (`domain/research_lead.py` `TEXT_ONLY_FIELDS`,
  `TEXT_ONLY_LISTS`, `is_text_edit`; the web's `isTextEdit` mirrors them). Not the brief's fields
  (an edit of one clears the analysis) and not `plan.research_questions` (items and comparisons
  name a research question by its text), never structure or the sample.
- Applying stays on the server gate. When a turn completes with the preference on, the web pane
  calls `POST …/lead/turns/{turn_id}/edits` with `decision: "accept"`, the text-edit indices, the
  working revision and `auto: true`. The server refuses `auto` unless the caller's preference is
  on (`auto_accept_off`), refuses it whole when the turn's frozen working revision is not the
  current one (409 `stale_turn`: someone saved while the Lead worked), refuses any non-text edit
  in it by index (`not_a_text_edit`), and writes `"auto": true` into each ledger row's comment.
  Structural edits wait as change blocks.
- The web asks only over a copy with nothing waiting to be saved, and reads the accepted revision
  into the same store in place (`ResearchStore.reload(…, { since })`): a change typed while the
  gate answered stays on screen, the copy in conflict, nothing saved over it, and the person told.
- **Vrátit.** The browser keeps, for the edits it auto-accepted in this study (the session's page
  memory, so a stage change keeps them), the wording each replaced and the revision its accept
  wrote; Vrátit is offered once the copy holds that revision, and writes that wording back as the person's own edit of the working copy (the
  normal revision-checked save), and refuses when the text has changed since. The ledger's
  accept stays: decisions are made once, and the revert is a later edit by the person.

## Where it landed

- Chunk 1 @ ccbed0fd: `application/verified_sources.py` (`add_verified_source`),
  `ClientKnowledgeRepository.add_source_once`, the route in `routers/deep_research.py`, the web's
  `VerifiedSourceButton` on the three places a captured source is shown, and `?item=` on Znalosti.
  Tests: `apps/api/tests/test_verified_sources_api.py`,
  `test_client_knowledge.py::test_a_checked_source_is_added_once_per_client_and_url`,
  `VerifiedSourceButton.test.tsx`.
- Chunk 2: `TEXT_EDIT_OPS` / `is_text_edit` in `domain/research_lead.py`, the column (migration
  `57eaa96a5538`, revises `7b3c32892aa9`), `ResearcherLeadRepository.set_preferences`,
  `ResearchLead.decide_edits(auto=)`, `record_lead_edit_decision(auto=)`, `PUT /lead/preferences`,
  the workbench's automatic accept and Vrátit, the toggle on Můj Vedoucí. Tests:
  `test_research_lead.py::test_a_text_edit_changes_wording_only`,
  `test_research_lead_api.py::test_an_automatic_accept_takes_text_edits_only_and_says_so_in_the_ledger`,
  `Workbench.test.tsx`, `lead.test.ts`, `LeadProfile.test.tsx`, and `lead_journey.mjs` (run on a
  local workbench, 12 checks, nothing paid).

## Checks run (2026-10-19)

After the review fixes (@ 7c01686c): strict mypy over the four source trees (423 files, clean);
ruff check and format on every Python file touched; the Lead, knowledge and verified-source tests
on SQLite (235 passed, 1 skipped) and on PostgreSQL 16 (236 passed); `tsc --noEmit`; the web
suite (1,837 of 1,838, the one failure above). `lead_journey.mjs` was not rerun.

Before them:

- Migration on a private PostgreSQL 16: upgrade to head, `alembic check` clean, downgrade one and
  upgrade again, `alembic check` clean.
- The knowledge, Lead and verified-source tests on that PostgreSQL as well as on SQLite.

## Findings (fixed)

From an independent review of the branch @ 5a217aab, and Codex on #489:

1. An automatic accept reloaded through the session, whose disposed store saved a change typed
   during the call against the old base (409, unheard): the change was lost
   (`Workbench.tsx:317 @ 5a217aab`). Fixed @ eced14ab; `Workbench.test.tsx` "keeps what the
   person typed while the gate answered…", "accepts nothing over a copy with changes still
   waiting…", `store.test.ts` "reload".
2. Under `auto` only the browser's base revision was checked, so a person's save made while the
   turn ran was overwritten without a click (`application/research_lead.py:545 @ 5a217aab`).
   Fixed @ c6c67549 (`stale_turn`);
   `test_research_lead_api.py::test_an_automatic_accept_leaves_a_save_made_while_the_lead_worked_and_says_why`,
   `Workbench.test.tsx` "leaves a turn the person saved over for their click…".
3. `is_text_edit` admitted brief fields (their edit clears the analysis) and research questions
   (a rename unlinks the items and comparisons that name them)
   (`domain/research_lead.py:304 @ 5a217aab`). Fixed @ 9854c02e, web and server;
   `test_research_lead.py::test_a_text_edit_keeps_the_analysis_it_did_not_change`,
   `test_an_edit_that_adds_removes_reoptions_or_resizes_is_no_text_edit`, `lead.test.ts`.
4. "Přijato automaticky" lived in the stage screen's state and was lost on a stage change,
   including the Lead's own `open_stage` (`Workbench.tsx:137 @ 5a217aab`). Fixed @ 2efffe74;
   `Workbench.test.tsx` "keeps the bar across a stage change…".
5. Vrátit was offered before the reload had read the accepted wording, so a quick click was
   refused as "text changed" (Codex on #489, `Workbench.tsx:317 @ 5a217aab`). Fixed @ eced14ab
   (offered once the copy holds the accept's revision); `Workbench.test.tsx` "offers Vrátit only
   once the copy holds what the accept wrote…".
6. The source-add ignored a Study's own `allow_self_approval=false`
   (`routers/deep_research.py:830 @ 5a217aab`). Fixed @ a9ba317d;
   `test_verified_sources_api.py::test_a_study_with_self_approval_off_files_the_source_as_a_proposal`.
7. A source was the same source only by its exact URL, not its final URL
   (`client_knowledge_repository.py:1120 @ 5a217aab`). Fixed @ d2b56f03;
   `test_client_knowledge.py::test_a_checked_source_is_the_same_source_by_its_final_url_either_way`.
8. The design panel's source button did not name `canReview` itself
   (`DeepResearchPanel.tsx:152 @ 5a217aab`); unobservable, as the bundle is read only under it.
   Stated @ 7c01686c.

- **Objectives are not wording only** (second independent review of #489). Where a plan states
  no research questions, its objectives are read as them (`analysis/native.py`
  `research_questions_of`, web `trace.ts` `researchQuestionsOf`), linked by text like research
  questions; a `list_replace` of `plan.objectives` left items linking the old wording. Removed
  from `TEXT_ONLY_LISTS` on both sides; tests: the objective rename among `STRUCTURAL_EDITS`
  (`test_research_lead.py`) and `structure` (`lead.test.ts`).
- **A message waits for the working copy's save** (same review). `LeadPane` now saves the
  waiting change before a message (`beforeMessage`, `store.flush` from `Workbench`), so the Lead
  reads it and its turn is frozen at the revision the person sees; before, a message within
  1.8 s of typing made every automatic accept on that turn `stale_turn`. Test:
  `LeadPane.test.tsx` "saves the working copy's waiting change before a message goes".
- **A failed reload keeps the waiting save** (same review). `ResearchStore.reload` re-arms the
  debounced save when its read fails. Test: `store.test.ts` "keeps a waiting change's save when
  the read fails".
- **A question's wording is not without effect** (same review; recorded, not changed). A
  question's new text still decides whether code answers it as a fact and which persona topics
  it draws, for a clicked accept as for an automatic one; readiness and the question outlook
  show it before a run. `is_text_edit`'s docstring now says so.

## Findings

- `tools/ui_workbench/lead_journey.mjs` is not rerunnable on one workbench: its note's first 40
  characters carry no timestamp, so a second run finds the first run's kept note
  (`lead_journey.mjs:121 @ 2e5028cc`, unchanged from develop). Run it on `workbench.py up --fresh`.
- `MethodologyVersions.test.tsx` "guided methodology editing" times out at 5 s on a loaded
  machine, on `origin/develop` @ 6c5cd620 as on this branch (hypothesis: load, not a defect).
  In the full web suite on 2026-10-19 (two runs @ 7c01686c, 1,838 tests) it failed once, and
  `QuestionnaireStep.test.tsx` "offers the three paths…" failed once (its heading not found within
  `findByRole`'s 1 s); both pass alone. QuestionnaireStep renders the classic layout in jsdom (no
  `matchMedia`), never the workbench this branch changed (hypothesis: load, not a defect).
- **Hypothesis** (not reproduced): a clicked accept has finding 1's race. `decide` flushes, asks
  the gate, then `reload()` -- `session.retry`, which disposes the store
  (`Workbench.tsx:429 @ 7c01686c`, `ResearchScreen.tsx:93 @ 7c01686c`); a change typed while the
  gate answers would be saved by `dispose` against the old base, refused 409 with no listener,
  and lost. Consequence: a researcher typing during a click on Přijmout loses what they typed.
  Smallest fix: read the copy in place as the automatic accept now does,
  `store.reload(undefined, { since })` with the copy as it was before the call. Test: a
  `ResearchScreen` test that types while a deferred `/edits` answer is held, then expects the
  text on screen and the save state `conflict`.

## Doc follow-up

Written in the PR description.
