# ADR 0034 — Open-answer coding: a frozen, reviewed assignment artifact, counts by a pure function, admitted like every number; the method awaits the methodology owner

**Status:** Accepted — 2026-10-26 (the product owner, Decision Review), with the
[amendment of 2026-10-26](#amendment-2026-10-26) below; **the coding method (decision 6), Q7, Q8 and
MQ-14a–f stay the methodology owner's**, and every count still refuses by name until his method
version exists. Proposed — 2026-10-20; held for the methodology owner's answers (the product
owner, 2026-10-20: "accept 0028-0033, 0035, 0038-0040; hold 0034, 0036, 0037"). **The coding
method (decision 6) is awaiting the methodology owner** (MVPQ-02b) and is not chosen here. The
admission rule [ADR 0026](0026-research-lead-proposes-a-person-decides.md) decision 4 requires
before any command reaches *open-answer coding*. **Builds on** [ADR 0007](0007-deterministic-tools.md)
(no model computes a number), [ADR 0016](0016-research-execution-and-model-transmission.md) (a run's
artifacts are immutable), [ADR 0023](0023-methodology-is-data-the-methodologist-owns.md) (method as
pinned, versioned data) and [ADR 0024](0024-panel-grounded-respondents-are-modelled-evidence.md)
(modelled answers stay internal until a validation lifts them). **Leaves unchanged** every respondent
answer and every fieldwork artifact.
**Owner decision, 2026-10-25** (ADR-HELD (a), the audit page, relayed by coordinator 3): accept once its methodology answer is
written in; the owner asked for the same review document as for ADRs 0020 to 0024 (its questions,
how it connects in AIA, its inputs and outputs, an example for each complex topic). The status is
unchanged until the methodology answer is written in and he accepts it.

**Date:** 2026-10-20
**Plan:** [assumptions-and-open-answer-coding](../../../.planning/plans/assumptions-and-open-answer-coding.md)
AOC4-AOC9; `report-delivery` RD10

## Context

The owner decided on 2026-10-20 (MVPQ-02) that coding of open answers is in the first release, with
a real producer: stored, versioned per-answer assignments over a frozen run's open answers,
deterministic counts and traceable examples. The answers exist: an AI respondent returns "a short
open answer" (`domain/ai_respondent.py:8 @ 854c209`) and the outlook marks such an item
`open_ended` (`domain/question_outlook.py:62 @ 854c209`). Nothing codes or counts them. The method
(the codebook and its rules, labels and multi-label semantics, the denominator and missing answers,
review and agreement, small-code support) is the methodology owner's and is open (MVPQ-02b). The
engineering around it is not, and is what this ADR fixes, so the method can drop into a contract.

## Decision

### 1. The assignment artifact: per answer, versioned, frozen once reviewed

A run-derived artifact beside the dataset, keyed by the run's dataset (artifact id and SHA-256):
for each answer, the answer id, its codes, the codebook version, the **assignment version**, the
coder (a person, or a model with its model and prompt pin), the reviewer, the time. It never
overwrites or edits an answer. Once a person marks it reviewed, an assignment version is frozen.
Recoding, by a person or a model, writes a **new** assignment version; changed assignments may
change counts, and say so.

### 2. Counts are a pure function

`coded_counts(dataset, codebook_version, assignment_version) -> counts` in `domain/`, no I/O: the
same three inputs give the same counts and the same fingerprint, bit for bit. The denominator and
the missing-answer treatment are parameters the method version supplies (decision 6), never
defaults in code.

### 3. A coding node in the run, with its own impact root

A step kind and template node after fieldwork, behind its own switch, keyed on the run's identity.
A codebook or assignment change invalidates coding, analysis and the report that read it, and
**never fieldwork**. A retry replays no paid classification: a model coder's calls are journaled
per answer like any paid step (the `client_work_journal` pattern), and a frozen assignment version
is reused, never recomputed.

### 4. Admission

