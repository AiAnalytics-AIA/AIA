---
status: planned
chunks:
  - "[ ] SD0. The owner answers Q1-Q8 below and accepts ADR 0043; the answers are written into this file and the ADR, nothing built before"
  - "[ ] SD1. A study's tombstone columns: studies.deleted_at, deleted_by and purge_after (migration), carried on the domain Study; nothing reads them yet"
  - "[ ] SD2. Every reader refuses a deleted study: ScopeResolver.study_context and accessible_studies, studies_in_client, the admin study listing, project memory search; a test per reader"
  - "[ ] SD3. The delete itself: GET /studies/{id}/deletion (counts and a one-time confirmation, the SB5 ticket shape) and DELETE /studies/{id}, under the study row lock, refused by name (runs not ended, an open hold, the Q2 rule), audited STUDY_DELETED with counts"
  - "[ ] SD4. Restore within the window: POST /studies/{id}/restore by the Q2 rule, audited STUDY_RESTORED; refused once purged (study_purged)"
  - "[ ] SD5. The purge of one study (SDL3, study part): the SB5 erase helpers narrowed to a study, approvals scrubbed, the study row tombstoned (name and slug to its id, its audit rows content-free), objects listed then deleted; a PostgreSQL test proves nothing of it remains and usage still reconciles"
  - "[ ] SD6. The purge sweep: studies past purge_after purged by a scheduled operator job, idempotent, resuming listed objects, each purge written to the SDL5 deletion journal"
  - "[ ] SD7. A deletion keeps a respondent system's confirmation once per organization: holdout_confirmations kept content-free under the tombstone, for a client and for a study (Finding F1)"
  - "[ ] SD8. Reader-side words for what a deletion leaves: the design-source note, a knowledge item's provenance and Settings' study and audit lists say smazaná studie, never a dead link or a guessed name"
  - "[ ] SD9. The web: Smazat studii in the study status menu (#892), the Czech confirmation with counts, the toast with Vrátit, and the Smazané studie list with Obnovit"
  - "[ ] SD10. Browser journey on the workbench: delete, gone from Výzkumy and project memory, restore, delete again, purge; zero paid jobs"
  - "[ ] SD11. Exercised on develop beside SDL6: a study deleted, purged and a restore replayed, with the evidence recorded here"
---
# Study deletion: Smazat studii

Written 2026-10-25 on `chore/study-deletion-plan` from `origin/develop @ f7762d72`. Every anchor
below is `@ f7762d72` unless it names another ref.

## Problem

The product owner answered OI-81 (b), "keep the gate; stamp the delivery date only once", with the
note "lets delete old studies", and has since said he wants a real feature: a person deletes a study
in AIA. Today nothing does. A study closes (`StudyStatus.ARCHIVED` / `CANCELLED`,
`packages/aia_core/src/aia_core/domain/scope.py:469-484`) through the one status change
(`application/wallet.py:95-105` over `infrastructure/scope_repository.py:1210-1245`), and an
archived study is only filtered out of some lists (`scope_repository.py:1109-1110`); it is still
found by project memory (`application/project_memory.py:102-106`, which lists with
`include_archived=True`, `scope_repository.py:1093`) and opened by id
(`application/scope.py:196-245` reads no study status).

A permission for it exists and nothing uses it for a study: `Permission.DELETE_STUDY`
(`domain/scope.py:186`) guards only a project's purge from the trash
(`infrastructure/repositories.py:669-680`) and an artifact's delete
(`infrastructure/artifact_repository.py:692-707`). Every Researcher holds it
(`domain/scope.py:192-194`, ADR 0019); the worker does not (`domain/scope.py:201-212`).

## What already exists, and what this plan does not repeat

- **`study-data-lifecycle` (S3) owns the backend delete path.** SDL0 writes MVPQ-07's contract
  (`.planning/mvp-owner-decisions.md:158-165`; ADR 0031 §5,
  `docs/architecture/adr/0031-production-environment.md:89-94`): at most 30 days in backups and
  object versions after a person deletes, a deletion journal replayed after any restore, content-free
  usage and audit rows kept for an OWNER or ADMIN. SDL2 makes S3 able to delete (versions, IAM),
  SDL4 owns attachment bytes, SDL5 the restore replay, SDL6 the proof on develop.
