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

## Also implemented

**Identity and scope.** `organizations`, `users`, `organization_members`,
`clients`, `studies`, `client_grants`, `study_grants`, `access_audit`.

`organizations`, `clients` and `studies` each carry a nullable
`allow_self_approval`. Nullable at every level so the hierarchy **inherits**
rather than duplicates: NULL means "ask my parent", and resolution is
`study > client > organization > false`. A copied-down boolean would mean enabling
self-approval for an organization silently failed to reach clients created
earlier. See [scope-and-authorization.md](scope-and-authorization.md).

**Durable workflows.** `workflow_runs`, `step_runs`, `step_dependencies`,
`step_attempts`, `budget_reservations`, `workflow_gates`, `workflow_events`.

`step_attempts` is **append-only**: each attempt keeps its own error, provider,
model, cost and timing, where the prototype kept a counter and the latest error
only. `budget_reservations` carries the `SETTLED_UNCERTAIN` status that makes a
possibly-billed call show as spent rather than available.

Run and step `status` are unconstrained `String(32)` rather than check-constrained
enums, deliberately: the state vocabulary has already been revised once
(`WAITING_GATE` → `AWAITING_GATE`, and the provider/capacity split), and a check
constraint turns each such revision into a constraint rebuild on a live table for
no gain the application layer does not already provide.

**Approvals.** `approval_decisions`, append-only, one row per gate decision and
artifact sign-off. Every field is denormalised onto the row on purpose: resolving
the policy again at read time would answer what the policy is *now*, not what it
was when somebody cleared a client deliverable.

**AI usage ledger.** `ai_usage_events`, append-only. Every model call writes a
`DISPATCHED` row **before** it is sent and a terminal row (`SUCCEEDED`, `FAILED`,
`UNCERTAIN`) after; a resolved uncertain call gains a `RESOLVED_*` row with
`cost_basis = COMPENSATION` naming what it `supersedes`. `(call_id, outcome)` is
unique, so no entry can be counted twice. A check constraint allows a negative
`cost_usd` only on a compensation. Token columns are nullable because "not
reported" is not zero. The study foreign key deliberately does **not** cascade: a
study with ledger entries cannot be deleted out from under its accounting record.
Attribution columns come from the egress decision, computed from an issued
`StudyContext`. See [ai-runtime.md](ai-runtime.md).

**A research Study's design and working content.** Two rows per research Study at
most, each pointing at an *owned* project (`projects.owner`), so the generic project
routes can neither see nor write them:

| Table | Holds | Rule the schema enforces |
| --- | --- | --- |
| `study_designs` | The Study's design project; its immutable revisions are the Design Revisions runs execute (ADR 0016) | `project_id` unique, RESTRICT on delete: an executed design cannot vanish |
| `study_workspaces` | The Study's working content: `content_state` (`EMPTY`, `NATIVE`, `MIGRATED`, `RECOVERED`, `UNRECOVERABLE`, `AWAITING_MIGRATION`), the working project (`project_id`, owner `study_workspace`), `lineage` (where migrated content came from), `last_stage` (ADR 0018) | `project_id` unique, RESTRICT on delete; a state with content has a project and one without has none (`content_state_matches_project`); `unit_project_id` unique and **lineage only** -- the 18.6.6 project a Study was bound to before ADR 0018, never a lookup key |

Every save of the working content is a `ProjectRepository.save` on the working
project: an immutable `project_revisions` row when content or analysis changed,
nothing when neither did, with its `project_events` entry. A save names the
revision it was edited from; a stale one is refused under a lock on the Study row
(`test_two_editors_saving_from_one_revision_cannot_overwrite_each_other`).

A file the brief carries is a `project_artifacts` row of the working project
(`artifact_type = STUDY_ATTACHMENT`, stage `BRIEF`) whose bytes are in the artifact
store under the Study's prefix, uploaded and read back before the row is written, as
every artifact is. The brief's `attachments[]` keeps the record (`attachment_id` is
the artifact id); nothing stores a URL. Removing a record from the brief leaves the
artifact, as 18.6.6 left the file.

