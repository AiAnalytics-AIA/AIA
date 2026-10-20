---
status: planned
chunks:
  - "[ ] 1. Every key finding cites an admitted claim (MVP-23): a new rule, not a tightening, since AIA has no 95 % threshold (that is the unit's)"
  - "[ ] 2. Run QC as a pure function over a run's stored dataset, EXACT against the unit's qc.kontrola (MVP-24)"
  - "[ ] 3. A run's QC stored beside it and shown as warnings on Fieldwork and Results, never a gate"
  - "[ ] 4. The straight-liner check: flags by code, no pause, the worker proposes keep or flag; replace is a new linked run (F18, settled); the one definition is run-qc-and-checkpoint RQC1"
  - "[ ] 5. One field-policy authority per evidence source: the population contract's list for panel respondents (MVP-29)"
  - "[ ] 6. Results serves admitted claims: an API over the evidence table with suppression decided server-side, so the screen no longer reads raw aggregates"
  - "[ ] 7. Wire the sealed-bundle external-context producer into module preparation and the Lead; preserve the existing prompt/fingerprint context field and context-not-evidence boundary"
  - "[ ] 9. A module with no supported finding (MVPQ-04, W1): stored as a structured diagnostic that is not a finding; report composition, approval and every export refuse while any of the eight modules is blocked or has no supported finding, until it is resolved; the diagnostic cannot satisfy the gate"
  - "[ ] 8a. A two-origin analysis input and its fingerprint, designed (W1) and reviewed with S3 before client-data-in-analysis 5"
  - "[ ] 8b. The two-origin input wired (W3): the production constructor supplies the client-reported table and the sealed-bundle context, and a changed context or origin changes the module's input fingerprint and payload"
---
# Evidence integrity: findings cite evidence, run QC warns, one policy authority

Track E of the MVP roadmap (`overview.md` § MVP roadmap, #493). Written 2026-10-19 from
`mvp-cohesion.md` F7 (#496): three decisions had no plan, and all three change the same two
places, the analysis gate and the evidence layer, so they share one plan. **Owner: a chat session,
named when chunk 1 starts.**

## Decisions this plan carries

| Id | Decision (2026-10-19) |
|---|---|
| MVP-23 | Every key finding of an analysis module cites admitted evidence (stricter than 18.6.6's 95 %): a finding without an admitted number behind it is refused, or shown as an unsupported hypothesis |
| MVP-24 | 18.6.6's run QC (straight-lining, speeders, inconsistent answers) is ported **as warnings** on Fieldwork, Results and to the Lead, never a gate; it pairs with the straight-liner worker (MVP-12) |
| MVP-29 | One field-policy authority: the population contract's stricter list (115 client-measurable fields); `domain.evidence` consumes it. A client's own data is outside this chunk: `client-data-in-analysis` chunk 0 |

## What exists

- A draft's key findings must cite claims: `FindingDraft` carries `claim_ids`, the gate checks
  each (`packages/aia_core/src/aia_core/domain/analysis/draft.py:116, 272 @ 085abe0`), and the
  module's docstring says the draft passes "when 95 % of the findings cited" (`:9`). **MVP-23 is a
  tightening of that threshold, not a new rule.** Hypothesis until chunk 1 reads the whole check:
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

1. **Findings cite all.** Read the gate, set the threshold to every key finding, make the repair
   turn name the uncited finding, store a still-failing draft `BLOCKED` as today. Test: a draft
   with one uncited finding is refused; a draft with all cited passes; `test_analysis_executor.py`
   stays green. Decide here whether "shown as an unsupported hypothesis" is built or only refusal
   (refusal is the smaller change and the default).
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

- **Empty-module behavior is settled (MVPQ-04, owner 2026-10-20): block the report until the module's lack of supported findings is resolved.** Chunk 9 builds it; no diagnostic may be patched with an invented finding.
- Replacement identity is settled (F18): a new linked run. Only weighting/effective-n/support semantics remain open in master §11.4 item 10; mechanism and ADR are `run-qc-and-checkpoint#RQC5`.

## Doc follow-up

`ARCHITECTURE.md` §4 (a finding cites an admitted claim; QC is a warning, never a gate).

## Added by the master plan (2026-10-19)

- **6.** `ResultsContext` and the Results artifact need the admitted evidence: today Results reads the raw
  aggregate artifact and decides suppression in the browser (`research-execution.ts:373`); no API serves
  `PrintGrade` or the evidence table (T3 A4). Gap G31. Test: a suppressed object's number is absent from
  the response, not hidden in the page.
- **7, corrected at 0d525bc8.** `AnalysisInputs.external_context` already exists (`application/analysis.py:101`) and reaches its fingerprint (:138) and prompt (:176). The missing connection is the production constructor in `application/analysis_results.py:570-579`, which supplies no external context. Trace the sealed-bundle provider into that constructor and the Lead, then test stored source lineage and payload. Reuse the existing field; do not build a second context type or claim its absence. External context remains context, never respondent evidence. Retiring it would change the integrated MVP scope and needs an explicit override.
- **8a, 8b.** `AnalysisInputs` holds one origin; client-reported numbers (`client-data-in-analysis`) need a
  second table and a fingerprint that names it. Interfaces I21.
- **1, settled and open.** MVP-23 flips the parity cases `finding-without-evidence` and
  `no-finding-at-all`, and the report needs all eight modules complete, so one module with no citable
  finding blocks the internal report. **The owner decided on 2026-10-20 that it blocks** until the lack of
  supported findings is resolved: by a same-data retry, a changed design or more data, never by an invented
  finding (chunk 9).


## Execution predecessors (2026-10-20)

Chunks 1 and 5 are W0 rule/authority work; 2-3 and 6 are W1 QC/admitted-result producers;
8a is the W1 proposed two-origin contract reviewed with S3 before client-data admission code;
4 and 8b (the implemented two-origin path) are W3. Chunk 7's external-context producer/consumer
contract is W1 and its wiring is W3 before Interpretation evidence is consumed. Keep this
requirement visible: integrating Deep Research context is MVP work, not an unrecorded removal.
MVPQ-04 is settled (block), so the diagnostic of chunk 9 is W1 and the composer's refusal W3; citation validators and missing-evidence negative tests never waited. No provisional finding is evidence.

**9, added 2026-10-20 (MVPQ-04).** A module that cannot state a supported finding stores a diagnostic: the module, reason codes and what would resolve it (a same-data retry through `retry_analysis`, a changed design, more data). It is not a finding, is not counted as admitted, and appears on Analysis and Results. The composer of the internal report and the exports (internal DOCX and PDF, with literature, client) refuse while any of the eight modules is BLOCKED or empty; the existing "all eight modules complete" rule is the same rule stated once. Test: a module with no finding blocks composition and export, shows its diagnostic, and a patched finding with no claim id is refused by the citation gate.
