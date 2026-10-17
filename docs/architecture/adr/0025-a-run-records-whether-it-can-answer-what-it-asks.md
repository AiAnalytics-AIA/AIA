# ADR 0025 — A run records whether it can answer what it asks; one that cannot starts only acknowledged

**Status:** Proposed — develop (2026-10-16). Plan:
[research-integrity-report](../../../.planning/plans/research-integrity-report.md), chunk 1
(decision D1 is the owner's). **Builds on** [ADR 0016](0016-research-execution-and-model-transmission.md)
(a run executes an immutable Design Revision) and the research trace of plan run-recovery-and-truth
3a–3e (`domain/research_trace.py`). **Sits beside** [ADR 0019](0019-two-roles-and-human-ai-gates.md):
it adds no fourth gate (decision 3 below). **Leaves unchanged** every evidence gate.
**Date:** 2026-10-16

## Context

Readiness decides whether a design is **technically runnable**: it compiles, its sample is in
bounds, fieldwork can ask every question. `ready` is `not any(FAIL)`
(`domain/research_design.py:950 @ 357d779`). Whether the run is **capable of answering the research
questions its design states** was a separate check, `research_question_coverage`, and always a
WARN (`domain/research_trace.py:302-346 @ 357d779`). A start never read it.

A fictional end-to-end run on develop (`RUN-9b6e0f5e6e0e4345`, study `STU-b58afeef95d64e`, 200
fictional respondents, 2026-10-16) stated four research questions and linked none of them to a
questionnaire item. Every readiness check was green or amber, the run started, and its analysis
could not answer three of the four. The report then read as the conclusion of a study that had
never been able to reach one. An external review of its PDF named this first: the research
questions were not operationalized before the simulation.

Making coverage a FAIL would stop that run, but also every methodology run on fictional
respondents and every design written before questionnaire items carried their research-question
links (harness 3). Many of those runs are deliberate: a researcher checking a procedure, not
answering a client.

## Decision

1. **Every start decides answerability, and the run records it.** `domain/answerability.py` reads
   the trace and the question outlook into one decision under named rules (`aia-answerability-1`):
   *capable* (every research question has a measure the analysis may cite, or one whose support
   only fieldwork decides, which is *pending* and never read as answered), or the **gaps**, each with
   its reasons (unmeasured, an unlinked design, measures the run will not answer, only open or
   analysis-excluded measures, a comparison that cannot be carried or is unknown, no research
   question at all). The gaps have a digest. The run's metadata keeps the note, whatever was
   decided.

2. **A run with gaps starts only on a person's acknowledgement of exactly those gaps, where the
   deployment requires it.** The acknowledgement is the digest the person was shown and a reason
   (10–1000 characters). A digest of other gaps covers nothing: a design that changed asks again.
   It is written to the approval ledger (subject `answerability`, `APPROVE_GATE`, so a worker cannot
   give it; `workflow_repository.py` `record_answerability_acknowledgement`, wt) and kept with the
   run. Without it the start is refused (`ResearchQuestionsUnanswerable`, 409
   `research_questions_unanswerable`) and nothing is created. `AIA_RESEARCH_ANSWERABILITY_GATE`
   decides whether it is required: **off by default**. Off, the run starts as before and records
   that nobody was asked (`enforced: false`). Readiness says whether a start would be refused
   (`acknowledgement_required`), so the page asks exactly when the server would refuse.

3. **It is a recorded precondition, not a fourth gate.** ADR 0019's gates are a person accepting
   what the AI produced. Here a person accepts a known limitation of their own design. It uses the
   ledger the way the spend confirmation does (gate 2's record), for audit, and adds nothing to
   ADR 0019's closed set. No self-approval policy refuses it, because the person starting the run is
   the one who knows why. The row still records who started the run and who acknowledged it, as
   every ledger row does (`observe_approval_independence`, `domain/scope.py:382 @ 357d779`).

4. **An acknowledgement never makes a research question answerable.** It records a decision to run
   anyway. The report prints the gaps as a limitation, says what was pending, and in the internal
   report says why the run started anyway, that the acknowledgement was inherited, that an analysis
   retry was exempt, or that nobody was asked; who acknowledged is the approval ledger's record,
   which the report names, never a person it prints from an id. Every answer the internal report
   gives to such a research question is marked where it is read. The client report prints the
   gaps without who or why.
   ARCHITECTURE.md §4's "no override field" stays true of every evidence gate. This is not one.

5. **A retry inherits an acknowledgement only while the gaps are the same.** A retry of a run with
   an acknowledgement of the same digest starts without asking. A retry of a run started before
   this rule, or whose gaps changed, asks. An analysis retry over the original's frozen dataset
   (`retry_analysis`) collects nothing new and is never refused. It is recorded as exempt
   (`analysis_retry`), never as "not enforced".

## Consequences

- A run's report says what it could not answer, from the record made at its start, not from what
  the analysis happened to produce.
- With the switch off nothing is refused; the gaps are still shown on the Run screen and printed in
  the report. Turning it on refuses starts that cannot answer what they ask until someone
  acknowledges them. The owner decides when develop turns it on (plan D1).
- The rules have a version. A change to what counts as a gap is `aia-answerability-2` (plan chunk 8
  plans association questions), and a run keeps the rules it started under.
- The approval ledger admits a new subject (migration `d2f4a6c8e0b3`). Its downgrade refuses while
  acknowledgements exist rather than drop them.

## Alternatives considered

**Coverage as a readiness FAIL.** Rejected: it stops deliberate methodology runs and every design
from before the research-question links, and it leaves no record of why a run went ahead.

**A fourth ADR 0019 gate.** Not proposed: it would put a person's decision about their own design
beside acceptances of AI output, and bring self-approval rules that have no meaning here. The
owner may decide otherwise (plan D1).

**Keep the WARN.** The Fio run is the evidence that a WARN nobody reads does not reach the report.
