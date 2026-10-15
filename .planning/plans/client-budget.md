---
status: in-progress
chunks:
  - "[x] CB1. The client's budget: clients.budget_usd / spent_usd, VIEW_CLIENT_COSTS and MANAGE_CLIENT_BUDGET, GET/PUT /clients/{id}/budget audited, shown and set on Profil"
  - "[x] CB2. Client-paid runs in the schema: one payer per project, run, hold, usage row and approval (study or, when none, the client), the client_sources owner; the repository's hold, charge and close paths read the payer"
  - "[x] CB3. A run's payer in the worker: ScopeResolver issues a ClientWorkContext against a held lease; reserve, settle and charge the client; the gateway, egress and usage ledger take either payer"
  - "[x] CB3b. Starting the client's own work: a client_sources project and a run created by a person under a ClientWorkContext issued for RUN_CLIENT_WORK"
  - "[x] CB4. Over budget: a client run parks AWAITING_BUDGET and a person lifts it from the client, recorded in the approval ledger"
  - "[ ] CB5. Proof: a scripted paid step charged to a client end to end on SQLite and PostgreSQL; Doc follow-up (lifecycle K2d pays from the client)"
---
# A client's own budget

**Owner:** client workspace. **Started:** 2026-10-15.

## Why

Client-level AI work (lifecycle K2d, AI proposals from a client's document; later K2e, a link
captured) has no study to pay for it. The owner's open question before K2d was who pays. The
answer (owner, 2026-10-15):

- **What it pays for:** client-level AI work only. Studies keep their own budgets, unchanged; a
  client budget neither caps nor funds them.
- **How:** a real client ledger. A hold, a usage row and an approval name either a study or a
  client. No hidden "account study".

## Where cost assumes a study today

Mapped 2026-10-15 on `origin/develop` @ 7d4f1ef5. Paths under `packages/aia_core/src/aia_core/`.

- **Schema** (`infrastructure/tables.py`): `study_id` NOT NULL with an FK to `studies` on
  `projects` (104, 138), `workflow_runs` (1129, 1159), `budget_reservations` (1323, 1344),
  `ai_usage_events` (1521, 1575) and `approval_decisions` (1418, 1452). `clients` has no budget
  columns.
- **Types:** `StudyContext` checked with `isinstance` in `WorkflowRepository` (248-255),
  `ProjectRepository` (133-147), `AIUsageRepository` (187-193), `ExecutionContext`
  (`domain/ai_execution.py:105-135`) and `evaluate_egress` (`domain/residency.py:215`).
- **Lookup:** `_reserve` walks attempt, step, run, then `run.study_id` and locks the study
  (`workflow_repository.py:1086-1130`); `_charge_study` (1420-1453) is the only increment of
  `spent_usd`.
- **Worker scope:** `ScopeResolver.execution_context` joins the run to its study and returns a
  `StudyContext` (`application/scope.py:288-356`). No lease path issues anything for a client.
- **Over budget:** `BudgetExceeded` parks the step `AWAITING_BUDGET`; `resume_budget_wait`
  (2017-2090) lifts it with `APPROVE_BUDGET`, which the worker lacks, and writes a `budget`
  approval for the study.

## Shape

- **The ledger is the study ledger, with a second payer.** A hold, a usage event and an approval
  carry `study_id` or `client_id` as their payer: a CHECK holds exactly one. `client_id` is
  already NOT NULL on runs, usage events and approvals; what changes is that `study_id` becomes
  nullable there, under that CHECK. Nothing study-paid changes its rows or its behaviour.
- **A client-paid run lives in a client-owned hidden project** (`projects.owner =
  client_sources`, `study_id` NULL), the same pattern as `study_population`, one level up.
- **Scope:** a `ClientWorkContext` (domain), issued only by `ScopeResolver` against a held
  lease, carrying `WORKER_CLIENT_PERMISSIONS` (no approval, no budget management). The
  repositories, the gateway's `ExecutionContext`, egress and the usage ledger accept a
  `StudyContext` or a `ClientWorkContext`, through one `Payer` reading, never by duck typing.
- **Spend:** `clients.spent_usd` is incremented only by `_charge_client`, the twin of
  `_charge_study`, from the same settle paths.
- **Default 0.** An existing client's budget is 0, so client AI work parks `AWAITING_BUDGET`
  until a person sets one. Never a presumed allowance.
- **Who sets it:** `MANAGE_CLIENT_BUDGET`, held by the Researcher like every permission (ADR
  0019); every change is audited `CLIENT_BUDGET_CHANGED`, previous and new values.

## Chunks

### CB1. The client's budget

- Migration: `clients.budget_usd`, `clients.spent_usd` (Float, NOT NULL, default 0, both >= 0).
- Domain: `ClientPermission.VIEW_CLIENT_COSTS`, `MANAGE_CLIENT_BUDGET`; the Researcher holds both.
- Repository: `ScopeRepository.client_budget(ClientContext)` (budget, spent, reserved: 0 until
  CB3, available) and `set_client_budget`, audited.
