# Data model

PostgreSQL is the durable source of truth. Artifact bytes live in object storage;
everything else lives here.

Schema: `packages/aia_core/src/aia_core/infrastructure/tables.py`.
Migrations: `migrations/versions/`.

## Implemented tables

### `projects`

The mutable project header. Content is **not** stored here — it lives in
revisions — so this table is small and safe to update frequently.

| Column | Notes |
| --- | --- |
| `project_id` | PK, `PRJ-` + 14 hex. Format kept from the prototype so operators and legacy exports stay comparable |
| `organization_id` | **The tenant boundary.** Every repository query filters on it |
| `project_type` | `research` \| `simulation`, check-constrained |
| `status` | `DRAFT`, `READY_TO_CONTINUE`, `RUNNING`, `WAITING`, `COMPLETED`, `FAILED`, `ARCHIVED`, `TRASHED` |
| `current_revision` | Pointer into `project_revisions`; `0` means no content yet |
| `current_stage`, `last_completed_stage` | Where the user resumes |
| `preferred_provider`, `provider_policy`, `max_api_cost_usd` | Cost and provenance controls |
| `trashed_at` | Soft delete. A hard delete requires a separate, deliberate purge |

Indexes: `(organization_id, modified_at)` for the portfolio listing — the hottest
read path — and `(organization_id, status)`.

### `project_revisions`

Immutable content snapshots. There is no update path; a correction creates a new
revision.

| Column | Notes |
| --- | --- |
| `(project_id, revision)` | Composite PK. `revision` starts at 1, check-constrained |
| `revision_id` | Opaque `REV-` id, unique, for external reference |
| `parent_revision` | Forms the revision chain |
| `content_sha256` | **The deduplication key.** An autosave whose content hashes to the current revision creates no row |
| `content` | JSONB on PostgreSQL, JSON elsewhere |
| `changed_fields`, `impact` | What changed and what it invalidated, recorded for audit |
| `reason` | `project_created`, `autosave`, `branch`, … |

Index: `(project_id, content_sha256)` for dedup lookups.

### `project_stages`

Stage state **per revision**, not per project, because "what was stage X's state
at revision N" is a question the product asks.

| Column | Notes |
| --- | --- |
| `(project_id, revision, stage_type)` | Composite PK |
| `ordinal`, `label` | Pipeline position and Czech display label |
| `status` | The `StageStatus` enum, including the three `WAITING_*` parked states |
| `input_fingerprint` | **The reuse key.** Artifacts are valid only while inputs still hash to this |
| `provider`, `model` | What produced the stage's work |
| `current_job_id`, `last_checkpoint` | Resume pointers, cleared on carry-forward |
| `waiting_reason`, `quota_reset_at` | Why it is parked and when to retry |
| `artifact_ids` | Denormalised list for fast stage rendering |

### `project_artifacts`

Metadata and provenance. **Bytes are not here** — `storage_key` points into
object storage.

Provenance columns exist so that every generated output can answer "what produced
this, from what inputs, on which provider and model, and when":
`input_fingerprint`, `provider`, `model`, `prompt_version`, `runtime_version`,
`produced_by_job_id`, `sha256`, `created_at`.

`sha256` is verified on read, so a corrupted or replaced object is detected rather
than served as valid research output. `is_approved` and `is_frozen` support the
human sign-off gate and simulation frozen results.

Index `ix_artifacts_reuse` on `(project_id, stage_type, artifact_type,
input_fingerprint)` serves exactly one query: *is there a valid artifact of this
type for this stage with this input fingerprint?* That query is the money-saver.

### `project_artifact_dependencies`

Edges in the artifact dependency graph, for evidence tracing — "which evidence
did this report section rest on".

### `project_events`

Append-only project history and audit trail. Never updated, never deleted. This
is what answers *"why did project X stop during stage Y?"* without opening files
on a server. Carries `actor_id` and `request_id` so a history entry ties back to
the log stream.

### `project_provider_events`

Audited provider usage and every switch. `explicit_user_action` is the column that
proves the no-silent-fallback rule held: a switch with that flag false **and** a
cost attached is a bug, and it is queryable.

Also carries `input_tokens`, `output_tokens`, `estimated_cost_usd`,
`actual_cost_usd` — the basis of AI cost observability.

## Planned tables

Sequenced by phase; see [../migration/migration-plan.md](../migration/migration-plan.md).

**Phase 1 completion — identity**
`organizations`, `users`, `organization_members` (role per tenant),
`api_credentials` (provider keys, encrypted at rest, never returned by any API).

**Phase 3 — durable workflows**
`workflows`, `jobs`, `job_dependencies`, `job_attempts`, `job_events`,
`approvals`, `schedules`, `schedule_occurrences`, `cost_reservations`,
`worker_state`. Modelled on the prototype's `job_store.py`, which already has
leases, heartbeats, idempotency keys and cancellation — the design is sound and
survives; only the storage engine changes.

**Phase 5/6 — research outputs**
`datasets` (uploaded client data), `respondent_runs`, `aggregations`,
`analysis_modules`, `reports`.

**Phase 8 — data library**
`library_sources`, `library_evidence`, `evidence_proposals`, `dimensions`,
`population_revisions`, `results_registry`.

**Phase 9 — visualisation**
`saved_segments`, `visualization_specs`, `visualization_layouts`,
`segment_intelligence`.

## Conventions

**Timestamps** are always `TIMESTAMP WITH TIME ZONE` and always UTC. The
prototype stored naive local-time strings, which made audit ordering and
scheduling ambiguous across timezones.

**JSON** uses `JSON().with_variant(JSONB, "postgresql")`, so PostgreSQL gets
indexable binary JSON while SQLite still works for offline unit tests.
`migrations/env.py` renders this variant explicitly because Alembic's default
rendering emits an un-importable `astext_type=Text()`.

**Constraint naming** follows an explicit convention in `NAMING_CONVENTION`, so
Alembic generates stable reviewable names rather than database-assigned ones.

**Foreign keys** cascade on delete. SQLite ignores foreign keys unless
`PRAGMA foreign_keys=ON` is set per connection, which
`aia_core.infrastructure.db` does — without it, development would silently accept
writes PostgreSQL rejects and leave orphans where production cascades.

**No enums in the database.** Status columns are `VARCHAR` validated by the
domain layer. A PostgreSQL `ENUM` requires a migration to add a value, and the
stage status set is still evolving during migration.

## Migration workflow

```bash
make migration m="add jobs table"   # autogenerate from model changes
make migrate                        # apply
```

CI runs `alembic upgrade head`, then `alembic check` to fail on model/schema
drift, then `downgrade base` and `upgrade head` to prove reversibility.
