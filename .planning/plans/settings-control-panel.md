# Settings control panel

**Status:** all chunks done; PR into `develop` · **Owner:** product-surface · **Started:** 2026-09-27

## Problem

`apps/web/src/app/org/[orgSlug]/admin/settings/page.tsx` @ 9cf1f58 is a two-card
stub written in the old prototype's vocabulary ("Org settings", "RBAC:
owner/admin/editor/reviewer", "billing"). None of those words exist in the
domain: organization roles are `OWNER / ADMIN / MEMBER`, study roles are
`VIEWER / REVIEWER / RESEARCHER / LEAD`
(`packages/aia_core/src/aia_core/domain/scope.py:103-129` @ 9cf1f58), and there is
no billing. An operator has nowhere to see, let alone set, the controls the
system actually has: members, client and study grants, study budgets, the
self-approval policy, provider and model policy, residency, workflow timing,
evidence thresholds.

Some of those controls already exist in the backend with no route. The clearest
case: `ScopeRepository.set_self_approval` (`infrastructure/scope_repository.py:512`
@ 9cf1f58) is fully implemented, audited and tested
(`packages/aia_core/tests/test_self_approval_policy.py`), and unreachable over HTTP.

## Approach

**Every setting on the page states how it is controlled**, and the page never
pretends a value can be changed when it cannot:

| Control | Meaning | On the page |
|---|---|---|
| `API` | An administrative action over an existing route | A live form |
| `DEPLOYMENT` | An environment variable, read at process start | Read-only, with the variable's name |
| `CODE` | A versioned constant; changing it is a reviewed PR | Read-only, with `module:CONSTANT` |
| `INVARIANT` | A product refusal (ARCHITECTURE §10) — not a setting | Locked, with the reason |

**Values come from the server, never copied into TypeScript.** A new
`GET /api/v1/settings` serialises the effective deployment settings (secrets
reduced to *configured / not configured*) and the domain constants and
vocabularies, so a default changed in Python cannot drift from what the page
shows (anti-pattern A6). The web keeps only the Czech labels, keyed by setting
key; an unlabelled key renders as its key, never hidden.

Rejected: a new runtime "org settings" table that makes deployment variables
editable from the browser. Those values (lease, heartbeat, identity provider,
CORS) are read once at process start and validated there; changing them at
runtime would need a reload protocol and would move a production guard from
startup into a request. Not this change.

The worker's `AIA_WORKER_*` values live in another process. The API reports the
domain defaults the worker falls back to, labelled as defaults — not as the
deployed worker's values, which it cannot see.

## Chunks

| # | Chunk | Lands | Verify |
|---|---|---|---|
| 1 | **Read-only settings document.** `GET /api/v1/settings` (organization member; the deployment block only for OWNER/ADMIN), schema, tests, CI contract path, docs | `routers/settings.py`, `schemas/settings.py`, `tests/test_settings_api.py` | pytest API, mypy, ruff, layer_check |
| 2 | **Self-approval over HTTP.** `ScopeRepository.self_approval_levels` (read) + `PUT /api/v1/self-approval` (org / client / study level, `null` = inherit), admin only, audited by the existing repository method | repository read + route + tests | the same |
| 3 | **Client status over HTTP.** `PUT /api/v1/clients/{client_id}/status` over the existing `set_client_status` | route + tests | the same |
| 4 | **Web API client.** Server-only fetch with the one error contract; `AIA_API_URL`; the local development identity header only when `AIA_WEB_DEV_SUBJECT` is set | `apps/web/src/lib/api/` | tsc, lint |
| 5 | **The settings page.** Sections: Deployment, Organization & members, Clients & access, Studies & budgets, Approvals, AI providers & models, Data residency, Workflow & worker, Population, Evidence, Invariants, Access audit. Live forms through server actions for every `API` control; an unreachable API renders as unavailable, never as fixture data | page + components + i18n | tsc, lint, build; a run against the dev API with screenshots |
| 6 | **Shell vocabulary.** The shell's "UI demo" labels, the default Next.js title, the search placeholder about "případy" | `AppShell.tsx`, `layout.tsx`, `i18n/cs.ts` | build |

## What this deliberately does not do

- No editable deployment configuration (above).
- No web unit tests: the web test runner is design-system chunk 3 (DS-1) and has
  not landed. Verification here is `tsc`, lint, build and a driven run.
- No design-system tokens: chunk 1 of `design-system.md` owns them. The page uses
  the existing Tailwind utilities and is restyled when the tokens land.