- API: `GET /clients/{id}/budget`, `PUT /clients/{id}/budget` (`0 <= budget_usd <= 1,000,000`).
  `GET /clients/{id}` does not carry it: costs stay behind their own permission.
- Web: Profil shows the client's budget, spent and available, and sets it. The words say it pays
  for work on the client (AI z podkladů), not for its studies. Settings → Klienti does not show
  it yet: one budget read per client row, left until a client list carries costs.
- Nothing spends it yet. That is CB3.
- **Landed** (2026-10-15):
  - `ClientBudget` and the two permissions (`domain/scope.py`); `ScopeRepository.client_budget` /
    `set_client_budget` (only a real change is audited); migration `e6a8c0b2d4f1`.
  - `GET` / `PUT /clients/{id}/budget` (`routers/workspace.py`); `GET /clients/{id}` does not
    carry it.
  - Profil's *Rozpočet klienta* card, shown only with `VIEW_CLIENT_COSTS`, set with
    `MANAGE_CLIENT_BUDGET`; at 0 it says client AI work waits for a budget.
  - Tests: `packages/aia_core/tests/test_client_budget.py` (5);
    `test_client_api.py::test_a_member_sets_the_clients_own_budget_and_the_directory_does_not_carry_it`;
    `ClientFirst.test.tsx` "shows the client's own budget on Profil…" and "shows no budget to a
    person who may not see the client's costs".

### CB2. Client-paid runs in the schema

- `study_id` nullable on `projects`, `workflow_runs`, `budget_reservations`,
  `ai_usage_events`, `approval_decisions`; `budget_reservations.client_id` added; a CHECK per
  table that the payer is one or the other; `projects.owner = client_sources` exactly when
  `study_id` is NULL.
