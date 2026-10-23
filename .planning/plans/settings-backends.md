---
status: in-progress
chunks:
  - "[x] SB1. The Metodik mark (D-14): organization_members.methodologist, granted and revoked by an OWNER, audited; only a marked member stores and activates methodology; the migration marks the product owner"
  - "[x] SB2. Member deactivate and reactivate (D-27) with the sealed Lead (ADR 0030): routes, the seal at once, erasure after 30 days, unsealed for the member on a reactivation within 30 days; the target resolved in the acting admin's organization (S15)"
  - "[ ] SB3. The organization's spend for Settings (develop-spend-attribution 6): spent, reserved, uncertain calls and the studies near their budget (90 %), OWNER/ADMIN only"
  - "[ ] SB4. Stav systému (MP6): the deploy smoke's check lines kept, the latest read by Settings; GlitchTip read through a read-only token (alerts, uptime, last 7 days' issues), not configured without it"
  - "[ ] SB5. Správa dat (study-data-lifecycle SDL3, client part): a client's deletion preview with counts and a confirm token, the irreversible delete (content gone, ledgers and audit kept under the client's id), the kept-records listing"
  - "[ ] SB6. Dosah (deep-research-web-search 52): the worker's Deep Research composition recorded at start, every route and connector as built, approved, active or refused with the reason; read in Settings"
  - "[ ] SB8. A pending Deep Research setting proposal withdrawn by its proposer or declined by another administrator (Settings' \"Stáhnout návrh\"): append-only, audited, never approved after; each version's state (#841)"
  - "[ ] SB7. Profil → Pravidla (deep-research-web-search 53 storage + client-knowledge-lifecycle K11): the client's data posture and wallet ceiling, set by an OWNER or ADMIN, audited, listed read-only in Settings; a Deep Research run pins the posture"
---
# Settings backends: what the redesigned Settings reads and writes

**Owner:** PM coordinator 3 (settings backend builder). **Started:** 2026-10-22 night.
**Design:** the Settings prototype, artifact `8W9LR8Ju9BWnR5JACmiWv7`, and its implementation
handoff (§3, "shown in the prototype, not supported by the API yet").

## Why

The Settings redesign shows tabs and cards whose data no route serves today: the Metodik mark,
member deactivation and the sealed Lead, the organization's spend, the deployment's readiness and
error tracking, client deletion and the kept records, Deep Research's reach, and the client's
posture and wallet ceiling. The product owner chose, 2026-10-22 night, to build these backends
rather than show "V AIA zatím není". This plan is the contract the Settings UI builds against.

## The owner's answers (2026-10-22, 23:2x UTC, in the coordinator's session)

| Question | Answer |
|---|---|
| What a client delete removes | Content gone, ledgers kept: studies, working copies, knowledge, sources, files and run artifacts deleted; the money ledger, the approval ledger and the audit trail kept, the client's name replaced by its id. The modal lists both, with counts. |
| How long a sealed Lead is kept | 30 days. Sealed and unreadable at once; erased after 30 days; reactivating within 30 days unseals it for that member only. |
| GlitchTip in Settings | A read-only API token in SSM, the full panel; the route says "not configured" without it. |
| Who holds the Metodik mark at ship | Only the product owner (`nigelblount@art-chain.io`); an OWNER grants it to others. |
| Spend with no recorded person | "Neznámý", never attributed by guess (already so in develop-spend-attribution 7). |
| A study budget "téměř vyčerpáno" | At 90 % of its budget used or held. |
| Dosah and posture/ceiling, owned by other plans | Built here; the owning plans tick their chunks from these PRs. |

Where an owning plan disagrees, these answers win, and the difference is recorded under the chunk.

## Contracts

All routes are under `/api/v1`, in Czech-free JSON; errors use the one error contract
(`{code, message, details?}`). "Admin" is an organization OWNER or ADMIN.

### SB1. The Metodik mark

- `GET /members`: each member gains `methodologist: bool`.
- `PUT /members/{user_id}/methodologist` body `{methodologist: bool}` → the member. OWNER only:
  403 `owner_only` otherwise; 404 `not_found` when the user is not a member of the caller's
  organization. Audited `METHODOLOGIST_GRANTED` / `METHODOLOGIST_REVOKED`.
- `GET /workspace/me` and the methodology catalogue's caller block gain `methodologist: bool`.
- `POST /methodology/{module}/versions` and `PUT /methodology/{module}/activation` require the
  mark: 403 `methodologist_required` otherwise. Admins without the mark read only (D-14).
- Migration: `organization_members.methodologist boolean not null default false`; the product
  owner's memberships (`users.email = 'nigelblount@art-chain.io'`) set true where present.
  The develop seed and the UI workbench mark their seed owner, so the journeys keep editing.

### SB2. Deactivate and reactivate, the sealed Lead

