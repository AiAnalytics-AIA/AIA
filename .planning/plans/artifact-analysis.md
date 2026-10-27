---
status: in-progress
chunks:
  - "[x] ANL1. Analýza's contract as data: view operations, pointable ids (module, finding, claim, research question) and V2's interaction contract"
  - "[x] ANL2. Milestones and Pokrytí výzkumných otázek: each research question with its answer state, the findings that answer it and what is missing"
  - "[x] ANL3. Findings with their claim chips, opened in the inspector down to the measure on Výsledky"
  - "[x] ANL4. Blokované nároky and a module with no supported finding, each with its reason and the way out"
  - "[ ] ANL5. The three registers apart: findings, labelled interpretation, external context from the sealed bundle, with its source chips"
  - "[ ] ANL6. Moduly analýzy and the same-data retry through the Lead's card, the stage's retry buttons removed"
  - "[ ] ANL7. Open-answer coding hosted here: the coded themes as a proposal, the counts as admitted claims"
  - "[ ] ANL8. Journey: Analýza at 1440, 1100, 768 and 390 px on recorded analysis, zero paid jobs"
  - "[x] ANL2b. The coverage table as Otázka | Odpověď (the answer's text) | Stav in three words (reopens ANL2; spec szz A3; W3)"
  - "[x] ANL3b. One findings list with a module filter (reopens ANL3; spec szz A4; W3)"
  - "[ ] ANL9. Analýza as a stage of its own, no Výsledky tabs (spec szz A1; W3)"
  - "[x] ANL10. The header 'Běh z … · interní · origin'; run and claim ids off the stage (spec szz A2; W3)"
  - "[ ] ANL11. Finding review on the server: ledger subject analysis_finding, its routes and migration (spec szz A7; W3)"
  - "[ ] ANL12. Finding review on the web: Přijmout / Upravit / Vyřadit / Vrátit, 'Přijato N z M' (spec szz A8; W3)"
  - "[ ] ANL13. Evidence grades on Analýza: each finding's cited numbers carry the report's glyph, with the legend (Nigel, 27 Oct 2026; W3, with artifact-results#RES13)"
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
    `lead-orchestration#LO5a.1`), with cards 23b and 23c, whose "Použít ve zprávě" weaves its findings into the
    internal draft's body (CQ4 = Q58, `artifact-chain-to-draft-report#CHN8`);
  - the coder (`assumptions-and-open-answer-coding#AOC7`), if AOC4 lets a model propose codes.
- **Inline proposals:** coding themes as change blocks (V2 `:82`), accepted by a person into the
  coding review.

## 5. Inputs and outputs

- **Reads:** the run's evidence table (admitted claims), the specification, `research_questions_of`
  of the frozen design, the run's metadata and, after `evidence-integrity#7`, the sealed bundle by
  reference.
- **Hands on:** eight module artifacts (each an artifact id + SHA-256, with its `input_fingerprint`),
  read by `compose_internal_report` (`application/report.py:129`) as `ch-1`..`ch-8` by module
  ordinal (`domain/analysis/modules.py:56-122`, `report.py:407`: EXECUTIVE `ch-1`, RESEARCH_QUESTIONS
  `ch-2`, OBJECTS `ch-3`, AUDIENCE `ch-4`, SEGMENTS `ch-5`, HYPOTHESES `ch-6`, IMPLICATIONS `ch-7`,
  LIMITATIONS `ch-8`; AUDIENCE prints before OBJECTS), and their claims as ledger
  refs. All eight must be complete, or no draft is composed (`report.py:156-157`).

## 6. Input interactions

- B17 (the analysis retry, as a card).
- Primitives: `InlineConfirm` for cancel, and `SpendDialog` through the card.

## 7. Chunks

**ANL1. Contract.** `lib/artifacts/analysis.ts`. Depends on `research-lead-workbench#14`, `#16`.

Landed on #563's registry (`lib/workbench-artifacts.ts` `ARTIFACTS.analysis`: open_stage, focus,
inspect; module, finding, claim; analysis_retry and interpretation_research). `lib/artifacts/analysis.ts`
names the targets through `aiaId` and reads them back (`analysisTarget`, `readAnalysisTarget`,
`inspectable`): `module:<kind>`, `finding:<module>:<n>`, `claim:<module>:<claim_id>` (a claim id is unique
only within its module; one outside the id grammar is left unnamed, never rewritten). No `rq:` here: the
coordinator's ruling on #563 keeps it on the design row until WCE1. The screen carries them on the
coverage table, every module's entry in the module list (rendered whichever module is selected, so the
Lead's focus finds any of them; research_questions is the coverage table alone), each key finding and
each cited number's first chip in the page (`claimMarks`), so every target names exactly one element. Tests: `artifacts/analysis.test.ts`,
`ExecutionSteps.test.tsx` "puts every module's key findings first …".

