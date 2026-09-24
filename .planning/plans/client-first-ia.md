# Client-first information architecture — the React AIA shell becomes the product

**Status:** complete, in review on `feature/client-first-ia` (from `develop` @ `8e7a6db`, PR #50 merged).
**Decided by:** the data owner, 2026-09-24: stop the screen-by-screen migration before PR C; correct
the information architecture first; the React client-first shell is the canonical product on
`develop`; NPC Panel 18.6.6 is the behavioural reference and a temporary, explicit hand-off.
**ADR:** [0015](../../docs/architecture/adr/0015-client-first-product-interface.md) (supersedes the
facade parts of 0012, 0013 and 0014).

## Audit (evidence, before any code) — `develop` @ `8e7a6db`

### 1. Route hierarchy

- `deploy/develop/Caddyfile:59-76` — `GET /` on the product hostname goes through the gate
  (`/api/v1/panel/gate`) and is rewritten to the web client's `/interface-document`, which fetches
  the unit's own `/` (`apps/web/src/app/interface-document/route.ts:20-23,38-81`) and adds the skin.
  **This is the NPC Panel 18.6.6 document.** Everything not matched earlier (`Caddyfile:105-117`)
  is proxied to `legacy-panel:8765`: a catch-all.
- React exists only under `/app` (`Caddyfile:84-99`, `apps/web/src/app/app/layout.tsx:9-14`,
  `AIA_INTERFACE_REHOME_ENABLED` on in `deploy/develop/docker-compose.yml:103`):
  `/app` → `/app/projects` (`app/app/page.tsx:5-7`); `/app/projects`, `/app/projects/trash`;
  `/app/research/new`; `/app/research/<unit project id>/<step>` (10 step keys,
  `src/unit/research/steps.ts:16`). No route names a client or a study.
- Nothing links into `/app/research`: the project card opens the classic interface
  (`ProjectCard.tsx:89` → `/#aia:open=<id>`), *Nový výzkum* starts it in the classic interface
  (`ProjectsScreen.tsx:152` → `/#aia:start=research`), the rail's *Výzkum* switches the classic
  product (`Shell.tsx:28`). The rebuilt research steps were reachable only by typing the URL.
- `/studies…` (`app/studies/**`) are AIA's own live pages on `/api/v1` (`lib/api.ts`), not linked
  from `/app`.
- The web root page (`app/page.tsx`) is never reached on develop: Caddy rewrites `/`.

### 2. Global navigation

`Shell.tsx:25-42` copies the classic rail item for item: *Úvod*, *Simulace*, *Výzkum*,
*AI asistent*, *Data Library*, *Nastavení* (group: *Obecné nastavení*, *Claude Code*,
*Diagnostika*), *Pokročilé* (*Command Center*), and *Správa projektů*, which is the only React
item. Every other item is a hand-off `/#aia:…`. The brand line says *NPC Panel*, the foot shows
the unit's *Claude Code* / *Core joint* codes, and *Klasické rozhraní* links to `/`. The research
rail (`ResearchRail.tsx`) sits above the main menu, in the global shell.

### 3. Client / Study domain model

- `packages/aia_core/src/aia_core/domain/scope.py:1-23,500-569` — Organization → **Client (hard
  confidentiality boundary)** → **Study (one engagement: budget, delivery, access)**; roles VIEWER
  < REVIEWER < RESEARCHER < LEAD granted at client level (`ClientGrant`) or study level
  (`StudyGrant`, authoritative both ways, `effective_role` :231-245); org OWNER/ADMIN get no
  implicit data access (ADR 0004).
- Only `ScopeResolver` issues contexts (`application/scope.py`): `OrganizationContext` (no client
  or study id), `StudyContext` (client id read from the study row, never from the caller). There
  is **no client-level context**: nothing is scoped to a client alone (ADR 0004 rule 1: every
  client-derived object resolves to a client *and a study*).
- `infrastructure/tables.py:80-140` — `projects` carry `organization_id`, `client_id`, `study_id`;
  artifacts are scoped through the project; the storage key is
  `org/…/client/…/study/…/proj/…` (`storage.py:122-155`). Population tables are shared platform
  data with no scope columns (`tables.py:1084-1091`).
- **No link exists between an AIA study/project and a unit project** (`PRJ-…` in the unit's own
  store, `legacy/npc-panel-18.6.6/app/project_store.py:16-24`, which has no client or study
  columns). The rebuilt research screens read and write only the unit (`/api/projects/load|save`,
  `src/unit/research/store.ts:42-63,144-152`); the unit's `client` is free text
  (`src/unit/projects.ts:25`).
- **No client knowledge exists** anywhere: no sources, documents, facts, findings or proposals
  scoped to a client; the Data Library is "not started" (`docs/architecture/domain-map.md:208-221`).

### 4. Client APIs

`apps/api/src/aia_api/routers/scope.py`: `GET /api/v1/clients` (218) returns **every** client of
the organization to any member (not grant-filtered); `POST /clients` (243, admin);
`POST /clients/{id}/grants` (276); `GET /studies?client_id=` (310, filtered to accessible studies);
`POST /studies` (334, admin, `client_id` in the body); `GET/PUT /studies/{id}…`. There is no
`GET /clients/{id}`, no client-scoped study list, no overview and no knowledge route. No API test
exercises the scope router.

### 5. Caddy routing (develop)

Product hostname: `/api/v1/*` → api; `@web` (`/login /logout /auth/* /config /version /studies*
/_next/* /skin/* /favicon.ico /icon.svg /apple-icon.png`) → web; `/` → gate → 18.6.6 document;
`/interface-document` → 404; `/app*` → gate → web; **everything else → gate → unit**. Legacy
hostname → basic auth → unit (the oracle, unskinned). CI asserts all of this
(`.github/workflows/ci.yml:635-737`), the smoke script asserts `/` → `302 /login?next=%2F`
(`deploy/develop/bin/smoke.sh:34-43`).

### 6. Reusable from PR #49 / #50 unchanged

The unit client and ledger-checked routes (`src/unit/client.ts`, `routes.ts`); the research
model, store, save state and the OI-56 session (`src/unit/research/*`, `ResearchSession`);
the job runner and panel; `useAiStep`; every step's logic module and its parity suite
(`brief`, `plan`, `questionnaire`, `audience`, `persona` — 45 to 72 checks each, all against the
frozen `ui_app.html`, none depends on a URL); the step components' bodies. What changes is only
where they are mounted, how a step names the next step's URL, and the frame around them.

### 7. Assumptions and ADRs that conflict

ADR 0012 decisions 1 and 5 (the unit serves `/`; screens re-homed last, looking the same);
ADR 0013 decision 1 and "the develop deployment is the canonical baseline for every screen";
ADR 0014 decisions 1, 4 and 7 (the classic interface stays at `/`; a classic screen's capture is
the specification; hand-offs to `/#aia:…`); `interface-rehome.md` (areas A1–A8 copied from the
classic rail, `/app/projects` as the landing page); `research-flow-rehome.md` (unscoped
`/app/research/<id>/<step>`, the classic seven steps as the spec, "next: chunk 7, run");
`PROGRESS.md` ("next: PR C"); `CLAUDE.md` ("The develop site is the 18.6.6 interface");
`ARCHITECTURE.md §9`; `deploy/develop/README.md` (route table, "you land on 18.6.6");
`docs/design/aia-design-system-brief.md` §7 (Portfolio across clients as screen 1; stale mock
note); `docs/product/README.md` (no navigation, no client workspace). The classic document also
assumes nothing about its path (`apiUrl` is `API_BASE + u`, no `location.pathname` use), so it can
be served at a path other than `/`.

## Decisions (recorded in ADR 0015)

1. **Canonical product:** `/` on the product hostname answers `302 /app/clients`. `/app/clients`
   is the application home. The classic interface moves to **`/classic`** — an explicit,
   gated, skinned, labelled hand-off with a way back — and is never reached by accident: the unit
   is routed only on the paths it serves (`/api/*` other than `/api/v1`, `/files/*`,
   `/artifacts/*`, `/project-attachments/*`, `/brand/*`, `/fullsim-arena`, `/health`, `/status`),
   and every other path is the web client's (its own 404). The legacy hostname is unchanged: the
   oracle, basic auth, unskinned.
2. **Hierarchy:** Client → (Výzkumy | Simulace | Znalosti | Data) → a research or simulation →
   its stages → results. **Research and Simulation are both AIA `Study` records**, distinguished
   by a persisted `studies.kind` (`RESEARCH` | `SIMULATION`). The Study is canonical for client
   scope, identity, lifecycle, permissions, budgets and costs, approvals, provenance, artifacts
   and history; only the workflow beneath it differs by `kind`.
3. **The unit store is a temporary migration bridge (OI-58), not the data model.** The unit
   project holding a study's working content is bound by an explicit AIA-owned binding
   (`study_workspaces`: one row per study, `unit_project_id` unique, written only through an
   issued `StudyContext` with `EDIT_STUDY`, once). Access always resolves the study through AIA's
   scope first and reads the unit id from the binding; a unit project id from the browser is never
   authorization, and no route finds a study by one. Removal condition: stage state stored and
   served by AIA's study-scoped contracts, the stages no longer calling the unit store, the
   bridged content migrated — then the table is dropped.
4. **Client scope:** `ScopeResolver.client_context()` issues a new, unforgeable
   **`ClientContext`**: a client-level grant (role, permissions), or study-only access (only the
   granted studies, no client knowledge). Denial is 404, as for studies.
5. **Client Knowledge** is client-scoped data that belongs to a client, not a study — an explicit,
   narrow amendment to ADR 0004 rule 1. Three layers, explicit and auditable:
   *AIA shared intelligence* (platform: population, shared definitions) → *Client Knowledge*
   (private to one client) → *Study context* (what a study consumes). A study never writes client
   knowledge: it **proposes**; a person with the approval permission decides (separation of duties
   as for gates); an approval creates a new item revision and a new **client context revision**,
   with provenance (study, project, proposal). Every read takes an issued `ClientContext` or
   `StudyContext`; there is no unscoped query, and the predicate is in the SQL (no filter after
   retrieval). `make layer_check` forbids the knowledge tables outside their repository.
6. **Global navigation:** *Klienti*, *Společenská inteligence*, *Projektová paměť*, *Nastavení*.
   Agents, templates, model configuration, diagnostics and the unscoped classic project store
   (`/app/projects` → `/app/settings/classic-projects`) live under *Nastavení*.
7. **Research stages** are mounted at `/app/clients/<client>/research/<study>/<stage>`, stage slugs
   `brief plan questionnaire audience dimensions run progress results verify next` (`dimensions`
   is the URL of the `persona` step). The stage rail belongs to the project, not to the shell.
   `/app/research/*` is retired (redirects to `/app/clients`).
8. **`/app` stays owner/admin-only — a temporary restriction (OI-59), not the authorization
   model.** The rebuilt stages still read the single-tenant unit. The target is *authenticated
   user → organization membership → client grant → study grant*, as every `/api/v1` route already
   resolves it; once stage state is AIA-scoped, researchers with the right grants use `/app`.
   Nothing in the client shell may depend on the caller being an owner or admin.

## Target route tree

```
/                                        302 → /app/clients  (Caddy)
/app                                     → /app/clients
/app/clients                             Klienti — the clients you can work for (+ Nový klient: admins)
/app/clients/<client>                    Přehled — active work, recent outputs, knowledge status, approvals
/app/clients/<client>/research           Výzkumy (+ Nový výzkum)
/app/clients/<client>/research/<study>/<stage>   brief … dimensions … (the rebuilt screens)
/app/clients/<client>/simulations        Simulace (+ Nová simulace)
/app/clients/<client>/simulations/<study>        the simulation's frame (its stages hand off for now)
/app/clients/<client>/knowledge          Znalosti — sources, knowledge, previous studies, dimensions,
                                         audiences, pending updates (review)
/app/clients/<client>/data               Data — the client's datasets and what it inherits
/app/intelligence                        Společenská inteligence (shared layer; classic Data Library hand-off)
/app/memory                              Projektová paměť — your studies across your clients
/app/settings                            Nastavení (+ /app/settings/classic-projects[/trash])
/classic                                 the 18.6.6 interface, labelled, with "Zpět do AIA"
```

## Component / shell tree

```
AppShell (global nav: Klienti · Společenská inteligence · Projektová paměť · Nastavení)
 ├─ PageHeader (breadcrumbs, title, one primary action)
 ├─ ClientWorkspace (client header + tabs Přehled · Výzkumy · Simulace · Znalosti · Data)
 │   ├─ ClientOverview, StudyList(kind), KnowledgeArea, DataArea
 │   └─ StudyFrame (study header + stage rail)  ← ResearchSession / ResearchScreen (re-homed)
 │        └─ BriefStep · PlanStep · QuestionnaireStep · AudienceStep · PersonaStep (unchanged bodies)
 └─ ClassicHandoff (explicit link, remembers the way back)
```

## Chunks

| # | Chunk | State |
|---|---|---|
| 0 | This plan and ADR 0015; OI-58, OI-59 (the two temporary states, with exits) | done @ `dba22e0`, `e90f367` |
| 1 | Core: `studies.kind`, `ClientContext`, `ScopeResolver.client_context`, isolation tests | done @ `464b43a` (`test_client_scope.py`, 11) |
| 2 | Core: `study_workspaces` (study ↔ unit project binding, last stage) | done @ `464b43a` (`test_study_workspaces.py`, 7) |
| 3 | Core: Client Knowledge — domain, tables, migration, repository, proposals → approval → revision, layer check | done @ `814d003` (`test_client_knowledge.py`, 9; 4 layer rules) |
| 4 | API: client routes (accessible list, one client, its studies, create research/simulation, overview), workspace, knowledge, study context; API tests incl. cross-client | done @ `16026f4`, `085eb14` (`test_client_api.py`, 11); OI-60 found and fixed @ `87da177` |
| 5 | Seed: two fictional clients with research, simulations and knowledge | done @ `aaaf8c3` |
| 6 | Web: AppShell, breadcrumbs, client directory, workspace, lists, knowledge, data, intelligence, memory, settings | done @ `bbc95de` (`ClientFirst.test.tsx`) |
| 7 | Web: re-home the five research stages under client/study; step URLs from one helper | done @ `bbc95de` (`app-routes.test.ts`; the stage tests unchanged and passing) |
| 8 | Hand-off to `/classic` with a way back; `/app/research` and `/app/projects` retired/moved | done @ `bbc95de`, `3180d7b` (`interface-handoff.test.ts`) |
| 9 | Caddy, smoke, CI routing checks, develop runbook | done @ `3180d7b` (`tools/caddy_routes.py`, `test_caddy_routes.py`, 6) |
| 10 | Workbench (API behind the facade), fixtures, capture; the real Caddyfile end to end locally | done @ `38dd917`, `bf6bff5`; a malformed id now reads "nothing here" @ `f51264c` |
| 11 | Documents: ADRs 0012–0014 status, plans, PROGRESS, CLAUDE.md, ARCHITECTURE.md, product and design docs, ledgers | done (this commit) |

### Proof through the real Caddyfile (chunk 10)

`sudo python3 tools/develop_routing_proof.py --keep` then `node tools/develop_routing_journey.mjs`,
Caddy v2.10.2, the committed `deploy/develop/Caddyfile`, local stand-ins for `api`, `web` and
`legacy-panel` (the unit behind its own `runtime/relay.py`), 2026-09-24:

| | This branch | `develop` @ `8e7a6db` |
|---|---|---|
| `GET /` signed out | `302 /app/clients` | `302 /login?next=%2F` (the gate) |
| `GET /` signed in | `302 /app/clients`, not the 18.6.6 document | `200`, the 18.6.6 document |
| `GET /classic` signed in | `200`, `X-AIA-Skin: applied`, hand-off script | `404` |
| `GET /no-such-page`, `/studies-archive` | `404` from the web client | `404` from the unit (the catch-all) |
| `GET https://legacy.localhost/` | `401`; with basic auth `200`, SHA256 = pinned `ui_app.html`, unskinned | the same |
| Requests passing | **15 / 15** | 10 / 15 |
| Browser journey | **13 / 13**: `/` → `/app/clients`; a new research opens on its brief under its client; breadcrumbs client / Výzkumy / study / stage; the first save binds the study to its unit project; `/classic` carries its label and *Zpět do AIA* returns to the stage; another client's study under this client's URL and a unit id in a study's place find nothing; no page errors | -- |

## Not in this PR

The whole Data Library; Simulation screens; Run / Progress / Results / Verify; knowledge ingestion
(upload, extraction); Project Memory search beyond listing; porting the research store from the
unit to AIA (OI-58); opening `/app` to members without an admin role (OI-59).
