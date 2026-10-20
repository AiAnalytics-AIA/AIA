# ADR 0030 — The Lead over time: it proposes updates to its own files, the researcher approves each, and a Lead belongs to its researcher alone

**Status:** Proposed — 2026-10-20. Not accepted until the product owner says so. **Amends**
[ADR 0026](0026-research-lead-proposes-a-person-decides.md) *Accepted with* 6 (the Lead proposes
updates to its own files on what it observes, not only when asked; revisions become readable and
restorable). **Builds on** [ADR 0004](0004-client-study-isolation.md) (client isolation decides
what a note may carry), [ADR 0008](0008-eu-data-residency.md) as amended 2026-10-19 (the Lead's
personal files are Class C, its client notes Class A) and
[ADR 0019](0019-two-roles-and-human-ai-gates.md). **Leaves unchanged** ADR 0026 decision 8: a
researcher's turns, and now also their Lead's files and notes, are read by nobody else.
**Date:** 2026-10-20. **Amended 2026-10-20** with the product owner's recorded answers D-32, D-33,
D-34 and Q5 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, #523 @ `ee21982`): no admin
read, no handover, no departure trigger; still Proposed.
**Plan:** [lead-orchestration](../../../.planning/plans/lead-orchestration.md) LO11 (migration M7)

## Context

Each researcher has their own Lead: a name, a SOUL and a USER file (each at most 2,000
characters, `infrastructure/tables.py:821-857 @ 854c209`), notes personal or for one client, all
with revisions. The Lead changes its files only through `self_update`, when the researcher asks
(`domain/research_lead.py:389 @ 854c209`). Nothing prompts either side to update them, so a Lead
barely evolves. File revisions are written and never read: `ResearcherLeadRepository.revisions()`
(`infrastructure/researcher_lead_repository.py:187 @ 854c209`) has no caller outside its tests
(`apps/executors/tests/test_research_lead_executor.py:407, 428 @ 854c209`).

The owner decided on 2026-10-19 (F14, Q18, Q19, Q26; `mvp-cohesion.md`) that the Lead proposes
updates and the researcher approves each, and that turns stay private. The same day's notes also
spoke of an admin reading a Lead and handing it on; on 2026-10-20 the owner withdrew that (D-32 to
D-34, Q5): "each researcher gets their own agent they build. they dont get transferred", "leads
dont change researchers", and there is no study assignment: "opening a study, just shows their own
agent within that studies artifacts". The draft's admin read and handover are therefore removed.

## Decision

### 1. Signals: what the Lead may learn from, by id, never by text

`researcher_lead_signals` (M7, insert-once): `signal_id`, `lead_id`, `organization_id`, `user_id`,
`kind` (`undid_lead_edit`, `rejected_lead_proposal`, `repeated_instruction`), `ref` (ids only: the
operation, change or turn), `created_at`, `consumed_turn_id`. The application layer writes one in
the transaction where a person undoes a Lead's operation (ADR 0029 decision 9) or rejects its
change. `repeated_instruction` is written by code that compares the person's own messages, never by
the model. A signal holds no text, no client name and no number.

### 2. Proposed updates, each approved

The Lead's next turn sees the unconsumed signals in its context and may return a `self_update` (the
closed output's existing field), shown as a "Pamatovat si" card. The researcher accepts, edits or
refuses it (`lead_self_update`, as built). A periodic review is **computed, not stored**: due at ten
unconsumed signals or thirty days since the last review, it adds one line to the turn's context; the
Lead may then propose. Nothing changes a file without a yes. A proposal's size is bounded by the
files' existing bounds; a proposal over them is refused, never truncated.

### 3. What a personal file may carry

A personal file or note holds working style and preferences only and goes with the researcher into
every study (Class C). A client fact belongs in a client note (Class A), which loads only into that
client's studies. The Lead's proposal is checked before it is shown: a proposed personal text that
contains the name of any client of the organization, or a number, is refused by code as
`client_fact_in_personal_file` and the Lead is told to propose a client note instead. The residual
risk (a client fact in words no check catches) stays as ADR 0026 *Accepted with* 6 states it: the
person sees every proposal before it is kept.

### 4. Revisions are readable and can be rolled back

The researcher reads every revision of their own files on Můj Vedoucí and can restore one; a restore
is a new revision, never a deletion.

### 5. A Lead is its researcher's alone: never read by another person, transferred or assigned

Each researcher builds and names their own Lead (the product owner, 2026-10-20, D-32 to D-34). No
permission lets anyone else read its files, notes or turns, an OWNER or ADMIN included; there is no
handover, no copy for a successor and no departure trigger. A study is not assigned to a Lead
(Q5): whoever opens a study works there with their own Lead, which carries its own files and that
study's context. Every read of `researcher_leads`, its revisions, notes and signals, and of
`study_lead_turns`, filters by the caller's own `user_id`.

What becomes of a deactivated member's Lead (kept read-only, or deleted under the deletion path of
MVPQ-07) is not decided here (*Open for Nigel*, 1).

## Alternatives considered

- **Let the model update its files on its own.** Rejected by the owner: nothing changes without a
  yes.
- **Store signals as text summaries.** A summary of a correction would carry the client material
  the correction was about into a Class C store.
- **An admin read of files and notes, and handover as a copy** (this ADR's draft). Withdrawn by the
  owner (D-32 to D-34): a Lead is never transferred.
- **Assign a study to one researcher's Lead.** Rejected by the owner (Q5).
- **Let an admin read turns.** Rejected by the owner (Q26).

## Consequences

- **New:** one table (`researcher_lead_signals`) and a revision reader with restore. The M7
  columns `archived_at` and `derived_from_lead_id`, the `READ_LEAD_FILES` permission, the
  `LEAD_FILES_READ` and `LEAD_HANDED_ON` audit actions and the two admin routes the target
  architecture proposed (§3.6, §5) are **not** built.
- **Lost, as decided:** when a researcher leaves, nobody inherits what their Lead learned about a
  client.
- **Cost:** a Lead turn's context grows by its unconsumed signals (ids and kinds, bounded).

## What enforces it

- `make layer_check`: `researcher_lead_signals` only through its repository.
- Tests: no query of `study_lead_turns`, `researcher_leads`, its revisions, notes or signals lacks
  the caller's `user_id` filter (a repository test over every method); an OWNER or ADMIN asking for
  another member's Lead gets 404; a proposed personal file naming a client of the organization is
  refused; a restore writes a new revision; a second organization's Lead answers 404.

## Unblocks

`lead-orchestration` LO11 (M7, W2) and the Lead's lifecycle in gate I-2.

## Open for Nigel

Answered by the product owner on 2026-10-20 (`answers-2026-10-20.md`, #523 @ `ee21982`):

- ~~Are client notes copied on handover?~~ There is no handover (D-34).
- ~~The departure trigger.~~ None; Leads are not transferred (D-32).
- ~~`READ_LEAD_FILES` and ADR 0019.~~ No admin read (D-33).
- ~~Amending ADR 0026.~~ Yes, as this ADR is accepted (D-08); the amendment is now narrower.

Still open:

1. **A deactivated member's Lead.** Kept read-only and unreadable by anyone, or deleted with the
   member under MVPQ-07's deletion path (content-free usage rows kept)? D-27 adds member removal.
2. **The per-study context file** (Q5, Q10: code plus "Poznámky ke studii", any Lead proposes, a
   person accepts) is new scope (`lead-orchestration#LO19`). It is the study's, not the Lead's, so
   this ADR does not decide it; does it need an ADR of its own, or a section here?
