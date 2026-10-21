---
status: planned
chunks:
  - "[ ] ANL1. Analýza's contract as data: view operations, pointable ids (module, finding, claim, research question) and V2's interaction contract"
  - "[ ] ANL2. Milestones and Pokrytí výzkumných otázek: each research question with its answer state, the findings that answer it and what is missing"
  - "[ ] ANL3. Findings with their claim and source chips, opened in the inspector down to the measure on Výsledky"
  - "[ ] ANL4. Blokované nároky and a module with no supported finding, each with its reason and the way out"
  - "[ ] ANL5. The three registers apart: findings, labelled interpretation, external context from the sealed bundle"
  - "[ ] ANL6. Moduly analýzy and the same-data retry through the Lead's card, the stage's retry buttons removed"
  - "[ ] ANL7. Open-answer coding hosted here: the coded themes as a proposal, the counts as admitted claims"
  - "[ ] ANL8. Journey: Analýza at 1440, 1100, 768 and 390 px on recorded analysis, zero paid jobs"
---
# Artifact: Analýza (Analysis)

Umbrella: `research-lead-workbench#21` (with Zpráva). Chain:
[`artifact-chain-to-draft-report.md`](artifact-chain-to-draft-report.md). Anchors `@ 25f26232`;
prototype `@ 9b50963f`.

## 1. What it is, and its single job

**Its job: what the admitted evidence answers, research question by research question, and what it
cannot.**

V2: `AnalysisArt` (`InterpretStages.tsx:37-101`).
- Milestones (`:15-29`).
- §1 Pokrytí výzkumných otázek: RQ, its answer, findings and what is missing (`:47-56`).
- §2 Zjištění, výklad a kontext: three registers, finding / interpretation / external context
  (`:31-35`), with claim chips, source chips and uncertainty.
- §3 Blokované nároky ("brána evidence").
- §4 the open answers Q9: the coding proposal, or "Unavailable kind=proposed".
- §5 Moduly analýzy, with "Nové kolo nad stejnými daty" on a failed module.
- Contract `CONTRACTS.analysis` (`fixture.ts:414`): a number only as an AdmittedClaim; the AI does not
  approve its own claims.

## 2. What exists today

- `AnalysisResults` (`ExecutionSteps.tsx:1594`): key findings across modules (`#key-findings-title`,
  `:1651`), `CitedNumbers` (`:1546`) linking to Data, then every module's text.
- `AnalysisRepair` (`:1059`), with paid retries at `:1077-1089`.
- `InterpretationResearch` (`InterpretationResearch.tsx:31`) is mounted in the analysis view
  (`ExecutionSteps.tsx:1487`); its start is at `:145` and its retry at `:161`.
- Routes: `GET …/analysis` (`routers/research.py:1739`), `…/analysis/retryable` (`:1588`) and
  `POST …/analysis/retry` (`:1626`).
- The analysis input holds the research questions only (`application/analysis_results.py:575`); the
  HYPOTHESES module cannot assess hypotheses (`assumptions-and-open-answer-coding#AOC3`).

## 3. Gaps

| # | Gap | Kind |
|---|---|---|
| N-1 | Coverage per RQ: the RESEARCH_QUESTIONS module's answers and the gaps recorded at start (`report_method.py:151`) | data exists |
| N-2 | Findings with claim chips (`evidence_ref`, `citedMeasure`) | data exists |
| N-3 | Per-claim refusals from admission (which claim, why) beside a module stored BLOCKED | needs a new API (the refused claims as stored); hypothesis until checked against the stored outcome |
| N-4 | A module with no supported finding as a diagnostic (`evidence-integrity#9a`) | needs a new API (owned there) |
| N-5 | External context wired into module preparation (`evidence-integrity#7`) | needs a new API (owned there) |
| N-6 | Labelled interpretation (map interpreter, `lead-orchestration#LO9b`) | needs a new API (owned there) |
| N-7 | Hypotheses and `decision_use` in the analysis input (AOC3, a Q12 gap) | needs a new API (owned there) |
| N-8 | Coding (`assumptions-and-open-answer-coding#AOC5`-`#AOC8`; method MVPQ-02b open) | needs a new API (owned there) |
| N-9 | Segment comparison: no admitted producer until `segment-maps-and-drilldown#10` | needs a new API (owned there) |
| N-10 | Lead targets (G11) | needs a new API (the target grammar) |