- **The client half of SDL3 is built** as settings-backends SB5 (#850 @ 46fc909f):
  `application/client_deletion.py`. The owner's rule of 2026-10-22, **content gone, ledgers kept**
  (`client_deletion.py:3-8`): content rows erased (`:189-203`), the approval ledger scrubbed
  content-free (`:205`, `workflow_repository.py:3858`), the client and its study rows kept as
  tombstones named by their ids (`scope_repository.py:857-916`), objects listed in the same
  transaction and deleted after commit (`client_deletion.py:207`, `:212-238`), a one-time ten-minute
  confirmation (`scope_repository.py:748-789`), refused while a run has not ended
  (`client_deletion.py:101-107`, `repositories.py:749-760`).
- **This plan is the person-facing study feature built on that:** who may delete a study, the
  soft-delete window and restore, what is refused, the purge of one study (the study half of SDL3),
  and what readers show afterwards.

| Chunk here | Relation to `study-data-lifecycle` |
|---|---|
| SD5 | **Is** SDL3's study part. SDL3's client part is SB5. When SD5 lands, SDL3 can be ticked for both. |
| SD6 | Writes to SDL5's journal; depends on SDL5's journal format (SDL0 contract). |
| SD11 | Runs inside SDL6's exercise; SDL6 is the release proof, SD11 adds the study case. |
| SD1, SD2, SD3, SD4, SD7, SD8, SD9, SD10 | Not in SDL: the person-facing feature. |

**Depends on:** SDL0 (the contract, already decided), SDL2 before SD5 runs against S3 (the
`DeleteObjectVersion` grant and the version lifecycle; SD5's object deletion is by key, as SB5's,
so `delete_prefix` is not needed), SDL4 for a brief attachment's bytes (they are artifacts of the
study's working project, so SD5 removes them with the project; SDL4's orphan sweep covers the rest),
SDL5 before SD6. **Not a dependency:** SDL1's `ai_usage_events.study_id` foreign key
(`tables.py:2148`, no `ondelete`). Because the study row stays as a tombstone, as SB5's do, no
foreign key to it is ever broken; SDL1 still matters for a hard row delete and for population
children.

**OI-81 itself is not closed by this plan.** Its question (re-delivery rewrites `delivered_at`,
`scope_repository.py:1227-1228`) is answered (b) and is a separate small fix; deletion only removes
the need to reopen an old study in order to clear it away.

## Design questions for the owner

Each question is asked once. Where MVPQ-07 or the owner's SB5 rule of 2026-10-22 already settled
something, it is marked settled and not asked.

**Q1. Soft delete or hard delete.**
- (a) Hard delete at once: the content goes in the same request, like a client today (SB5).
- (b) Soft delete: the study is hidden at once and restorable for **7 days**, then purged through
  SD5. To keep MVPQ-07's 30 days counted from the click, SDL2 sets the S3 noncurrent-version
  lifecycle to 23 days (7 + 23 = 30; RDS's 14 days after the purge end on day 21).
- (c) Soft delete for 30 days, MVPQ-07's 30 days counted from the purge (content can then live up to
  60 days after the click: this amends MVPQ-07).
