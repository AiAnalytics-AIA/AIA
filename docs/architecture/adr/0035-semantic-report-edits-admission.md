# ADR 0035 — A report edit changes wording and order, never evidence: closed operations on a stored document, re-validated, a draft of its own, approval of the exact version

**Status:** Proposed — 2026-10-20. Not accepted until the product owner says so. The admission rule
[ADR 0026](0026-research-lead-proposes-a-person-decides.md) decision 4 requires before any command
reaches *semantic report edits*. **Builds on** [ADR 0016](0016-research-execution-and-model-transmission.md)
(a run is immutable), [ADR 0019](0019-two-roles-and-human-ai-gates.md) gates 1 and 3 and the report
model (numbers only as refs). **Leaves unchanged** every claim, every run and its fieldwork, and the
approval of a stored report.
**Date:** 2026-10-20
**Plan:** [report-delivery](../../../.planning/plans/report-delivery.md) RD5, RD5a, RD6, RD7;
`lead-orchestration` LO9b, LO9c

## Context

The owner wants a report writer (MVP-12, `polish_report`): it changes a draft's wording and order;
numbers stay references, re-admitted. ADR 0026 decision 4 gave it no command until this ADR exists,
because a report is composed from admitted claims and frozen on approval. Today:

- **The document is discarded.** The report steps store DOCX bytes only
  (`apps/executors/src/aia_executors/report.py:140-157 @ 854c209`), and a `Paragraph` has no id
  (`domain/report/model.py:97-101 @ 854c209`), so nothing can name the paragraph an edit changes.
- **Numbers are refs, and prose is trusted.** No block carries a number: a value is an
  `evidence_ref` the renderer prints (`domain/report/model.py:11-13 @ 854c209`), and the validator
  refuses an unknown or suppressed ref (`UNKNOWN_REF`, `SUPPRESSED_CITED`,
  `domain/report/validation.py:69-73, 182 @ 854c209`). It does not re-parse prose for a typed digit,
  because the analysis checked its text for uncited numbers before composition. An edit after
  composition has had no such check.
- **Approval binds a stored artifact once** (`application/report_approval.py:43 @ 854c209`).

## Decision

### 1. The document is stored and addressable

The `ReportDocument` is stored as JSON beside each DOCX under the same fingerprint (RD5a), with a
stable id on every heading, paragraph, list item and table, derived deterministically from the
composer's structure so a rerun with the same inputs gives the same ids.

### 2. A closed set of edit operations

`paragraph_rewrite` (new inline content for one paragraph), `paragraph_move` (within its chapter),
`section_move` (of a chapter the template marks movable), `lede_set` (one chapter's headline
paragraph from among its paragraphs). Nothing else: no operation adds or removes a claim ref, a
table, a figure, a chapter, a disclosure or a label, and none touches a number.

### 3. The admission rule, checked by code on every edit

An edited paragraph is admitted only when:

1. **its refs are exactly the original paragraph's refs** (the same set; order may change), so no
   evidence enters or leaves through wording;
2. **its text contains no numeric token**: every number it prints is one of those refs, rendered by
   the renderer, never typed. This is a new check on edited prose, reusing the Lead's number reader
   (`number_tokens`, `domain/research_lead.py:457 @ 854c209`);
3. **the sentence-level claim check passes** (RD7): a sentence that claims a comparison, ranking or
   direction carries a ref that admits it; the refusal names the sentence;
4. **the edited document validates whole** (`require_valid`), the template's required chapters and
   disclosures still in place.

A failed edit is refused by name and the paragraph keeps its text.

### 4. A draft counter of its own; fieldwork never reopens

An accepted edit set writes a new **draft revision** of that report: `(base fingerprint, accepted
operations)`, its own fingerprint, its own counter, separate from the Design Revision. It never
reruns fieldwork, aggregation, analysis or the Sociomap, and never changes the run.

### 5. The worker proposes; a person accepts each change

The report writer is a results worker (LO9c): keyed on (run, report artifact), frozen input by id
and SHA-256, its output a proposal of operations, each a change accepted or rejected by a person
(ADR 0029's per-change accept, on the report). Accepting needs `APPROVE_GATE`.

### 6. Approval is of the exact version

Approving binds the draft revision's fingerprint. Any accepted edit after an approval makes a new
draft that needs its own approval; the approved one stays downloadable as it was. Downloads of a
client deliverable follow approval (RD3).

## Alternatives considered

- **Let the writer rewrite the whole report.** Its claims could not be checked against what was
  admitted, paragraph by paragraph.
- **Allow adding or dropping refs.** Dropping a ref drops a finding (MVPQ-04 blocks a report with a
  module unsupported); adding one is composition, the composer's job, not wording.
- **Check claims by a model.** The check is code (RD7), and a model checking a model is not a gate.

## Consequences

- A stored document per report variant, stable ids, one operation module, a draft counter and the
  sentence check. The DOCX is rendered from the stored document, so the two never disagree.
- The writer cannot shorten a report by removing findings; it can make them clearer.

## What enforces it

- Tests: the stored document renders to the same DOCX bytes; ids are stable across a rerun with the
  same fingerprint; an edit that adds or drops a ref is refused; a typed number is refused; a
  comparison sentence with no admitting ref is refused by name; an accepted edit changes no run
  artifact; an approval does not cover a later draft.
- An import contract: the report writer's executor does not import the composer's claim admission.

## Unblocks

RD5a and RD5 (W2/W3), RD6's accept destination, RD7, LO9b's report binding, and AC-13.

## Open for Nigel

1. **Moving chapters.** The client report keeps the legacy `client_report_v2` section order
   (`domain/report/templates.py`); this ADR lets `section_move` touch only chapters a template marks
   movable, so the client report's order is fixed. Confirm.
2. **Ref-set equality is strict.** A rewrite that merges two paragraphs is two operations here
   (rewrite one, the other untouched); confirm that merging paragraphs is not wanted.
