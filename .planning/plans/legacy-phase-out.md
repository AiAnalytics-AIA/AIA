# Phase out NPC Panel 18.6.6 from AIA's product runtime

**Status:** in progress · **Owner:** integration-architecture (all chunks) ·
**Started:** 2026-09-27 · **Decision:** [ADR 0018](../../docs/architecture/adr/0018-aia-runs-without-18-6-6.md)

## Problem

AIA is meant to be its own application: its own interface, authentication, data
model, APIs, workers and deployment. On `develop` @ `4c4c3dd` it is not. The back
end (API, worker, executors, core) never calls the unit, but the product does:

- the research stages keep their **working content in the unit's SQLite project
  store** (`/api/projects/load|save`) and load the unit's bootstrap before they
  render (OI-58);
- `/app` sits behind the **legacy panel gate**, open to owners and admins only and
  switched off with `AIA_LEGACY_PANEL_ENABLED`, which production refuses (OI-59);
- `/classic` and a dozen links hand people to the 18.6.6 interface;
- the deployment **builds, runs, hydrates and smoke-checks** the unit, and CI fails
  a Caddyfile that does not route to it.

With the unit stopped, the research stages cannot load, `/app` cannot be reached,
and every deploy fails its smoke.

## Dependency inventory (measured 2026-09-27, `develop` @ `4c4c3dd`)

Class: **N** native (AIA serves it, no unit), **L** legacy-dependent (needs the
running unit), **R** reference-only (comparison, fixtures, workbench; never product).

### Frontend (browser → unit)

All through `apps/web/src/unit/client.ts` and the route table
`apps/web/src/unit/routes.ts:15-54`, same origin, behind the gate.

| Area | Unit routes | Class | Replacement |
|---|---|---|---|
| Research session load/save | `GET /api/bootstrap`, `POST /api/projects/load`, `POST /api/projects/save` (`research/store.ts:42-63,144-152`, `unit/boot.ts:26-35`) | L | `GET`/`PUT /api/v1/studies/{id}/workspace/content` (chunk 1); template from `aia_core.domain.research_template` |
| Brief attachments | `POST /api/project/attachment`, `/project-attachments/*` (`BriefStep.tsx:166-171`) | L | `POST /api/v1/studies/{id}/workspace/attachments`, bytes in AIA storage (chunk 3) |
| Questionnaire import | `POST /api/questionnaire/upload`, `/api/questionnaire/template` (`QuestionnaireStep.tsx:249`) | L | `POST /api/v1/studies/{id}/workspace/questionnaire-import`, the unit's stdlib parser ported (chunk 4) |
| AI design steps | `POST /api/research/analyze`, `…/build_questionnaire`, `/api/questionnaire/optimize`, `/api/audience/propose`, `/api/persona/suggest`, `GET /api/job`, `POST /api/jobs/{id}/cancel` | **N already** | PR #63 routes them to `/api/v1/studies/{id}/research/agent-jobs` (`lib/research-agent-jobs.ts:6-10`); the unit job runner is dead code, removed in chunk 5 |
| Deep research | `POST /api/research/deep` | N (explicitly unavailable) | Already refused in the browser (`ResearchScreen.tsx:208`); ADR 0017 is its plan |
| Provider checks | `GET /api/providers/claude-code/status`, `POST /api/settings/ai_check` | dead | `useAiStep.providerOk` already returns true; removed (chunk 5) |
| Diagnostics | `POST /api/support/bundle` | L (only for unit jobs, which no longer run) | removed (chunk 5) |
| Audience catalogues and preview | bootstrap `population_subpanels` / `special_panels` / `audiences`, `GET /api/audience/dimensions`, `POST /api/audience`, `POST /api/audiences/preflight`, `GET /api/audiences`, `POST /api/audiences/upload` | L — computed from the licence-bound panel (pandas) | Explicitly unavailable in AIA until a population version is imported through `PopulationRuntime` (Next item c); the whole population works, stored filters stay visible (chunk 5) |
| Dimension library | `GET /api/library`, `/system-catalog`, `/populations`, `/results-registry`, `POST /api/library/dimension/request` | L | The client's approved DIMENSION knowledge items; a request becomes a knowledge proposal (`POST /studies/{id}/knowledge-proposals`) (chunk 5) |
| Classic project store admin | `GET /api/projects`, `/dashboard`, `/trash`, `POST /api/projects/history-action`, `GET /api/demos`, `POST /api/demos/copy` (`/app/settings/classic-projects`) | L | Removed from the product (chunk 9); the migration report replaces it for studies' content |
| Hand-offs | `/classic#aia:…` from 9 places (`ClassicLink`, `classicHref`), `public/skin/handoff.js`, `app/interface-document` (fetches `AIA_LEGACY_PANEL_URL`) | L | Removed; capabilities not in AIA say so where the person is (chunk 9) |
| Rail status | `GET /api/bootstrap` edition/joint status (`unit/shell.ts`) | L (unused by the client-first shell) | Removed (chunk 9) |