Content migrated from 18.6.6 (ADR 0018 decision 2) is the same shape. Revision *k* of
the working project is the unit's *k*-th, with `reason` `unit:<the unit's reason>` and
`created_by` null (the unit recorded no author); one `WORKSPACE_MIGRATED` event names
the person who ran it. A migrated file is an attachment artifact whose metadata keeps
`legacy_attachment_id`, `legacy_stored_name`, `named_in_brief` and `migrated_from`; its
brief record keeps `legacy_attachment_id` beside the artifact's `attachment_id`. The
Study's `lineage` records `source`, `unit_project_id`, `outcome`, `migration_version`,
`migrated_at`, `migrated_by` and, for a migrated Study, each revision's unit id,
timestamp, reason and hash, the unit title and trash mark, and which files came over or
did not; for a recovered one, the Design Revision it came from.

**Population registry.** `population_dataset_versions`, `populations`,
`population_promotions`, `population_companion_sets`, `population_companion_assets`,
`run_population_bindings`. Platform reference data, so the
first three carry no organization, client or study; the binding hangs off
`workflow_runs` and inherits its scope.

| Table | Rule the schema enforces |
| --- | --- |
| `population_dataset_versions` | **Insert-only.** `content_sha256` unique (same bytes never registered twice); `(dataset_id, label)` unique (a label never re-pointed); `parent_version_id` self-FK without cascade; the import report kept in `validation_json` |
| `populations` | One `STATIC` and one `LIVE` per dataset (`population_one_per_kind`). `current_version_id` is the single answer to "which population is in use" |
| `population_promotions` | **Append-only.** `from_version_id` NULL for the establishing entry. SUPERSEDED is derived from this table, never stored |
| `population_companion_sets` | **Insert-once** per version: the companion-set digest, the joint-certificate state and the report it was accepted on. A version whose contract declares companions is unusable without one |
| `population_companion_assets` | Each companion's SHA256, size and location, re-verified on every load |
| `run_population_bindings` | One row per run (PK `run_id`), never updated, cascades with the run. Every binding field denormalised — including `dictionary_sha256`, `field_policy_version`, `companion_set_sha256` and `joint_state` — so the record still says what the run used, and under which rules, after later promotions |

Promotion is a compare-and-set `UPDATE … WHERE kind = 'LIVE' AND
current_version_id = :expected` under a row lock, so concurrent promoters get
exactly one winner (`test_concurrent_live_promotions_have_exactly_one_winner`) and
a STATIC pointer can never be written after establishment. The panel **bytes**
never live here: `storage_location` points into the population asset store, and
every load re-verifies the bytes against `content_sha256`.

## Planned tables

Sequenced by phase; see [../migration/migration-plan.md](../migration/migration-plan.md).

**Phase 4 — AI runtime**
`api_credentials` (provider keys, encrypted at rest, never returned by any API),
and the extension of the metered-cost ledger from model calls (`ai_usage_events`,
implemented) to every other metered source — research, search and retrieval APIs,
paid datasets — attributed down to `Client → Study → Revision → WorkflowRun →
Step → Agent/Tool/Call`, with corrections as compensating entries rather than
edits.
`egress_decisions`, recording what left AIA, under which classification and over
which approved route, per [adr/0008](adr/0008-eu-data-residency.md).

**Phase 5/6 — research outputs**
`datasets` (uploaded client data), `respondent_runs`, `aggregations`,
`analysis_modules`, `reports`.

**Phase 8 — data library**
`library_sources`, `library_evidence`, `evidence_proposals`, `dimensions`,
`results_registry`. (`population_revisions` is superseded by the implemented
population registry above: a new LIVE revision is a new dataset version plus an
explicit promotion.)

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
