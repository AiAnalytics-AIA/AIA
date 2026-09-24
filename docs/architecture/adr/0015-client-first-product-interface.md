# ADR 0015 — The React AIA client-first shell is the product; 18.6.6 is the reference and an explicit hand-off

**Status:** Accepted — develop (data owner's decision, 2026-09-24). **Supersedes** the facade
decisions of [ADR 0012](0012-legacy-interface-as-product-facade.md) (decisions 1 and 5: the unit
serves `/`, screens are re-homed last and look the same), of
[ADR 0013](0013-interface-skin-at-the-facade.md) (decision 1: the skinned document is served at
`/`; "the develop deployment is the canonical baseline for every screen") and of
[ADR 0014](0014-rebuild-the-interface-in-react.md) (decision 1: the classic interface stays at `/`;
decision 4: a classic screen's capture is the specification; decision 7: hand-offs to `/#aia:…`).
Everything else in those ADRs stands: the vendored unit and its oracle (0011), the gate in front
of it and the owner/admin rule (0012), the skin as long as the classic document is served
(0013), the ledger-checked unit client and the fragment hand-off mechanism (0014). Narrowly
**amends [ADR 0004](0004-client-study-isolation.md) rule 1** for Client Knowledge (below).
**Date:** 2026-09-24

## Context

After PR #49 and PR #50 the develop site still looked like NPC Panel 18.6.6, and it was meant to:
`GET /` on the product hostname was the 18.6.6 document (ADR 0012, `Caddyfile` `handle /`), and
the React screens lived only under `/app`, where nothing linked to the rebuilt research steps
(the only way in was typing `/app/research/<id>/<step>`). The React work had inherited the
classic interface's architecture along with its behaviour: a global project list with no client,
a rail copied item for item, a seven-step research rail in the global shell, and hand-offs for
everything else.

AIA's own model has always been client-first: Client and Study are hard isolation boundaries
(ADR 0004), and every study belongs to exactly one client. The interface should say so. A
researcher's first decision is *which client am I working for*; everything else follows inside
that client.

## Decision

1. **The canonical product on develop is the React AIA shell.** `GET /` on the product hostname
   answers `302 /app/clients`; `/app/clients` is the application home. Signed out, `/app/*` sends
   the visitor to `/login` and back.

2. **Hierarchy.** AIA → Klienti → one client's workspace (Přehled · Výzkumy · Simulace ·
   Znalosti · Data) → one research or simulation → its stages → results, artifacts, sociomaps.
   **Research and Simulation are both AIA `Study` records**, distinguished by a persisted
   `studies.kind` (`RESEARCH` | `SIMULATION`). The Study is the canonical AIA object for client
   scope, identity, lifecycle, permissions, budgets and costs, approvals, provenance, and
   artifacts and history; only the workflow beneath it differs by `kind`. The stage rail belongs
   to the open study; it is never global navigation. Sociomaps are an output of a study, reached
   through it.

3. **Global navigation** is *Klienti*, *Společenská inteligence*, *Projektová paměť*,
   *Nastavení*. Execution infrastructure (agents, templates, model and provider configuration,
   diagnostics, the classic project store) is contextual or under *Nastavení*.

4. **18.6.6 is a behavioural reference and a temporary, explicit hand-off, not the product.**
   - The **legacy hostname** stays exactly as it is: the parity oracle, basic auth, unskinned.
   - On the product hostname the classic document is served at **`/classic`**, through the same
     gate, with the skin (ADR 0013) and the hand-off script (ADR 0014). A React screen that
     needs a capability not yet rebuilt links there visibly (`/classic#aia:…`), remembers where
     the person came from, and the classic page shows one bar, *Zpět do AIA*, that returns
     there. That bar is the one element the script adds to the classic page.
   - The unit is routed **only on the paths it serves** (`/api/*` other than `/api/v1`,
     `/files/*`, `/artifacts/*`, `/project-attachments/*`, `/brand/*`, `/fullsim-arena`,
     `/health`, `/status`), each through the gate. There is no catch-all to the unit: an unknown
     path is the web client's 404, so normal navigation cannot fall into the old product.

5. **The unit store is a temporary migration bridge, not the data model** (open item OI-58).
   Until the research store is ported, the unit project that holds a study's *working content*
   is bound to the study by an explicit, AIA-owned binding, `study_workspaces` (one row per study;
   the unit project id unique, so one unit project belongs to one study only; the last stage
   opened). The rules:
   - **Access resolves through AIA authorization first.** A client-first route resolves the study
     through `ScopeResolver` (404 outside the caller's scope) and reads the unit project id from
     the binding; only then does the browser load that unit project.
   - **A unit project id supplied by the browser is never authorization.** The binding is written
     only through an issued `StudyContext` holding `EDIT_STUDY`, only once per study, and never to
     a unit project already bound elsewhere; no route accepts a unit project id to find a study.
   - **The unit store is not the target.** The Study is authoritative for everything in
     decision 2; the unit holds only the working content of the rebuilt stages, as a copy the
     migration will move. The direction stays: study state and client knowledge move into
     AIA-owned storage and contracts; the unit is retained only as the oracle and a fallback.
   - **Removal condition:** the research (and then simulation) stage state is stored and served by
     AIA's own study-scoped contracts (`/api/v1/studies/{study_id}/…`), the rebuilt stages no
     longer call the unit's project store, and the bound working content has been migrated. Then
     `study_workspaces` is dropped with a migration and this decision is retired.
   The unit itself remains single-tenant and open to organization owners and admins only
   (`LEGACY_PANEL_ROLES`, ADR 0012), so isolation of the bridged content is enforced at AIA's
   resolution layer and by that gate, not by the unit.

6. **A client-level scope.** `ScopeResolver.client_context()` is the only issuer of a
   `ClientContext`: an active member, a client of their organization that is not archived, and
   either a client-level grant (its role and permissions) or at least one study grant within the
   client (study-only access: those studies, and no client knowledge). Anything else raises
   `ScopeDenied` and the API answers 404, as for studies. **Starting a study** -- a research or a
   simulation -- under a client needs `CREATE_STUDY`, which a client-level `RESEARCHER` or `LEAD`
   holds (`CLIENT_ROLE_PERMISSIONS`); a `VIEWER`, a `REVIEWER` or study-only access cannot, and
   an organization role alone grants nothing (data owner, 2026-09-24).

7. **Client Knowledge — amends ADR 0004 rule 1.** Some client-derived objects belong to the client,
   not to one study: its sources, documents, datasets, approved facts and findings, terminology
   and entities, dimensions, audiences and artifacts. They carry `organization_id` and
   `client_id` and are read and written only through an issued `ClientContext` (or, for what a
   study consumes, its `StudyContext`, whose client id comes from the study row).
   - **Three layers, explicit and auditable:** *AIA shared intelligence* (platform data such as the
     population registry and shared definitions, no client columns) → *Client Knowledge* (private
     to one client) → *Study context* (what a study consumes). Retrieval resolves the scope first
     and puts it in the query; nothing queries an unscoped pool and filters afterwards.
   - **A study never mutates client knowledge.** It proposes (`client_knowledge_proposals`, with
     its study, project and origin as provenance); a person holding the approval permission
     decides — never the proposer unless self-approval is allowed at that scope, as for gates —
     and an approval appends an item revision and advances the client's **knowledge revision**.
     Revisions are append-only.
   - Knowledge management (reading the whole context, proposing directly, deciding) needs a
     client-level grant; a study-only grantee sees what their study consumes and nothing else.

8. **Research stages are re-homed, not rewritten.** The screens of PR #49 and #50 are mounted at
   `/app/clients/<client>/research/<study>/<stage>` with their store, save state, job runner and
   parity-tested logic unchanged. `/app/research/*` (unscoped) is retired; the unscoped classic
   project store moves under *Nastavení* as an administrative tool.

## Alternatives considered

- **Keep `/` on 18.6.6 until every area is rebuilt** (ADR 0014's exit condition). Rejected: the
  develop site would keep teaching the classic architecture for months, and each rebuilt screen
  would keep inheriting it.
- **Redirect `/` to a React copy of *Správa projektů*.** Rejected: a global, unscoped project list
  is exactly the hierarchy this ADR replaces.
- **Serve the classic interface only on the legacy hostname.** Rejected for the hand-off: that
  hostname is the oracle, deliberately unskinned and behind a basic-auth credential people should
  not need; the hand-off script and the way back must not be added to the oracle.
- **A database (or schema) per client.** Rejected: the hard boundary is the scope model plus the
  predicate in every query (ADR 0004), and nothing contractual requires physical separation.
  Row-level security remains owed as defence in depth.
- **Port the research store to AIA first.** Deferred: it is the right end state, but the unit's AI
  jobs read the unit's store, so it is its own change; the binding makes the move a data
  migration of one table later.

## Consequences

- The develop site opens on the client directory. People who need an unrebuilt capability see
  where they are going and can come back.
- **`/app` stays owner/admin-only for now — a temporary restriction, not the authorization model**
  (open item OI-59). The rebuilt stages still read and write the single-tenant unit, which
  cannot apply client or study scope, so the gate in front of `/app` is the panel gate. The
  target is unchanged: *authenticated user → organization membership → client grant → study
  grant*, exactly as every `/api/v1` route already resolves it. **Removal condition:** stage state
  is fully AIA-scoped (OI-58 closed for the stages a researcher uses); then `/app` moves to a gate
  that admits any provisioned member, and every page's data is resolved by `ScopeResolver` as
  now. Nothing in the client shell may depend on the caller being an owner or admin.
- CI's routing checks, the smoke script and the runbook change with the Caddyfile (`/` is a
  redirect; `/classic` is the gated document; no catch-all).
- A new permission family governs client knowledge; the permission matrix grows.

## Revisit when

- The research store moves to AIA: the binding is migrated and dropped (OI-58).
- Stage state is AIA-scoped: `/app` opens to every member with the right grants (OI-59).
- The last hand-off is gone: `/classic` is removed; the legacy hostname stays as the oracle.
