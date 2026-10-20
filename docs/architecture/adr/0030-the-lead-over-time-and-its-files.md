# ADR 0030 — The Lead over time: it proposes updates to its own files, an admin may read and hand them on, and the turns stay private

**Status:** Proposed — 2026-10-20. Not accepted until the product owner says so. **Amends**
[ADR 0026](0026-research-lead-proposes-a-person-decides.md) decision 8 and *Accepted with* 6 (the
Lead's files and notes become readable by an organization OWNER or ADMIN; a Lead can be handed on
as a copy; a Lead can be archived). **Builds on** [ADR 0004](0004-client-study-isolation.md)
(client isolation decides what a note may carry), [ADR 0008](0008-eu-data-residency.md) as amended
2026-10-19 (the Lead's personal files are Class C, its client notes Class A) and
[ADR 0019](0019-two-roles-and-human-ai-gates.md) (one Researcher role; the Admin adds system
settings and user administration). **Leaves unchanged** the privacy of a researcher's turns, the
Lead's closed output and every study's design and results.
**Date:** 2026-10-20
**Plan:** [lead-orchestration](../../../.planning/plans/lead-orchestration.md) LO11 (migration M7)

## Context

Each researcher has their own Lead: a name, a SOUL and a USER file (each at most 2,000
characters, `infrastructure/tables.py:821-857 @ 854c209`), notes personal or for one client, all
with revisions. The Lead changes its files only through `self_update`, when the researcher asks
(`domain/research_lead.py:389 @ 854c209`). Nothing prompts either side to update them, so a Lead
barely evolves. File revisions are written and never read: `ResearcherLeadRepository.revisions()`
(`infrastructure/researcher_lead_repository.py:187 @ 854c209`) has no caller outside its tests
(`apps/executors/tests/test_research_lead_executor.py:407, 428 @ 854c209`). And when a researcher
leaves, their Lead has no successor.

The owner decided on 2026-10-19 (F14, Q18, Q19, Q26; `mvp-cohesion.md`): the Lead proposes updates
and the researcher approves each; an organization admin can read a researcher's Lead (files and
notes) and hand it on; turns stay private; a handed-on Lead is a copy with personal notes removed;
the departed researcher's Lead is archived, never reassigned.

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

### 5. An admin reads files and notes, never turns

A new permission, `READ_LEAD_FILES`, held by an organization OWNER or ADMIN and not by the
Researcher role, reads a named researcher's Lead: its name, SOUL, USER, revisions and notes
(personal and client). **It never reads turns**: `study_lead_turns` and the Lead turns' outputs stay
filtered by `user_id` in every query (ADR 0026 decision 8). Each read writes `access_audit`
`LEAD_FILES_READ`, naming the reader and the Lead.

### 6. Handover is a copy; the original is archived

`POST /admin/leads/{user_id}/handover` (OWNER or ADMIN, `LEAD_HANDED_ON` in the audit) creates a
new Lead for the successor with `derived_from_lead_id` set: the name, the SOUL and the client notes
copied; the USER file (it describes the departed researcher) and every personal note **not**
copied. The departed researcher's Lead gets `archived_at` and is read-only; it is never reassigned.
Turns are not copied and stay with the archived Lead, readable by nobody but its owner (who, having
left, reads nothing).

## Alternatives considered

- **Let the model update its files on its own.** Rejected by the owner: nothing changes without a
  yes.
- **Store signals as text summaries.** A summary of a correction would carry the client material
  the correction was about into a Class C store.
- **Reassign the departed researcher's Lead.** It would hand the successor the predecessor's personal
  profile and make the predecessor's turns readable by another person.
- **Let an admin read turns.** Rejected by the owner (Q26).

## Consequences

- **New:** one table, two columns on `researcher_leads` (`archived_at`, `derived_from_lead_id`), one
  permission, two audit actions, two admin routes.
- **Weakened, as decided:** a researcher's Lead files are no longer private from an admin. The pane
  says so on Můj Vedoucí.
- **Cost:** a Lead turn's context grows by its unconsumed signals (ids and kinds, bounded).

## What enforces it

- `make layer_check`: `researcher_lead_signals` only through its repository.
- Tests: no query of `study_lead_turns` lacks the `user_id` filter (a repository test over every
  method); an admin read writes `LEAD_FILES_READ` and returns no turn; a Researcher without
  `READ_LEAD_FILES` gets 404; a handed-on copy has no personal notes and no USER text; a proposed
  personal file naming a client of the organization is refused; a second organization's Lead answers
  404.

## Unblocks

`lead-orchestration` LO11 (M7, W2) and the Lead's lifecycle in gate I-2.

## Open for Nigel

1. **Are client notes copied on handover?** "A copy with personal notes removed" implies client notes
   go with the copy; they are the predecessor's working notes about a client, Class A, visible only in
   that client's studies. This ADR copies them; the alternative copies nothing but the name and SOUL.
2. **The departure trigger** (LO11). Who marks a researcher as departed and what happens to their
   Lead until a handover: this ADR has an admin act alone, with no automatic trigger on a user being
   deactivated.
3. **`READ_LEAD_FILES` and ADR 0019.** ADR 0019 gives the Admin "system settings and user
   administration"; reading another person's assistant files is neither. Confirm it belongs to OWNER
   and ADMIN.
4. **Amending ADR 0026, which is Accepted**, decision 8 and *Accepted with* 6, needs the owner's
   explicit yes.