### Server, authentication, state, files, background

| What | Where | Class |
|---|---|---|
| The gate: `POST/DELETE /api/v1/panel/session`, `GET /api/v1/panel/gate`, 404 unless `AIA_LEGACY_PANEL_ENABLED` | `apps/api/src/aia_api/routers/panel.py:52-199` | L → replaced by AIA's own session gate (chunk 8) |
| Owner/admin admission `LEGACY_PANEL_ROLES`, `authorize_legacy_panel` | `domain/scope.py:127`, `application/scope.py:170-197` | L → retired (chunk 10) |
| Login page opens the panel session; "disabled" when the flag is off | `apps/web/src/app/login/page.tsx:83-106`, `lib/panel.ts` | L → AIA session (chunk 8) |
| The study ↔ unit binding `study_workspaces` (`unit_project_id`) and `PUT /studies/{id}/workspace` | `infrastructure/study_workspace_repository.py`, `routers/workspace.py` | L → the workspace row names an AIA working project; the unit id is lineage only (chunk 1) |
| Working content: `/app/data/project_store.sqlite` (`projects`, `project_revisions`, `project_attachments`) in the `legacy_state` volume | unit `project_store.py:14-120` | L → AIA `projects` owned `study_workspace` (chunk 1); migrated by chunk 7 |
| Attachment bytes: `/app/data/ui_uploads/project_attachments/ATT-…_<name>` | unit `ui_server.py:38-39,1020-1045` | L → AIA ArtifactStore (S3 in deployment) (chunk 3, migrated in chunk 7) |
| Population panel `FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz` and companions, hydrated from `s3://<ops>/legacy-data/86b70bfb5c1b/` | unit hydration, `deploy.sh:46-52` | L for the unit; **preserved** in the ops bucket; enters AIA only through `PopulationRuntime.import_version` (`application/population.py:149`) |
| Background execution | AIA's worker runs research and agent jobs; the unit's own worker runs only unit jobs | N |

### Deployment and CI

| What | Where | Class |
|---|---|---|
| `legacy-panel` service, `legacy_state` volume, `AIA_LEGACY_*` env on caddy/web/api | `deploy/develop/docker-compose.yml:50-56,111,134-135,194-215,249` | L → removed from the product stack; `deploy/reference/` (chunk 11) |
| Caddy: `/classic`, `/interface-document`, `@unit`, `@retired_ai`, the gate on `/app`, the oracle site | `deploy/develop/Caddyfile:77-147,170-197` | L / R → product Caddyfile has none; the oracle is the reference stack's (chunk 11) |
| Pull and sync: `pull … legacy-panel`, `aws s3 sync … legacy-data` | `deploy/develop/bin/deploy.sh:40-52` | L → removed (chunk 11) |
| Smoke: `/classic` 302, `/api/bootstrap` 401, cross-origin 403, `legacy: the 18.6.6 unit is healthy`, legacy hostname 401 | `deploy/develop/bin/smoke.sh:57-112` | L → AIA's own checks (chunk 11) |
| Legacy state backup (off by default) | `bin/backup.sh:33-48`, `bin/backup-legacy-state.py` | L → the reference stack's (chunk 11) |
| Image build and push `aia-legacy-panel` | `.github/workflows/deploy-develop.yml:128-142`; `infra/develop/main.tf:17` | L → a separate, manual reference workflow (chunk 11); ECR repo kept (Terraform unchanged, human action) |
| CI routing check requires a route to `legacy-panel:8765` and the oracle site | `tools/caddy_routes.py:160-190`; `ci.yml:650-726` | L → inverted: no route may reach the unit (chunk 11) |
| API contract requires `/api/v1/panel/*` | `ci.yml:445-448` | L → requires `/api/v1/session/*`, forbids `/panel/*` (chunks 7, 10) |
| Frontend `skin:check` reads the vendored `ui_app.html` | `ci.yml:509-511`, `apps/web/scripts/build-skin.mjs:30` | L → the skin goes with `/classic` (chunk 9) |
| Oracle parity (`oracle-parity` job, `make test-oracle`, `tools/legacy_oracle.py`), UI function fixtures (`U<nn>`), parity tests reading `ui_app.html` | `ci.yml:274-326`, `packages/aia_core/tests/fixtures/legacy_ui/` | **R** — kept; needs the reference stack or the vendored files, never the product |
| UI workbench, develop routing proof | `tools/ui_workbench/`, `tools/develop_routing_proof.py` | R → the workbench runs AIA without the unit by default (chunk 12) |