**ANL2. Coverage.** Test: an RQ recorded as a gap at start reads "bez doložené odpovědi" with the
recorded reason.

Landed ahead of ANL1, whose registry (`research-lead-workbench#14`, `#16`) is not on develop yet:
`lib/analysis-coverage.ts` (`coverage`, `findingsOf`, `rqTarget`, `findingAnchor`) and
`AnalysisCoverage.tsx` (the table and the milestones Sběr dokončen and Povinná analýza; Zpráva
zrevidována is Zpráva's, read there). The research questions are the frozen Design Revision's
(`researchQuestionsOf`) and nothing else: until that revision is read the table says they are loading,
and after a failed read that they are unknown, never that the design has none and never a list made
from the module's own answers (which would drop an unanswered question and read as full coverage). A finding answers a question when it
cites a measure (`evidence_ref`) the module's answer cites; a module stored BLOCKED reads "nelze
říct", never an answer. Targets `module:research_questions` (the table) and `finding:<module>:<n>`,
plain strings until ANL1's `aiaId` (#563). No `rq:` target: the coordinator ruled (#563 f174ea5) that
`rq:<id>` belongs to the design row and waits for stable research-question ids (WCE1); ANL8's Lead
focus lands on `module:research_questions` or the answering finding until then. Tests: `analysis-coverage.test.ts`, `ExecutionSteps.test.tsx` "covers
every research question … (ANL2)".

**ANL3. Findings.** Test: a claim chip resolves to its measure on Výsledky (`citedMeasure`); an
unresolved ref is kept as a code, never as text.

The inspector body has landed; the chunk stays open until the frame opens it. `lib/analysis-inspect.ts`
(`inspectView`, `numberWords`) shows a finding with every number it cites, each resolved to its measure
(`#measure-<id>`). It shows a claim with its measure and the sentences of its module that cite it. A target
the run does not hold reads as missing, with the reason. `AnalysisInspect.tsx` has the coordinator's
signature (`{ target: { kind, id } }`, no header of its own) and reads the analysis the page shows,
which `AnalysisResults` publishes (`setShownAnalysis`), so the drawer never opens another run's item. Still
open: the frame wiring `inspect` and a person's click to it (the integration coordinator's).

*Landed (2026-10-22, `feature/analysis-inspector`).* The frame's drawer (#623) draws `finding` and `claim`
through `AnalysisInspect` (`BODIES` in `ItemInspectBody.tsx`, as the coordinator invited). A person opens
them the three ways V2 does:
- a coverage chip;
- each key finding's inspector button;
- a cited-number chip, whose measure link is in the drawer.

`useOpenAnalysisItem` is null outside the workbench, so there the page keeps its scroll and its measure
links. Tests: `ExecutionSteps.test.tsx` "opens a finding and a cited number in the workbench's inspector …
(ANL3)" and `analysis_journey.mjs` (drawer from the chip, the button and the number; the measure from the
drawer). Source chips moved to ANL5, with the external-context register they belong to: a finding of
this run cites admitted numbers only.

**ANL4. Blocked claims and diagnostics.** Test: a module stored BLOCKED shows "Potřebuje opravu",
never "Hotovo" (`needsRepair`). Depends on `evidence-integrity#9a`.

The part that needs no new API has landed; the chunk stays open for evidence-integrity 9a's diagnostic.
- `lib/analysis-blocked.ts`: `blockedModules`, every module stored BLOCKED in module order, its stored violations
  grouped by reason with each subject beside its own detail; `wayOut`, the way out the server gives (`GET
  …/analysis/retryable`): a same-data round only for a module it lists, "the same data would refuse it again" for a
  module the preflight refused before any model turn, nothing promised while the run runs or the list is unread.
- `AnalysisBlocked.tsx`: "Blokované nároky" after the overview, each reason in words (`research.exec.violation`,
  every `ViolationCode` worded, held to `domain/evidence/gate.py` by `analysis-blocked.test.ts`; a code without words
  keeps its code), counted, subjects and details folded; the way out per module only where the person can act
  (`canEdit` and a Průběh to go to). `ViolationList` words the selected module's pane the same way. The Lead is not
  offered as a way out: it cannot ask a same-data round until ANL6.
