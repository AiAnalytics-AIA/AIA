---
status: in-progress
chunks:
  - "[x] WCE0. The contract: the closed operation set, ids, validation, the lock rule and the text-only marker, with one shared fixture (tests/fixtures/edit_ops/cases.json) read by the Python and the TypeScript tests"
  - "[x] WCE1. Stable item identity: ids for objectives, research questions, hypotheses, options, battery objects and sections; existing content gets ids on load; `FOCUS_ID` and `design_items` keys use them"
  - "[ ] WCE2. `workspace_edit_ops` (M1) and `apply_edit_ops`: the one writer of the working copy; every other writer becomes a recorded whole-copy operation"
  - "[ ] WCE3a. The web store on the server vocabulary, Brief and Design stages"
  - "[ ] WCE3b. The web store on the server vocabulary, Questionnaire (manual operations, move, remove, reference by stable id)"
  - "[ ] WCE3c. The web store on the server vocabulary, Audience, Dimensions and Sample"
  - "[ ] WCE4. Presence (M2) and the change feed: `study_presence`, `GET …/workspace/ops?since=` (ADR 0029), a poll, two sessions"
  - "[ ] WCE5. Field-level merge, per (item_key, field) (D-06), and a stale rule that a later Design Revision does not defeat"
  - "[ ] WCE6. Per-change accept (M6): `proposal_change_decisions`, one change identity across the three accept routes, a dependency rule for coupled changes, `touched_items` returned to the web; any member with the accept permission may accept a proposal another member's Lead prepared (Q16), the chat text staying private"
  - "[x] WCE7a. Readiness on a working revision: `GET …/research/readiness/working?working_revision=n`, the readiness a submit of that revision reads, nothing written"
  - "[x] WCE7b. Vzorek reads it on the working revision it shows, no submit on a visit (Návrh's coverage in artifact-design, Spuštění in artifact-fieldwork#FLD6)"
  - "[x] WCE7c. Impact per stage: `GET …/research/impact`, every pipeline stage CURRENT, CHANGED or RECHECK going from a Design Revision to the working copy"
  - "[x] WCE7d1. The stage track reads it: a stage the working copy reopened says so, measured against the newest run's design, so a run whose design is older than the copy says so on every stage it reopened"
  - "[ ] WCE7d2. The working copy accepted as a revision, explicitly, from the workbench"
  - "[ ] WCE8. Sociomap declarations: an editor for `sociomap_rating` and `context_objects`, the hard lock and `sociomap_unlock`"
  - "[ ] WCE8b. The questionnaire proposal keeps protected inputs and item identity (W2, with WCE8, before research-lead-workbench 7 and 17): declared batteries, tracked sets and rating questions copied from the baseline under their ids, never from model output; proposed items keep a baseline id"
  - "[ ] WCE9. Undo and restore of a person's edit, and a route that reads an old working revision"
  - "[ ] WCE10. The Lead's edit vocabulary widened (Audience, Dimensions, Sample), with a prompt and harness version and an `is_text_edit` ruling per operation"
  - "[ ] WCE11. Auto-apply per stage (MVP-14, D18): the researcher's `auto_accept_text_edits` gains a per-stage structural choice, off by default"
  - "[ ] WCE12. Journey: two researchers, one study, recorded doubles (the I-1 exit)"
  - "[x] WCE13. Routing in the questionnaire (W1, with research-lead-workbench 17): route_set sets, edits and removes a display condition, validated by the domain (the condition names an earlier question and an option it has), and readiness accepts a valid conditional question (behind AIA_ROUTING_ENABLED, off until RQC11 routes fieldwork; #763, #766, #777, #788)"
  - "[ ] WCE14. A stimulus item: content shown to respondents before a question (respondents.context), in the edit vocabulary and the design (D-45)"
---
# Working-copy edit operations, merge and the Sociomap lock

The work that lets two researchers, each with their own Lead, edit one working copy through one server-validated vocabulary, with per-change accept, a merge that is item by item, presence and a hard lock. Written 2026-10-19 from the cohesion traces (`.planning/evidence/mvp-master-traces/trace-1-design.md`); anchors are there.

**Owner: S1.** Takes the gap rows G14, G18, G19, G21, G22, G24 and interfaces I2, I8, I9, I11 of `mvp-master-plan.md` §6.1 and serves AC-02, AC-03, AC-07 and gate I-1.
Every chunk below is **open**; a chunk is built from this file, not from the master plan.

## Decisions this plan carries (settled by the owner; not re-asked)

- One shared edit vocabulary: a person and the Lead use the same server-validated operations (cohesion F11).
- Per-change accept and reject; the unit of acceptance is the revision; identity is a stable id and the number is only a label (F11).
- The manual AI buttons are removed; every AI action goes through the Lead (D15, MVP-8).
- An append-only log of every operation, kept with its study (Q27); presence by polling plus a heartbeat in PostgreSQL, no push service (target architecture §3.2).
- A hard lock on Sociomap inputs with a recorded unlock the Lead can never call (Q15).
- Structural edits may auto-apply per stage, off by default, each one still a working revision and a ledger row marked auto (MVP-14, D18). Text-only is the **default and the only automatic accept until a researcher turns a stage on**; the "text only" sentences in cohesion F11 and the architecture mean that default.

## Chunks

**WCE0. The contract: the closed operation set, ids, validation, the lock rule and the text-only marker, with one shared fixture (tests/fixtures/edit_ops/cases.json) read by the Python and the TypeScript tests**  
Writes `domain/edit_ops.py` and the fixture before any writer changes. Replaces the duplicated rules (`applyLeadEdit` against `apply_edit`; `trace.ts` against `research_trace.py`) with one fixture. Test: both languages pass the same cases. Interfaces I2.

**WCE1. Stable item identity: ids for objectives, research questions, hypotheses, options, battery objects and sections; existing content gets ids on load; `FOCUS_ID` and `design_items` keys use them**  
Today those items are keyed by normalised text (`design_items.py:120-172`), so a reword is a remove and an add, links break and `FOCUS_ID` cannot name them. Test: a reword keeps its research-question links; two people adding different questions to one section do not touch the same key; a section move is an item.

**WCE2. `workspace_edit_ops` (M1) and `apply_edit_ops`: the one writer of the working copy; every other writer becomes a recorded whole-copy operation**  
The PUT, questionnaire import, reuse, the 18.6.6 migration, Design Research accept and the web autosave are the six other writers; none may change a locked item or skip the log. Test: a whole-copy write leaves an op and cannot change a locked item. Interfaces I8.