Counts reach a result only through `admit_numeric_claims`, with effective-n support and intervals
as the method version states; a code below its support is suppressed and named, never shown. Raw
answer text is never an admitted claim. Counts over AI respondents' answers are modelled
(`MODELLED_AI_PANEL`) and internal until a validation lifts them, as every modelled number is.
Answer text sent to a model has a `MaterialRule` and lineage (`run-qc-and-checkpoint` RQC3).

### 5. What a model may do

At most **propose** codes, as a worker (AOC7) whose output is a draft assignment version a person
reviews; a model never freezes, reviews or accepts its own codes. Whether a model may propose at
all is the method's (decision 6); if it may not, AOC7 is closed with that reason.

### 6. The method, awaiting the methodology owner

The method is a versioned, pinned record in the methodology store (ADR 0023): the codebook and who
defines it; the unit and multi-label semantics; the label set and its versioning; the denominator
and missing answers; review and acceptance; agreement measures; support and suppression of small
codes; whether a model may propose. **Until a version is approved, the coding node refuses
(`coding_method_unapproved`) and no count is produced**; the contracts, storage, refusal tests and
the assignment artifact's schema proceed.

## Alternatives considered

- **Let a model return counts or themes.** A model's number is not admitted evidence (ADR 0007) and
  is not reproducible.
- **Code answers in place in the dataset.** A respondent answer is frozen; an assignment is a
  separate, versioned judgement about it.
- **A fixed codebook in code.** The method is the methodologist's (ADR 0023), not a constant.

## Consequences

- One artifact type, one step kind, one domain function, a methodology record type and a report
  chapter (RD10); possibly a twelfth worker (AOC7).
- The feature ships its storage and refusals before it ships a single count.

## What enforces it

- Tests: the same frozen assignment version, dataset and codebook give the same counts and
  fingerprint; a new assignment version may change them and records why; a retry replays no
  classification call; a codebook change leaves fieldwork's artifacts untouched; a count below
  support is suppressed; no count exists without a claim; raw text is not marked admitted; a model
  coder cannot review its own assignment; with no approved method version the node refuses by name.
- `make layer_check`: the counts function is pure (`domain/`, no I/O, already enforced for the
  layer).

## Unblocks

AOC5 (W2, storage and node), AOC6-AOC8 and RD10 (W3) once the method is approved; AOC9.

## Open for Nigel

1. **MVPQ-02b, the method**, is the methodology owner's (A. Bahbouh), approved by the owner. Every
   numeric behaviour above waits for it.

## Amendment, 2026-10-26

The product owner's verdict in the Decision Review, 2026-10-26 (relayed by the PM coordinator),
REV-ADR-0034-VERDICT: **(b) "Accept with the amendment described"**. The review's amendment: align
decision 4 with ADR 0024's client-report lift and name the coding node's switch. Only the verdict is
answered. He left the rest to the methodology owner ("a lot of questions are for the methodology
owner so lets leave that to him"), so these stay open and are not decided here:

- **MQ-14a–f** (MVPQ-02b, decision 6): the denominator and missing answers, multi-label semantics,
  small-code suppression, what a model may do, review and agreement, who writes the codebook.

**0034-Q7 (a)** (the product owner in chat, 26 Oct 2026 ~12:20 UTC, relayed by the PM coordinator): coded counts over AI answers follow ADR 0024's client-report lift like
every other modelled number: they reach the client report only under the owner's lift, and analysis
prose only after a validation. Decision 4's "internal until a validation lifts them" reads so.

**0034-Q8 (a)** (the product owner in chat, 26 Oct 2026 ~12:30 UTC, relayed by the PM coordinator): the coding node gets its own off switch, named in AOC5, off by default and
on for develop only once the coding method version is approved.

What acceptance changes: decisions 1-5 are the accepted contract for open-answer coding (decision
4 as amended by Q7 below), so
`assumptions-and-open-answer-coding` AOC5's storage, node and refusals are built against them; the
node refuses `coding_method_unapproved` and no count exists until the method version is approved.