- Still open: N-3 (per-claim refusals as stored, a new API) and 9a's "no supported finding" diagnostic.

*Done (#968, 2026-10-26).* The note opens the analysis, before the milestones. "Bez doloženého zjištění" lists
each module whose stored `diagnostic` (9a, `domain/analysis/artifact.py` `finding_diagnostic`) says it stated
nothing, with the reason and its resolutions in words (`lib/analysis-blocked.ts` `unsupportedModules`,
`research.exec.resolution.*`). In the workbench "Opakovat analýzu" sends the person's typed "Zopakuj analýzu",
only on the run that command retries (`GET …/lead` `analysis_retry_run`); elsewhere the Průběh link stays. N-3
(per-claim refusals as stored) is not part of ANL4; it needs a new API and no chunk carries it yet.

**ANL5. Registers.** Test: an external finding is labelled "Externí kontext" and has no claim chip.
Depends on `evidence-integrity#7`, `lead-orchestration#LO9b`.

*External context landed (2026-10-22, `feature/analysis-external-register`).* `GET …/analysis` answers
`external_context`: the findings of the Design Research bundle the run pinned (evidence-integrity 7), exactly
as the modules were shown them, claims folded and cut (`domain/analysis/external.py` `shown_context`), from the
same verified read as the modules' sources (`RunAnalysis.external`); `None` without a pin or before any module
has an outcome. A pin that no longer names its bundle refuses the view (409 `sources_refused`, `context_moved`). Analýza lists them as "Externí kontext"
(`AnalysisExternal.tsx`), each labelled, its source a chip that links only an http(s) address
(`lib/analysis-external.ts` `sourceChip`), never a claim chip or a Lead target. Tests:
`ExecutionSteps.test.tsx` "lists the Design Research the modules were shown as Externí kontext … (ANL5)",
`analysis-external.test.ts`, `test_analysis_executor.py` (the route lists exactly the modules' lines; none
without the switch), and the journey (no register without a pin). Still open: the labelled-interpretation
register, which waits on `lead-orchestration#LO9b`.

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

## Findings

From the ANL8 audit in a browser: the UI workbench's recorded analysis, the `persona` fixture's finished run,
1440/1100/768/390 px (`tools/ui_workbench/analysis_journey.mjs`). Fixed on `feature/analysis-audit-fixes`.

- **F1.** The milestone "Sběr dokončen" read "čeká" on a finished run.
  - Anchor: `AnalysisCoverage.tsx:59 @ bfe6d15b` reads a step keyed `fieldwork`; the fieldwork step is keyed `run`
    (`research-execution.ts:16 @ bfe6d15b` `STEP_ORDER`).
  - Repro: the journey's milestone check, or `ExecutionSteps.test.tsx` "covers every research question … (ANL2)".
  - Consequence: every finished run said its fieldwork was still waiting.
  - Fix: `stepOf(run, "run")`. Test: the milestone's `data-done` is `true` on the completed fixture.
- **F2.** The Analýza stage opened about 1,780 px above its analysis (2,670 px at 390), at scroll 0.
  - Anchor: `ResultsWorkspace.tsx:51-53 @ bfe6d15b` draws the report card (`lead`) and the run's summary above
    the view tabs on every result stage. `ExecutionSteps.tsx:1659 @ bfe6d15b` (the analysis card) is below them.
  - Repro: the journey's "opens on its analysis" check.
  - Consequence: a person opening Analýza saw "Kdo odpovídal" and the report card, and had to scroll to find the analysis.
  - Fix: when the stage is Analýza (`stageOf`), `AnalysisResults` scrolls its card into view once its read settles,
    an error included, unless the person scrolled meanwhile, and again on every later move to Analýza within the page.
    The same frame puts Sociomapa and Zpráva below the same header; that is reported to the integration coordinator.
  - Test: the journey's checks at every width, and on moving from Výsledky to Analýza within the page.
- **F3.** At 390 px the coverage table was cut off by a horizontal scroll (`min-w-[36rem]`, `AnalysisCoverage.tsx:88 @ bfe6d15b`).
  - Repro: the journey's clip check at 390 px.
  - Consequence: "Zjištění" was clipped and "Co chybí" was out of sight.
  - Fix: below md each row is a card, each cell under its column's name.
  - Test: the journey checks that the table is never wider than its section.
- **F4.** A finding chip in the coverage table sent the page to Přehled.
  - Anchor: `AnalysisCoverage.tsx:101 @ bfe6d15b` linked `#analysis-finding-…`, a hash `ResultsWorkspace` reads as no view.
  - Repro: the journey's chip check, or `ExecutionSteps.test.tsx` "covers every research question … (ANL2)".
  - Consequence: the finding was hidden, and the workbench's stage track moved to Výsledky.
  - Fix: the chip is a button that scrolls to and focuses the finding, with no hash.
  - Tests: `ExecutionSteps.test.tsx` (hash unchanged, the finding focused) and the journey (AI analýza still selected).

## 8. Owner questions

None here. A module with no supported finding blocks the report: MVPQ-04 settled it
(`mvp-owner-decisions.md:87-99`, 2026-10-20), and its diagnostic is shown here (ANL4) and in the
refusal (`artifact-chain-to-draft-report#CHN10`); it never satisfies the gate.

## Doc follow-up

- Register this plan and its chunks.

## From the research build spec (2026-10-26)

Source: the research build spec (https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy), checked chunk by chunk against this plan's front-matter at
develop `bd0d1ad6` in the research chunk register (26 Oct 2026); waves recorded in
`.planning/mvp-execution-contracts.md`. Lane and order: [`prototype-build.md`](prototype-build.md).
A spec id carries its section prefix (`navrh/`, `vzorek/`, `sber/`, `szz/`, `lead/`), because the
ids repeat across sections. A ticked chunk the spec reopens is never unticked: its rework is a
follow-up chunk below.

**ANL2b. Coverage table** (spec `szz/A3`; reopens ANL2; W3, lane G). *Done (#946).* Otázka | Odpověď | Stav:
the module's answer text with its findings or what is missing under it, and one word per row
(`lib/analysis-coverage.ts` `CoverageRow.verdict`): Odpovězeno, Orientačně (only `segments_unavailable` recorded),
Bez dat, and Čeká / Neznámé, kept so an unknown is never scored answered.

**ANL3b. One findings list** (spec `szz/A4`; reopens ANL3; W3, lane G). With ANL5. *Done (#962).* "Zjištění":
each finding once, under its module, with a filter (Vše and the eight modules). A finding the filter leaves off is
unmounted; a Lead focus, a coverage chip or the inspector brings it back through `LEAD_REVEAL` (a claim only an
answer cites opens its module). The module's summary stays in the pane above the list, not the inspector.

**ANL9. Its own stage** (spec `szz/A1`; W3, lane G).

**ANL10. Header** (spec `szz/A2`; W3, lane G). *Done (#932).* "Běh z 21. 10. · interní · modelováno"
(`lib/analysis-coverage.ts` `analysisHeader`); no run id or claim id on the stage.

**ANL11. Finding review, server** (spec `szz/A7`, no backend; W3, lane G). A ledger subject migration on LO16's pattern; analysis draft.check.
- The seam to Zpráva (found 2026-10-26): the report must read the review, so a finding a person discarded never
  prints and an edited one prints as edited. Without it, ANL12's Vyřadit changes the screen and not the report.

**ANL12. Finding review, web** (spec `szz/A8`; W3, lane G). After ANL11 and ANL3b.

**Notes.**
- ANL4 and ANL6 carry `szz/A5`; ANL6 `szz/A6` (its ceiling from `lead-orchestration#LO23`); ANL8 `szz/A10`.

## From the unplanned-features inventory (2026-10-27)

Source: the five inventories of 27 Oct 2026 (the Lead, the client pages, Settings, the research stages and the
prototypes, each compared with develop `dbaa7720`) and the product owner's decisions on them (Nigel, 27 Oct 2026,
~01:10-01:40 UTC, in the PM coordinator's chat: "lets turn these into chunks", then an answer to every decision
question). The research build spec cited is <https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy> (spec v6,
prototype v78); its ids carry their section prefix (`navrh/`, `vzorek/`, `sber/`, `szz/`, `lead/`). Waves are in
`.planning/mvp-execution-contracts.md`; a chunk marked **after the MVP** has the wave POST there. Ids are only
added, never renumbered; a ticked chunk a decision reopens gets a follow-up chunk.

**ANL13. Grades on Analýza** (W3, lane G). RES13's component beside each number a finding cites. Test: a cited
modelled number carries the modelled glyph.