## Approach

**Replace, then migrate, then remove** — never remove a dependency before its
native replacement and the verified migration of its data exist.

1. **Native state first.** A research Study's working content is an owned AIA
   project (`projects.owner = study_workspace`), found only through the Study's
   `study_workspaces` row, written through `ProjectRepository.save` — the facility
   that already gives immutable, deduplicated revisions with event history — and
   served by study-scoped routes. The workspace row names a `ContentState`, so a
   Study never silently shows an empty document: `EMPTY`, `NATIVE`, `MIGRATED`,
   `RECOVERED`, `UNRECOVERABLE`, `AWAITING_MIGRATION`. A save names its base
   revision; a stale one is a 409, not a silent overwrite (the unit had no such
   check). Rejected: a new parallel table for working revisions (duplicates
   `project_revisions`); storing working saves as Design Revisions (would make
   every autosave something a run could execute, and flood the revision list ADR
   0016 reads).
2. **Explicit, repeatable migration.** `python -m aia_executors.legacy_workspace`
   reads a WAL-safe copy of the unit's `project_store.sqlite` (read-only, stdlib
   `sqlite3`) and the attachment directory, and for each `AWAITING_MIGRATION` Study
   writes the unit project's revisions into its working project with lineage, copies
   attachments into AIA storage, validates the result against the source, and
   reports every case it could not migrate. Dry run by default. It never deletes
   or writes the source.
3. **AIA's own gate.** `/app` behind `GET /api/v1/session/gate`: any active
   member of an organization, with the data behind it authorized per call by
   `ScopeResolver` as before. No legacy flag.
4. **An interface without hand-offs.** Every capability AIA does not have says so
   where the person is; nothing links to `/classic`.
5. **A product deployment without the unit**, and a separate, optional
   `deploy/reference/` stack for the oracle.

## Trade-off accepted

Capabilities that depend on the licence-bound panel (audience filters and their
preview, special audiences, customer audience uploads) and the classic-only
screens (simulation, verification, the 18.6.6 report) are **unavailable in AIA,
and say so**, until they are rebuilt; the unit no longer backs them in the product.

## Chunks

PR 1 — native research workspace (`feature/native-research-workspace`)
- [x] 1. Working content in AIA: `domain/workspace.py` (states, validation),
  `domain/research_template.py`, `study_workspaces` gains `content_state`,
  `project_id`, `lineage` (migration `5b1d0f3e9a21`), `StudyWorkspaceRepository`
  load/save/revisions, `GET`/`PUT /studies/{id}/workspace/content`,
  `GET …/revisions`; the binding route removed — tests:
  `test_study_workspaces.py`, `test_research_template.py`,
  `test_workflow_concurrency.py` (two editors, two first saves),
  `test_client_api.py`
- [x] 2. Web: the research flow's logic moves from `src/unit/research` to
  `src/research`; the session loads and saves through the API; the unit job runner,
  provider checks and support bundle go (every AI step was already a native agent job);
  a step AIA has not rebuilt and the missing 18.6.6 report say so instead of handing off;
  the workbench fixtures are written through AIA — tests: `store.test.ts`,
  `ResearchScreen.test.tsx`, every stage's test on `test-workspace.ts`,
  `test_ui_workbench_fixtures.py`
