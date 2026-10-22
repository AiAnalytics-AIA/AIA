---
status: in-progress
chunks:
  - "[x] 1. Every key finding cites an admitted claim (MVP-23): a new rule, not a tightening, since AIA has no 95 % threshold (that is the unit's)"
  - "[ ] 2. Run QC as a pure function over a run's stored dataset, EXACT against the unit's qc.kontrola (MVP-24)"
  - "[ ] 3. A run's QC stored beside it and shown as warnings on Fieldwork and Results, never a gate"
  - "[ ] 4. The straight-liner check: flags by code, no pause, the worker proposes keep or flag; replace is a new linked run (F18, settled); the one definition is run-qc-and-checkpoint RQC1"
  - "[ ] 5. One field-policy authority per evidence source: the population contract's list for panel respondents (MVP-29)"
  - "[ ] 6. Results serves admitted claims: an API over the evidence table with suppression decided server-side, so the screen no longer reads raw aggregates"
  - "[ ] 7. Wire the sealed-bundle external-context producer into module preparation and the Lead; preserve the existing prompt/fingerprint context field and context-not-evidence boundary"
  - "[ ] 9a. A module with no supported finding (MVPQ-04, W1): stored as a structured diagnostic that is not a finding, shown on Analysis and Results, with its resolution paths named"
  - "[ ] 9b. The refusal (MVPQ-04, W3): report composition, approval and every export refuse while any of the eight modules is blocked or has no supported finding, until it is resolved; the diagnostic cannot satisfy the gate"
  - "[ ] 8a. A two-origin analysis input and its fingerprint, designed (W1) and reviewed with S3 before client-data-in-analysis 5"
  - "[ ] 8b. The two-origin input wired (W3): the production constructor supplies the client-reported table and the sealed-bundle context, and a changed context or origin changes the module's input fingerprint and payload"
  - "[ ] 10. The filtered base (W2, after run-qc-and-checkpoint RQC11): a conditional question aggregated over the respondents it was asked, its own effective n and support, the base stated on Results and in the report"
---
# Evidence integrity: findings cite evidence, run QC warns, one policy authority