- Per-project provider policy and budget are already set through
  `PATCH /studies/{study_id}/projects/{project_id}`; they belong on the project
  screen, and the page links the rule rather than duplicating the form.

## Progress

Chunks 1–6 committed on this branch (`0a4960a` … `a87807d`); the port onto `develop` is chunks 7–8 below.

- [x] 1 — `GET /api/v1/settings` · `apps/api/tests/test_settings_api.py` (9 tests)
- [x] 2 — `GET`/`PUT /api/v1/self-approval`, `ScopeRepository.self_approval_levels` ·
      `apps/api/tests/test_self_approval_api.py` (9),
      `test_self_approval_policy.py::test_levels_read_back_as_stored_not_as_resolved`,
      `::test_reading_self_approval_levels_requires_organization_administration`
- [x] 3 — `PUT /api/v1/clients/{client_id}/status` · `apps/api/tests/test_client_status_api.py` (5)
- [x] 4 — `apps/web/src/lib/api/{server,types}.ts`
- [x] 5 — the page, `components/settings/`, `settings` keys in `i18n/cs.ts`
- [x] 6 — shell title, header and search placeholder; `<html lang="cs">`

### Found on the way

- **`GET /api/v1/access-audit` answered 500 for any organization with a grant.**
  `ScopeResolver.audit_trail` returns a `payload` key the closed `AuditEntryResponse`
  did not declare. Fixed here first (`34961a3`, by dropping the payload); `develop`
  fixed it independently by declaring it (`87da177`), and that fix is the one kept at
  the merge. Test: `apps/api/tests/test_scope_api.py::test_the_access_audit_lists_entries_with_their_payload`.
- **`get_settings()` ignored `create_app(settings)`.** Already fixed on `develop`
  (`get_app_settings`); the settings route uses `SettingsDep` since the merge.

### Verification of the first cut (driven run, since superseded by the port)

API on SQLite with development identity, `next start` with `AIA_API_URL`, driven
with Playwright: set organization self-approval (the level reads back *povoleno*),
set a study budget 500 → 750 (the summary and the audit trail show it), created a
study, archived a client (leaves the default list), and a RESEARCHER's budget
change came back refused (`HTTP 404 · not_found`) and was shown as given. A MEMBER
sees no deployment group; with no `AIA_API_URL` the page says *not connected* and
renders no data.

## Port onto `develop` (2026-09-27)

This branch was cut from `main` @ `9cf1f58`; `develop` is the integration branch
(its `CLAUDE.md` § Branches) and carries Cognito sign-in and the `/app` interface.
`develop` deleted the `/org` tree the first page lived in, and its token lives in the
browser (`sessionStorage`, `apps/web/src/lib/auth.ts`), so a server-rendered page
calling the API from Next.js could never carry it.

- [x] 7 — **Merge `develop`** (`984a5df`). Develop wins on the web surface; the `/org`
      page, its server actions and the server-side client are removed. Develop's own
      `/access-audit` fix (`87da177`, payload declared) replaces this branch's
      strip-the-payload fix; develop's `SettingsDep` already reads `app.state.settings`.
- [x] 8 — **The panel on `/app/settings`.** `components/aia/settings/ControlPanel.tsx`
      below develop's account / Bedrock / classic cards; client-side, through
      `lib/api.ts` `admin` with `Authorization: Bearer <id token>` — no development
      header anywhere. Client and study *creation* are left to the client workspace
      (`workspace.startClient` / `startStudy`); the panel links there instead of adding
      a second creation path. `ControlPanel.test.tsx` (9 tests): the bearer token and no
      `X-AIA-Subject`, control per setting, null ≠ value, hidden costs ≠ zero, an
      unknown group still renders, a change re-reads, a refusal shown verbatim, a
      member not asked for admin reads, a malformed document, sign-out → `/login`.

Driven on the UI workbench (`make ui-workbench`: real API on SQLite with local identity
and the develop seed, `next dev`, the facade): every `/api/v1/settings` and
`/self-approval` request carried `Authorization: Bearer …` and no `X-AIA-Subject`;
setting organization self-approval to *allow* answered *Uloženo.*, the level re-read as
*povoleno*, and `SELF_APPROVAL_CONFIGURED organization=true` headed the audit.

Superseded from the first cut: `AIA_API_URL` / `AIA_WEB_DEV_SUBJECT`, the `make
dev-web` default and the `.env.example` web section (develop's config route and
same-origin `apiBase` replace them).