- **Recommendation: (b).** "Delete old studies" is a researcher's housekeeping, where a mistaken
  click needs an undo, and the code already treats a hard delete as a deliberate second action
  (a project's trash, then purge, `repositories.py:630-680`), while (b) keeps MVPQ-07 as decided.

**Q2. Who may delete, and may a study with an approved report be deleted.**
- (a) Any member: every Researcher holds `DELETE_STUDY` (`domain/scope.py:186`, `:192-194`).
- (b) Only an organization OWNER or ADMIN, as for a client (`scope_repository.py:709-719`
  `require_administer`).
- (c) Any member for a study that is not `DELIVERED` and holds no approved report or client report;
  an OWNER or ADMIN for one that does. Restore follows the same rule.
- **Recommendation: (c).** An approved deliverable is what a client was given
  (`is_approved` on artifacts, `tables.py:310`; its sign-off in `approval_decisions`,
  `tables.py:1951-1962`), so removing it is an administrator's act, while an unfinished study is the
  researcher's own work under ADR 0019's one role.

**Q3. Runs, artifacts, S3 objects and the working copy.**
- (a) All of it goes: the working copy and its history, the Design Revisions, every run with its
  steps and artifacts, attachments, Lead turns, the study's fieldwork journal; the rows through the
  study's projects (`projects.study_id` cascades, `tables.py:144`), the objects listed and deleted
  after commit as SB5 does.
- (b) As (a), but approved reports are kept (as content) under the tombstone.
- (c) As (a), and the confirmation first counts what goes (runs, reports, files) and offers each
  approved report's download before the delete.
- **Recommendation: (c).** SB5 already counts a client's projects, revisions, runs and artifacts
  for its confirmation (`repositories.py:686-695` `ClientProjects`), the same counts serve a study,
  and (b) would keep content after a deletion, which the owner's rule of 2026-10-22 refuses.

**Q4. What survives.**
- **Settled by MVPQ-07 and the owner's SB5 rule (2026-10-22):** the AI usage ledger, budget holds,
  the approval ledger (content-free, `workflow_repository.py:3858`) and the audit log (names replaced
  by ids, other text erased, `scope_repository.py:887-905`) are kept, readable by an OWNER or ADMIN;
  the study row stays as a tombstone named by its id; a `STUDY_DELETED` audit row records the counts,
  never a name. Not asked again.
- Open, one point only: a validation study's holdout confirmation (`holdout_confirmations`, one per
  respondent system in an organization, `tables.py:1064-1096`).
  - (a) Keep the confirmation row content-free (fingerprint, run id, who, when) under the tombstone,
    so a system confirmed once stays confirmed once.
  - (b) Erase it with the study (what SB5 does for a client today, `holdout_repository.py:264-272`).
  - (c) Refuse to delete a study that holds a confirmation.
  - **Recommendation: (a).** Erasing it frees the unique constraint, and a second confirmation of
    the same system is then accepted (Finding F1): a failed validation could be deleted and run again
    until one passes, which is what the constraint exists to stop.

**Q5. Money.**
- (a) Refuse while any of the study's runs has not ended or any of its holds is `RESERVED`
  (`repositories.py:749-760`, `tables.py:1743-1775`, `paid_call_in_flight` `:1762`); the person
  cancels first. The study's budget and wallet close with it (the status change already closes the
  wallet, `wallet.py:95-105`); wallet rows and settled holds stay as the money ledger, under the
  tombstone; the client's budget is untouched (its holds name no study,
  `scope_repository.py:1041-1044`).
- (b) Cancel the study's runs automatically, release its holds, then delete.
- (c) Delete regardless; open holds released by the reconciler.
- **Recommendation: (a).** A hold with a paid call in flight is settled only when the call's
  outcome is recorded, so deleting under it loses money the worker is about to book, and SB5 already
  refuses on the same rule (`client_deletion.py:182-184`).

**Q6. Client knowledge.**
- (a) The study's **pending** proposals go with it (their evidence is the study's run, named in
  their provenance); its knowledge selection (K4, `client_knowledge_selections`, `tables.py:1374-1392`)
  goes; **accepted** knowledge stays, being the client's, and its provenance reads smazaná studie
  (`client_knowledge_revisions.provenance`, `tables.py:1349-1351`, keeps the study id with no
  foreign key).
- (b) As (a), but pending proposals become the client's own (study id cleared) and stay in
  Ke schválení.
- (c) Refuse to delete a study while it has pending proposals.
- **Recommendation: (a).** A proposal's evidence is the deleted run, so keeping it would ask a
  person to approve what nothing can show any more; accepted items are already the client's own
  write (`client_knowledge_repository.py`), which the study's deletion does not own.

**Q7. Project memory and design reuse.**
- (a) A deleted study vanishes from project memory and from reuse sources at once (it is refused
  by `ScopeResolver.study_context`, which both go through, `project_memory.py:102-106`,
  `design_reuse.py:151`); a study that reused its design keeps its own copy and its citation
  (`study_design_sources` keeps `source_study_id` with no foreign key by design,
  `tables.py:806-837`), and its note says Zdrojová studie byla smazána, with the revision, labels and
  no link.
- (b) As (a), and the reusing study's citation row is deleted too.
- (c) Refuse to delete a study whose design another study reused.
- **Recommendation: (a).** The reused design is the other study's own content now, and the labels
  were derived when it was reused; today's note links to the source and falls back to its bare id
  when it cannot be read (`DesignSourceNote.tsx:31-34`, `:48-49`), which would become a dead link.