- [x] 3. Attachments in AIA storage: `domain/attachments.py` (the unit's rules),
  `infrastructure/document_text.py` (the unit's `_extract_text`, the same libraries as
  the `documents` extra, ZIP bounds added), `StudyWorkspaceRepository.attach` /
  `.attachment` (artifacts of the working project), `POST`/`GET
  /studies/{id}/workspace/attachments[/{attachment_id}]`, the brief's upload and download
  — tests: `test_document_text.py` (fixtures captured from the unit by
  `tools/attachment_text_capture.py`), `test_study_workspaces.py`, `test_client_api.py`,
  `BriefStep.test.tsx`
- [x] 4. Questionnaire import ported: `domain/questionnaire_import.py` (the unit's row
  rules and the `normalize_project` rules an import meets, `StudySpec`'s included),
  `infrastructure/questionnaire_file.py` (the unit's CSV and stdlib XLSX readers; AIA's
  own template workbook), `POST …/workspace/questionnaire-import`, `GET
  …/workspace/questionnaire-template`; the stage puts the sections on its content and
  saves; the classic methodology link (a file the unit never served) is gone — tests:
  `test_questionnaire_import.py` (24 fictional files, the unit's own function via
  `tools/questionnaire_import_capture.py`), `test_client_api.py`,
  `QuestionnaireStep.test.tsx`, `questionnaire.parity.test.ts`
- [x] 5. Audience and Dimenze without the unit: the Dimenze catalogue's library is the
  client's approved DIMENSION knowledge (`GET /studies/{id}/context`) and a request a
  knowledge proposal (`POST /studies/{id}/knowledge-proposals`); what 18.6.6 computed
  from its panel or audience store (factor catalogue and filters, preview, subpanels,
  own audiences, panel factors) says "V AIA zatím není", stored choices stay visible
  and marked unused; the Deep Research hand-off is gone; `useUnitCatalogues` and the
  unit catalogue loader removed; the unit job runner, provider checks and support
  bundle had gone in chunk 2 — tests: `AudienceStep.test.tsx`, `PersonaStep.test.tsx`;
  every research stage's test now fails on any unit URL (`unitCalls()` in its
  `afterEach`)
- [x] 6. Documents: CLAUDE.md map, ARCHITECTURE §4, data-model, OI-58, both ledgers,
  AGENTS.md (the Alembic backfill default; jsdom downloads), ADR 0018 (the save
  normalization difference) — kept in step with each chunk. And the proof on AIA
  alone: `workbench.py up --no-unit` (`make ui-workbench-aia`: the unit not started,
  its paths answer 502), on which `make ui-fixtures`, `make ui-research` (Run →
  Progress → Results) and the new `make ui-workspace` (a new study's brief text and
  file, a reload, the download; AIA's template imported back; audience and Dimenze)
  pass in Chromium, both journeys failing on any request to a path of the unit
  (2026-09-27: 244 requests, none to the unit, no 502)

PR 2 — migration (`feature/legacy-workspace-migration`)
- [x] 7. The migration command, its validation and its report; runbook (ADR 0018
  decision 2): `domain/workspace_migration.py` (the rules: file references, record
  rewrite, source checks against the unit's own hashes, one-for-one validation, the
  report), `infrastructure/unit_project_store.py` (a copy read `mode=ro&immutable=1`,
  a live database refused, the backup ZIP unpacked to a scratch directory; files by
  base name only), `StudyWorkspaceRepository.unit_bindings` / `import_migrated` /
  `mark_unrecoverable`, `ProjectRepository.create(author_unknown=True)`,
  `ArtifactRepository.put(artifact_id=…)`, `application/workspace_migration.py` (as a
  person through `ScopeResolver`, per-Study transactions, dry run unless applied,
  `recover_missing` for the OI-66 cases), `aia_executors.legacy_workspace` (the
  command); the stages say recovered content is the last submitted design, and when
  a migrated brief's files did not all come over; runbook `deploy/develop/README.md`
  § Migrating 18.6.6 content — tests: `test_workspace_migration.py` (stores written
  in the unit's own layout, its schema read from `project_store.py` as text),
  `test_legacy_workspace.py`, `test_project_repository.py`, `test_artifacts.py`,
  `store.test.ts`, `ResearchScreen.test.tsx`. **Not run on develop**: that is the
  operator's step 2 below.

PR 3 — AIA's own session gate (`feature/aia-session-gate`)
- [x] 8. `POST/DELETE /api/v1/session`, `GET /api/v1/session/gate`
  (`routers/session.py`; admission `ScopeResolver.authorize_session`: any active
  member, audited `AIA_SESSION`; GET and HEAD only); `/login` opens AIA's session and
  the panel's best effort (`lib/session.ts`); sign-out clears both; Caddy's `@app`
  behind `/api/v1/session/gate`; the `/app` switch retired (ADR 0014 decision 6);
  `tools/caddy_routes.py` refuses `/app` behind the panel's gate; smoke checks that a
  panel cookie does not open AIA and a page takes no writes; the routing proof and
  journey open both sessions; OI-59 — tests: `test_session_api.py`,
  `test_caddy_routes.py`, `login/page.test.tsx`, `lib/session.test.ts`

PR 4 — the interface without 18.6.6 (`feature/interface-without-classic`)
- [x] 9. The interface hands nothing to 18.6.6 (ADR 0018 decision 4). Removed:
  `app/interface-document`, `lib/interface-skin*`, `lib/interface-handoff*`,
  `lib/rehome*`, `lib/panel.ts`, `src/skin/`, `scripts/build-skin.mjs`,
  `scripts/skin-lint.mjs`, `public/skin/skin.css` and `handoff.js`, `ClassicLink`, the
  classic projects screens (`rehome/projects/`, `/app/settings/classic-projects`) and,
  with them, `src/unit/`. `/classic` is the web client's public page saying 18.6.6 is
  gone (`app/classic/page.tsx`); the simulation, the Data Library, the verify and next
  stages, the report and the Sociomap's tools say they are not in AIA; `/login` opens
  AIA's session only, and sign-out still clears a panel cookie left from before while
  the panel's gate stands. The Caddyfile has no `/classic` or `/interface-document`
  route and `tools/caddy_routes.py` fails one that comes back; smoke checks `/classic`
  is AIA's page and `/interface-document` a 404; Compose's `web` loses
  `AIA_INTERFACE_SKIN_ENABLED`, `AIA_INTERFACE_REHOME_ENABLED` and
  `AIA_LEGACY_PANEL_URL`; CI loses `skin:check`; `interface-screens.json` is 5
  `REBUILT`, 3 `REBUILDING`, 4 `SUPERSEDED`, 16 `NOT_IN_AIA`; the workbench runs no skin
  process — tests: `NotInAia.test.tsx`, `interface-screens.test.ts`,
  `login/page.test.tsx`, `lib/session.test.ts`, `test_caddy_routes.py`,
  `test_develop_host_resilience.py`, `test_ui_workbench.py`

PR 5 — the deployment without 18.6.6 (`feature/deploy-without-legacy`)
- [ ] 10. Retire the panel gate and its settings
- [ ] 11. Product Compose/Caddy/deploy/smoke/CI without the unit;
  `deploy/reference/`; reference image workflow
- [ ] 12. Workbench without the unit by default; offline verification recorded;
  ADR 0018, OI-58/59, PROGRESS

## Operator sequence (none of it is run by an agent)

1. Merge PR 1, deploy. Bound Studies show *Čeká na migraci z 18.6.6*; new Studies
   work natively.
2. Merge PR 2, deploy. On the host, by `deploy/develop/README.md` § Migrating 18.6.6
   content: take a WAL-safe copy of the unit's state (`bin/backup-legacy-state.py`)
   and of its attachment directory, run the migration as a dry run, read the report,
   back up PostgreSQL, run it with `--apply`, keep both reports. Only when the copy is
   known complete, `--recover-missing` for the Studies whose project it lacks.
3. Merge PR 3 and PR 4, deploy.
4. Merge PR 5, deploy: the unit stops being part of the product. Its volume and
   data bundle stay untouched; `deploy/reference/` can start it again as the oracle.

## Review outcome

(Filled in when archived.)