- PostgreSQL and SQLite both; the existing rows already satisfy the CHECKs.
- **Landed** (2026-10-15), with one change of shape: rather than a study-XOR-client CHECK,
  `client_id` stays NOT NULL everywhere (now on holds too, backfilled from each hold's study)
  and the payer is *the study, or, when `study_id` is NULL, the client*. Every scoped table
  then reads the same way, and a client's outstanding holds are one indexed sum.
  - Migration `f8b0d2a4c6e3`: `study_id` nullable on `projects`, `workflow_runs`,
    `budget_reservations`, `approval_decisions`, `ai_usage_events`;
    `budget_reservations.client_id` (FK, `ix_reservations_client_status`);
    `ck_projects_project_study_unless_client_owned`. Checked on PostgreSQL 16: upgrade with an
    existing hold backfilled, the CHECK refusing an ordinary project without a study,
    downgrade and upgrade again, `alembic check` clean. (A fresh SQLite `alembic upgrade`
    already fails at `6750a204efd9`, before this; SQLite runs on `create_all`.)
  - The repository's money paths, brought forward from CB3 because the types forced the
    question: `_reserve` locks and checks the payer row (study or client);
    `_outstanding_reservations(client_id=, study_id=)` sums one payer's holds;
    `_charge(hold or run)` charges the study or the client, the same atomic increment;
    `_close_open_reservations` charges a hold's payer, else the run's.
    `ClaimedWork.study_id` and `AIUsageEvent.study_id` are `str | None`.
  - Tests: `packages/aia_core/tests/test_client_paid_holds.py` (4), on SQLite and PostgreSQL;
    the reservation, concurrency, ledger and engine suites unchanged on both.

### CB3. A run's payer in the worker

- `ClientWorkContext`, `ScopeResolver.execution_context` returning it for a client run, the
  repositories and the gateway path taking it. (`_reserve` locking the client landed in CB2.)
- Creating a client run: a `client_sources` project for the client and `create_run` under a
  person's `ClientContext` with a new `RUN_CLIENT_WORK` permission. Split out as **CB3b**.
- **Landed** (2026-10-15):
  - `ClientWorkContext` (`domain/scope.py`): organization, client, actor, the worker's
    permissions, an issued grant, no study; `WorkScope = StudyContext | ClientWorkContext`;
    `payer_study_id(scope)`, the one reading of who pays.
  - `ScopeResolver.execution_context` returns a `ClientWorkContext` for a run that names no
    study: the same lease rule, the run's own client, refused when archived
    (`application/scope.py`).
  - `WorkflowRepository` takes either; under a client scope its isolation predicate is the
    client's runs with no study, and `.scope` (everything about a study) refuses by name
    (`client_work_scope`). `AIUsageRepository`, `ExecutionContext` and `evaluate_egress`
    take either; an egress decision and a usage event name no study for client work.
  - The worker: `AttemptContext.work_scope` is what paid calls run under
    (`StepModelCaller` reads it); `.scope` refuses on client work, so an executor written
    for a study fails closed there.
  - Tests: `packages/aia_core/tests/test_client_work_scope.py` (4, SQLite and PostgreSQL);
    `apps/worker/tests/test_worker_loop.py`: a paid call on the client's work charged to
    the client under the real worker loop, and one too large for its budget parked
    `AWAITING_BUDGET` while the study's $100 stood untouched.

### CB3b. Starting the client's own work

- **Landed** (2026-10-15):
  - `ClientPermission.RUN_CLIENT_WORK` (the Researcher holds it, ADR 0019);
    `ScopeResolver.client_work_context(principal, client_id)` issues a `ClientWorkContext` to a
    member who holds it, resolving the client exactly as `client_context` does; the worker's
    permissions, so the person starts and follows work and approves nothing.
  - `CLIENT_WORK_PROJECT_OWNER = "client_sources"` (`domain/scope.py`). `ProjectRepository` takes
    a `ClientWorkContext` only with that owner (`TypeError` otherwise); its isolation predicate
    is the client's projects with no study. `WorkflowRepository.create_run` under a client scope
    runs only in that project (`WorkflowNotFound` for any other) and records no study.
  - `application/client_work.py`: `client_work_project` (one per client, created on first use)
    and `start_client_work` over `start_workflow`, which now takes either scope.
  - Tests: `packages/aia_core/tests/test_client_work_start.py` (3, SQLite and PostgreSQL).

### CB4. Over budget

- A client run parks `AWAITING_BUDGET`; `lift_client_budget_wait` raises the client's budget
  and resumes the step, as a person, recorded as a `budget` approval naming the client.
- **Landed** (2026-10-15):
  - `WorkflowRepository.resume_client_budget_wait(approver: ClientContext, …)` over the same
    `_resume_budget_wait` as the study's lift (whose behaviour is unchanged): the repository's
    scope is the client's work, the approver must hold `MANAGE_CLIENT_BUDGET` on that client,
    and the `budget` approval names the client and no study.
  - `application/client_work.py`: `lift_client_budget_wait(session, client, work, run, node,
    budget_usd=, note=)`: one person's two scopes on one client; below the current budget
    refused (`BudgetNotRaised`), equal lifts without a change; checked before anything is
    written.
  - `POST /clients/{id}/work/runs/{run_id}/steps/{node_key}/budget` (`routers/workspace.py`):
    404 for a run of a study or another client, 409 `not_waiting_for_budget`, 422
    `budget_not_raised`.
  - Tests: `packages/aia_core/tests/test_client_budget_lift.py` (2);
    `test_client_api.py::test_a_member_lifts_the_clients_budget_for_its_own_waiting_work`;
    `apps/worker/tests/test_worker_loop.py::test_a_person_lifts_the_clients_budget_and_the_waiting_step_finishes_on_it`
    (parked at $1, lifted to $5, the next worker finishes it: $1.50 to the client, $0 to the
    study).

### CB5. Proof

- A scripted paid step under the real worker loop: reserved, dispatched, settled and charged
  to the client; parked when over; lifted; the study's ledger untouched. SQLite and the
  multi-process PostgreSQL suite.

## Findings

- **F-CB1. A client-source test flaked on a random id** (fixed on this branch).
  `test_client_sources.py::test_a_source_is_not_knowledge_and_no_study_reads_it` asserted that
  the digits `7319` from a client's file never reach a study's snapshot; a fresh item id
  (`KNW-e3170301731944`, hex) contained them, so the test failed on a correct snapshot (one
  SQLite run, 2026-10-15). Fixed by a marker of letters outside hex (`qzxw`). The test that
  would have caught it: the same test, run until an id collided; the rule is "a marker must
  not be producible by an id generator".
- **F-CB2. A fan-out slot test asserts timing, not only the limit** (found here, not fixed:
  another plan's test).
  1. `test_fan_out_coordination.py::test_eight_threads_never_hold_more_slots_than_the_limit`
     requires the peak to *reach* 3 as well as never pass it, so it fails when the slots are
     slower to take than the 10 ms they are held.
  2. `packages/aia_core/tests/test_fan_out_coordination.py:465 @ 500e5c8e`
     (`assert peak == 3`).
  3. Failed once in the full core + worker suite on PostgreSQL 16 (2026-10-15, peak 2);
     `DATABASE_URL=postgresql+psycopg://… pytest packages/aia_core/tests/test_fan_out_coordination.py`
     alone passes (21/21).
  4. No user-visible consequence: the safety property (never above the limit) held; CI can
     go red on a correct change.
  5. Smallest fix: assert `peak <= 3`, and prove the limit is reachable separately with a
     barrier that holds three slots until all three are taken (or hold each slot ~50 ms).
  6. The test that would have caught it: the same test under load (`-n` or a busy runner).

## Doc follow-up

- Lifecycle K2d's text says it runs "beneath the chosen study and its budget". After CB5 it is
  paid by the client: the K2d slice in `client-knowledge-lifecycle.md` is that plan's to edit.
