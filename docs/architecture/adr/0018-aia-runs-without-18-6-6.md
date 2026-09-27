# ADR 0018 — AIA runs without NPC Panel 18.6.6; the unit is reference only

**Status:** Proposed — develop (product direction, 2026-09-27). Implemented in increments
([plan](../../../.planning/plans/legacy-phase-out.md)); each decision below says which
increment carries it. **Supersedes**, once every increment has landed: the product-facade
decisions of [ADR 0012](0012-legacy-interface-as-product-facade.md) (the 18.6.6 interface
behind AIA sign-in; the panel gate), [ADR 0013](0013-interface-skin-at-the-facade.md) (the
skin, which exists only for that interface), [ADR 0014](0014-rebuild-the-interface-in-react.md)
decisions on the ledger-checked unit client and the fragment hand-off, and
[ADR 0015](0015-client-first-product-interface.md) decisions 4 (`/classic` and the unit's
paths on the product hostname) and 5 (the unit store as a bridge), and its OI-59
consequence (`/app` open to owners and admins only). **Amends**
[ADR 0011](0011-vendor-legacy-product-unit.md): the vendored unit stays, frozen, as the
behavioural reference and parity oracle; it is no longer part of the product deployment.
**Date:** 2026-09-27

## Context

AIA is its own application: its own architecture, interface, authentication, data model,
APIs, workers and deployment. On `develop` @ `4c4c3dd` its back end already was -- the API,
worker, executors and core never call the unit -- but the product was not
(`.planning/plans/legacy-phase-out.md` § Dependency inventory):

- the research stages kept their working content in the unit's single-tenant SQLite project
  store and loaded the unit's bootstrap before rendering (OI-58);
- `/app` sat behind the legacy panel gate, open to organization owners and admins only, and
  switched off by `AIA_LEGACY_PANEL_ENABLED` -- which production refuses (OI-59);
- `/classic` and a dozen links handed people to the 18.6.6 interface;
- the deployment built, ran, hydrated and smoke-checked the unit, and CI failed a Caddyfile
  that did not route to it.

18.6.6 remains valuable as a reference -- behaviour, methodology, datasets, algorithms,
prompts -- and as the oracle parity is measured against. Neither needs it in the product.

## Decision

1. **A research Study's working content is AIA's** (increment 1). It is an owned AIA project
   (`projects.owner = study_workspace`), found only through the Study's `study_workspaces`
   row and served at `/api/v1/studies/{study_id}/workspace/content`. Saves are
   `ProjectRepository.save` revisions -- immutable, deduplicated, with event history -- and
   each names the revision it was edited from: a save from a stale copy is refused (409),
   never applied over a newer one. The row names a `ContentState`; a Study never shows an
   empty document in place of content it does not have:

   | State | Meaning |
   | --- | --- |
   | `EMPTY` | nothing saved yet; the stages start from the research template |
   | `NATIVE` | saved in AIA |
   | `MIGRATED` | brought from the 18.6.6 store by the migration, with lineage |
   | `RECOVERED` | the bound 18.6.6 project was gone; recovered from the Study's newest Design Revision, with lineage |
   | `UNRECOVERABLE` | the bound 18.6.6 project was gone and nothing recoverable existed; a person who may edit starts again explicitly |
   | `AWAITING_MIGRATION` | bound to an 18.6.6 project not yet migrated; **not editable**, so the content cannot fork |

   The research template is AIA's copy of the unit's empty project
   (`aia_core.domain.research_template`), pinned to the unit's answer by a test. The working
   copy is not what runs execute: a run still executes a Design Revision the browser submits
   (ADR 0016), and the Run stage submits only what AIA holds -- a change still waiting for its
   save is saved first, and a copy whose save was refused as stale is never submitted. The working copy is stored as the stage saved it: 18.6.6 ran every save through
   `normalize_project` and refused a project that did not normalize, so an autosave of a
   half-edited question failed; AIA keeps the person's work and applies its rules where they
   decide something, when a Design Revision compiles. The brief's files are artifacts of the
   working project; a questionnaire file is read in AIA and yields sections, normalized by the
   unit's rules for an import, compared with the unit's own function. *Rejected:* a parallel table of working revisions (duplicates
   `project_revisions`); saving autosaves as Design Revisions (every keystroke-pause would
   become something a run could execute, and flood the list ADR 0016 reads).

