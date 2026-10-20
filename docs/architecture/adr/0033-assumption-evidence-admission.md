# ADR 0033 — An assumption's status is a person's decision, and its evidence is an attachment code verifies: an admitted claim or a grounded Deep Research finding

**Status:** Accepted — 2026-10-20 (the product owner, in his words: "accept 0028-0033, 0035, 0038-0040; hold 0034, 0036, 0037").
Proposed the same day. The admission rule
[ADR 0026](0026-research-lead-proposes-a-person-decides.md) decision 4 requires before any command
reaches *audience-assumption evidence*. **Builds on** [ADR 0019](0019-two-roles-and-human-ai-gates.md)
gate 1, [ADR 0021](0021-deep-research-purpose-target-lineage.md) (Deep Research is external context,
never respondent evidence) and the evidence gates (`AdmittedClaim`). **Leaves unchanged** every
existing claim, the sealed bundle and the canonical Sociomap.
**Date:** 2026-10-20
**Plan:** [assumptions-and-open-answer-coding](../../../.planning/plans/assumptions-and-open-answer-coding.md)
AOC0-AOC3, AOC9; `report-delivery` RD9

## Context

The owner decided on 2026-10-20 (MVPQ-02) that tracked assumptions are in the first release: stable,
editable items with a status, supporting evidence and human-approved updates. ADR 0026 decision 4
gave the prototype's *audience-assumption evidence* no command until an ADR and a deterministic
admission rule exist. This is that ADR. It adds no scientific method: what counts as evidence is
already fixed. A number reaches a result only as an `AdmittedClaim`
(`domain/evidence/admission.py:188, 298 @ 854c209`); a Deep Research finding is a quote in a captured
source, grounded by code (`domain/deep_research/grounding.py:116 @ 854c209`), and a captured source
reaches the study only from the run's verified sealed bundle (`application/verified_sources.py:47 @
854c209`).

## Decision

### 1. An assumption is a design item

A kind in `domain/design_items.py` and the edit vocabulary (ADR 0029): a stable id, a statement,
links to the research questions or measures that test it, a status, its attachments. Text edits of
the statement are text edits; a status change and an attachment are structural, each a proposal a
person accepts (`assumption_add`, `assumption_edit`, `assumption_link`, `assumption_set_status`,
`assumption_attach`). No status is ever derived by code or a model from prose.

### 2. Statuses, and what each needs

| Status | Needs |
|---|---|
| `UNTESTED` | nothing: tracking what is not yet known is the core use |
| `SUPPORTED`, `CONTRADICTED` | at least one admitted **respondent** claim attached (decision 3) and a person's accept; external findings may sit beside it as context but never count toward it (the product owner, 2026-10-20, D-16) |
| `RETIRED` | a person's accept; kept, never deleted |

The set is closed: these four and no other (the product owner, 2026-10-20, Q11 b; there is no
`UNVERIFIED`). Readiness lists `UNTESTED` assumptions as a warning, never a failure.

### 3. An attachment is admissible only as one of two references, verified by code

- **Respondent evidence:** an `AdmittedClaim` ref of a finished run of **this** study, as stored by
  the run's analysis or aggregate. Code resolves the ref through the run (never the browser) and
  refuses one that is unknown, suppressed, or of another study.
- **External context:** a Deep Research finding by run id and finding id, from a run of this study
  whose sealed bundle verifies; the finding must be **accepted** by the run's verifier (not rejected,
  not quarantined), and its quote must locate in the content-addressed snapshot it cites. Code copies
  the quote, the source URL and the snapshot's SHA-256 from the bundle; nothing the browser or a
  model sends is stored as the quote.

An attachment carries its basis (`respondent` or `external`). A Design Research proposal may
propose an attachment; accepting it is a person's act and **never changes the status**: the status
is a separate accepted operation.

### 4. What the report prints

The assumptions chapter (RD9) prints each assumption with its status, the person's accept that set
it (from the ledger), and its attachments: claims by reference (re-admitted for the report's
surface), external findings labelled external with their quote and source. A status with no
accepted decision, or an evidence-backed status whose attachments no longer verify, is not printed
as established; the composer refuses it by name.

## Alternatives considered

- **Let the Lead or a Design Research run set a status.** Ruled out by gate 1 and the owner.
- **Attach findings by their text.** A model's paraphrase of a finding is not the finding; code
  copies from the bundle.
- **`SUPPORTED` on external findings alone, its basis printed as external** (this ADR's draft).
  Rejected by the product owner (D-16): web text is context, and ADR 0021 forbids reading it as
  respondent evidence.

## Consequences

- A new item kind, five operations, one ledger subject reused (the design accept), and one chapter.
- An assumption cannot be marked supported or contradicted on web evidence alone; until a run of the
  study produces a respondent claim it stays `UNTESTED`, with any external findings shown as context.

## What enforces it

- The shared fixture of ADR 0029 carries the assumption cases for Python and TypeScript.
- Tests: an attachment whose quote is not in a captured snapshot is refused; a rejected or
  quarantined finding is not attachable; a claim ref from another study is refused; a status change
  without a person's accept is refused; accepting an attachment leaves the status unchanged; the
  composer refuses a `SUPPORTED` or `CONTRADICTED` assumption with no attached respondent claim, and
  one whose only attachments are external findings; an `UNTESTED` assumption
  with none is accepted and printed as untested.

## Unblocks

AOC1 (W1, the item and `UNTESTED` tracking), AOC2 (W2, attachments), AOC3 and RD9 (W3), AOC9.

## Open for Nigel

1. ~~**May `SUPPORTED` rest on external findings alone?**~~ Answered 2026-10-20 by the product owner
   (D-16, b): no; `SUPPORTED` and `CONTRADICTED` need at least one admitted respondent claim, and an
   external finding is context only. Decision 2 reads so. The question as it was put: the plan says both "Deep Research evidence
   … cannot by itself mark one supported" (its *Decisions*) and "only an evidence-backed assertion
   needs support, … cited Deep Research findings as external context" (AOC0). The draft let a person
   set `SUPPORTED` on external attachments alone; the owner chose the stricter reading.
2. ~~**The status set.**~~ Answered 2026-10-20 by the product owner (Q11 b): `UNTESTED`,
   `SUPPORTED`, `CONTRADICTED` and `RETIRED`; there is no `UNVERIFIED`. Decision 2 reads so.
