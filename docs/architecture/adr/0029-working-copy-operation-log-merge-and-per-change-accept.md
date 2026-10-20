# ADR 0029 — The working copy changes only through one operation vocabulary: an append-only log, an item-level merge, per-change accept and a hard lock on Sociomap inputs

**Status:** Accepted — 2026-10-20 (the product owner, in his words: "accept 0028-0033, 0035, 0038-0040; hold 0034, 0036, 0037").
Proposed the same day. **Amends**
[ADR 0026](0026-research-lead-proposes-a-person-decides.md) decision 5 (an item is keyed by a stable
id, no longer by its normalised text) and decision 6 (an accept may take some of a proposal's
changes, and a Lead edit's accept submits the Design Revision too). **Builds on**
[ADR 0018](0018-aia-runs-without-18-6-6.md) (a Study's working content lives in AIA) and
[ADR 0019](0019-two-roles-and-human-ai-gates.md) gate 1. **Leaves unchanged** the Design Revision as
what a run executes (ADR 0016), the evidence gates and every run's pins.
**Date:** 2026-10-20. **Amended 2026-10-20** with the product owner's recorded answers D-06, D-07,
D-08, D-30 and D-31 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, #523 @ `ee21982`).
**Plan:** [working-copy-edit-ops](../../../.planning/plans/working-copy-edit-ops.md) WCE0-WCE13

## Context

The owner decided on 2026-10-19 (F11, F12, Q15, Q16, Q27; `mvp-cohesion.md`) that a person and the
Lead edit through one server-validated vocabulary, that two researchers, each with their own Lead,
work one working copy, that a proposal's changes are accepted or rejected one by one, that every
operation is kept with its study, and that the Sociomap's inputs are locked behind a recorded unlock.
The code today:

- **A save is a whole copy, and a stale base is refused whole** (`stale_revision`,
  `infrastructure/study_workspace_repository.py:234-271 @ 854c209`). Two people editing different
  questions refuse each other.
- **The Lead's vocabulary is the only typed one**: `set_text`, `list_add/replace/remove`,
  `question_add/edit/remove`, `set_n` (`domain/research_lead.py:208-293 @ 854c209`), mirrored by hand
  in the web (`applyLeadEdit`). The web's 33 `store.update` sites write whatever they build.
- **Items are keyed by normalised text** (`domain/design_items.py:121 @ 854c209`), so a reword is a
  remove and an add, the research-question links break, and `FOCUS_ID` cannot name an objective or
  a research question (`domain/research_lead.py:176 @ 854c209`).
- **The accept is all or nothing**, and stale when the head Design Revision moved before any item is
  compared (`application/proposal_accept.py:117-118 @ 854c209`). Any job start, rebuild or visit to
  the Run stage submits a revision and kills every other pending proposal.
- **A Lead edit's accept saves the working copy and submits nothing**
  (`application/research_lead.py:504-601 @ 854c209`), so a run started afterwards executes the
  pre-accept design.

## Decision

### 1. One closed vocabulary, in the domain, read by both languages

`domain/edit_ops.py` owns every operation a person or the Lead may apply to the working copy:
today's Lead set, plus `question_move`, `question_merge`, `section_add/edit/remove/move`,
`set_add/edit/remove` (tracked sets), `route_set` (a display condition, WCE13), `scale_set`,
`comparison_set`, the Audience, Dimensions and Sample operations (WCE10) and the assumption
operations (`assumptions-and-open-answer-coding` AOC1). Each operation declares its item, its field,
its validation and whether it is a **text edit** (`TEXT_EDIT_OPS`, `domain/research_lead.py:314 @
854c209`). One fixture, `tests/fixtures/edit_ops/cases.json`, is read by the Python and the
TypeScript tests, so `applyLeadEdit` and `apply_edit` cannot drift.

### 2. Stable item identity

Objectives, research questions, hypotheses, options, battery objects, sections and questions carry
ids; existing content gets ids on load, deterministically, and is saved with them. `ItemKey`
(`design_items.py:79 @ 854c209`) and `FOCUS_ID` use the id; the text is a label. A reword keeps its
links. This replaces ADR 0026 decision 5's text keys.

### 3. `apply_edit_ops` is the only writer of the working copy, and every write is logged

`workspace_edit_ops` (M1) is append-only and insert-once: one row per operation, with its batch,
`base_revision`, `result_revision`, actor (`person` or `lead`, and the researcher whose Lead it is),
`source` (`ui`, `lead_turn`, `proposal_accept`, `undo`), `item_key`, `field`, the operation and its
inverse computed by code. It is kept with its study until a person deletes the study (Q27, MVPQ-07).

`apply_edit_ops` (application layer) is the only writer. The other six writers today (the PUT,
questionnaire import, design reuse, the 18.6.6 migration, Design Research accept, the web autosave)
become recorded **whole-copy operations** through it; none may skip the log or change a locked item.

### 4. The conflict rule: merge unless the same field moved

A batch names `base_revision`. The server reads the operations after it that touch the same
`(item_key, field)`. None: the batch applies to the **latest** working copy and answers
`merged: true`. Some: `409 edit_conflict`, naming those operations, so the screen marks that item
alone. Conflicts are per field, not per item (the product owner, 2026-10-20, D-06): two people
editing a question's wording and its options both merge. A whole-copy write keeps today's whole-copy stale rule.

### 5. A proposal goes stale only when an item it touches changed

The accept's stale rule becomes the item rule alone: stale when an item in `touched_items` changed
in the working copy since the proposal's baseline (or the baseline is unknown). A Design Revision
submitted elsewhere no longer stales a proposal on other items (WCE5).

### 6. Per-change accept, one mechanism for every proposal

A proposal's changes carry a **change identity** (item, operation, base revision, proposer). The
agent-job accept, Design Research's `item_ids` and the Lead's `indices` become one route that takes
`change_ids`. Coupled changes are one **dependent group** (a research-question reword and the
questionnaire links that name it), accepted or rejected together; a split that would leave the copy
invalid is refused by validation. `proposal_change_decisions` (M6, insert-once) records each
decision: `ACCEPTED`, `REJECTED`, `DROPPED_STALE`; a proposal is `ACCEPTED_IN_PART` when some were
taken. A change the person did not accept is `REJECTED` by default, and `DROPPED_STALE` when it
conflicted (the product owner, 2026-10-20, D-07).

**Every accept writes the working revision and submits the Design Revision in one transaction**
under the study lock, with the ledger row and the operations, so the head equals the working copy
after any accept. A test asserts it for each of the three sources.

**Shared proposals (Q16).** Any member with `EDIT_STUDY` and `APPROVE_GATE` may accept a change
another member's Lead prepared. The change reaches them through the change feed (decision 7)
**without the turn's text**; the accept does not require owning the turn.

### 7. Presence and the change feed poll

`study_presence` (M2): a heartbeat every 5 s, a row older than 20 s is not read, never audited,
never a lock. The change feed is a read of the log since a revision, with authors and pending
changes (change identity, item, proposer, status, never chat text). Both poll; there is no push
service (ADR 0002).

### 8. The Sociomap inputs are locked; the unlock is a person's recorded act

The declared Sociomap inputs (`sociomap_rating` questions and `context_objects` on a battery, with
the tracked sets they rate) are locked once declared: the declared inputs and the sets they rate,
the union, so nothing a map reads can move under it (the product owner, 2026-10-20, D-30). An operation that changes one is refused
unless the batch carries an unlock: `POST …/sociomap-unlock`, a person's act under `APPROVE_GATE`,
warned, one ledger row `sociomap_unlock`, valid for one working revision. **The Lead can never call
it**: it is not in the Lead's output schema and the command is human-only (ADR 0026 decision 4). A
questionnaire proposal copies protected inputs from its baseline under their ids, never from model
output (WCE8b).

### 9. Undo is an operation; automatic accept stays text-only by default

Undo writes the stored inverse as a new operation (`source = undo`) and is subject to the conflict
rule. A researcher's automatic accept takes text edits only by default; a per-stage structural
choice (MVP-14) is off by default, and cannot be turned on before undo exists. After fieldwork, a
structural automatic accept is refused, never applied silently.

**Who performs a structural automatic accept, and where it is switched on** (the product owner,
2026-10-20, D-31): a **named server path** applies it under the person's standing choice, so a
change a continuation turn or a plan step proposes with no browser open is not left waiting
overnight. It runs in the application layer as that person, with their `EDIT_STUDY` and
`APPROVE_GATE` read from their membership at the moment it applies, never from the worker's
context, and only for the stages that person switched on. The ledger row is marked automatic and
names the person and their setting ("automaticky, podle vašeho nastavení"). The switch is on Můj
Vedoucí, one per stage, off by default.

## Alternatives considered

- **Keep whole-copy saves with a stale refusal.** Two people refuse each other on unrelated items;
  the owner decided they work one copy.
- **Operational transforms or CRDTs.** Built for keystroke-level co-editing; the unit here is an
  item, edits are human-paced and an item-level conflict shown to a person is the honest answer.
- **Store revisions only, diff for the log.** A diff cannot say who did what, cannot undo one
  person's edit, and cannot attribute a Lead edit to its turn.
- **A push service for presence.** ADR 0002 rules it out; a 5 s poll is enough for about ten users.

## Consequences

- **Cost:** about 1,900 lines of TypeScript move onto the vocabulary stage by stage (WCE3a-c), with
  the 18.6.6 parity tests green at every step; every edit is a database write (an index plan and a
  test at 10,000 operations, `mvp-target-architecture.md` §9).
- **Gain:** "what changed since my Lead's last turn", attribution, undo, per-change accept and the
  lock all read one source.

## What enforces it

- `make layer_check`: `workspace_edit_ops`, `study_presence` and `proposal_change_decisions` are
  reached only through their repositories; the working copy's save is called only from
  `apply_edit_ops`.
- The shared fixture, run by `pytest` and Vitest.
- Tests: a whole-copy write leaves an operation and cannot change a locked item; two sessions on
  different items both merge; the same field conflicts on that item alone; after any accept the
  head's content equals the working copy's; member B accepts member A's Lead's change without reading
  A's turn and cannot read it through the feed; the Lead's schema cannot express an unlock.

## Unblocks

`working-copy-edit-ops` WCE0-WCE13 (M1, M2, M6), `research-lead-workbench` 14-19, AOC1, and gate I-1
(AC-02, AC-03, AC-07).

## Open for Nigel

Answered by the product owner on 2026-10-20 (`answers-2026-10-20.md`, #523 @ `ee21982`), and
written into the decisions above:

1. ~~Conflict granularity.~~ Per field, `(item_key, field)` (D-06, a). Decision 4.
2. ~~What an unaccepted change becomes.~~ `REJECTED` by default, `DROPPED_STALE` on conflict (D-07,
   a). Decision 6.
4. ~~What the lock covers.~~ The declared inputs and the sets they rate (D-30, a). Decision 8.
5. ~~Who performs a structural automatic accept.~~ A named server path under the person's standing
   choice, switched per stage on Můj Vedoucí, off by default (D-31, rec: (a) with (i)). Decision 9.
6. ~~Amending ADR 0026.~~ Yes, as this ADR is accepted (D-08, a).

3. ~~The route names.~~ `POST/GET …/workspace/ops?since=`, as this ADR has it (the coordinator,
   2026-10-20; the planning session aligns WCE4's wording).

Nothing remains open in this ADR.