2. **Legacy working content is migrated explicitly, once, with a report** (increment 2). An
   operator command (`python -m aia_executors.legacy_workspace`) reads a WAL-safe *copy* of
   the unit's `project_store.sqlite` read-only and its attachment directory, brings each
   `AWAITING_MIGRATION` Study's project -- every revision, its analysis, its attachments into
   AIA storage -- over with lineage, validates the result against the source, and reports
   every case it could not migrate. It never writes or deletes the source; nothing in the
   product reads it afterwards. How it does that:

   - **As a person, through their grants.** The operator names an active AIA user; each Study
     is opened through the scope `ScopeResolver` issues that person, with `EDIT_STUDY`. A
     Study they may not edit, a closed Study and a simulation project are reported and left
     waiting. An organization owner has no implicit access here either.
   - **One for one.** AIA revision *k* is the unit's *k*-th, with its analysis and a reason
     `unit:<the unit's reason>`; a repeated document is still its own revision. The unit
     recorded no author, so a migrated revision has none (`created_by` null) rather than the
     operator's name; one `WORKSPACE_MIGRATED` project event names who ran it. The unit's
     revision ids, timestamps, reasons and hashes are kept in the Study's lineage.
   - **Files by artifact id.** Each file a brief names, and each the unit bound to the project
     that no brief names, is copied into AIA storage when its bytes match the SHA256 the unit
     recorded; its brief record then names the artifact (`attachment_id`), keeps the unit's id
     (`legacy_attachment_id`) and drops the unit's URL and stored name. A file missing from the
     copy, or changed, is reported and its record kept exactly, so the brief marks it as not in
     AIA.
   - **Checked twice.** Before writing: every revision must hash to the SHA256 the unit
     recorded (the unit's `_sha` and AIA's `fingerprint` are one function) and be content AIA
     can hold. After writing, in the same transaction: every revision's hash must be the
     source's with its file records rewritten. A Study that fails either is rolled back and
     stays waiting, with the difference in the report.
   - **Dry run by default; `--apply` writes.** Each Study is its own transaction. A second run
     changes nothing and lists what was done before.
   - **Missing is not lost until the operator says so.** A Study whose unit project is not in
     the copy stays waiting. Only with `--recover-missing` -- the operator's statement that the
     copy is complete -- does it become `RECOVERED` from its newest Design Revision, or
     `UNRECOVERABLE`, so a partial or wrong copy cannot decide a Study's fate. The stages say
     that recovered content is the last submitted design, not the last save.
   - Every unit project no Study refers to is listed; it stays in the unit's volume.

3. **`/app` has AIA's own gate** (increment 3): any active organization member with an AIA
   session; every page's data is authorized per call by `ScopeResolver`, as it always was.
   No legacy flag decides whether AIA can be reached. `/login` turns the Cognito id token
   into an HttpOnly session cookie (`POST /api/v1/session`, `aia_session`, admission by
   `ScopeResolver.authorize_session`, recorded in the access audit). Caddy asks
   `GET /api/v1/session/gate` before every request to `/app`: a navigation without a
   session goes to `/login`, a fetch gets 401, and any method but GET and HEAD is refused,
   because the pages take no writes. The web client's switch for `/app`
   (`AIA_INTERFACE_REHOME_ENABLED`, ADR 0014) is retired there: it existed so the classic
   interface could stand in. While the unit's paths remain on the product hostname, they
   keep the owner/admin panel gate. Until increment 4, `/login` opened that session too, best
   effort, for the 18.6.6 interface alone; since increment 4 it does not, and sign-out still
   clears a panel cookie an earlier sign-in left, as long as the panel's gate stands.
   *Rejected:* opening `/app` to anyone signed in to Cognito (a page shell is harmless, but
   a person who is no member has no business in the product); keeping the panel gate with a
   wider role set (it answers 404 when the legacy flag is off and is refused in production,
   so AIA would still depend on it).

4. **The interface hands nothing to 18.6.6** (increment 4). No page links to the 18.6.6
   interface or opens one of its screens; the web client serves no 18.6.6 document and no
   skin, and calls none of the unit's paths. `/classic` stays a path, because old links and
   bookmarks point at it: it is the web client's public page saying the 18.6.6 interface is
   not part of AIA, with the way into AIA; it shows no data, so it needs no gate. A capability
   AIA does not have says so where the person is (*V AIA zatím není*): the simulation flow,
   the Data Library, verification and the next-steps stage, the 18.6.6 client report and the
   Sociomap's interactive tools, what 18.6.6 computed from its licensed panel (audience
   filters, the feasibility check, subpanels, customer audiences, panel factors), and Deep
   Research for a dimension. `docs/migration/interface-screens.json` records every classic
   screen as `REBUILT`, `REBUILDING`, `SUPERSEDED` (AIA does its job its own way) or
   `NOT_IN_AIA` with the AIA page that says so (none where AIA has no place a person would
   look for it, as for the unit's DEMO library); its test fails a screen with any other
   status. The classic projects screens (`/app/settings/classic-projects`), the last caller
   of the unit's store, are removed: a Study's bound project comes over by the migration
   (decision 2), and until then the Study says it is waiting; a unit project no Study refers
   to stays in the unit's volume, listed in the migration's report. *Rejected:* redirecting `/classic`
   to `/app/clients` without a word (a person who followed a link to 18.6.6 would land
   elsewhere without knowing why); keeping the hand-off for owners until increment 5 (each
   hand-off is a way for a supported workflow to keep needing the unit); removing the
   notices with the hand-offs (hiding a missing capability does not make it AIA's).

5. **The product deployment has no unit** (increment 5): no `legacy-panel` image, service,
   volume mount, hostname, credentials, data sync or health check; CI fails a product
   Caddyfile that routes to the unit. The unit runs, when a comparison needs it, from a
   separate optional reference setup (`deploy/reference/`), reached on the host's loopback.
   Its working volume and data bundle are left exactly as they are.

## Consequences

- The research flow saves, reloads, executes and shows its results with the unit stopped.
- Studies bound to 18.6.6 are read-only until the migration runs; the operator runs it
  between increments 2 and 5.
- Capabilities that exist only in 18.6.6 are unavailable in the product until rebuilt, and
  say so; they are no longer reachable through a hand-off.
- The parity oracle is reachable only from the reference setup; the oracle CI job still skips
  without its secrets, as it did.

## Revisit when

- A capability listed as unavailable in decision 4 is rebuilt: its notice goes.
- The migration has run on develop and its report is accepted: the `AWAITING_MIGRATION` state
  can no longer be entered, and `unit_project_id` becomes history only.