Track E of the MVP roadmap (`overview.md` § MVP roadmap, #493). Written 2026-10-19 from
`mvp-cohesion.md` F7 (#496): three decisions had no plan, and all three change the same two
places, the analysis gate and the evidence layer, so they share one plan. **Owner: a chat session,
named when chunk 1 starts.** Chunks 1, 7 and 9a: the Analýza screen session (2026-10-22, the PM's assignment).

## Decisions this plan carries

| Id | Decision (2026-10-19) |
|---|---|
| MVP-23 | Every key finding of an analysis module cites admitted evidence (stricter than 18.6.6's 95 %): a finding without an admitted number behind it is refused, or shown as an unsupported hypothesis |
| MVP-24 | 18.6.6's run QC (straight-lining, speeders, inconsistent answers) is ported **as warnings** on Fieldwork, Results and to the Lead, never a gate; it pairs with the straight-liner worker (MVP-12) |
| MVP-29 | One field-policy authority: the population contract's stricter list (115 client-measurable fields); `domain.evidence` consumes it. A client's own data is outside this chunk: `client-data-in-analysis` chunk 0 |

## What exists

- A draft's key findings must cite claims: `FindingDraft` carries `claim_ids`, the gate checks
  each (`packages/aia_core/src/aia_core/domain/analysis/draft.py:116, 272 @ 085abe0`), and the
  module's docstring says the draft passes "when 95 % of the findings cited" (`:9`), but the check
  rejects only uncovered numbers and dangling references (`:254-282`), so a finding with no `claim_ids`
  passes. **MVP-23 is a new rule, not a tightening: AIA has no 95 % threshold to tighten (that is the
  unit's).** Hypothesis until chunk 1 reads the whole check:
  whether a refused finding triggers a repair turn today as a refused claim does.
- 18.6.6's QC: `legacy/npc-panel-18.6.6/app/qc.py:70` (`kontrola(v, prahy)`), thresholds in
  `PRAHY` (`:31`, `straightline_max` 0.15, which the file calls "my calibration, not an industry
  standard"), straight-lining on scales at `:200-207`. A speeder check needs a response time; an AI
  respondent has none (hypothesis: that check has no input in AIA and is recorded as not
  applicable, not ported as zero).
- Two lists decide what may back a client-facing measured claim: the population contract's
  `RECOMMENDED_USE_POLICY` (`domain/population/policy.py:162 @ 085abe0`, 115 of 400 fields) and
  `domain/evidence/field_policy.py` (the dictionary as typed policy). That they agree is
  **unverified**; chunk 5 starts by proving it either way.

## Chunks

1. **Findings cite all.** Read the gate, **add** the rule that every key finding names at least one admitted claim (a new validation, not a changed threshold), make the repair
   turn name the uncited finding, store a still-failing draft `BLOCKED` as today. Test: a draft
   with one uncited finding is refused; a draft with all cited passes; `test_analysis_executor.py`
   stays green. Decide here whether "shown as an unsupported hypothesis" is built or only refusal
   (refusal is the smaller change and the default).
   *Landed.* `check_analysis_draft` refuses a key finding with no `claim_ids` as
   `ViolationCode.FINDING_UNCITED`, subject `key_findings[<i>]` (`domain/analysis/draft.py` `_coverage`). A
   finding that names only an unknown claim stays `DANGLING_CLAIM_REF`, and one whose claims fail admission
   fails the draft as before, so "names at least one claim" is "cites at least one admitted claim".
   - The hypothesis is settled: a refused finding reaches the repair turn like any violation. `repair_prompt`
     lists each, and the test asserts the finding's path is named. A draft still failing is stored BLOCKED
     by the existing harness.
   - Refusal only, no "unsupported hypothesis" register: the default. A finding that cannot cite evidence is
     not a finding.
   - The rule is part of the identity. `ANALYSIS_HARNESS_VERSION` moves to `aia-analysis-harness-3`
     (`domain/analysis/harness.py:79`) and `PROMPT_TEMPLATE_VERSION` to `analysis-module-v4`, whose rule 1 now
     states it, so the model learns it before a paid turn.
     - Without the bump, a module stored COMPLETED with an uncited finding would fail re-admission under
       today's gate. It would not read stale (`_stale`, `application/analysis_results.py:726 @ 16682082`), so
       `_retryable` (`:705`) would never offer it, and its run's analysis would stay unreadable.
     - With the bump, every module completed under harness 2 reads stale and retryable, and Analýza and
       Průběh say so (PC3) until a same-data round asks it again.
     - The workbench's recorded wire answers from the payload (`aia_executors/recorded_models.py`
       `grounded_draft`, every finding cited), so the bump does not break it.
   - `AnalysisModuleResult` refuses a key finding with no claim too (`domain/analysis/result.py`), so no path
     around the gate builds one. A finding that cites nothing is not also scanned for numbers: one defect,
     one violation.
   - Parity: "finding-without-evidence" is now EXACT (both refuse that draft). The new
     "nineteen-of-twenty-cited" is an INTENTIONAL_DIFFERENCE: the unit's 95 % lets one uncited finding in
     twenty through, and AIA does not. "no-finding-at-all" stays owed, waiting on 9a's diagnostic (MVPQ-04),
     not on a gate refusal.
   - Tests: `test_analysis_draft.py` (one uncited finding refused and named, also in the repair prompt; a
     finding citing only an unknown claim; a draft without findings left to 9a; a hand-built result with an
     uncited finding refused), `test_analysis_gate_parity.py`, the version pins in `test_analysis_harness.py`
     and `test_analysis_modules.py`;
     `test_analysis_executor.py`, the recorded-analysis and acceptance suites green.
2. **QC function.** `domain/` pure: straight-lining first, over a run's stored dataset, thresholds
   as declared parameters (the unit's, recorded as such). EXACT fixture captured from the unit's
   own `qc.py` with `tools/` capture (the pattern of `respondent_capture.py`), pinned by SHA-256.
   Inconsistent-answer checks only where the unit's rule needs no data AIA lacks.
3. **QC stored and shown.** One artifact per run, a warning list on Fieldwork and Results,
   included in the Lead's results context (`mvp-cohesion.md` F4). No step waits on it. Test: a
   straight-lined dataset completes the run and shows the warning.
4. **Straight-liner worker.** Flags come from chunk 2's code; the worker only proposes keep or
   replace, per `mvp-cohesion.md` F2 (a model never reads respondent rows to find them). **Decide
   first** whether replacing a respondent is a new run (the dataset changes, so the run's identity
   does; hypothesis) or a recorded exclusion. Needs the worker row from `research-lead-workbench`
   chunk 11 (`mvp-cohesion.md` F5).
5. **One authority.** Test that every field `domain.evidence` admits client-facing is allowed by
   `RECOMMENDED_USE_POLICY`; then make `domain.evidence` read the population list and delete the
   duplicate. Blocked on `mvp-cohesion.md` F3 only for client data columns.

## Depends on / feeds

Chunk 3 feeds the workbench's Fieldwork and Results artifacts (chunks 19, 20) and the Lead's
results context. Chunk 4 needs the worker row. Chunks 1 and 5 touch `domain/evidence/`, which
`complete-study-report`, `panel-grounded-respondents` and `sociomap-formula-corrections` also
name: this plan owns the edit, they review it (`mvp-cohesion.md` F8).

## Open

- **Empty-module behavior is settled (MVPQ-04, owner 2026-10-20): block the report until the module's lack of supported findings is resolved.** Chunks 9a (diagnostic, W1) and 9b (refusal, W3) build it; no diagnostic may be patched with an invented finding.
- Replacement identity is settled (F18): a new linked run. Only weighting/effective-n/support semantics remain open in master §11.4 item 10; mechanism and ADR are `run-qc-and-checkpoint#RQC5`.

## Doc follow-up

`ARCHITECTURE.md` §4 (a finding cites an admitted claim; QC is a warning, never a gate).

## Added by the master plan (2026-10-19)

- **6.** `ResultsContext` and the Results artifact need the admitted evidence: today Results reads the raw
  aggregate artifact and decides suppression in the browser (`research-execution.ts:373`); no API serves
  `PrintGrade` or the evidence table (T3 A4). Gap G31. Test: a suppressed object's number is absent from
  the response, not hidden in the page.
- **7, corrected at 0d525bc8.** `AnalysisInputs.external_context` already exists (`application/analysis.py:101`) and reaches its fingerprint (:138) and prompt (:176). The missing connection is the production constructor in `application/analysis_results.py:570-579`, which supplies no external context. Trace the sealed-bundle provider into that constructor and the Lead, then test stored source lineage and payload. Reuse the existing field; do not build a second context type or claim its absence. External context remains context, never respondent evidence. Retiring it would change the integrated MVP scope and needs an explicit override.
  - *Module preparation, landed on `feature/analysis-external-context` (2026-10-22); the Lead is still to come.*
    - A run with analysis pins the Study's newest finished Design Research run's sealed bundle when it starts:
      `metadata.analysis_context` holds the run, the published artifact and its SHA-256
      (`ResearchRuns.design_research_pin`, `application/research.py`, among the newest 200 Deep Research runs).
    - It is behind the API's `AIA_AI_ANALYSIS_EXTERNAL_CONTEXT`, off by default. A retry keeps the original's pin
      (`kept`). The pin is metadata only, never the run's key.
    - `native_sources` reads the pin again through `DeepResearchRuns.bundle` and holds it to the same artifact and
      bytes, its seal verified. Any other answer is refused by name (`context_pin`, `context_not_found`,
      `context_unverified`, `context_moved`), never read as no context. The client report reads the data alone
      (`with_context=False`), so a broken pin refuses only what the context is part of.
    - `prepare_module` passes `external_context_lines(public_context(bundle))` (`domain/analysis/external.py`)
      into the existing payload field and fingerprint: the public (Class C) findings only, since a module's
      request is classed from its dataset and design, never from this context; 24 findings at most, each claim
      cut at 400 characters.
    - The gate is unchanged: a figure copied from the context cites no row and is refused.
    - Tests:
      - `test_analysis_executor.py` "a run pins its design research and every module is shown it as context"
        (fails without the wiring; a Class A finding left out; each broken pin refused by name) and "without the
        switch a run pins no context";
      - `test_analysis_external.py`;
      - `test_analysis_draft.py` "a figure from external context is refused like any uncited number".
    - The Lead's half (LO9d's "newest sealed bundle's findings by reference") reads the same provider. It is
      `research_lead.py`'s, the integration coordinator's, and was requested there.
- **8a, 8b.** `AnalysisInputs` holds one origin; client-reported numbers (`client-data-in-analysis`) need a
  second table and a fingerprint that names it. Interfaces I21.
- **1, settled and open.** MVP-23 flips the parity cases `finding-without-evidence` and
  `no-finding-at-all`, and the report needs all eight modules complete, so one module with no citable
  finding blocks the internal report. **The owner decided on 2026-10-20 that it blocks** until the lack of
  supported findings is resolved: by a same-data retry, a changed design or more data, never by an invented
  finding (chunks 9a, 9b).


## Execution predecessors (2026-10-20)

Chunks 1 and 5 are W0 rule/authority work; 2-3 and 6 are W1 QC/admitted-result producers;
8a is the W1 proposed two-origin contract reviewed with S3 before client-data admission code;
4 and 8b (the implemented two-origin path) are W3. Chunk 7's external-context producer/consumer
contract is W1 and its wiring is W3 before Interpretation evidence is consumed. Keep this
requirement visible: integrating Deep Research context is MVP work, not an unrecorded removal.
MVPQ-04 is settled (block), so the diagnostic of chunk 9a is W1 and the composer's refusal 9b is W3; citation validators and missing-evidence negative tests never waited. No provisional finding is evidence.

**9a and 9b, added 2026-10-20 (MVPQ-04).** A module that cannot state a supported finding stores a diagnostic: the module, reason codes and what would resolve it (a same-data retry through `retry_analysis`, a changed design, more data). It is not a finding, is not counted as admitted, and appears on Analysis and Results. The composer of the internal report and the exports (internal DOCX and PDF, with literature, client) refuse while any of the eight modules is BLOCKED or empty; the existing "all eight modules complete" rule is the same rule stated once. Test: a module with no finding blocks composition and export, shows its diagnostic, and a patched finding with no claim id is refused by the citation gate.

## Cross-check additions (2026-10-20)

From the independent cross-check of the master plan against the code (`mvp-master-plan.md` §6.1, G47-G57). Anchors are `@ 085abe0`.

**10. The filtered base (G53, X8).** A routed question's numbers are over those it was asked, never over everyone. The aggregate takes the routed respondents as its base, computes its own effective n and support (a small base is suppressed like any other), and every admitted claim carries the base; Results and the report state it ("n = 84, those who never visit"). Tests: Q7's percentages sum over the routed base; a base below the support floor is suppressed and named; the claim's base appears on Results.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

**Existing chunks, changed.** 5 (G61): its test reads "one authority per evidence source", and AC-08's
row names it. 1 moves from E20 to E32 (G62), before its W1 consumer 9a.

### Ordering (the coordinator's census, 2026-10-21, OI-192)

`segment-maps-and-drilldown#10` (segment evidence) lands before `evidence-integrity#9b` (the
refusal while a module has no supported finding) and `artifact-chain-to-draft-report#CHN10`. Once
9b lands, the Segments chapter (ch-5) has no admitted producer without 10, so no run could reach a
draft report.
