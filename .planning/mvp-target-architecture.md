# MVP target architecture (Proposed, 2026-10-19)

**What this is.** The data model, the workers, the API and the AWS structure the MVP needs, derived
from the owner's decisions of 2026-10-19 (recorded in #496, #497, #493, #494, #495). It is the
design `mvp-development-plan.md` builds in waves. It is **designed, not built**: `.planning/` holds it
until its ADRs are accepted, after which a docs PR moves what is accepted into `ARCHITECTURE.md` and
`docs/architecture/`. Where a plan file or an accepted ADR disagrees with this file, they win.

**Anchors.** A claim about code carries `file:line @ 085abe0` or names its test. **◇** marks a
hypothesis: confirm it in the chunk that needs it, never build on it unread.

---

## 1. Decisions this design implements

| Decision (owner, 2026-10-19) | Where it lands |
|---|---|
| One shared, server-validated edit vocabulary; every operation stored (F11) | §3.1, §5 |
| Per-change accept and reject inside a proposal (F11) | §3.5, §5 |
| Two researchers, each with their own Lead, one working copy; item-level merge; presence by polling (F12) | §3.1, §3.2 |
| Per-study envelope, set by the researcher up to a client ceiling, no expiry until the study closes, priced Deep Research inside, a fieldwork run through a plan card approved once (F13) | §3.3, §3.4 |
| Hard lock on Sociomap inputs with a recorded unlock (F13) | §3.8 (ledger subject), §5 |
| Each researcher's Lead proposes updates to its own files; an admin can read and hand them on (F14) | §3.6 |
| Population-built respondents by default (F15) | §4 (no schema change) |
| Two header meters, report and snapshot approvals by a second person, no pause after fieldwork, client data in the Brief and Dimensions (F16-F19) | §3.7, §3.8, §5 |
| Production: a separate environment on the one-host pattern with RDS; about 10 users; no permanent staging; tier B runs on develop | §6 |
| Models tiered by role, pinned, shown in Settings | §6.4 |
| Two to three sessions build in parallel | `mvp-development-plan.md` §2 |

## 2. Shape

```
                       Route 53 ─ Caddy (TLS, one hostname)
                            │            │
                          web (Next.js)  api (FastAPI)  ── never calls a model, never runs a step
                                              │
   EC2 host (one per environment)             │
     worker ×1-2 ── claims steps from PostgreSQL, runs executors, owns every model and search call
        │                                      │
        ├── Bedrock, EU inference profiles (application profiles, tagged)
        ├── search routes: Class C (Wikipedia, Brave), Class B EU provider (contract pending)
        │                                      │
   PostgreSQL 16  ◄───────────────────────────┘     S3: artifacts · ops · population (EU region)
   develop: container on the host                   Cognito (Google Workspace) · SSM · ECR
   production: Amazon RDS                           CloudWatch · SNS · Budgets · Route 53
```

Nothing new is added to the compute layer: no queue service, no cache, no push service (ADR 0002).
What is new is the second environment, RDS in it, tagged Bedrock profiles in both, and the tables
below. Everything keeps the existing layering (`ARCHITECTURE.md` §2): the API validates and
delegates, the application layer issues every scope and owns every use case, a repository is the only
reader and writer of its tables, a worker knows nothing about what a step does.

## 3. Data model

**Conventions every new table follows** (read from `infrastructure/tables.py @ 085abe0`): string ids
of 64 characters; `organization_id`, `client_id` and `study_id` denormalised on every row that has a
study, with `ondelete="CASCADE"` foreign keys; timestamps `DateTime(timezone=True)` defaulting to
`utcnow`; JSON as `JSONType`; every enumerated column a `CheckConstraint`; the naming convention in
`NAMING_CONVENTION`; an **insert-once** row guarded by a `before_update` listener that raises, as
`study_lead_turns` is. Each table has **one repository that is its only reader and writer**, held by
a `layer_check` rule (§8). A migration lands in the lane of `mvp-development-plan.md` §4.

### 3.1 `workspace_edit_ops`: every change to the working copy (append-only)

Why: item-level merge, undo, "what changed since my Lead's last turn", per-change accept and
attribution all need the operation, not only the resulting revision. A revision already carries
`created_by` and `reason` (`project_revisions`, `tables.py @ 085abe0`); this adds the operation.

