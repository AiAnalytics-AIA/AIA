# ADR 0035 — The Lead edits a report freely; the evidence does not move: every number a ledger ref, every claim admitted, a draft of its own, approval of the exact version

**Status:** Proposed — 2026-10-20. Not accepted until the product owner says so. The admission rule
[ADR 0026](0026-research-lead-proposes-a-person-decides.md) decision 4 requires before any command
reaches *semantic report edits*. **Builds on** [ADR 0016](0016-research-execution-and-model-transmission.md)
(a run is immutable), [ADR 0019](0019-two-roles-and-human-ai-gates.md) gates 1 and 3 and the report
model (numbers only as refs). **Leaves unchanged** every claim, every run and its fieldwork, and the
approval of a stored report.
**Date:** 2026-10-20. **Amended 2026-10-20** with the product owner's recorded answers D-35 and Q6
(`.planning/evidence/scope-freeze/answers-2026-10-20.md`, #523 @ `ee21982`): free edits, numbers as
ledger refs; the draft's closed operations and per-paragraph ref equality are withdrawn. Still
Proposed.
**Plan:** [report-delivery](../../../.planning/plans/report-delivery.md) RD5, RD5a, RD6, RD7;
`lead-orchestration` LO9b, LO9c

## Context

The owner wants a report writer (MVP-12, `polish_report`): it changes a draft's wording and order;
numbers stay references, re-admitted. On 2026-10-20 he widened it (D-35, Q6): "I want the
researcher's lead agent to edit the documents as they see fit. If it's about joining paragraphs,
editing copy, whatever, the lead agent can help change that", with "free report edits with numbers
as ledger refs". ADR 0026 decision 4 gave it no command until this ADR exists,
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
composer's structure so a rerun with the same inputs gives the same ids. The DOCX is always
rendered from the stored document, so the two never disagree.

### 2. Free edits, by the Lead or the person

The Lead (or the person) may change the draft as they see fit (D-35): rewrite and shorten text,
join or split paragraphs, move paragraphs and chapters, the client report's chapter order included,
and remove sentences. An edit is expressed against the stored document by node id, so it can be
shown, accepted and undone, but the set of edits is not a short closed list.

### 3. What an edit can never change: the admission rule, checked by code on the whole document

An edited draft is admitted only when all of these hold over the **whole edited document**:

1. **No typed number.** Edited text contains no numeric token; every number printed is an
   `evidence_ref` the renderer prints. This is a new check on edited prose, reusing the Lead's number
   reader (`number_tokens`, `domain/research_lead.py:457 @ 854c209`).
2. **Every ref is an admitted claim of this run for this report's surface.** A joined paragraph
   carries the union of its parts' refs; a ref may move with its sentence or be removed with it, but
   no ref is added that the composer did not admit (`UNKNOWN_REF`, `SUPPRESSED_CITED`,
   `WRONG_SURFACE`, `domain/report/validation.py:69-73 @ 854c209`).
3. **No required finding disappears.** Each analysis module the report requires still cites at least
   one admitted finding (MVPQ-04's gate: a report with a module unsupported is blocked), and every
   disclosure and label the template requires (the modelled-evidence label, *z dat klienta*, the
   method's reader note) is still present.
4. **The sentence-level claim check passes** (RD7, MVPQ-09): a sentence that claims a comparison,
   ranking or direction carries a ref that admits it; a failure blocks approval and names the
   sentence.
5. **The document validates whole** (`require_valid`).

A failed edit is refused by name, naming the rule and the node, and the draft keeps its previous
text.

### 4. A draft counter of its own; fieldwork never reopens

An accepted edit set writes a new **draft revision** of that report: `(base fingerprint, accepted
edits)`, its own fingerprint, its own counter, separate from the Design Revision. It never reruns
fieldwork, aggregation, analysis or the Sociomap, and never changes the run.

### 5. The Lead proposes; a person accepts

The report writer is the researcher's Lead working on the report artifact through a results worker
(LO9c): keyed on (run, report artifact), frozen input by id and SHA-256, its output a proposal of
edits, each a change a person accepts or rejects (ADR 0029's per-change accept, on the report).
Accepting needs `APPROVE_GATE`.

### 6. Approval is of the exact version

Approving binds the draft revision's fingerprint. Any accepted edit after an approval makes a new
draft that needs its own approval; the approved one stays downloadable as it was. Downloads of a
client deliverable follow approval (RD3).

## Alternatives considered

- **A closed set of operations with the same refs per paragraph** (this ADR's draft). Withdrawn by the
  owner (D-35, Q6): it forbade joining paragraphs and reordering the client report. The whole-document
  rule above keeps what it protected: no typed number, no unadmitted claim, no lost finding.
- **Let the writer type numbers and check them afterwards.** A typed number is a second source of
  truth beside the ledger; refs keep one.
- **Check claims by a model.** The check is code (RD7), and a model checking a model is not a gate.

## Consequences

- A stored document per report variant, stable ids, an edit applier over node ids, a draft counter,
  and the whole-document checks run on every accepted edit set.
- A client report's chapter order is no longer the legacy `client_report_v2` order once edited; the
  composer's first draft still follows it.

## What enforces it

- Tests: the stored document renders to the same DOCX bytes; ids are stable across a rerun with the
  same fingerprint; joining two paragraphs keeps both refs; a typed number is refused; a ref the
  composer did not admit for the surface is refused; removing a required module's last finding or a
  required disclosure is refused by name; a comparison sentence with no admitting ref blocks approval
  and names the sentence; reordering the client report's chapters is accepted; an accepted edit
  changes no run artifact; an approval does not cover a later draft.
- An import contract: the report writer's executor does not import the composer's claim admission.

## Unblocks

RD5a and RD5 (W2/W3), RD6's accept destination, RD7, LO9b's report binding, and AC-13.

## Open for Nigel

Answered by the product owner on 2026-10-20 (`answers-2026-10-20.md`, #523 @ `ee21982`):

- ~~Moving chapters.~~ Free, the client report included (D-35).
- ~~Ref-set equality.~~ Paragraphs may be joined; refs are unioned (D-35, Q6).

Still open:

1. **Does the researcher's automatic accept apply to report edits?** ADR 0029 decision 9 lets text
   edits apply without a click when the researcher turns it on; Q10 applies the toggle to the study
   context file. This ADR has every report edit accepted by a person; whether the toggle extends to
   reports waits for the owner's pending Q13 (per researcher: suggestions or direct edits).
2. ~~The Lead's web search.~~ Written as [ADR 0040](0040-the-leads-web-lookup.md).
