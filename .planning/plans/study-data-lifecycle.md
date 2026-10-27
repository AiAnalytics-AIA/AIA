---
status: planned
chunks:
  - "[ ] SDL0. Write down the owner's deletion policy (MVPQ-07, 2026-10-20) as the contract SDL1-SDL5 build: 30 days at most in backups and versions, journal replay after restore, content-free usage and audit rows kept for OWNER/ADMIN"
  - "[ ] SDL1. Foreign keys and the ledger: `ai_usage_events.study_id` and `population_dataset_versions.owner_client_id` get an `ondelete` rule"
  - "[ ] SDL2. Storage: `delete_prefix` for S3, a `DeleteObjectVersion` grant, a bucket lifecycle for versions, IAM for population children"
  - "[ ] SDL3. The delete service for a study and a client: rows, S3 prefixes, audit policy, logs and the error tracker"
  - "[ ] SDL4. The lifecycle of an attachment's bytes: orphans and removal"
  - "[ ] SDL5. A restore after a deletion does not resurrect it: the restore runbook re-applies the tombstones"
  - "[ ] SDL6. Exercised once on develop: a delete, then a restore, with the evidence recorded"
  - "[ ] SDL4b. Deleting one client source, its bytes and readings, by any researcher from the source's card (D-29)"
  - "[ ] SDL7. After the MVP: a client's data export as a feature, today an operator procedure in the runbook (D-29; master, The scope baseline, Out) (Nigel, 27 Oct 2026)"
---
# Study and client data lifecycle: retention and the delete path

Retention is decided; the delete path is required and blocked four ways today (foreign keys with no `ondelete`, IAM, `delete_prefix`, versioned buckets). Written 2026-10-19 from `.planning/evidence/mvp-master-traces/trace-5-deepresearch-data-infra.md`.

**Owner: S3.** Takes the gap rows G8, G25 (attachment bytes) and interface I26 of `mvp-master-plan.md` §6.1 and serves the release checklist (a production blocker) and AC-15.
Every chunk below is **open**; a chunk is built from this file, not from the master plan.

## Decisions this plan carries (settled by the owner; not re-asked)

- Client data is kept until a person deletes it; the operation log is kept with its study (Q27).
- A documented delete path (database cascade, S3 prefixes, the RDS snapshot window stated) is required before production release (Q27); it is not optional.

## Chunks

**SDL0. Decide the deletion horizons, tombstones and backup-resurrection semantics**  
**Decided by the owner, 2026-10-20 (MVPQ-07).** After a person deletes a client or study, its content may remain in backups and object versions for **at most 30 days** (RDS's 14-day recovery window lies inside it; the S3 version lifecycle is set to 30 days, not left at a default; **amended 2026-10-26:** 23 days, because `study-deletion` Q1 (b) holds a deleted study for 7 days before its purge and the 30 days count from the click). A durable deletion journal, kept apart from the snapshots, is replayed after any restore before the environment serves traffic. **Content-free usage and audit rows** (date, model, tokens, USD and identifiers; no text, no client name) are kept so spend still reconciles, readable by an organisation OWNER or ADMIN only. This chunk writes that down as the contract SDL1-SDL5 build to.

**SDL1. Foreign keys and the ledger: `ai_usage_events.study_id` and `population_dataset_versions.owner_client_id` get an `ondelete` rule**  
Neither has one (`tables.py:1833, 1938-1939`). The usage ledger must still reconcile to spend (AC-15) after a deletion: SDL0 keeps the content-free usage rows, so a usage row is never cascaded with its study; it keeps the study's identifier without a foreign key to a deleted row.

**SDL2. Storage: `delete_prefix` for S3, a `DeleteObjectVersion` grant, a bucket lifecycle for versions, IAM for population children**  
`delete_prefix` exists only on the filesystem store (`storage.py:366`); IAM grants no delete on population children (`infra/develop/main.tf:364-368`).

**SDL3. The delete service for a study and a client: rows, S3 prefixes, audit policy, logs and the error tracker**  
Test on PostgreSQL: delete a study; nothing of it remains in the database or the artifact bucket; the usage ledger still reconciles.
*2026-10-26:* the client part is built as `settings-backends` SB5 (#850 @ 46fc909f); the study part is `study-deletion#SD5`.
SDL1's study foreign key is not on the deletion path once studies are tombstoned (ADR 0043).

**SDL4. The lifecycle of an attachment's bytes: orphans and removal**  
No code deletes an attachment's bytes today.

**SDL5. A restore after a deletion does not resurrect it: the restore runbook re-applies the tombstones**  
Interfaces I26.

**SDL6. Exercised once on develop: a delete, then a restore, with the evidence recorded**  
A production release checklist item (`production-environment#PE9a`).

## Open: owner clarifications

- None: the horizons, the journal and the surviving facts were decided on 2026-10-20 (MVPQ-07, SDL0).


## Release ordering (2026-10-20)

SDL0 precedes the deletion FK migration M12 and destructive lifecycle settings. SDL1-SDL4 then
implement the accepted policy; SDL5 specifies restore ordering and SDL6 exercises it on disposable
test data. The original tombstone/journal must survive independently of the restored snapshot;
its scope ids/cutoff and replay result are evidenced before restored traffic is enabled. Retain
only the content-free usage and audit rows MVPQ-07 accepts. PE9a cannot pass without SDL6's actual proof.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

**New chunk.** SDL4b (W4), D-29.

**Existing chunks, changed.** SDL3 (D-29) gains its entry points: an OWNER or ADMIN deletes a client
from Settings with a typed confirmation; knowledge is retired, never deleted (*stale since the owner's rule of 2026-10-22: a client's deletion deletes its
content, knowledge among it, `client_knowledge_repository.py:1699-1702 @ f7762d72`; ledgers kept under a tombstone,
ADR 0043*). Export of a client's
data and erasing one person are an operator procedure in the runbook for about ten users. SDL5
(D-25): RPO 24 h, RTO 4 h.

## From the unplanned-features inventory (2026-10-27)

Source: the five inventories of 27 Oct 2026 (the Lead, the client pages, Settings, the research stages and the
prototypes, each compared with develop `dbaa7720`) and the product owner's decisions on them (Nigel, 27 Oct 2026,
~01:10-01:40 UTC, in the PM coordinator's chat: "lets turn these into chunks", then an answer to every decision
question). The research build spec cited is <https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy> (spec v6,
prototype v78); its ids carry their section prefix (`navrh/`, `vzorek/`, `sber/`, `szz/`, `lead/`). Waves are in
`.planning/mvp-execution-contracts.md`; a chunk marked **after the MVP** has the wave POST there. Ids are only
added, never renumbered; a ticked chunk a decision reopens gets a follow-up chunk.

**SDL7. Client data export** (after the MVP). The master plan's scope baseline keeps the export of a client's data an
operator procedure in the runbook for about ten users (D-29). Nigel, 27 Oct 2026, keeps it after the MVP. Nothing
scheduled.