**Q8. The UI.**
- (a) Smazat studii… as the last item, set apart, of the study status menu (#892's
  `StudyStatusMenu`, `apps/web/src/components/rehome/research/StudyStatus.tsx:41-54 @ 4ccf1c15`,
  PR open), opening a dialog with the counts and a checkbox, as the client deletion has
  (`apps/web/src/i18n/cs.ts:1655-1667`); after it, a toast with Vrátit; a Smazané studie view on the
  client's Výzkumy with Obnovit until the purge.
- (b) Only in Settings → Správa dat beside Smazat klienta, for an OWNER or ADMIN.
- (c) As (a), but the person types the study's name to confirm.
- Proposed wording for (a):
  - title: Smazat studii „{name}“?
  - body: Smaže se pracovní verze, design, {runs} běhů, {reports} zpráv a {files} souborů studie.
    Záznamy útraty AI, schválení a audit zůstanou, bez obsahu. Do {date} můžete studii obnovit
    v seznamu Smazané studie; potom ji vrátit nepůjde.
  - checkbox: Rozumím, že po {date} smazání nepůjde vrátit.
  - button: Smazat studii · toast: Studie „{name}“ je smazána. [Vrátit]
- **Recommendation: (a).** #892 makes the study itself the one place a study's state changes, a
  7-day window (Q1 b) makes a typed name more friction than the risk needs, and the client deletion's
  checkbox dialog is the pattern people already meet.

## ADR needed?

**Yes: ADR 0043, drafted as Proposed** (`docs/architecture/adr/0043-study-deletion.md`). Deletion
crosses scope, the money and approval ledgers, artifacts and audit. ADR 0031 §5 records only
MVPQ-07's retention and journal (`0031-production-environment.md:89-94`); ADR 0019 records the roles
and gates, not deletion; the owner's rule of 2026-10-22, content gone and ledgers kept under a
tombstone, lives only in a docstring (`client_deletion.py:3-8`) and the SB5 plan. The ADR records
that rule for both clients and studies, plus the study's window, the refusals and the holdout rule.
ADR 0042 is reserved by `lead-client-knowledge` LK1 (`.planning/plans/lead-client-knowledge.md:5`),
so this takes 0043.

## Chunks

**SD0. Owner answers and ADR acceptance.** Q1-Q8 answered, written in here and in ADR 0043. No code
before. The chunks below assume the recommendations; an answer that differs changes them first.

