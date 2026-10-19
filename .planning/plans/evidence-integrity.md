---
status: planned
chunks:
  - "[ ] 1. Every key finding cites an admitted claim: raise the gate from 95 % to all (MVP-23)"
  - "[ ] 2. Run QC as a pure function over a run's stored dataset, EXACT against the unit's qc.kontrola (MVP-24)"
  - "[ ] 3. A run's QC stored beside it and shown as warnings on Fieldwork and Results, never a gate"
  - "[ ] 4. The straight-liner check: flags by code, keep or replace proposed; settle what replacing means"
  - "[ ] 5. One field-policy authority per evidence source: the population contract's list for panel respondents (MVP-29)"
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

- Unsupported hypothesis shown or refused only (chunk 1).
- What replacing a flagged respondent means for the run's identity (chunk 4).

## Doc follow-up

`ARCHITECTURE.md` §4 (a finding cites an admitted claim; QC is a warning, never a gate).
