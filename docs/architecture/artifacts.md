# Artifacts and storage

**Status: implemented in software; storage infrastructure still to provision.**

`ArtifactStore` has three backends — S3 (lazy `boto3` import, SSE/KMS), filesystem
(atomic temp → fsync → rename) and in-memory — all enforcing identical key
validation and hash verification. `ArtifactRepository` carries fingerprinting,
dependency edges, provenance, revision association and cross-revision reuse, and
the write order below is enforced rather than left to callers.

What remains is **deployment**: an S3 bucket, its encryption configuration and its
lifecycle policy. Code implementation and provisioned infrastructure are different
things and this document does not conflate them.

An artifact is a durable output of one pipeline stage: an evidence pack, a
compiled questionnaire, a respondent dataset, an analysis module, a report, an
export bundle.

## The split

> **Metadata in PostgreSQL. Bytes in object storage. Never the reverse.**

The database row is authoritative for identity, provenance and validity. The
object is just the payload.

```
project_artifacts row                object storage
─────────────────────                ──────────────
artifact_id      ART-…        ──►    storage_key
sha256           abc123…             org/<org>/proj/<pid>/rev/<n>/<stage>/<artifact_id>
size_bytes       48210
content_type     application/json
input_fingerprint …
provider / model …
produced_by_job_id …
```

The prototype stored artifacts as filesystem paths under the application
directory. That breaks the moment there is more than one process: a worker on a
different machine cannot read another's disk, a container redeploy loses the
files, and nothing is backed up.

## Write protocol

Ordering matters. A metadata row must never reference an object that does not
exist yet.

1. Compute the bytes.
2. Compute `sha256`.
3. Check reuse: is there already a `VALID` artifact for this
   `(project_id, stage_type, artifact_type, input_fingerprint)`? If yes, reference
   it and stop — no upload, no AI spend.
4. Upload to object storage under a content-addressed key.
5. Verify the stored object's hash matches.
6. **Then** commit the metadata row inside the job's transaction.
7. Only then mark the stage complete.

The prototype achieves the same guarantee locally with temp file → `fsync` →
atomic rename → SHA256 verify → registry commit. The property being preserved is
that a stage is never declared complete before its primary durable artifact is
committed and verified.

## Read protocol

`sha256` is verified on read. A mismatch marks the artifact `CORRUPT` and raises,
rather than returning bytes that may have been silently altered. For a system
that makes research claims, serving unverified content as a finding is worse than
an error.

Clients never receive a storage key or a filesystem path. Downloads go through
a short-lived pre-signed URL scoped to the artifact, issued only after the tenant
check.

## Reuse: where the money is saved

This is the mechanism behind the whole durability model.

```
stage inputs ──► input_fingerprint ──► existing VALID artifact?
                                        │
                              yes ──────┴────── no
                               │                 │
                      reference it        run the stage
                      (no AI call)        (AI call, then store)
```

The index `ix_artifacts_reuse` on
`(project_id, stage_type, artifact_type, input_fingerprint)` exists for exactly
this lookup. Reuse is checked across **prior revisions**, not only the current
one, which is why editing a late stage does not re-run early ones.

A reused artifact is referenced, not copied. The project overview resolves those
references so reused upstream work stays visible without duplicating bytes.

## Provenance

Every artifact records where it came from: originating revision, stage, artifact
type, input fingerprint, provider, model, prompt version, runtime version,
producing job, content hash, size, creation time. Dependency edges in
`project_artifact_dependencies` make evidence traceable — "which evidence did this
report section rest on" is a query, not an investigation.

## Lifecycle states

| State | Meaning |
| --- | --- |
| `VALID` | Verified and reusable |
| `SUPERSEDED` | A newer artifact covers the same stage and type |
| `INVALIDATED` | Its stage's inputs changed; not reusable |
| `CORRUPT` | Hash verification failed on read |

`is_approved` records human sign-off. `is_frozen` marks simulation frozen results
and approved deliverables: a frozen artifact is immutable and may not be
superseded in place, because a client has been shown it.

Sign-off requires `SIGN_OFF_DELIVERABLE` **and** independence from the producer.
Independence is the default and may be lifted only where self-approval has been
explicitly enabled by persisted policy for that organization, client or study —
never by an argument to the call. Every sign-off, self-approved or not, is appended
to `approval_decisions` with the policy in force and where it came from, so a
decision stays reconstructible after the configuration changes. See
[scope-and-authorization.md](scope-and-authorization.md).

## Storage layout

```
org/<organization_id>/proj/<project_id>/rev/<revision>/<stage_type>/<artifact_id>
```

The organization prefix is first so that bucket policies, lifecycle rules and
per-tenant metering can be expressed as prefix rules.

## Classes of data and where each belongs

The prototype accumulated persistent state across the whole application
directory. Every class now has one explicit home:

| Class | Home |
| --- | --- |
| Immutable packaged reference data (population panel, instrument library, dimension catalogue) | Versioned read-only asset bundle, mounted or fetched at deploy; never written at runtime |
| Durable application state (projects, revisions, stages, jobs, events) | PostgreSQL |
| Uploaded customer data (client datasets, attachments) | Object storage + `datasets` metadata; tenant-scoped, retention-governed |
| Generated artifacts (evidence, analysis, reports, exports) | Object storage + `project_artifacts` |
| Ephemeral cache (provider model lists, rendered map imagery — never a layout, which is a fingerprinted `SociomapArtifact`) | Recomputed on demand; no cache service is deployed, and none is planned until there is measured pressure. Any cache holding client material is itself client-derived and falls under [ADR 0008](adr/0008-eu-data-residency.md) |
| Temporary computation (checkpoints mid-fieldwork) | Worker scratch space, with the durable checkpoint in PostgreSQL |
| Secrets and configuration | Platform secret manager; environment variables at runtime; never in the repository |
| Test fixtures and demo data | Repository fixtures and a seeded demo tenant; never mixed with production state |

There is no runtime-writable application directory. A container filesystem is
treated as disposable.

## Retention and deletion

Trashing a project is a soft delete: `trashed_at` is set and nothing is removed.
Purging is a separate, deliberate action that only a trashed project accepts, and
it cascades through revisions, stages and events.

Object deletion lags database deletion: a reaper removes objects whose metadata
rows are gone. Deleting the object first would risk orphaning a live reference if
the transaction rolled back.

Frozen and approved artifacts are exempt from automatic retention. A deliverable
a client has been shown is not garbage-collected on a schedule.
