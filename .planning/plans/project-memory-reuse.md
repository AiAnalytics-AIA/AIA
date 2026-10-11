---
status: in-progress
chunks:
  - "[x] M0. Decide the reuse unit, its eligibility and its reach (owner, 2026-10-10)"
  - "[x] M1a. The match, pure: dimension titles in the core, accent-folded words, the fields that matched"
  - "[x] M1b. The search, scoped to one client: latest Design Revision, else the working draft, else the name"
  - "[ ] M1c. The route: GET /clients/{client_id}/memory/search"
  - "[ ] M1d. The pages: Projektová paměť asks for a client first; the client's Výzkumy list searches too"
  - "[ ] M2. Inspect: a past study's design, method, results and their labels, read-only"
  - "[ ] M3. Reuse a past study's design in a new one: a person accepts, the revision cites its source, labels carried"
  - "[ ] M4. Proof: the source unchanged, labels carried, another client and another organization refused"
---
# Project memory: a past study's design reused in a new one, with its citation

**Owner:** unassigned. **Written:** 2026-10-09, from `mvp-workflow-assurance.md` A2
(`develop @ c6ee438`); **re-cut to the MVP scope 2026-10-10** by the owner's answers below.
Depends on nothing unbuilt: the past study's Design Revisions, results and labels already
exist and are found through the Study. `client-knowledge-lifecycle.md` keeps the reuse of
individual results (its § Consumers, "Project memory"); see *After the MVP*.

## M0. Decisions (owner, 2026-10-10)

1. **Reach: the same client only.** A study sees the past studies of its own client and no
   other, nor another organization's. Reuse of a method across clients may come later as an
   explicit, labelled action; it is not built here.
2. **Reusing individual results is out of the MVP.** Nothing marks a result as approved for
   reuse, wraps it in a knowledge item or searches across results. The MVP reuses how a past
   study was **designed** (its Design Revision: brief, questions, questionnaire, audience,
   dimensions), not what it found. A finding still reaches a new study as Client Knowledge
   written and accepted by a person, as today, without a link back to the exact result.
   When result reuse is built, its unit is a knowledge item pointing at the exact artifact
   (recommended, not yet decided).
3. **Draft and synthetic sources may be reused, their labels carried and enforced.** A design
   taken from a study whose data was synthetic (`SYNTHETIC_AI_FICTIONAL`, `SYNTHETIC_FIXTURE`)
   or whose report is `DRAFT_UNAPPROVED` carries those labels into the new design, where it is
   design input only and never evidence.

## What exists and where it stops (at `c6ee438`)

| Hop | State | Anchor |
|---|---|---|
| Find past studies | Navigation only | `apps/web/src/components/aia/GlobalPages.tsx:41-49` (names and client names) |
| Find approved reusable artifacts | ABSENT | `research_artifacts` reads one study's own project (`application/research.py:76-85`) |
| Approve an artifact | No caller | `infrastructure/artifact_repository.py:523-571` (`approve`) is called only by tests; `is_reusable` means a fingerprint cache hit, not approval |
| The memory agent | Own client's knowledge only | `domain/research_agents.py:477-514`; it never reads another study's artifacts |
| Inspect sources and method | Inside one study | report `review_state` and `synthetic` (`apps/api/src/aia_api/routers/research.py:949-953`); artifact provenance (`artifact_repository.py:89-118`) |
| Propose reuse | Untyped | a study's knowledge proposal is free kind/title/summary (`routers/workspace.py:385-394`); the `ARTIFACT` kind exists (`domain/knowledge.py:81`) and nothing creates one |
| A person accepts | EXISTS for knowledge | `client_knowledge_repository.py:355`; flaw F-K1 (`client-knowledge-lifecycle.md`) |
| Into a new Design Revision | Refused | accepting an advice answer raises `advice_only` (`application/research.py:637-638`); a revision's provenance is only `source_stage` (`study_design_repository.py:34-36`) |
| Past results stay immutable | Mechanism | revisions immutable (`domain/design.py:98`); `freeze` one-way (`artifact_repository.py:573-587`) |
| Another organization refused | Primitives | `application/scope.py:376-381, 426-462`; no memory test |

18.6.6 searched every project's revisions for whitelisted artifact types with `status='VALID'`
and no approval or tenant (`legacy/npc-panel-18.6.6/app/project_memory.py`,
`POST /api/assistant/search`); its route is undecided in `legacy-route-ledger.json`.

## Chunks