## 4. The Lead on this artifact

- **View operations:** `open_stage(analysis)`, `focus(target)` and `inspect(finding|claim)`, which
  opens the inspector (V2's `C.visual.inspect`).
- **Pointing:** `module:<id>`, `finding:<module>:<n>`, `claim:<evidence ref>` and `rq:<id>`.
  `data-aia` is `analysis.finding.<id>` and `analysis.claim.<id>` (`InterpretStages.tsx:59, 71`).
- **Edit operations:** none. Findings are a run's output; a person can only ask for a new round.
- **Workers and cards:**
  - the analysis retry as a run card (a new round over the frozen dataset, `retry_failed_modules`);
  - Interpretation Research over a module (Q44: the research-questions module by default;
    `lead-orchestration#LO5a.1`), with cards 23b and 23c, whose "Použít ve zprávě" selects the report
    variant;
  - the coder (`assumptions-and-open-answer-coding#AOC7`), if AOC4 lets a model propose codes.
- **Inline proposals:** coding themes as change blocks (V2 `:82`), accepted by a person into the
  coding review.

## 5. Inputs and outputs

- **Reads:** the run's evidence table (admitted claims), the specification, `research_questions_of`
  of the frozen design, the run's metadata and, after `evidence-integrity#7`, the sealed bundle by
  reference.
- **Hands on:** eight module artifacts (each an artifact id + SHA-256, with its `input_fingerprint`),
  read by `compose_internal_report` (`application/report.py:129`) as the executive, RQ, audience,
  objects, segments, hypotheses, implications and limitations chapters, and their claims as ledger
  refs. All eight must be complete, or no draft is composed (`report.py:156-157`).

## 6. Input interactions

- B17 (the analysis retry, as a card).
- Primitives: `InlineConfirm` for cancel, and `SpendDialog` through the card.

## 7. Chunks

**ANL1. Contract.** `lib/artifacts/analysis.ts`. Depends on `research-lead-workbench#14`, `#16`.

**ANL2. Coverage.** Test: an RQ recorded as a gap at start reads "bez doložené odpovědi" with the
recorded reason.

**ANL3. Findings.** Test: a claim chip resolves to its measure on Výsledky (`citedMeasure`); an
unresolved ref is kept as a code, never as text.

**ANL4. Blocked claims and diagnostics.** Test: a module stored BLOCKED shows "Potřebuje opravu",
never "Hotovo" (`needsRepair`). Depends on `evidence-integrity#9a`.

**ANL5. Registers.** Test: an external finding is labelled "Externí kontext" and has no claim chip.
Depends on `evidence-integrity#7`, `lead-orchestration#LO9b`.

**ANL6. Modules and the retry.**
- `ExecutionSteps.tsx:1077-1089`'s starts move to the Lead's run card or a typed start; the list stays.
- Test: the 26f guard.
- Depends on #550, `research-lead-workbench#26f`, `lead-orchestration#LO5`.

**ANL7. Coding.** Depends on `assumptions-and-open-answer-coding#AOC8`.

**ANL8. Journey.**
- At 1440, 1100, 768 and 390 px on the workbench's recorded analysis
  (`artifact-chain-to-draft-report#CHN7`):
  - a finding opened to its measure;
  - the Lead focusing `rq:<id>`;
  - a module retried through the card on recorded answers.
- Zero paid jobs. 768 and 390 px depend on `research-lead-workbench#26b`-`#26d`.

## 8. Owner questions

None here. A module with no supported finding blocks the report: MVPQ-04 settled it
(`mvp-owner-decisions.md:87-99`, 2026-10-20), and its diagnostic is shown here (ANL4) and in the
refusal (`artifact-chain-to-draft-report#CHN10`); it never satisfies the gate.

## Doc follow-up

- Register this plan and its chunks.
