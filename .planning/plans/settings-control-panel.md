# Settings control panel

**Status:** in progress · **Owner:** product-surface · **Started:** 2026-09-27

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

- [ ] 1 · [ ] 2 · [ ] 3 · [ ] 4 · [ ] 5 · [ ] 6