- **M1. Find.** One search over the client's own studies (`accessible_studies` within the
  client of the scope), matching name, goal, research questions and dimension titles from each
  study's latest Design Revision. A study of another client is never returned. The search
  lives under the client (its id from the client workspace's route, never inferred); the
  global Projektová paměť page (`GlobalPages.tsx` `MemoryPage`, which today aggregates every
  accessible client's studies) asks for a client first and issues the same per-client search,
  never one across clients. Replaces its name-only filter and the client workspace's.
  *Done when:* a search names the studies whose design matches, and a test shows another
  client's matching study absent.
- **M2. Inspect.** A past study's page, read-only: its Design Revisions, its runs and their
  results through the existing study routes, with every label the result carries (synthetic,
  draft, `INTERNAL_ONLY`, suppression). No new reader: `research_artifacts` stays the only one.
- **M3. Reuse the design.** From a past study, "start from this design" into a new or an
  existing study of the same client, by the person who asked. Into an existing design it is
  submitted through `submit_if_current` against that study's own latest revision; into a study
  with no design yet, `submit_if_current` has nothing to compare (it rejects a study with no
  latest revision, `study_design_repository.py:146-163`), so the first revision goes through
  `submit` (`:103`), or one repository operation that takes either case explicitly. The new
  revision records its source (source study id and Design Revision id) and the source's
  labels in a provenance field of its own (today a revision's provenance is only
  `source_stage`, `study_design_repository.py:34-36`). **The labels are derived by one
  conservative rule, never picked:** over every run executed of that source revision, the
  union of what they carry (any synthetic fieldwork origin makes the source synthetic; any
  report `DRAFT_UNAPPROVED` makes it draft; no run makes it "never run"), recorded with the
  run and report artifact ids it was derived from, so a later run of the source cannot
  change what was cited. The
  same may be done for one part (questionnaire, dimensions). The labels are shown wherever the
  new design is, and nothing in the new study counts the source's data as evidence.
  *Done when:* a reused design opens in the new study with its citation and labels, and the
  source study's revisions are unchanged.
- **M4. Proof.** One connected test: reuse from a synthetic source, the source's revisions and
  artifacts byte-identical afterwards, the labels on the new revision, and **both** refusals
  asserted separately: a sibling client's request for the source in the same organization is a
  404, and another organization's request is a 404 (one passing cannot stand for the other: an
  organization predicate alone would pass the second and still expose a sibling client).

## After the MVP

Reusing individual results: approving an artifact for reuse (`ArtifactRepository.approve` has
no caller outside tests), a knowledge item pointing at it with its identity and limitations
derived by the server, search across them, and a cited reuse into a design. Cross-client reuse
of a method, as an explicit labelled action. 18.6.6's assistant search
(`legacy/npc-panel-18.6.6/app/project_memory.py`, `POST /api/assistant/search`) is superseded
by M1 for studies; its route-ledger entry is decided with this section.

## M1, the design (2026-10-12)

**Decisions (owner, 2026-10-12).** (a) Dimensions are matched by their **titles**, resolved
on the server: the 18 canonical labels move into `aia_core`, and a client's own dimension (a
Client Knowledge `DIMENSION` item) is named by its title from that client's knowledge. (b) A
study with no Design Revision is searched on its **working content**, and a hit there is
labelled a working draft, never a design.

**What the code has.** A design stores dimension ids (`persona_dimensions.approved`: slugs
such as `zdravi`, or knowledge item ids), never titles; the titles are only in the web
(`apps/web/src/research/persona.ts` `PERSONA_DIM_LABELS`). One client's studies are listed
through `ScopeResolver.client_context` (`application/scope.py`), and a study's design and
working content are read only under its own `StudyContext` (`study_design_repository.py`,
`study_workspace_repository.py`), which `layer_check` keeps that way. Many studies have no
Design Revision: a study before its first submission, every simulation, every study migrated
from 18.6.6.

**Chunks.**

- **M1a. The match, pure.** `domain/project_memory.py`: `DIMENSION_LABELS` (pinned to the
  web's by a test), `fold` (Unicode-decomposed, combining marks dropped, case-folded), the
  searchable text of one study (its name; the content's `title`, `goal`, `decision_use`,
  `research_plan.research_questions`, `research_plan.objectives`, `sections[].title` and
  battery `object_family`; its dimensions' titles), and `match(query, study)`: every word of
  the query must occur, folded, in some field; the answer names the fields that matched, with
  the text that matched.
- **M1b. The search, scoped.** `application/project_memory.py` `search_client_studies`:
  `client_context` for the client the route names (a client the person cannot see is
  `ScopeDenied`), then each study of that client through `study_context` -- the only way to
  read its design. Source per study: the latest Design Revision (`design`, with its number),
  else the working content (`draft`), else the name alone (`name`). The client's dimension
  titles come from its own knowledge, read once under the `ClientContext`. Another client's
  study is never read: the loop is over `ClientContext.study_ids`.
- **M1c. The route.** `GET /api/v1/clients/{client_id}/memory/search?q=` (two characters at
  least): the hits, newest study first. 404 for a client the person cannot see. Tests: a
  sibling client's matching study is absent; another organization's request is 404; a draft
  hit says draft; a dimension found by its Czech title.
- **M1d. The pages.** Projektová paměť asks for a client first and runs that client's search;
  the client workspace's Výzkumy list gets the same search. Each hit says what matched and
  whether it came from a design, a draft or the name.

**Cost.** About six queries per study searched (the resolver's study context, then its design
or working content); a client with 50 studies is about 300 small queries, under a second on
PostgreSQL. A client with hundreds of studies would want one client-wide read in
`study_design_repository.py`; not built until that is measured.

**Not in M1:** reuse (M3), the inspection page (M2), result search (after the MVP).