| Column | Type | Meaning |
|---|---|---|
| `op_id` | String(64) PK | |
| `organization_id`, `client_id`, `study_id` | String(64) | scope, FKs cascade |
| `batch_id` | String(64) | operations applied in one request share one resulting revision |
| `base_revision` | Integer | the working revision the caller edited from |
| `result_revision` | Integer | the working revision this batch wrote |
| `actor_kind` | String(16) | `person` or `lead` (check) |
| `actor_user_id` | String(64) | the person, or the researcher whose Lead made it |
| `source` | String(24) | `ui`, `lead_turn`, `proposal_accept`, `undo` (check) |
| `source_ref` | String(64) NULL | Lead turn id, agent run id or the op undone |
| `item_key` | String(160) | `design_items.ItemKey` of what it touches (`occurrence_keys`) |
| `field` | String(48) NULL | the field within the item, for conflict detection |
| `op` | JSONType | one operation of the closed vocabulary (below) |
| `inverse` | JSONType | computed by code, for undo |
| `created_at` | DateTime | |

Constraints: `UNIQUE (study_id, op_id)`; index `(study_id, result_revision)` for the change feed and
`(study_id, item_key, field)` for conflicts. Insert-once. **Repository:** `WorkspaceEditRepository`.

**The vocabulary** extends the Lead's closed edit set (`domain/research_lead.py:252-296 @ 085abe0`:
`set_text`, `list_add/replace/remove`, `question_add/edit/remove`, `set_n`) with what a person can do
and the Lead cannot today: `question_move`, `question_merge`, `section_add/edit/remove/move`,
`set_add/edit/remove` (tracked sets), `route_set` (a display condition), `scale_set`, `comparison_set`.
One module, `domain/edit_ops.py` ◇ (name to be confirmed), owns it; **`apply_edit_ops` in the
application layer is the only writer** of the working copy for stages, called by the API for a person
and by the Lead's accept route for a Lead.

**The rules, written once** (this is what "one vocabulary" buys): a lock on Set 1 and the declared
Sociomap rating question refuses an operation unless it carries an unlock (§3.8); text-only
operations are the only ones an automatic accept may take (`is_text_edit`); validation is the
domain's, not the client's.

**Conflict rule.** A batch names `base_revision`. The server loads the operations after it that
touch the same `(item_key, field)`. None: apply the batch to the *latest* working copy (a merge, not
a refusal) and answer `merged: true`. Some: refuse with `409 edit_conflict` listing them, so the
screen shows the conflict on that item alone. Today any stale base is refused whole
(`infrastructure/study_workspace_repository.py:234-271 @ 085abe0`, `stale_revision`); that route
stays for whole-copy writes (an import, a migration).

### 3.2 `study_presence`: who is in the study (advisory, expiring)

`study_id`, `user_id` (composite PK), `organization_id`, `client_id`, `stage` String(32),
`element_ref` String(160) NULL, `editing` Boolean, `last_seen_at` DateTime. Written by a heartbeat
the web sends every 5 s; a row older than 20 s is not read. Never audited, never a lock. No
foreign-key chain to the ops log. **Repository:** `StudyPresenceRepository`. The change feed is a read
of §3.1 `GET …/workspace/ops?since=<revision>`; both poll (decision: no push service).

### 3.3 The envelope: `study_envelopes`, `study_envelope_raises`, `study_envelope_charges`

