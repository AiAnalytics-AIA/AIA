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
**Decided by the owner, 2026-10-20 (MVPQ-07).** After a person deletes a client or study, its content may remain in backups and object versions for **at most 30 days** (RDS's 14-day recovery window lies inside it; the S3 version lifecycle is set to 30 days, not left at a default). A durable deletion journal, kept apart from the snapshots, is replayed after any restore before the environment serves traffic. **Content-free usage and audit rows** (date, model, tokens, USD and identifiers; no text, no client name) are kept so spend still reconciles, readable by an organisation OWNER or ADMIN only. This chunk writes that down as the contract SDL1-SDL5 build to.

**SDL1. Foreign keys and the ledger: `ai_usage_events.study_id` and `population_dataset_versions.owner_client_id` get an `ondelete` rule**  
Neither has one (`tables.py:1833, 1938-1939`). The usage ledger must still reconcile to spend (AC-15) after a deletion: SDL0 keeps the content-free usage rows, so a usage row is never cascaded with its study; it keeps the study's identifier without a foreign key to a deleted row.

**SDL2. Storage: `delete_prefix` for S3, a `DeleteObjectVersion` grant, a bucket lifecycle for versions, IAM for population children**  
`delete_prefix` exists only on the filesystem store (`storage.py:366`); IAM grants no delete on population children (`infra/develop/main.tf:364-368`).

**SDL3. The delete service for a study and a client: rows, S3 prefixes, audit policy, logs and the error tracker**  
Test on PostgreSQL: delete a study; nothing of it remains in the database or the artifact bucket; the usage ledger still reconciles.

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