**SD1. Tombstone columns.** `studies.deleted_at`, `deleted_by`, `purge_after` (none today; the
client's are `tables.py:538-539`), on `Study`. Migration only, no reader.

**SD2. Readers refuse a deleted study.** `ScopeResolver.study_context` raises `unknown_study` for a
deleted study, as for one that does not exist (`application/scope.py:236-245`); `accessible_studies`
(`:506-528`) and `studies_in_client` (`scope_repository.py:1088-1112`) leave it out; the admin listing
(`list_studies`, `scope_repository.py:1181-1208`) shows it only in a deleted view. One test per reader. A worker
cannot hold a lease on it (SD3 refuses while a run lives, and a start needs a study context).

**SD3. The delete.** `GET /studies/{id}/deletion`: counts on both sides and a one-time confirmation
(the SB5 ticket, `scope_repository.py:748-789`, keyed to the study). `DELETE /studies/{id}` with it:
the study row locked, refused `study_has_active_work` (Q5), `study_has_open_holds`,
`delivered_needs_admin` (Q2 c); sets SD1's columns (purge after 7 days), audited `STUDY_DELETED`.
Writers that lock the study row re-read `deleted_at` (SB5's P3 finding,
`.planning/plans/settings-backends.md:138-147`, applies here too).

**SD4. Restore.** `POST /studies/{id}/restore` before `purge_after`: clears the columns, audited
`STUDY_RESTORED`; after the purge `study_purged` (409). Same permission rule as the delete.

**SD5. Purge one study (SDL3, study part).** Study-scoped variants of SB5's erase helpers
(`client_deletion.py:189-203`): knowledge proposals and selections of the study only, Lead turns,
fieldwork journal, edit ops, designs, workspaces, the study's projects; `scrub_client_approvals`
narrowed to the study; the study row tombstoned as `tombstone_client` does for its studies
(`scope_repository.py:875-905`); objects listed, then deleted after commit. PostgreSQL test: nothing
of the study remains in rows or the bucket; the usage ledger reconciles; another study of the client
is untouched.

**SD6. The purge sweep.** An operator job (not the request path, not `WorkQueue`) purges studies past
`purge_after`, retries listed objects, writes each purge to SDL5's journal. Idempotent; a test runs it
twice.

**SD7. Holdout confirmation kept (Finding F1).** `erase_client_holdouts`
(`holdout_repository.py:264-272`) and SD5 keep `holdout_confirmations` rows (content-free) under
the tombstone. Test in Finding F1.

**SD8. Reader-side words.** `DesignSourceNote`: Zdrojová studie byla smazána, no link; a knowledge
item's provenance names a deleted study as smazaná studie; Settings' study and audit lists show the
tombstone's id. Vitest per function.

**SD9. The web.** After #892 merges: Smazat studii… in `StudyStatusMenu`, the dialog (Q8 wording,
counts from SD3's preview), the toast with Vrátit (SD4), the Smazané studie view on Výzkumy
(`apps/web/src/lib/study-table.ts:14` holds the closed-status filter today).

**SD10. Browser journey.** On the workbench: delete a fictional study, it is gone from Výzkumy and
project memory search, Vrátit restores it, delete again, a time-shifted sweep purges it; zero paid
jobs; four widths.

**SD11. On develop.** With SDL6: a study deleted, purged, a snapshot restored and the journal
replayed; evidence recorded here.

## Findings

**F1. Deleting a client frees its respondent system's once-per-organization confirmation, so the
same system can be confirmed again.**
1. Claim: `erase_client_holdouts` deletes the client's `holdout_confirmations` rows, which removes
   the only thing holding `holdout_confirmation_once_per_system`, so another study of the
   organization may then start a second confirmation of the same respondent system.
2. Anchor: `packages/aia_core/src/aia_core/infrastructure/holdout_repository.py:264-272 @ f7762d72`
   (the delete), called from `application/client_deletion.py:194 @ f7762d72`; the constraint
   `infrastructure/tables.py:1064-1096 @ f7762d72` (docstring: "several preregistrations of one system
   cannot each be run and the passing one kept"); the refusal it feeds,
   `holdout_repository.py:217-221` and `application/validation.py:181-185`.
3. Reproduction (run 2026-10-25, SQLite, the real table and helper): insert a confirmation of
   fingerprint X for client A; a second for client B is refused; call
   `erase_client_holdouts(session, client_id="client-a")`; the second is then accepted. Output:
   `before delete: second confirmation refused (once per system)` /
   `after client-a deleted: second confirmation ACCEPTED`.
4. Consequence: a failed holdout confirmation can be erased by deleting its client and run again
   until one passes; a passing confirmation is what lifts a modelled number's `INTERNAL_ONLY`
   (`domain/evidence/validation.py:151` `lifts_internal_only`), so evidence could reach a client report
   on a validation that was chosen, not preregistered.
5. Smallest fix: keep the confirmation row (it is content-free: fingerprint, sha, run id, who,
   when) and erase only the preregistration's content; drop its foreign key to the preregistration
   or keep the preregistration row content-free (SD7).
6. Test: `test_client_deletion.py::test_a_deleted_clients_confirmation_still_holds_its_system`:
   delete a client whose validation study started a confirmation; a second study's start of the
   same fingerprint is refused `holdout_system_confirmation_started` (`validation.py:181-185`).

## Doc follow-up

- `.planning/open-items.md`: Finding F1 as a new OI (defect, settings-backends SB5 / this plan SD7).
  OI-81: note the owner's answer (b) and that deletion is planned here.
- `.planning/plans/study-data-lifecycle.md` (by its owner, S3, or the docs PR): SDL3's client part is
  built as SB5 (#850 @ 46fc909f) and its study part is `study-deletion#SD5`; its scope-freeze line
  "knowledge is retired, never deleted" is stale against the owner's 2026-10-22 rule (content goes,
  `client_knowledge_repository.py:1699-1702 @ f7762d72`); SDL1's study foreign key is not on the
  deletion path once studies are tombstoned; SDL2's version lifecycle is 23 days if Q1 is (b).
- `.planning/plans/mvp-master-plan.md` §3: add `study-deletion` (S3, with `study-data-lifecycle`);
  `tools/master_check.py` reports it missing until then.
- `docs/architecture/adr/README.md`: list ADR 0043 (Proposed).
- `CLAUDE.md` §2 map, when SD3/SD5 land: `application/study_deletion.py` and the three study routes;
  `ARCHITECTURE.md`: a deleted study is refused at scope resolution, as an archived client is.