`study_envelopes`: `envelope_id` PK; scope; `cap_usd` Float > 0; `ceiling_usd` Float NULL (the
client's ceiling when it was set); `set_by`; `created_at`; `closed_at` NULL; `closed_reason`. A
**partial unique index** allows one open envelope per study (`WHERE closed_at IS NULL`). No expiry
(decision): it closes with the study.
`study_envelope_raises`: `raise_id`, `envelope_id`, `from_cap_usd`, `to_cap_usd`, `raised_by`,
`created_at`; insert-once. A raise above the client's ceiling is refused.
`study_envelope_charges`: `run_id` PK (FK `workflow_runs`), `envelope_id`, `plan_id` NULL,
`decision_id` (the `approval_decisions` row that authorised it), `ceiling_usd` Float, `created_at`;
insert-once. **Accounting is by cost ceiling, not by settled spend**: remaining = `cap_usd` minus the
sum of `ceiling_usd` over the envelope's charges, checked under the study row lock like a spend
confirmation, so a start never exceeds the cap and an unknown cost counts as its ceiling, never zero
(`ARCHITECTURE.md` §10). Settled spend is read from the usage ledger for display.
**Client ceiling:** a nullable column `clients.envelope_ceiling_usd`, set only by an organisation
OWNER or ADMIN; null means the envelope may not exceed the study's spend limit. The spend limit
(`PUT /studies/{id}/spend-confirm`) stays the hard stop for everything. **Repository:**
`StudyEnvelopeRepository`; it is the only code that writes the three tables.

### 3.4 The plan card: `lead_plans`, `lead_plan_steps`

`lead_plans`: `plan_id` PK; scope; `user_id` (whose Lead prepared it); `turn_id`; `envelope_id` FK;
`design_revision_id`; `workspace_revision`; `steps` JSONType (frozen at proposal, at most 12, each a
typed step: `agent_job`, `research_run`, `deep_research`, `interpretation_research`, with its own
`ceiling_usd`); `cost_ceiling_usd`; `status` (`PROPOSED`, `APPROVED`, `RUNNING`, `DONE`, `STOPPED`,
`REFUSED`); `decided_by`, `decided_at`, `stopped_reason`. `lead_plan_steps`: `(plan_id, step_index)`
PK, `status`, `run_id` NULL, `started_at`, `finished_at`. A plan is bound to the revisions it was
prepared on; if the working copy or head revision moves, the plan is `STOPPED` with that reason, never
re-read as current (the stale rule, `application/proposal_accept.py`).

**How a plan runs.** Approving it (a person, `APPROVE_GATE`, one ledger row `lead_plan`) creates a
workflow of a new closed type, `lead_plan` (`domain/workflow_templates.py:126-264 @ 085abe0` is where
types are defined), one step kind `lead_plan_step` per plan step, each depending on the previous. The
executor starts the child (an agent job, a run, a Deep Research run) through the application layer
under a **plan authority**: a capability `ScopeResolver` issues only against a held lease and an
`APPROVED` plan row, which can start what the frozen step names and nothing else, holds no
`APPROVE_GATE`, and writes `study_envelope_charges` and a ledger row naming the plan. A step that
reaches a gate no plan approval covers (a budget lift, a report approval, an unlock, a spend
confirmation when the run's ceiling reaches the limit) **parks** and waits for a person; it is never
skipped. This is the content of the orchestration-scope ADR.

**A run started by asking (owner, 2026-10-19).** Inside an open envelope a person's own request starts
a job without a plan card: asking is authorising, one ledger row `chat_start` naming the person's
message, the envelope charged by the job's ceiling. A Lead-initiated start still needs an approved
plan. **Security condition, proposed:** the server, not the model, must establish that the *person*
asked. A model's reading of a message is not enough, because text the Lead has read (a client
document, a Deep Research source, a pasted brief) can carry instructions that make it "decide" the
person asked. So the by-request path accepts only a **typed command** the web sends from the
composer's quick action (for example `start_run` with the revision it names), which the server
executes directly under the envelope; free text still goes to the Lead, which prepares a card. The
request names the exact revision, never "the latest". The spend confirmation of ADR 0019 gate 2
(a run whose ceiling reaches the spend limit) still needs its own confirmation.

### 3.5 Per-change accept: `proposal_change_decisions`

`run_id` (the agent or Design Research job), `change_id`, `decision` (`ACCEPTED`, `REJECTED`,
`DROPPED_STALE`), `decided_by`, `decision_id` (the ledger row), `created_at`; PK `(run_id,
change_id)`; insert-once. `proposal_state` (`domain/research_agents.py`) gains `ACCEPTED_IN_PART`;
unaccepted changes are `REJECTED` or `DROPPED_STALE` by default (the owner's default, open to
change). `accept_into_working_copy` takes `change_ids`, merges only those items
(`domain/design_items.py` `merge_items`), and writes one revision, one ledger row and the ops of §3.1
in one transaction under the study lock. **Repository:** `ProposalChangeRepository`.

### 3.6 The Lead over time: `researcher_lead_signals`, handover columns

`researcher_leads` (`ResearcherLeadRow @ 085abe0`: `name`, `soul` ≤ 2000, `user_profile` ≤ 2000;
revisions in `researcher_lead_revisions`; notes in `researcher_lead_memories`) gains `archived_at`
NULL and `derived_from_lead_id` NULL (a handed-on Lead is a **copy** with personal notes removed;
the departed researcher's row is archived, not reassigned).
`researcher_lead_signals`: `signal_id`, `lead_id`, `organization_id`, `user_id`, `kind` (`undid_lead_edit`,
`rejected_lead_proposal`, `repeated_instruction`), `ref` JSONType (ids only, never text),
`created_at`, `consumed_turn_id` NULL. A signal is written synchronously by the application layer
when a person undoes a Lead's operation (§3.1) or rejects its proposal; the Lead's next turn sees the
unconsumed ones, may prepare a `self_update` card ("Remember this"), and the researcher decides it
(`lead_self_update`, as built). A periodic review is **computed, not stored**: due when 10 unconsumed
signals exist or 30 days have passed. **Rule and test:** a signal and a personal file hold no client
name or number (personal files are Class C, client notes Class A: `domain/research_lead.py:18-30`).
**Admin read and handover:** new `access_audit` actions `LEAD_FILES_READ` and `LEAD_HANDED_ON`, an
organisation OWNER or ADMIN permission distinct from the one Researcher role (ADR 0019); conversation
**turns stay private** (decided: an admin reads files and notes only); a handed-on Lead is a copy and the departed
researcher's Lead is archived, never reassigned.

### 3.7 Client data: `client_data_contracts`, `client_dataset_copies`

`client_data_contracts`: `contract_id`, `organization_id`, `client_id`, `source_id` (the client's
source), `version`, `period_start`, `period_end`, `unit` String, `columns` JSONType (per column: name,
meaning, `classification` `personal` or `not_personal`, `used` Boolean), `use_rights` Text,
`quality_report` JSONType (computed by code), `accepted_by`, `accepted_at`; insert-once; unique
`(source_id, version)`. **Only columns the contract names `used` and `not_personal` are copied**: an
allowlist, not the preview's personal hints (`domain/client_datasets.py:9-14 @ 085abe0` calls them
hints). `client_dataset_copies`: `copy_id`, `contract_id`, `artifact_key`, `sha256`, `rows`,
`columns_kept` JSONType, `created_at`; the copy is an artifact under
`org/<org>/client/<client>/datasets/<sha256>/` in the artifacts bucket, verified on every read. A
contract is **not** used until `accepted_at` is set. The evidence policy for these columns is the
deferred decision of `client-data-in-analysis` chunk 0. **Repository:** `ClientDataContractRepository`
(never read by the API, the worker or the executors directly; same rule as `ClientSourceRepository`).

### 3.8 Existing tables that change

| Table | Change | Reason |
|---|---|---|
| `approval_decisions` | extend `approval_subject_type_known` (`tables.py @ 085abe0`) with `envelope`, `lead_plan`, `plan_step`, `chat_start`, `data_contract`, `map_snapshot`, `sociomap_unlock` | each human act is one ledger row; **one early migration adds all seven so later migrations do not collide** |
| `clients` | add `envelope_ceiling_usd` NULL | §3.3 |
| `researcher_leads` | add `archived_at`, `derived_from_lead_id` | §3.6 |
| `ai_usage_events` | ◇ add `inference_profile_arn` if `model`/`served_model` do not carry it | reconcile the ledger with the tagged AWS cost (`develop-spend-attribution`) |
| `workflow_runs` | none: a `lead_plan` is a new workflow type, not a column | closed set of types |

**New artifact types** (no table): `research_run_qc`, `research_segment_maps`, `research_map_snapshot`
(approved through the existing artifact approval, so a snapshot is an approvable object),
`client_dataset_analysis_copy`, `client_dataset_computations`. **New evidence origin:**
`CLIENT_REPORTED` in `domain/fieldwork.py` (ADR 0027).

## 4. Workers and executors

Step kinds today are set in `domain/workflow_templates.py` and registered in
`apps/executors/.../registry.py` (compile, preflight, fieldwork, aggregate, sociomap, analysis,
report, `research_agent`, `research_lead`, the six Deep Research kinds, `population_materialize`,
`client_source_proposals`, report PDF). The MVP adds:

| Kind | Does | Model? | Switch (off by default, off in test) |
|---|---|---|---|
| `lead_plan_step` | starts one child under the plan authority (§3.4) | no | `AIA_LEAD_PLANS_ENABLED` |
| `research_qc` | run QC from the stored dataset, warnings only (MVP-24) | no | `AIA_RUN_QC_ENABLED` |
| `research_segment_maps` | one map per segment through the existing engine | no | rides the Sociomap pin |
| `client_data_prepare` | builds the analysis copy from the contract's allowlist | no | `AIA_CLIENT_DATA_ENABLED` |
| `client_data_compute` | descriptive tables and benchmark gaps | no | same |
| `research_agent` actions `interpret_map`, `polish_report`, `flag_straightliners` | the three new workers (MVP-12), each a closed task | yes | `AIA_AI_RESEARCH_WORKERS_*` |

**One worker row, written once** (`mvp-cohesion.md` F5): id, closed task, context layer, data-class
rule (`material_rules`), capability, reservation, prompt id and pinned version (editable in Settings,
ADR 0020), switch, card kind, result kind. The eight existing actions and the three new ones are
rows; Settings' `ai_runtime` document reads the list, so no screen names a worker by hand.
**Respondents:** population-built by default needs `AIA_AI_POPULATION_PERSONAS_ENABLED` on in every
deployed worker and the panel path composed; the invented roster stays in tests and the workbench.

## 5. API surface (all study-scoped under `/api/v1/studies/{study_id}/…`)

| Route | Does | Needs |
|---|---|---|
| `POST workspace/ops` | apply a batch of operations on a base revision; `merged` or `409 edit_conflict` | `EDIT_STUDY` |
| `GET workspace/ops?since=` | the change feed with authors | member |
| `PUT/GET presence` | heartbeat and who is here | member |
| `GET/PUT envelope`, `POST envelope/raise` | the envelope; raise up to the client ceiling | `EDIT_STUDY`; ceiling set by admin |
| `POST lead/plans` (from a turn), `POST lead/plans/{id}/approve`, `…/stop` | the plan card | `APPROVE_GATE` |
| `POST lead/commands` ◇ `{command: start_run, revision_id}` | a typed quick action starts a job inside the envelope; ledger `chat_start`; the model is not in the path | `APPROVE_GATE` |
| `POST agent-jobs/{id}/accept` with `change_ids` | per-change accept (extends today's accept) | `APPROVE_GATE` |
| `GET research/runs/{id}/respondents/{rid}` | the drill-down: one respondent, labelled modelled, never exported | `EDIT_STUDY` |
| `GET research/runs/{id}/map/filters` | aggregates for a filter set, never rows | `EDIT_STUDY` |
| `POST research/runs/{id}/snapshots/{sid}/approve` | approve a map snapshot, second person | `APPROVE_GATE` |
| `POST …/sociomap-unlock` | "Unlock for this revision": warns, one ledger row `sociomap_unlock`; the Lead can never call it | `APPROVE_GATE` |
| `PUT /clients/{id}/datasets/{source_id}/contract` | accept a data contract | `PROPOSE_CLIENT_KNOWLEDGE` ◇ |
| `GET/PUT /organization/clients/{id}/envelope-ceiling` | the client ceiling | org OWNER or ADMIN |
| `GET /admin/leads/{user_id}`, `POST /admin/leads/{user_id}/handover` | admin reads Lead files, hands one on | org OWNER or ADMIN |

Every route is in `.github/workflows/ci.yml`'s `api-contract` list with the study-scoping assertion.

## 6. AWS structure

### 6.1 What exists (develop)

One Terraform root `infra/develop/` (`main.tf`, `identity.tf`, `github.tf`, `variables.tf`): S3
buckets `artifacts`, `ops`, `population` (versioned, encrypted, TLS-only, lifecycle), ECR, SSM
parameters, an EC2 host (`t3a.medium` default) with an instance role and EIP, Route 53 records,
Cognito user pool with Google as the identity provider, a DLM snapshot policy, a CloudWatch log
group, an SNS alert topic and three alarms (system check, disk, CPU), an AWS Budget; Compose runs
caddy, web, api, worker and a PostgreSQL container with a nightly `pg_dump` to S3
(`deploy/develop/`). The account, the region (`eu-central-1`) and "no modules" are decided
(ADR 0008, 0009).

### 6.2 Production: a second root, `infra/production/`

Same pattern, three differences: **RDS replaces the Postgres container**; its own Cognito pool, host,
buckets, Bedrock profiles and OIDC deploy role; a **manual approval gate** before deploy.

| Resource | Production setting (proposed; ◇ = measure first) |
|---|---|
| Host | `t3a.large` ◇ for web, api and worker(s) (about 10 users); EBS encrypted, DLM snapshots |
| RDS PostgreSQL 16 | `db.t4g.medium` ◇, single-AZ, private subnets, security group open only to the host, KMS encryption, 14-day point-in-time recovery, automated snapshot before every migration, deletion protection |
| S3 | `artifacts`, `ops`, `population`, same policies as develop; a separate bucket per environment |
| Cognito | own user pool and client, Google Workspace federation, callback URLs for the production hostname |
| Secrets | SSM SecureString: database URL, Class B provider key, Brave key; read by the instance role only |
| Deploy | `deploy-production.yml` on `main`, a GitHub environment with required reviewers, OIDC role scoped to that environment; migrations run once as a distinct step after an RDS snapshot; smoke; no automatic rollback of a migration |
| Alarms | the three develop alarms plus RDS CPU, free storage and connections; an alarm on the oldest `QUEUED` step age (custom metric from `WorkQueue`) ◇ |
| Budgets | AWS Budget with the `Environment` tag filter, alerting to the SNS topic |

**Production shares develop's AWS account** (owner, 2026-10-19; a separate account was recommended, so
the risk is written here, not left implicit). A mistake in an account-level setting, a leaked
credential or a shared quota can reach production. What this design does about it, all in Terraform:
separate subnets and security groups per environment; an IAM role per environment whose policies are
conditioned on the `Environment` resource tag and carry a permission boundary, so a develop role cannot
touch a production resource; the deploy role of each GitHub environment assumable only from that
environment; a KMS key, a Cognito pool, an S3 bucket set, an RDS instance and a Terraform state
(with its own lock) per environment; S3 bucket policies that deny the other environment's roles; AWS
Budgets filtered by the tag; CloudTrail on for the account. **What it does not fix:** Bedrock quotas
are account-wide, so a tier B run on develop and production use draw on the same limits (run tier B
outside working hours and cap develop's concurrency), and an account-level IAM mistake still has no
second boundary. Revisit the separate account at the first incident or the first client-facing
release.

**Still open:** the production hostname; whether `infra/production` is a copy of `infra/develop` or a
shared root with two variable sets (the "one root, no modules" rule of ADR 0009 favours a copy with a
documented diff).

### 6.3 Not added, on purpose

No SQS or Redis (ADR 0002), no push service (presence and the change feed poll), no Fargate, no
load balancer, no WAF, no staging environment (develop is staging, tier B runs there).

### 6.4 Bedrock: application inference profiles, tagged, per tier

One application inference profile per model in use, over the system EU profile, tagged
`Environment=develop|production`, so AWS cost can be filtered to an environment and reconciled with
AIA's ledger (MVP-30; `develop-spend-attribution`). Today Terraform grants the instance role invoke on
two profiles, the main model and the Lead's (`infra/develop/main.tf:34, 39 @ 085abe0`).

| Tier | Roles | Pinned in | Profile count |
|---|---|---|---|
| Top | the Lead, the eight analysis modules, the report writer, the map interpreter | the model policy, shown in Settings | 1 |
| Mid | the design workers (brief analysis, build and optimise questionnaire, audience, dimensions, critique, copilot, memory answer) | same | 1 |
| Small | AI respondents, the straight-liner check, Deep Research's light triage (`LightModelSettings`, `apps/executors/src/aia_executors/ai_runtime.py:187 @ 085abe0`) | same | 1-2 |

Every profile used by the acceptance run is tagged, IAM-granted and in the registry; a model left
untagged still enters the ledger and breaks the reconciliation. The exact model per tier is set by
measurement on the first acceptance runs (open).

### 6.5 Search and egress

Class C routes (Wikipedia, Brave) as today; the Class B EU provider (candidate Linkup, owner's
contract pending) is one more route behind `RetrievalGate`, credential by reference. The host's
security group allows egress to Bedrock, the S3 and SSM endpoints and the named search hosts; the
list is a Terraform variable, reviewed with the provider contract.

## 7. Sequences

**A person edits a question.** Web sends `POST workspace/ops {base_revision, ops[]}` → API validates
shape → `apply_edit_ops` (application) locks the study row, checks the lock and the vocabulary,
detects conflicts against `workspace_edit_ops` since the base, writes one working revision and the
ops → answers `{revision, merged}` → the other researcher's poll sees it in the change feed.

**Two researchers, same question.** Second batch finds the first's op on the same `(item_key, field)`
→ `409 edit_conflict` with that op → the screen marks that question, offers "keep mine", "keep theirs"
(a new op), nothing else is blocked.

**A Lead proposal, accepted in part.** The worker writes a proposal; the web shows change blocks;
the person accepts three of five → `POST accept {change_ids}` → under the study lock: stale check per
item, merge those items, one revision, `proposal_change_decisions` rows, one ledger row, ops with
`source=proposal_accept` → the other changes are `REJECTED` or `DROPPED_STALE`.

**A plan card.** The Lead's turn proposes a plan inside the envelope → the card shows steps and the
cost ceiling → the person approves (`lead_plan` ledger row) → a `lead_plan` workflow starts → each
`lead_plan_step` starts its child under the plan authority, charging the envelope by ceiling → a gate
the plan does not cover parks the step and shows a card → on the last step the plan is `DONE`.

**The Lead learns.** A person undoes a Lead edit → a `researcher_lead_signals` row (ids only) → the
Lead's next turn sees it and may prepare a "Remember this" card (`self_update`) → the researcher
accepts, edits or refuses (`lead_self_update`) → a `researcher_lead_revisions` row, rollbackable.

**A client dataset reaches an analysis.** Brief materials picks the source → the contract drawer shows
the preview, the person classifies each column and accepts (`data_contract` ledger row) →
`client_data_prepare` copies the allowlisted columns → `client_data_compute` writes the computations →
evidence admits them as `CLIENT_REPORTED` (policy decision pending) → shown beside the modelled results.

**A report is delivered.** Internal report approved by a member; the client report and each map
snapshot approved by a reviewer other than the producer (`approval_decisions.self_approved` false,
unconditional for client-facing) → DOCX and PDF become downloadable only after approval.

## 8. Layering and CI additions

New `layer_check` rules, each added once it passes (`ARCHITECTURE.md` §3 ratchet): the ops log, presence,
envelope, plan, proposal-change, lead-signal and data-contract tables are reached only through their
repositories; the working copy is written only by `apply_edit_ops`; the plan authority is issued only
by `ScopeResolver` and never carries `APPROVE_GATE`; the API never starts a plan step. CI additions:
`tests/acceptance` in the collect-only pass and a JUnit step (`mvp-acceptance-harness` chunk 3);
`alembic heads` is a single head (a check on every PR); `infra/production` validated by `terraform
validate` in the docs-and-config job.

## 9. Open decisions and risks

| # | Open | Who | Blocks |
|---|---|---|---|
| 1 | ~~Separate AWS account for production~~ **decided 2026-10-19: the same account**, with the mitigations in §6.2 | owner | none |
| 2 | Production hostname, Cognito pool, Google Workspace callbacks | owner and an operator | production deploy |
| 3 | RDS and host sizing (◇ measured on develop under the acceptance run) | an operator | production deploy |
| 4 | Bedrock quota for the chosen models (about 10 users) | an operator | tier B |
| 5 | Which model per tier | owner, by measurement | worker waves |
| 6 | The Class B provider and contract | owner | Deep Research live |
| 7 | Derived-query class: amendment and data owner | owner, data owner | `class-b-search-route` 6 |
| 8 | Evidence policy for client columns | owner | `client-data-in-analysis` 4-5 |
| 9 | ~~Whether a plain chat request starts a run without a plan card~~ **decided 2026-10-19: yes**, through a typed command the server matches (§3.4 security condition, to confirm in the ADR) | owner | none |
| 10 | ~~Admin read: do turns stay private; what handover means~~ **decided 2026-10-19: turns private; handover is a copy** | owner | none |
| 11 | ~~Retention~~ **decided 2026-10-19: kept until a person deletes it; the log is kept with its study.** A documented **delete path** (database cascade, S3 prefixes, RDS snapshot retention of 14 days stated) is needed before production | owner | production release |

**Risks.** The ops log makes every edit a write: volume is human-paced and small, but it needs an
index plan and a test at 10 000 operations ◇. A plan authority is a new kind of capability: it is the
riskiest piece to build and gets the most tests and a kill switch. Production on one host is a single
point of failure: RDS protects the data, not availability; accepted for an internal tool at about 10
users, revisited at the first outage or the first request for more users.
