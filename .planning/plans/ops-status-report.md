---
status: in-progress
chunks:
  - "[x] 1. aia_executors.status_report: one redacted JSON line of the deployment's state (switches, runs and steps by status with reason codes, model calls and spend, Deep Research approvals), codes, counts and ids only"
  - "[x] 2. bin/deploy.sh runs it after the smoke and bin/backup.sh after the nightly dump, both into /var/log/aia-deploy.log, so it reaches CloudWatch /aia/develop (stream <instance>/deploy)"
  - "[ ] 3. A GlitchTip read-only token in SSM aia_glitchtip_api_token (operator, Nigel): Settings → Stav systému's GlitchTip card, and the failure reasons GlitchTip already holds"
---
# The deployment's state, readable without a shell or a database

**Drafted:** 2026-10-27 · **Base:** `develop` @ `f5916652` · **Owner:** the infra session, on the
product owner's go-ahead in the session ("do 2 and 3", 2026-10-27).

## Why

The infra audit of 2026-10-27 could read AWS but not AIA's own state: which runs failed and why,
which steps are parked and on what, what the model calls cost, which Deep Research settings an
organization approved. Postgres is on the host's internal network only; every API route that reads
those needs a person's session; the agent is denied `ssm:StartSession` and `ssm:SendCommand`, on
purpose. The container logs reach CloudWatch, but the worker logs a step's status, never its reason.

A green deploy therefore says nothing about whether the product works: the smoke's AI row is
NOT_RUNNABLE by design, and the activation profile (`mvp-master-plan` MP6) is not built.

## What

`python -m aia_executors.status_report [--days 7]`, an operator command that acts as no one (as
`smoke_record` and the seed do). It prints **one line**, `aia-status {json}`, and exits 0; a failure to
read prints `aia-status-error <class>` and exits 1, never failing the caller.

The line holds:

- `build`, `generated_at`, `window_days`;
- `switches`: an allowlist of the worker's own environment (booleans, model ids, route id, search
  route, data-class gates); a key not on the list is never printed, and no secret is on it;
- `runs` and `steps`: counts by status of those touched in the window or still live, whatever their
  age;
- `live_problem_steps`: every step parked (budget, gate, provider, capacity) or awaiting recovery,
  whatever its age, and `failed_steps`: the window's failed steps; each list newest first, at most 50
  of its own: run id, workflow type, step kind, status, `waiting_reason`, the last attempt's
  `error_json.reason` and `failure_class`, the time;
- `model_calls`: per model and outcome, the ledger rows, tokens and cost in the window; `open_calls`:
  calls dispatched with no known outcome and no resolution, whatever their age;
- `open_holds`: budget reservations still open, counted, with their sum;
- `deep_research_approvals`: per organization, the setting keys whose newest approval is in force.

**Never in it:** text a person or a model wrote, a design, a prompt, a name, an e-mail, a client's
name, a URL, a secret. Reason codes are printed only when they match `^[A-Za-z0-9_.:-]{1,64}$` (upper case for the
statuses and failure classes the engine stores in it); anything
else prints `uncoded`. Ids are AIA's own opaque ids.

## Where it runs

`bin/deploy.sh` after `bin/smoke.sh`; `bin/backup.sh` after the nightly dump (the timer's output is
not shipped, so it appends to `/var/log/aia-deploy.log`, which the CloudWatch agent already ships as
`<instance>/deploy`). Both bounded by `timeout`, neither able to fail its caller.

## Trade-off

One more cross-organization read outside the work queue. It is an operator surface, acting as no
one, in one module (`infrastructure/operations_status.py`), printing only codes, counts and ids: the
same footing as `deploy_smoke_repository.tenant_count` and the reconciler. In a multi-tenant
production the per-organization Deep Research rows name organization ids, never names.

## Doc follow-up

- CLAUDE.md § 2: `apps/executors/.../status_report.py` (operator command, one redacted line, run by
  deploy.sh and backup.sh) and `packages/aia_core/.../infrastructure/operations_status.py` (the ONLY
  reader for it; codes, counts and ids).
- (`deploy/develop/README.md` § Logs carries the runbook note in this PR.)

## Findings

- (none yet)