WCE2 split (scoped 2026-10-22, approved by the PM): **2a** the log as values
(`domain/edit_log.py`); **2b** M1, the table and `WorkspaceEditRepository`; **2c**
`apply_edit_ops` for whole-copy writes, the PUT, `submit_as_working_copy` and reuse through it, the
lock enforced; **2d** the Lead's `decide_edits` as vocabulary operations (closes F-WCE1-1); **2e**
the agent-job and Design Research accepts; **2f** the 18.6.6 migration, then `save` and
`import_migrated` reachable from `apply_edit_ops` alone (layer_check). The eight callers, at
`3a544cb3`: `routers/workspace.py:2164` (PUT: autosave, every stage, questionnaire import),
`application/research_lead.py:822` (Lead edits), `study_design_repository.py:226`
(`submit_as_working_copy`, the template behind OI-173), `application/design_reuse.py:186`,
`proposal_accept.py:185` from `research.py:1981` and `design_research.py:135`,
`workspace_migration.py:151, :238`.

- **WCE2a (2026-10-22).** `domain/edit_log.py`: a row per `(item, field)` a write touched
  (`design_fields.changed_fields`), a whole-copy write's `op` `{"op": "whole_copy", "reason"}`;
  a write no field counts (a re-spaced list entry, an id list) logs one `content:copy:` row, so no
  write skips the log; `WriteBy` refuses a write without its author unless it is a migrated
  revision, and only a person's (18.6.6 had no Lead); which code may name the `migration` source
  is held by `layer_check` ("only the 18.6.6 migration logs a write as migrated":
  `domain/edit_log.py` and `application/workspace_migration.py` alone), so the exemption is not a
  label any writer can pick (review of #762); a key or field past its column is a prefix and a
  digest, deterministic. Measured: a
  40-question import into the template is 44 rows in 5.6 ms (median of 20), one wording edit on it
  1 row in 7.3 ms. Tests: `test_edit_log.py`.
- **WCE2b (2026-10-22).** M1: `workspace_edit_ops` (`migrations/versions/20261022_90dc672445b1_the_working_copy_operation_log.py`), insert-once
  (a `before_update` listener; the downgrade refuses while a row is stored), the three scope
  columns cascading with the study, CHECKs on the actor and source sets and on an author for
  everything but a migrated revision (`workspace_edit_op_author_unless_migrated`), indexes for the
  feed `(study_id, result_revision)` and for conflicts `(study_id, item_key, field)`. No foreign
  key on the author: the log keeps who wrote it. `infrastructure/workspace_edit_repository.py` is
  its only reader and writer (`append` under `EDIT_STUDY`, `rows(after_revision=)`), held by two
  `layer_check` rules. `alembic check` against PostgreSQL 16: no difference from the model.
  Tests: `test_workspace_edit_repository.py`.
- **WCE2c (2026-10-22).** The lock and the log sit where every whole-copy write already passes, under
  the study lock: `StudyWorkspaceRepository.save` refuses, after the stale check, a write that
  changes a Sociomap input the current copy has locked (`sociomap_input_locked`, 409 on the PUT),
  and logs a write that made a revision, one row per changed field, in its transaction, made by
  `by` (`WriteBy`). The PUT passes the person (`ui`), `submit_as_working_copy` the person it acts
  for (`authored`), reuse the person and the revision reused (`reuse`). The Lead's and the proposals'
  accepts pass no `by` yet (WCE2d, WCE2e); WCE2f makes it required, so no write skips the log.
  This is a refinement of the scoped split: `apply_edit_ops` stays the application entry for a
  vocabulary batch (WCE2d), and `save` stays the one persistence point the batch and every
  whole-copy writer reach, rather than a second writer beside it. Measured on PostgreSQL 16: a
  40-question import over the template, 44 rows, 28.5 ms logged against 22.0 ms unlogged (median of
  3). Evidence for the lock: on the workbench database (7 working copies) and a freshly seeded
  develop world (0), no working copy declares a Sociomap input; no fixture or seed writes one, and
  the web never writes `sociomap_rating` or `context_objects` (`research/readers.ts` reads them).
  Tests: `test_workspace_writes_logged.py`, `test_design_reuse.py::test_a_reuse_is_logged_…`,
  `test_client_api.py::test_a_put_is_logged_as_the_persons_and_cannot_change_a_declared_…`.
  One existing test met the lock: `test_sociomap_acceptance.py::test_each_changed_input_is_a_new_…
  [rating_input]` changed a declared rating question's scale in the same study's copy. That write is
  now refused (`sociomap_input_locked`), which the case asserts; the engine's answer to a changed
  rating input (a new specification, a new run, the map on the new scale, the first run untouched)
  is read in a sibling study, where nothing is locked, until WCE8's recorded unlock exists.
  The web's store meets the refusal (stand-in review of #784): on `sociomap_input_locked` it puts the
  locked items back as AIA last held them (`research/sociomap-lock.ts` `restoreLocked`, the web's
  reading of `locked_items`: each tracked set and rating question by id) and keeps every other change
  to save on its own debounce ("Zamčený vstup Sociomapy vrácen … · ostatní změny se uloží"; a
  section removed whole with a rating question goes back as saved); an item it cannot find again by id
  leaves the copy blocked until a reload, so a refused change is never re-sent. The PUT says what
  happened (`_workspace_conflict`). Pre-merge check for deployed develop (read-only; checked against
  `tables.py` and run on a migrated PostgreSQL 16 schema): `select w.study_id from study_workspaces w
  join projects p on p.project_id = w.project_id join project_revisions r on r.project_id =
  p.project_id and r.revision = p.current_revision where r.content::text like '%"sociomap_rating"%'
  or r.content::text like '%"context_objects"%';` Result: **0 studies affected on develop,
  2026-10-22** (run read-only by the product owner, 16:35 UTC), so the lock changed no deployed study.
- **WCE2d (2026-10-22).** The Lead's accepted edits are the vocabulary's operations:
  `decide_edits` hands the edits it would apply to `application/working_copy.apply_edit_ops`,
  which applies them in order to the copy as loaded, refuses alone an edit that writes a locked
  Sociomap input (`lock_refusal`, `sociomap_input_locked`) or that the copy cannot take, and saves
  once through `save`, which logs each edit under its own `op` (the edit without its `why`) for the
  fields it touched (`edit_ops.touches`, keyed by the ids it was applied with) and the rest of the
  write (the stages' `ui_state`, the analysis a plan or brief edit wrote, links followed) as a
  `whole_copy` change (`edit_log.write_rows`). Made by `WriteBy(LEAD, researcher, lead_turn,
  turn_id)`: the Lead wrote the change; the ledger row records the person's accept. A copy that
  keeps the web's ids (`item_ids.stores_item_ids`) is settled (`settle_item_ids`), so a reworded
  research question keeps its links: closes F-WCE1-1. A copy without ids is given none, so with
  `AIA_WEB_STABLE_ITEM_IDS` off nothing writes an id. Tests: `test_lead_edits_logged.py` (three
  failed before the change: the log, the lock refused alone, the links), `test_edit_log.py::
  test_a_write_of_operations_…`, `test_item_ids.py::test_a_copy_keeps_ids_only_once_…`. One edge
  left to WCE8: with ids kept and an input declared, a reword whose links follow onto a locked rating
  question touches it, and `save` refuses the whole accept (409 `sociomap_input_locked`) rather than
  half of it.
- **WCE2e (2026-10-22).** The proposal accepts are logged: `accept_into_working_copy` takes `by`
  (required) and its merged write is logged as a whole-copy write made by the person who accepts,
  citing the run (`proposal_accept` for an agent job, `ResearchAgentJobs.accept`;
  `design_research_accept` for a Design Research proposal, `DesignResearchProposals.accept`). The
  lock already held for them through `save` (WCE2c). Tests: the accept tests in
  `test_research_agent_executor.py` and `test_design_research_proposals.py` assert the rows (both
  failed before the change). With it, two tests WCE2d's review asked for (`test_lead_edits_logged.py`):
  an automatic accept takes the unlocked text edit and refuses the locked one alone; a reword whose
  links follow onto a locked question refuses the whole accept and writes nothing (the WCE8 edge).
  Held at the 2026-10-22 feature freeze; released by the product owner overnight ("Drive all to
  merge").

**WCE3a. The web store on the server vocabulary, Brief and Design stages**  
33 `store.update` sites in 9 files and about 1,900 lines of TypeScript with 18.6.6 parity tests are moved stage by stage; the parity tests stay green at every step.

**WCE3b. The web store on the server vocabulary, Questionnaire (manual operations, move, remove, reference by stable id)**  
Includes the @ pointer carrying id and revision (workbench 16) and the questionnaire import confirmation (an import replaces all sections and drops every research-question link today: it names what it would orphan).

**WCE3c. The web store on the server vocabulary, Audience, Dimensions and Sample**  


**WCE4. Presence (M2) and the change feed: `study_presence`, `GET …/workspace/ops?since=` (ADR 0029), a poll, two sessions**  
Test: two sessions edit one study; each sees the other within a poll; a presence row expires without a heartbeat. Gate I-1. The feed also carries each pending proposal (change identity, item, proposer, status) with no chat text, so another member can accept it (`WCE6`, gap G42).

**WCE5. Field-level merge, per (item_key, field) (D-06), and a stale rule that a later Design Revision does not defeat**  
`proposal_accept.py:117-118` refuses on "head moved" before comparing items, and any job start, rebuild, Lead approval or a visit to the Run stage submits a Design Revision, killing every other pending proposal. The check becomes: stale only when a field the proposal touches, `(item_key, field)`, changed since its baseline (D-06). Tests: a revision submitted elsewhere does not stale a proposal on other items; a change to another field of the same item does not stale it either (Q4's wording and its options merge); the same field changed does.

**WCE6. Per-change accept (M6): `proposal_change_decisions`, one change identity across the three accept routes, a dependency rule for coupled changes, `touched_items` returned to the web**  
The agent-job accept, Design Research `item_ids` and the Lead `indices` become one mechanism. A research-question reword and the questionnaire links that name it are one dependent group. Every accept writes the working revision **and** submits the Design Revision in one transaction, so the head equals the working copy after any accept (`proposal_accept.py:142-156`); the Lead edit accept (`research_lead.py:592-601`) saves only today and is fixed here. **Shared proposals (Q16, gap G42):** `decide_edits` takes the caller's own completed turn (`research_lead.py:515-518`), so another member cannot accept an edit block its author's Lead prepared. A proposed change becomes an artifact-level item addressed by its change identity (item, operation, base revision, proposer, status) and carried to the others by `WCE4`'s feed **without the turn's chat text**; accepting needs `EDIT_STUDY` and `APPROVE_GATE` and the item-level stale rule, not ownership of the turn. Tests: member B accepts a change member A's Lead prepared without ever reading A's turn; B cannot read A's turn text through the feed; a second accept of the same change keeps the first decision; the ledger names both people. Interfaces I9.

**WCE7. Readiness and impact on a working revision: readiness without a submitted Design Revision, "current / changed / re-check" per stage, and accepting a working copy as a revision**  
Hand edits create no Design Revision today and `impact_preview` has no route for a study, so AC-07 cannot be tested as written. Test: edit the questionnaire after a run; the stages after it read "reopened" and the run says its design is older than the head.

Split 2026-10-21 (owner: the Vzorek session, assigned by the PM) into three PRs:
- **WCE7a, delivered.** `ResearchRuns.outlook_working(working_revision)` (`application/research.py`)
  reads `StudyWorkspaceRepository.at_revision` and assesses it through the same `_assess` as
  `outlook`, so a working revision and the Design Revision submitted from it (equal by hash) read
  the same readiness. Its answerability names no Design Revision, so its digest never stands for
  a start's acknowledgement. Route `GET /studies/{id}/research/readiness/working`
  (`WorkingReadinessResponse`: the readiness fields and `working_revision`); a revision the Study
  never saved is 404 `working_revision_not_found`. Test:
  `test_readiness_reads_a_working_revision_without_submitting_a_design`.
- **WCE7b, delivered.** Vzorek (`useSampleReadiness.ts`) reads `research.workingReadiness` on the
  store's working revision: an editor's waiting change is saved first (a save, never a Design
  Revision), a refused save is never read, and a new working revision reads it again with the
  previous answer kept on screen. Test: `SampleView.test.tsx` "loadSampleReadiness"; journey:
  `workbench_journey.mjs` asserts no `POST …/design/revisions` during the Vzorek block.
  Návrh's coverage card (`DesignCoverage.tsx`) reads the latest Design Revision and submits
  nothing; moving it to the working revision is `artifact-design`'s. Spuštění reads it while open
  and submits only at start, with that revision's readiness checked again: the Sběr dat session's,
  in `artifact-fieldwork#FLD6`.
- **WCE7c, delivered.** `domain.pipeline.stage_impacts(before, after)`: a stage whose own input
  fingerprint differs is CHANGED; the invalidated range starts at the earlier of `impact_preview`'s
  root and the first CHANGED stage, so a field `IMPACT_ROOTS` does not map (title,
  aggregation_policy) still reopens what follows (review on #638); in the range and unchanged is
  RECHECK; the rest CURRENT. `ResearchRuns.impact(working_revision, design_revision_id=None)` (the
  newest Design Revision when none is named) and `GET /studies/{id}/research/impact`. Tests:
  `test_pipeline_parity.py::test_a_questionnaire_edit_changes_its_stage_and_reopens_every_stage_after_it`
  (AC-07 in the domain) and `test_research_api.py::test_impact_reads_each_stage_of_a_design_against_the_working_copy`.
- **WCE7d.** The workbench reads it: the stage track's "reopened", the run's "design older than
  the head" and the explicit accept of a working copy as a revision. The stage track and lane are
  the integration coordinator's; this chunk is a request to them, with the route and the pipeline
  → workbench stage map (BRIEF brief, RESEARCH_DESIGN design, QUESTIONNAIRE questionnaire, AUDIENCE
  audience, DIMENSIONS dimensions, SAMPLE_PLAN sample, FIELDWORK fieldwork, AGGREGATION results and
  sociomap, ANALYSIS analysis, REPORT report).
- **WCE7d1, delivered (`feature/stage-track-impact`).** Built on Vzorek's #638 (`GET
  …/research/impact`) and #673 (`lib/working-impact.ts` `stageImpacts`, `research.workingImpact`).
  - The workbench reads the impact each time the copy's saved revision moves
    (`components/workbench/useWorkingImpact.ts`). The last answer stays while the next is read, so
    the marks do not flicker on every save.
  - It reads against the newest run's Design Revision; before any run, against the newest Design
    Revision (`impactBase`). A run whose design is older than the copy therefore shows on every stage
    the copy reopened, the result stages included.
  - The stage navigator marks a CHANGED stage with a filled dot and a RECHECK stage with a ring
    (`.nav__impact`). Each mark has words in its title and for a screen reader (`impactWords`), for
    example "změněno od běhu (revize 2)".
  - It shows nothing for a 404 (no Design Revision), a failure, an answer about another revision than
    the base asked for, or a stage not fully answered (`impactMarks`).
  - Tests: `working-impact.test.ts` "impactBase", "impactWords", "impactMarks";
    `Workbench.layout.test.tsx` "the stage track reads the working copy's impact".
- **WCE7d2.** Accepting the working copy as a revision from the workbench is still to do.

**WCE8. Sociomap declarations: an editor for `sociomap_rating` and `context_objects`, the hard lock and `sociomap_unlock`**  
Nobody can set the declarations (zero web hits), so the lock has no subject. The unlock is a ledger row (`sociomap_unlock`, M3), warns, and cannot be called by the Lead. Test: the whole-copy route cannot change a locked item. Interfaces I11.

**WCE9. Undo and restore of a person's edit, and a route that reads an old working revision**  


**WCE10. The Lead's edit vocabulary widened (Audience, Dimensions, Sample), with a prompt and harness version and an `is_text_edit` ruling per operation**  
Its operations today are `set_text`, `list_*`, `question_*` and `set_n`; `propose_audience` returns prose and `suggest_dimensions` an empty list. The valid n has one authority, the domain readiness limits (`run-qc-and-checkpoint#RQC9`).

**WCE11. Auto-apply per stage (MVP-14, D18): the researcher's `auto_accept_text_edits` gains a per-stage structural choice, off by default**  
Each applied edit is a working revision and a ledger row marked auto, with the undo of WCE9. Test: with a stage on, a structural edit applies when its turn finishes and can be undone; with it off, nothing structural applies without a click.

**WCE12. Journey: two researchers, one study, recorded doubles (the I-1 exit)**  
The second edit merges or conflicts on one item only; a locked item refuses; presence and the feed show. Member B accepts a change member A's Lead prepared without reading A's turn. Adds its steps to `workbench_journey.mjs` and the acceptance harness.

## Open: owner clarifications

- None for the owner. A research-question reword with a dependent questionnaire change is one group, accepted or rejected together, and a split that would leave the copy invalid is refused by the server's validation (`WCE6`); "content from revision n" is computed from where an item last changed, never stored (`WCE7`).


## Execution predecessors (2026-10-20)

WCE0 is the W0 contract for text and structural operations; its text-only marker limits the
default automatic acceptance, not the available manual edit vocabulary. S2 supplies the declared
Sociomap fields before W1 so WCE2 can enforce protected writes from its first implementation.
WCE1-WCE7, WCE10 and WCE12 are W1; WCE8-WCE9 and WCE11 are W2. WCE10 consumes RQC9's
single n authority. The W1 locked-write negative test uses the existing lock contract; WCE8 adds
the complete declaration/unlock editor. WCE11 cannot turn on before WCE9's recorded undo exists.

## Assumption item kind (2026-10-20, MVPQ-02)

Tracked assumptions are a design-item kind with a stable id, extending `WCE0`'s vocabulary and `WCE1`'s identity; `assumptions-and-open-answer-coding#AOC1` owns it. Their status changes are proposals a person accepts through `WCE6`; text edits of the statement are text edits, a status change is structural.

## Cross-check additions (2026-10-20)

From the independent cross-check of the master plan against the code (`mvp-master-plan.md` §6.1, G47-G57). Anchors are `@ 085abe0`.

**WCE8b. The questionnaire proposal keeps protected inputs and item identity (G49, X3).** `proposal_result` discards every non-library `object_battery` and `questions` section and gives every proposed section and question a fresh `ai_section_N` / `ai_q_N_M` id (`domain/research_agents.py:748-787`), and the closed output models cannot carry `context_objects` or `sociomap_rating` (`:155-159`). Once WCE8 makes the declarations settable and WCE2 locks them, a build or optimise accept on a map study is either refused by the lock or drops them, and per-change accept sees every item removed and re-added. This chunk copies a battery with `context_objects`, a tracked set and a `sociomap_rating` question from the baseline byte for byte under their ids (the context marks them fixed); `QuestionnaireProposal` sections and questions gain an optional baseline id that `proposal_result` keeps; `ai_*` ids only for new items; an omitted baseline item is a remove. Harness and `prompt_version_for` bump for build and optimise; a shared fixture case. WCE6 and `research-lead-workbench` 17 depend on it. Tests: an optimise accept over a battery with `context_objects` keeps both declarations and does not trip the lock; rewording one of five questions yields one changed item that can be accepted alone.

**WCE13. Routing in the questionnaire (G53, X8; the owner, 2026-10-20: build routing end to end).** Today the code cannot run a condition: readiness FAILs any conditional question, the outlook marks it UNANSWERABLE and fieldwork asks every respondent every question. This chunk makes `route_set` set, edit and remove a display condition through the shared vocabulary, validated by the domain (the condition names an earlier question and one of its options; a cycle or a forward reference is refused by name), and readiness accepts a valid conditional question instead of failing it. Fieldwork is `run-qc-and-checkpoint#RQC11`, the filtered base `evidence-integrity#10`. Test: a condition on Q7 for those who answered "never" to Q2 is stored, passes readiness, and a condition naming a later question is refused.

*Owner and order (the PM, 2026-10-22):* the Dotazník session, in four PRs: (a) the condition model
and its checks in compile, (b) `route_set` in `edit_ops` with the web mirror (`lib/lead.ts`
`applyLeadEdit`, held to `tests/fixtures/edit_ops/cases.json`), (c) the condition edited at the
question on Dotazník, (d) readiness and the outlook accept a valid condition behind
`AIA_ROUTING_ENABLED` (off; off on develop until RQC11 routes in fieldwork). With the switch off a
conditional question fails readiness exactly as today.

- *(a) Progress (feature/wce13-condition-model):* a question's `filtr` is
  `{"question_id": <stored id>, "options": [...]}`, compiled into `SpecQuestion.condition`
  (`SpecCondition`: the compiled id, the answers), absent from the fingerprint when there is none.
  `read_condition` also reads the two expressions the 18.6.6 interface wrote that are exactly a
  choice (`Q1 == 'Nikdy'`, `Q1 in [...]`); anything else stays as written and is refused by
  name: `condition_unstructured` (also anything past 2,000 characters or the parser's depth,
  and literals joined by juxtaposition), `condition_unknown_question`,
  `condition_forward_reference` (a later question or itself; with only earlier references a cycle
  cannot form), `condition_ambiguous_question` (two questions share the id, never bound to the
  first), `condition_not_choice`, `condition_unknown_option`. An 18.6.6 expression names a
  question as the unit resolved it: exactly, else case-insensitively by stored, then compiled id.
  A condition on an earlier question compile refused adds nothing to that question's problem.
  A refused condition does not stop compile (the PM, 2026-10-22: Kontrola keeps every other
  check): the question carries `condition_problem` (its code and message, out of the fingerprint
  when none), and readiness fails it by name as `condition:<question id>`. `has_filter` is held
  equal to a declared condition, read or refused. A valid condition still fails
  `conditional_questions`. Test: `test_research_conditions.py`.
- *(b) Progress (feature/wce13-route-set):* `route_set` is applied (`edit_ops.RouteSet`: a question's
  `condition` set, changed, or `null` removed), a person's alone: `WorkingOp` is every applied
  payload, `EditOp` stays the Lead's eight (`in_lead_output` false). It is held to the compiler's
  own rule before it is written (`research_design.condition_refusal`, the same `_condition`), and
  refused with its words (`condition_*`, now in `REFUSALS`); it writes the question's `filtr`
  (the catalogue's field), so the lock (`sociomap_input_locked`) and `touches` follow from it.
  The web's mirror: `research/questionnaire.ts` `conditionRefusal`, `lib/lead.ts` `applyEdit` (the
  Lead's `applyLeadEdit` beside it, `WorkingEdit`), held to the server by the shared case file's
  route_set cases. Tests: `test_edit_ops.py`, `test_research_conditions.py`,
  `edit-ops.cases.test.ts`.
- *(c) Progress (feature/wce13-condition-editor):* the condition is edited at its question on
  Dotazník (`components/rehome/research/QuestionCondition.tsx`), read by the question's place
  (`research/questionnaire.ts` `conditionOf`). "Podmínka zobrazení" opens a form offering only what
  a condition may stand on: earlier choice questions with answers, each the only question under its
  id and numbered as Dotazník numbers them; nothing when the question's own id is shared, as
  `route_set` names it by id. Their answers are chips; "Uložit podmínku" writes through `applyEdit`'s
  `route_set`, and a refusal (the copy moved under the form) is said in the form, which stays open.
  A condition in the design's form reads as a sentence (who is asked, after which answers) with
  why the run still refuses it; one the rule refuses says why in the server's words
  (`EDIT_REFUSAL_WORDS`) and can be set again; an 18.6.6 expression is shown as stored. "Odebrat
  podmínku" removes it by the question's place. An 18.6.6 expression in the two forms the compiler
  reads (`Q1 == 'x'`, `Q1 in [...]`) is judged as compile judges it (`readExpression`,
  `expressionState`), held to the compiler by `tests/fixtures/conditions/expressions.json`; where
  the web cannot know the server's answer (another form, a name only a compiled id matches) it is
  shown as written, with no claim either way. Setting or editing one is behind the switch (d)
  reads, `AIA_ROUTING_ENABLED`, through /config's `routing` (off: a stored condition is shown and
  can be removed). Tests: `QuestionnaireStep.test.tsx`,
  `questionnaire-conditions.test.ts`; `questionnaire_journey.mjs` sets, reads back and removes one
  at 1440, 1100, 768 and 390 px, the sentence at a reading width (390 px squeezed it to 50 px).
- *(d) Progress (feature/wce13-routing-switch):* `AIA_ROUTING_ENABLED` (the API's
  `Settings.routing_enabled`, off by default and off on develop until RQC11 routes fieldwork) is
  `ResearchRuns.routing_enabled`. Readiness (`assess_readiness`/`prepare`, `routing=`) passes a
  valid condition under it (`conditional_questions` PASS, naming the questions) and fails it
  exactly as before without it; a condition compile refused fails either way (`condition:<id>`).
  The outlook (`question_outlook`, `routing=`) asks a routed question of part of the sample the
  forecast does not model, so support the whole sample reaches is `support_unknown` there, never
  good. A new run of a design with a valid condition pins it (`metadata.routing`, the preflight
  and fieldwork steps' `routing`); its preflight reads the pin, never the worker's switch, and a
  retry keeps the original's. Fieldwork fails a routed run by name (`routing_unavailable`) until a
  source routes (RQC11), so the switch never yields answers everyone gave to a question some should not
  see. The pin is not in the run's key: without it such a design never starts, so a start after
  the switch is off still finds its run. A design with no condition pins nothing and keeps its
  run. Metodika's readiness comparison reads the switch too (`readiness_impact(routing=)`). The Lead's typed start takes the switch with the rest (`RunStartSettings.routing_enabled`).
  Metodika's sample-size step re-pinned to `assess_readiness`. Tests: `test_research_conditions.py`,
  `apps/executors/tests/test_routing_pin.py`, `test_research_api.py`
  (`test_the_routing_switch_passes_a_valid_condition_and_pins_it_on_the_run`).

**WCE11, amended (G56, X11).** The chunk states who performs a structural auto-apply (the researcher's browser session, or a named server path under the person's standing authority, coordinated with G42), where the per-stage choice lives (Můj Vedoucí or the artifact header), and the rule once fieldwork exists (a structural auto-apply is refused or announced in the conversation, never applied silently). Today an automatic accept is an act of the signed-in browser after it sees a turn finish, and `decide_edits` needs the caller's `APPROVE_GATE` and own completed turn, so a continuation turn (LO6) finishing with no browser open applies nothing. Test: with a stage on and no browser open, a continuation turn's structural edit stays pending; after fieldwork exists it is not applied silently.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

**New chunk.** WCE14 (W2), D-45 in; fieldwork carries it (`run-qc-and-checkpoint#RQC13`).

**Existing chunks, changed by the owner's answers.**

- **WCE0 / WCE5 (D-06).** Conflicts are per `(item_key, field)`.
- **WCE7 / WCE9 (D-07).** An unaccepted change is `REJECTED`; `DROPPED_STALE` when it conflicted.
- **WCE4.** One feed name, `…/workspace/ops?since=`.
- **WCE8 (D-30).** The lock covers the declared inputs and the sets they rate.
- **WCE11 (D-31).** A named server path accepts a structural change under the person's standing
  choice; the switch is per stage on Můj Vedoucí, off by default.
- **WCE1** gains no decision, expected-answer or done-when kinds: the question chain is **out** (D-44).

### After the stage-handoff answer (the owner's answers on the PM status page, 2026-10-20 about 20:35 UTC, relayed by the coordinator (page ids Q10, Q11, Q12; `.planning/evidence/scope-freeze/answers-2026-10-20.md`, third table))

- **WCE7 (Q12).** A declared map of what each stage reads (its upstream stages and items), the one
  source for "current / changed / re-check", for `lead-orchestration#LO9d`'s worker inputs and for
  staleness. A **pending proposal** built on an older upstream item is flagged "postaveno na starší
  verzi …", not only a run: today the lane marks a run's staleness only (`apps/web/src/research/
  lane.ts:34-96 @ 7878bad`). Test: accepting a brief change flags a pending questionnaire proposal
  built before it.

## WCE0 delivered (2026-10-21)

`packages/aia_core/src/aia_core/domain/edit_ops.py` is the vocabulary; the Lead's edit payloads,
`is_text_edit` and `apply_edit` moved there verbatim from `domain/research_lead.py`, which
re-exports them (its output schema and prompt hash unchanged, checked before and after).

- **The closed set** (`CATALOGUE`, `OpName`): 30 operations. The eight the Lead proposes today are
  `APPLIED`; the other 22 are `DECLARED` with their item kinds, fields, text ruling, lock relevance
  and owning chunk (WCE2, WCE3a, WCE3b, WCE8, WCE10, WCE13, WCE14, AOC1), refused by name
  (`op_not_available`) until that chunk gives each its payload and apply. `in_lead_output` is a
  fact about today's Lead schema (a test reads the schema), never a plan.
- **Ids**: `ITEM_ID` (the id part of `FOCUS_ID`), `ID_PREFIX` per `IdKind` (`Q_` and `sec_` as
  written today; `obj_`, `rq_`, `hyp_`, `set_`, `opt_`, `o_`, `asm_`, `stim_` new), `new_item_id`,
  `new_op_id` (`EOP-`, for M1's rows). Giving existing content ids stays WCE1.
- **Validation**: `refusal` (the grounding `ground_edits` now calls), `op_refusal`, `REFUSALS`.
- **Touches**: `touches(edit, content)`, the `(item key, field)` pairs (D-06), on `design_items`'
  keys; a plan-list item is text-keyed until WCE1.
- **The lock** (D-30): `declares_sociomap_inputs`, `locked_items` (declared rating questions and
  every questionnaire tracked set, once anything is declared; the plan's own `tracked_sets` are not
  read by the map and are not locked), `lock_refusal`, `whole_copy_lock_refusal`. Nothing calls them
  yet: WCE2 makes every writer ask; `ground_edits` deliberately does not, so the Lead's behaviour
  does not change in this chunk.
- **Text only**: `is_text_edit` / `TEXT_EDIT_OPS` unchanged; a test holds that only a `BY_PAYLOAD`
  operation can be one and a declared operation never is, so the default automatic accept stays
  text-only.
- **One refusal for what cannot apply**: `refusal`, `apply_edit` and `lock_refusal` ask `op_refusal`
  first, so a declared operation is `op_not_available` and an unknown one `unknown_edit` at all
  three, none raising (`test_every_entry_point_refuses_an_operation_it_cannot_apply_with_one_word`).
- **One case file**: `packages/aia_core/tests/fixtures/edit_ops/cases.json` (25 apply cases, the
  text marker, touches, lock, whole-copy lock, the trace's link key and `research_questions_of`),
  read by `packages/aia_core/tests/test_edit_ops.py` and `apps/web/src/lib/edit-ops.cases.test.ts`.
  `applyLeadEdit` now mirrors the server's `apply_edit` and answers the server's refusal word
  (`reason`) beside its Czech sentence.

## Findings

- **F-WCE0-1. The web's applyLeadEdit wrote a different working copy from the server's
  apply_edit.** Anchor: `apps/web/src/lib/lead.ts:180-238 @ 6b76eef4` against
  `packages/aia_core/src/aia_core/domain/research_lead.py:1200-1320 @ 6b76eef4`. Reproduction: the
  case file's test against that `lead.ts` fails 10 of 25 apply cases: five on behaviour (the two
  problem-summary cases, a research question added and one reworded: a list or summary edit went
  through `applyNarrative` with the whole narrative, so it copied the analysis' other lists and an
  empty `problem_summary` over the plan's; and options on a scale, dropped silently where the
  server refuses `options_on_non_selection`) and five because it gave no refusal word. The web
  also trimmed a list value and a new question's text, which the server stores as given
  (`lead.ts:199, 203, 217 @ 6b76eef4`; no case turned on it). Consequence: after an
  automatic accept the screen's copy, from which "Vrátit" reads the wording to put back, differed
  from the saved one until the reload. Fix: this chunk (the web follows the server). Test:
  `apps/web/src/lib/edit-ops.cases.test.ts`.
- **F-WCE0-2. The two sides fold case differently.** Anchor: `apps/web/src/lib/lead.ts:139 @
  6b76eef4` (`toLocaleLowerCase("cs")`) against `domain/edit_ops.py` `_key` (`str.casefold`).
  Reproduction: `python -c "print('STRASSE'.casefold() == 'straße'.casefold())"` prints `True`;
  `"STRASSE".toLocaleLowerCase("cs") === "straße".toLocaleLowerCase("cs")` is `false` in Node.
  Consequence: a list item spelled with `ß` (or another character `casefold` expands) is found by
  the server and not by the screen; rare in Czech content, and gone once WCE1 keys items by id.
  Smallest fix: key by id (WCE1); no case in the file until then. Test: a case-file case with `ß`.

- **F-WCE0-3. `touches()` keys a question and a section by its raw id; `locked_items()` by
  `design_items`' occurrence key.** Anchor: `domain/edit_ops.py` `touches` against `locked_items`
  (`item_values`, `occurrence_keys`) at #534's head. Reproduction: a working copy with two questions
  both `id: "Q1"`, the second marked `sociomap_rating`: `locked_items` holds `content:question:Q1#2`;
  a `question_edit` of `Q1` touches `content:question:Q1` (the first, which `apply_edit` edits) and
  is let through, which is right for the first and says nothing of the second; a section with no id
  is `#<i>` in `design_items` and `""` in `touches`. Consequence: none on well-formed content (ids
  unique, the first occurrence's key is the plain id); on a malformed copy the two keyings disagree.
  Smallest fix: WCE1's stable, unique ids, after which both read one key; mapping occurrence keys
  back to positions here is more code than the case is worth. Test: a case-file case with a
  repeated id once WCE1 refuses or renames them.

## Doc follow-up (WCE0)

- `CLAUDE.md` § 2, under `domain/`: `edit_ops.py` (the working copy's edit vocabulary: the closed
  set, ids, validation, touches, the Sociomap lock, the text-only marker; ADR 0029 decision 1);
  under `research_lead.py`: "its edits are `edit_ops`'s". Under `src/lib/lead.ts`: `applyLeadEdit`
  mirrors the server's `apply_edit`, held to it by `tests/fixtures/edit_ops/cases.json`.
- `open-items.md`: number F-WCE0-3 (open, WCE1).


## WCE1 delivered (2026-10-21)

`packages/aia_core/src/aia_core/domain/item_ids.py` is the identity; `apps/web/src/research/item-ids.ts`
its port; one case file, `packages/aia_core/tests/fixtures/item_ids/cases.json`, holds the two
together (`test_item_ids.py`, `item-ids.test.ts`: 47 web cases equal the server's).

**The choice: ids beside the lists, not inside them.** Per-element ids are the known answer to
index-addressed list edits going wrong under concurrent change (ShareJS addresses JSON arrays by
index; `articulated` and json-joy give each list element a persistent id). Turning the plan's lists
of strings into `{id, text}` objects would have broken every reader of them (compile, the trace,
the analysis, the research agents' contracts and prompts, Deep Research subjects, the report, the
web's stages and parity tests). So each id-bearing list carries a parallel id list:
`objective_ids` / `research_question_ids` / `hypothesis_ids` (in `research_plan` and the analysis),
`kategorie_ids` on a question, `object_ids` on a tracked set. Each entry is `{id, bound}`, `bound`
the hash of the wording the id was last given with, so a list a writer changed without the ids
(the stages before WCE3, a proposal spread over its baseline, an accepted Lead edit before WCE2) is
still read deterministically: anchors by wording (an LCS, so they never cross; a moved item keeps
its id), rewords in place where a gap between anchors holds as many old entries as new wordings,
nothing guessed otherwise; a list with no id list is matched by wording to the baseline; the rest
derive `<prefix><10 hex>` from FNV-1a 64 + MurmurHash3's finaliser over (kind, folded wording,
occurrence). Content stored before WCE1 therefore has exactly one id per old text key:
`legacy_keys` reads the shared design_items cases (unchanged file, so no conflict with #539's added
cases) back through the ids and every case passes; derived ids are that content's identity from now
on, and the case file pins them.

- **Sections** without an id get the compiler's (`section_ids`: `compile_design`'s slug and
  uniqueness rules, in order). `test_ids_change_nothing_a_run_compiles` compiles 300 random
  questionnaires and every fixture design before and after ids: identical problems, spec, fingerprint
  and respondent columns, so this chunk needs no `COMPILER_VERSION` bump (#538 moved it to `-2` for its own reason). A question keeps the
  id it has; one without stays keyed by place (no case needs it: every writer gives one).
- **design_items** keys plan-list items by id (`item_values(docs, previous=)`; `design_items` reads
  `after` against `before`); a reword its id list records is one changed item. Values exclude the id
  lists. `merge_items(…, baseline=)` keys by ids and writes nothing that was not stored but a merged
  plan list whose working copy keeps an id list. `proposal_accept` passes the baseline and reads keys
  a worker recorded before the deploy as the ids they name (`from_legacy_keys`).
- **The field view** (`domain/design_fields.py`, the D-06 unit): `item` (existence), each field,
  a question's `section`, and order as items of its own (`order:sections`, `order:section:<id>`,
  `order:<kind>`) that differ only when common items stand differently. `edit_ops.touches` is now
  the field diff of applying the edit (exact by construction, `new_id=` names an added item), which
  closes **F-WCE0-3**: `touches` and `locked_items` read one keying. Accept still compares items
  (`design_items`); WCE5 moves it onto the field view.
- **Links follow a reword** (`follow_rewords`, `settle_item_ids`): a research question's id naming
  a new wording carries the `research_questions` links and its comparison key to it.
- **FOCUS_ID** is unchanged: every id is `[A-Za-z0-9_.-]{1,80}`, so `plan:<id>`, `section:<id>`,
  `question:<id>` are admitted (`test_every_id_is_one_the_interface_can_focus`). Focusing one plan
  item on screen (a `data-aia` per item for `focusSelector`) is WCE3a's.
- **Behind a switch, off**: `AIA_WEB_STABLE_ITEM_IDS` (`/config` `stableItemIds`). On, the store
  writes ids on load (`completed`, so a submit saves first) and settles every change; off, nothing
  writes an id and the server's derived keys are a one-to-one renaming of the old text keys.

Plan tests: `test_a_reword_keeps_its_research_question_links`,
`test_two_people_adding_questions_to_one_section_touch_different_keys`, `test_a_section_move_is_an_item`.

### Findings (WCE1)

- **F-WCE1-1. Until WCE2, a reword accepted on the server does not carry its links; the same edit
  accepted automatically in the browser (switch on) does.** Anchor: `application/research_lead.py`
  `decide_edits` saves `edit_ops.apply_edit`'s result, which does not call `settle_item_ids`, at this
  branch's head. Reproduction: with `AIA_WEB_STABLE_ITEM_IDS` on, a Lead `list_replace` of a linked
  research question accepted by click leaves the link dangling; accepted with auto it does not.
  Consequence: a dangling link the trace names, only with the switch on. Smallest fix: WCE2's one
  writer settles every write. Test: a WCE2 test of the accept route asserting no dangling link. **Closed
  by WCE2d**: `test_lead_edits_logged.py::test_a_reworded_research_question_keeps_its_links_…`.
- **F-WCE1-2. A whole-list replacement that keeps a stale id list reads as rewords, and with the
  switch on the web then moves questionnaire links onto a different research question.** Blocks
  turning `AIA_WEB_STABLE_ITEM_IDS` on; owner WCE8b with WCE2. Anchor: `domain/item_ids.py`
  `reconcile` (the equal-count gap rule) with `follow_rewords`, reached in the web by
  `apps/web/src/research/plan.ts` `applyVariant` and `plan-edit.ts` `applyNarrative`, which replace
  `research_questions` and spread the old `research_plan` with its `research_question_ids`.
  Reproduction (`settle_item_ids`, from the independent review of #543): before
  `["Kdo kupuje kávu?", "Jak často?", "Kde nakupují?"]` with Q1 linked to "Jak často?", after
  `["Proč nekupují?", "Které značky znají?", "Kde nakupují?"]`: Q1 now links "Které značky znají?".
  Consequence: a stamped guess, a measure moved onto an unrelated research question (today the
  link dangles, which the trace shows). With the switch off nothing stores id lists and no server
  path settles, so links never move. Smallest fix: the writers that replace a whole list drop its
  id list, and `follow_rewords` follows only a reword the binding vouches for, never a gap match.
  Test: the reproduction, asserting the link dangles rather than moves.
- **F-WCE1-3. `touches` and `lock_refusal` differ from before (switch-on and WCE2 prerequisite).**
  Anchor: `domain/edit_ops.py` `touches` (the field diff of applying the edit). A `question_edit`
  that changes nothing on a locked rating question now passes the lock (it touches nothing); an
  edit `apply_edit` refuses touches nothing, so it is refused with its own word, not the lock's.
  Reproduction: the review's probe over set_text, list ops, question add / edit / remove, set_n,
  malformed content and a locked question and battery: no refusal became an apply. Consequence:
  none today (`lock_refusal` is not wired). Fix: WCE2 asks `refusal` before the lock. Test: WCE2's
  every-writer lock tests.
- **F-WCE1-4. Switching on rewrites every loaded study's design bytes (switch-on prerequisite).**
  The store marks such a copy `completed`, so it is saved before a submit. The agents' context then
  carries `*_ids` and their hashes, and `research_agents.py` `proposal_result` spreads model output
  over that plan, so a model can echo stale entries back (F-WCE1-2's input). Deep Research
  classifies a design by its exact bytes (OI-129), so those designs park until an operator
  classifies them again. Fix before switching on: a rollout note, the agents' context without id
  lists (or WCE8b), and the re-classification planned.
- **F-WCE1-5. On, then off, leaves stale id lists (switch-on prerequisite).** The stored id lists
  stay and go stale under writers that ignore them; the server keeps reading them by the gap rule
  (links never move on the server). Fix: strip them when off, or record that turning off is one-way
  until WCE2.

Fixed in this PR after the independent review: an `items_changed` refusal carries each
conflicting item's wording (`conflicting_wording`, from the current copy else the baseline; the web
prefers it), so a reworded or removed item is never named by its hash
(`test_a_refusal_names_a_reworded_research_question_by_its_wording`, `proposal-items.test.ts`).
Keys recorded before ids for sections and questions without one (`#i`, `#i#j`) are translated to
the compiler's ids, and a recorded key that names nothing in either design is refused
`unknown_baseline`, never accepted and dropped, as is a place (`#0`) the baseline and the proposal
fill with different sections (`ambiguous_legacy_keys`, from the re-review; `test_proposal_accept_ids.py`). Identity folds
exactly as the old text keys did (`" ".join(split()).casefold()`, one function; the web adds the
297 code points where case folding is not lower-casing, `apps/web/src/research/case-folds.ts`), so
`ß` and final sigma map one to one (`test_a_respelling_the_old_keys_called_one_item_is_still_one`).

### Doc follow-up (WCE1)

- `CLAUDE.md` § 2, under `domain/`: `item_ids.py` (stable item ids beside the lists they name:
  `*_ids` entries `{id, bound}`, derived for content stored before; section ids the compiler's;
  links follow a reword; `apps/web/src/research/item-ids.ts` its port, one case file) and
  `design_fields.py` (the D-06 field view: `item`, fields, a question's `section`, order items).
  Under `design_items.py`: plan-list items keyed by id; `legacy_keys` / `from_legacy_keys`.
  Under `edit_ops.py`: `touches` is the field diff of applying the edit.
- `CLAUDE.md` § 2, under `src/research/`: the store keeps ids behind `AIA_WEB_STABLE_ITEM_IDS`
  (`/config` `stableItemIds`, off).
- `AGENTS.md` (Next.js/TypeScript): the web's `tsconfig` targets below ES2020, so BigInt literals
  do not compile; `item-ids.ts` does 64-bit arithmetic in 16-bit limbs (wrong: `1n << 64n`;
  right: `mul64` over `[hi, lo]`).
- `open-items.md`: close F-WCE0-3 (this chunk); number F-WCE1-1 (open, WCE2), F-WCE1-2 (open,
  WCE8b with WCE2; blocks switching `AIA_WEB_STABLE_ITEM_IDS` on) and F-WCE1-3 to F-WCE1-5 (open,
  switch-on prerequisites).
