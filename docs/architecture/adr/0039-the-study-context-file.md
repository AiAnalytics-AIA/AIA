# ADR 0039 — Every study has a context file every researcher's Lead reads: code-built facts plus "Poznámky ke studii", versioned, frozen into each turn

**Status:** Proposed — 2026-10-20, from the product owner's answers Q5 (c) and Q10 (b) of the same
day (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, #523 @ `ee21982`). Not accepted until
the product owner says so. **Amends** [ADR 0026](0026-research-lead-proposes-a-person-decides.md)
decision 2 (the Lead's *Study's state* layer becomes the study context file). **Builds on**
[ADR 0029](0029-working-copy-operation-log-merge-and-per-change-accept.md) (the operation log, per-change
accept and the automatic text accept) and [ADR 0030](0030-the-lead-over-time-and-its-files.md) (a
Lead is its researcher's alone). **Leaves unchanged** the privacy of every researcher's turns, the
Lead's closed output and the 96 KB context bound.
**Date:** 2026-10-20
**Plan:** [lead-orchestration](../../../.planning/plans/lead-orchestration.md) LO19 (#523);
`research-lead-workbench` 32

## Context

There is no study assignment: whoever opens a study works there with their own Lead (Q5, ADR 0030
decision 5). The owner: "he carries his own files, but also the context of each study session.
maybe we need to have an md file attached to each study session so the researches ai can get the
context of hte study, this should be updated regularly within each study." On who writes its prose
(Q10, b): code, plus "Poznámky ke studii" that any Lead proposes and a person accepts, with the
automatic text accept applying.

Today a turn's context is frozen at enqueue in fixed layers (`freeze_context`,
`packages/aia_core/src/aia_core/domain/research_lead.py:782 @ 854c209`, bounded at 96 KB, `:116`).
Its study layer carries the name, stage, budget and runs in flight (ADR 0026 decision 2), and
nothing else carries what other researchers decided in the study: two researchers' Leads in one
study each see only their own conversation.

## Decision

### 1. The file is two parts: facts by code, notes by people

- **Fakta** are a deterministic projection of the study's shared state, never a researcher's
  private turns: the brief and research questions; each stage's state; the head Design Revision and
  what changed since the previous one (from the operation log, ADR 0029); runs and their states;
  approved results and report state; the approval ledger's decisions (accepted and refused changes,
  approvals, spend confirmations); open items. Every line names its source (a revision, run or
  ledger row). No model call, no cost.
- **Poznámky ke studii** are short prose notes about the study: what was agreed with the client,
  why a choice was made, what to watch. Any researcher's Lead may propose one, as a change in its
  turn's closed output (a new `study_note` edit); a person accepts or rejects it through ADR 0029's
  per-change accept, and the researcher's automatic text accept applies to it when that researcher
  has it on (Q10). A person may write, edit or retire a note directly. Notes are kept with their
  revisions in the study, attributed to who proposed and who accepted, never deleted (retired).

### 2. Always current, without a write on every change

The file is computed when it is read, from the state at that moment, not stored after every change:
the notes are rows; the facts are read from the tables that already hold them. Its **version** is the
SHA-256 of its canonical text together with the revisions it was built from (working revision,
Design Revision, latest ledger row, latest run event). Two reads of the same state give the same
file and version.

### 3. A turn freezes the version it read

At enqueue, `freeze_context` takes the file as the study layer, with a byte budget of its own inside
the 96 KB. Over budget, the oldest history lines of the facts go first, then the oldest notes, and
the omission is named in the file; it is never cut silently. The turn records the file's version,
so a turn stays reproducible and "what did the Lead know" has one answer.

### 4. Class and privacy

The file takes the most restrictive class of what it holds by `domain/material_rules.py`: Class B
for a design and study notes (study material, as a design is, ADR 0008 amendment 2026-10-19), Class A
when it carries approved client knowledge. It is sent only to a route approved for that class. No
turn text, no researcher's Lead files or personal notes, and no unaccepted proposal's text appear in
it; a proposed note's text becomes study material only once a person accepts it.

### 5. Readable in the study

The Lead pane shows it as *Kontext studie*, with its version and each line's source, to every member
who opens the study.

## Alternatives considered

- **Store the file and rebuild it on every change.** A write on every keystroke batch, run event and
  ledger row, with a race between them; computing on read gives the same content and version.
- **Let a model write the facts.** A summary of the state is a second source of truth that can be
  wrong; code projects the state itself.
- **Let each Lead keep its own study notes** (in its personal files). Another researcher's Lead would
  never see them, which is the problem Q5 asks to solve; personal files are also Class C and must hold
  no client fact (ADR 0030 decision 3).
- **Put turns of other researchers in the file.** Turns stay private (ADR 0026 decision 8).

## Consequences

- One new table for the notes and their revisions, one new edit kind (`study_note`) in the shared
  vocabulary, a pure projection function and a layer in `freeze_context`.
- Every Lead in a study works from the same facts and the same agreed notes.
- The owner's wish to have the Lead "live edit the document" with comment or rewrite modes (Q10's
  note) is not decided here; it is not planned yet.

## What enforces it

- The projection is pure (`domain/`), tested with fixtures: the same state gives the same text and
  version.
- Tests: two researchers' Leads in one study read the same file and version; no turn text, Lead file
  or unaccepted proposal appears in it; a run event or an accepted change changes the version; a turn
  records the version it read; over budget, the omission is named; a proposed note is not in the file
  until accepted; the file is refused by a route not approved for its class.
- `make layer_check`: the notes table only through its repository.

## Unblocks

`lead-orchestration` LO19 (W2, after LO8 and `working-copy-edit-ops` WCE4), `research-lead-workbench`
32 (Kontext studie), and the Lead's context in gate I-2.

## Open for Nigel

1. **Live editing** (Q10's note: "integrate wordcraft … revize the text as a comment or rewrite it
   directly"): which document, and what "wordcraft" means. The coordinator is asking; this ADR covers
   the notes only.
2. **Amending ADR 0026, which is Accepted**, in decision 2's study layer, needs the owner's explicit
   yes (D-08 named the other amendments, not this one).