- `POST /members/{user_id}/deactivate` → the member with `is_active: false`,
  `lead_sealed_at`, `lead_erase_after` (sealed + 30 days). Admin; OWNER rule and the last
  active OWNER kept (#782 `_guard_owner`). 404 when the user is not a member of the caller's
  organization (S15). Audited `USER_DEACTIVATED` and `LEAD_SEALED` ("Vedoucí zapečetěn").
- `POST /members/{user_id}/reactivate` → the member, `is_active: true`. Within 30 days the
  Lead is unsealed for that member (`LEAD_UNSEALED`); after erasure `lead_erased: true` and
  the member starts a new Lead. Admin; audited `USER_REACTIVATED`.
- Sealed means no route serves the Lead's profile, notes, revisions or turns to anyone,
  the member included, until unsealed; the worker's Lead turn for a sealed Lead parks.
- Erasure: a sweep deletes sealed Leads past `lead_erase_after` (rows and stored files),
  audited `LEAD_ERASED` with counts and no content.

### SB3. The organization's spend

- `GET /settings/organization-spend?period=this_month|last_month|year_to_date` → admin only.
  `{period, spent_usd, model_usd, tools_usd, reserved_usd, uncertain_calls, near_limit:
  [{study_id, study_name, client_id, client_name, budget_usd, used_usd, share}]}`;
  `near_limit` lists studies whose spent plus held is at least 90 % of a set budget.
  Uncertain calls are counted, never folded into a zero.

### SB4. Stav systému

- Table `deploy_smoke_results`: one row per check per smoke run (`run_id`, `build_sha`,
  `check`, `status` ok/FAIL/NOT_RUNNABLE, `detail`, `ran_at`). `aia_executors.smoke` writes
  them after it prints; a write failure never fails the smoke.
- `GET /settings/system-status` → admin. `{latest: {run_id, build_sha, ran_at, checks:
  [{check, status, detail}]} | null}`, not-ready checks first.
- `GET /settings/error-tracking` → admin. `{configured: bool, dashboard_url, project,
  alerts: [...], uptime: [...], issues_7d: [{title, culprit, count, last_seen, url}],
  error: str | null}`. `configured` is false without `AIA_GLITCHTIP_API_TOKEN`; the token is
  read-only, never logged or returned, and a GlitchTip failure answers `error`, never a 500.

### SB5. Správa dat

- `GET /clients/{client_id}/deletion` → admin. `{client_id, name, status, deleted: {studies,
  working_revisions, knowledge_items, sources, files, runs, artifacts}, kept: {usage_rows,
  approval_rows, audit_rows}, confirm_token, expires_at}`. The token is signed, binds the
  client and the caller, and lives 10 minutes.
- `DELETE /clients/{client_id}` body `{confirm_token}` → admin. Deletes the content in one
  transaction, then the stored objects; the kept rows stay with their ids, and the client's
  name in kept audit rows is replaced by its id. Audited `CLIENT_DELETED` with counts.
  A second call answers `{already_deleted: true}`. Irreversible.
- `GET /settings/kept-records` → admin. `[{record, count, kept_for, why}]`; the retention of
  usage and audit rows reads "čeká na rozhodnutí vlastníka" until MVPQ-07 is decided.

### SB6. Dosah

- Table `deep_research_compositions`: the worker writes, at start, `{worker, composed_at,
  routes: [{route, kind (search|fetch|connector|index), state (built|approved|active|refused),
  reason}]}` from its composition, one row per worker start.
- `GET /settings/deep-research/reach` → any member. The newest composition, its routes
  ordered waiting/active/off, or `null` when no worker has recorded one.

### SB7. Profil → Pravidla

- `clients.data_posture` `OPEN` | `CLASSIFIED` | null (null reads as not set and is treated
  as `CLASSIFIED`, never as open).
- `GET /clients/{client_id}/rules` → anyone with the client: `{data_posture,
  wallet_ceiling_usd, set_by, set_at}`. `PUT /clients/{client_id}/rules` body
  `{data_posture?, wallet_ceiling_usd?}` → admin, audited `CLIENT_RULES_CHANGED` with from/to.
  The ceiling is ≥ 0 or null (null: a wallet may not exceed its study's budget).
- `GET /settings/client-rules` → any member: every client's posture and ceiling, read-only.
- A Deep Research run pins the client's posture at enqueue and a retry copies it. Whether the
  posture replaces classification in Deep Research's gates (53's second half) is its own
  change, reviewed with the security audit; it is not in SB7.

## Findings

- **Stav systému reads the whole deployment (SB4, security review of #839).** Smoke results and
  GlitchTip's issues are every tenant's, but the routes are gated on an organization's OWNER or
  ADMIN. Until an operator gate exists, both refuse 409 `deployment_shared` whenever the
  deployment holds more than one organization (the develop seed's `aia-develop-smoke` not
  counted). A multi-tenant deployment needs that operator gate before Settings can show them.
  Anchor: `application/system_status.py` `_single_tenant`, test
  `test_system_status_api.py::test_with_a_second_organization_both_are_refused_as_the_deployments`.
- **SB4's contract changed:** no `detail` column on smoke results; only each check's label and
  result are kept (infra, 2026-10-23).
- **SB2 merged as #830** (32475bdc), with S15 fixed there.
