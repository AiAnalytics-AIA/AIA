# ADR 0043 — Deleting a study or a client: content gone, ledgers kept under a tombstone; a study hidden for 7 days first

**Status:** Accepted — 2026-10-26, by the product owner ("Q1 (b) 7-day window; Q2-Q8 as
recommended; accept ADR 0043"); confirmed the same day in the Decision Review (the product owner,
relayed by the PM coordinator), answer by answer, below. Proposed 2026-10-25; its study-specific decisions are the
recommendations of `study-deletion` Q1-Q8, which he adopted unchanged (SD0).
**Records** the owner's rule of 2026-10-22 for a client's deletion (settings-backends SB5, #850 @
46fc909f), which no ADR holds today. **Builds on** [ADR 0031](0031-production-environment.md) §5
(MVPQ-07: at most 30 days in backups and versions, the deletion journal replayed after a restore) and
[ADR 0019](0019-two-roles-and-human-ai-gates.md) (one Researcher role; gates recorded in the approval
ledger). **Leaves unchanged** the retention horizons, the journal and who reads kept records (MVPQ-07).
**Date:** 2026-10-25.
**Plan:** [study-deletion](../../../.planning/plans/study-deletion.md); `study-data-lifecycle` SDL3.

## Context

The owner wants a person to delete a study in AIA ("lets delete old studies", answering OI-81).
A client can already be deleted by an OWNER or ADMIN
(`packages/aia_core/src/aia_core/application/client_deletion.py:161-209 @ f7762d72`): its content rows
are erased, its approval ledger scrubbed content-free, its client and study rows kept archived and
named by their ids (`infrastructure/scope_repository.py:857-916 @ f7762d72`), its objects deleted
after the commit. That rule lives in a docstring (`client_deletion.py:3-8`). A study has no deletion:
`Permission.DELETE_STUDY` (`domain/scope.py:186`) guards only a project's purge and an artifact's
delete, and an archived study is still found by project memory and opened by id
(`application/scope.py:196-245` reads no study status).

## Decision

1. **Content gone, ledgers kept** (the owner, 2026-10-22), for a client and for a study. Content is
   every row and object a person or a model wrote for it. The AI usage ledger, budget holds, wallet
   rows, the approval ledger and the audit log stay, content-free: ids, codes, numbers and times; a
   name becomes its id; any other text is erased. They are read by an OWNER or ADMIN only (MVPQ-07).
2. **The row stays as a tombstone.** A deleted client's or study's row is kept with `deleted_at`,
   named and slugged by its id, so every kept row still resolves and no foreign key to it breaks. No
   scope is issued for it again: `ScopeResolver` refuses it as `unknown_study` / `unknown_client`.
3. **A study is hidden for 7 days, then purged.** Deleting a study hides it at once and sets
   `purge_after`; within it, the same person rule may restore it. An operator job purges it after,
   through the same erase as decision 1, and writes the purge to the deletion journal. MVPQ-07's 30
   days count from the person's click, so the S3 noncurrent-version lifecycle is 23 days. A client's
   deletion stays immediate (SB5).
4. **Who.** Any member deletes a study that is not `DELIVERED` and holds no approved report or
   client report; an OWNER or ADMIN deletes or restores one that does, and any client.
5. **Refused while money or work is open.** A run that has not ended or a `RESERVED` hold refuses
   the deletion by name; the person cancels first. On deletion the study's budget and wallet close;
   their ledgers stay (decision 1).
6. **A confirmation is not erased.** A respondent system's holdout confirmation is kept content-free
   under the tombstone, so a deletion never frees a system to be confirmed again.
7. **Readers say what is gone.** A citation of a deleted study (design reuse, knowledge provenance,
   audit) shows its id and the words smazaná studie, never a link or a guessed name.
8. **Counted first, nothing lost by surprise.** The confirmation counts what goes and offers each
   approved report's download before the person confirms; then all of the study's content goes.
9. **Client knowledge.** The study's pending proposals and its knowledge selection go; accepted
   knowledge stays, the client's, its provenance reading smazaná studie.
10. **Project memory and reuse.** A deleted study is gone from project-memory search and from reuse
    at once; a study that reused its design keeps its copy and citation, marked "source deleted"
    (Zdrojová studie byla smazána), with no link.
11. **Where.** "Smazat studii…" in the study's status menu, a dialog with the counts, a toast with
    Vrátit, and a Smazané studie view with Obnovit.

## What stays out

Erasing one person's data and exporting a client's data stay an operator procedure (D-29). Deleting
one client source is SDL4b. The backup horizons and the journal are ADR 0031 §5's.

## Alternatives considered

- **Hard delete of the study row.** Breaks the usage ledger's foreign key (`tables.py:2148`) or
  forces it to be dropped, and leaves kept rows naming nothing; the tombstone costs one row.
- **Delete a study at once, as a client.** No undo for a researcher's housekeeping click; the project
  trash already treats a purge as a second, deliberate act (`infrastructure/repositories.py:630-680`).
- **Archive is enough.** An archived study is still searched, reused and opened, and its content
  stays forever; the owner asked for deletion.

## Consequences

- Every study reader goes through `ScopeResolver`, so one check hides a deleted study everywhere; a
  reader that bypasses it is a defect.
- `holdout_confirmations` stops cascading with its client (SD7), which SB5's deletion changes too.
- Content may live up to 30 days after the click in backups and versions (MVPQ-07), and 7 of them in
  the database, hidden.

## What enforces it

`study-deletion` SD2 (one test per reader), SD5 (PostgreSQL: nothing of the study remains, the usage
ledger reconciles), SD7 (a second confirmation refused after a deletion), SD10 (the browser journey),
SD11 with SDL6 (a restore replays the purge).

## Open for Nigel

None. `study-deletion` Q1-Q8 are answered (2026-10-26). The Decision Review the same day (relayed by
the PM coordinator) gave: Q1 (b) "Hidden for 7 days, then purged" (backups expire 23 days later, so
MVPQ-07's 30 days count from the click); Q2 (c) "Any member, unless the study is delivered or holds an
approved or client report; then OWNER/ADMIN"; Q3 (c) "All go, after showing the counts and offering
the approved reports to download first"; Q4 (a) "Keep it, without content"; Q5 (a) "Refuse while a
run is live or money is held; budget and wallet close, ledgers stay"; Q6 (a) "Its pending proposals
and its knowledge selection go; accepted knowledge stays, marked 'smazaná studie'"; Q7 (a) "Gone from
search and reuse; a study that reused it keeps its copy and citation, marked 'source deleted', with
no link"; Q8 (a) "'Smazat studii…' in the study's status menu"; and REV-SD-F1-NOW (a) "Yes, a small fix
PR now": decision 6's client half (OI-232) is built ahead of the plan as its own small PR
(`study-deletion#SD7`).
