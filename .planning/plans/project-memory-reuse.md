---
status: planned
chunks:
  - "[ ] M0. Decide the reuse unit, its eligibility and its reach (questions below)"
  - "[ ] M1. Approve an artifact for reuse: ArtifactRepository.approve behind a route, a person's act"
  - "[ ] M2. A reusable item: an ARTIFACT knowledge item whose identity and limitations the server derives"
  - "[ ] M3. Scoped retrieval: an organization-bounded search over approved items and past studies"
  - "[ ] M4. Cited reuse into a new Design Revision, accepted by a person"
  - "[ ] M5. Proof: the source unchanged, limitations carried, another organization refused"
---
# Project memory: an approved result reused in a new study, with its citation

**Owner:** unassigned. **Written:** 2026-10-09, from `mvp-workflow-assurance.md` A2
(`develop @ c6ee438`). `client-knowledge-lifecycle.md` describes project memory in prose
("retrieve accepted reusable items with original scope, source, method and evidence category.
Reuse proposes exact revisions for a new study and requires explicit accept", § Consumers)
and the reusable-artifact record type, but none of its chunks K2-K7 builds retrieval or the
path from reuse to a design. This plan owns those hops and depends on K3 (typed revisions
against a reviewed base) and K4 (a study's frozen context).

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

## M0. Questions for the owner

1. May memory reach across clients inside one organization? The knowledge plan forbids silent
   copying between clients; the MVP journey only excludes another organization.
2. Is the unit of reuse a raw artifact, or a Client Knowledge `ARTIFACT` / `FINDING` item that
   wraps one (recommended: the item, so acceptance, revision and retirement are the knowledge
   plan's)?
3. May a synthetic or `DRAFT_UNAPPROVED` artifact be reused with its labels, or is it excluded?
   Either way a synthetic finding never returns as independent measured evidence.
4. Does a Design Revision carry its citations in a new provenance field (recommended) or in
   its reason?
5. Is 18.6.6's assistant search ported, or retired in favour of M3?

## Chunks

- **M1. Approval.** `approve` behind a route and a permission, a named person's act in the
  approval ledger. "Approved for reuse" = approved, frozen and valid, kept separate from
  eligibility for a given use.
- **M2. The item.** Proposing an `ARTIFACT` item from a study: the server derives artifact id,
  sha256, run, project revision, method and limitations (`synthetic`, `review_state`, method
  status) from the row, never from the request. Needs K3's base-revision check.
- **M3. Retrieval.** One search, bounded by `accessible_clients` (and M0.1), returning approved
  items and past studies with source study, revision and limitations.
- **M4. Reuse.** A reuse proposal citing item ids; a person's acceptance writes a new Design
  Revision through `submit_if_current`, with its citations and the limitations carried, and a
  ledger row (the pattern of `application/design_research.py:81-133`).
- **M5. Proof.** The source study's artifacts are byte-identical after reuse, the synthetic
  label persists into the new design, and another organization's request is a 404.
