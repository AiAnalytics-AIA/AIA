---
status: planned
chunks:
  - "[ ] RES1. Výsledky's contract as data: view operations, pointable ids (measure, set, object row, open question) and V2's interaction contract"
  - "[ ] RES2. Results read admitted rows from the server: suppression and support decided there, no raw aggregate read by the screen"
  - "[ ] RES3. The body as V2 draws it: each set's means with intervals and Kish n, suppressed rows with their reason, the reading line (an order only where intervals part), shares with bases"
  - "[ ] RES4. Původ a kvalita and the reopened note: run, revision, origin, suppression rule, QC count; 'Výsledky běhu z revize N; studie je na revizi M' when the design moved"
  - "[ ] RES5. Open answers on Results: up to five raw answers per open question, internal only and labelled as data (RQ1 = Q52 a), and their coded counts once coding exists"
  - "[ ] RES6. The Lead on Výsledky: Interpretation Research on a question or a set as a Lead card, the stage's own client-knowledge ask removed"
  - "[ ] RES7. Journey: Výsledky at 1440, 1100, 768 and 390 px on a fictional run, zero paid jobs"
---
# Artifact: Výsledky (Results)

Umbrella: `research-lead-workbench#20` (with Sociomapa). Chain:
[`artifact-chain-to-draft-report.md`](artifact-chain-to-draft-report.md). Anchors `@ 25f26232`;
prototype `@ 9b50963f`.

## 1. What it is, and its single job

**Its job: the frozen run's admitted numbers, with their uncertainty, and nothing that is not
admitted.**

V2: `ResultsArt` (`EvidenceStages.tsx`, after `ShareRow`).
- The reopened note: "Výsledky běhu z revize N; studie je na revizi M".
- §1 Sada 1: mean on 1-10, 95 % interval, an interval bar and Kish n; a suppressed row says why. The
  reading line: "Pořadí platí jen tam, kde se intervaly rozcházejí".
- §2 shares with intervals and bases, and a note on a small base.
- §3 the open question Q9: example answers and "data, ne připuštěná evidence; nejsou kódované".
- §4 others, with "srovnání segmentů" unavailable.
- §5 Původ a kvalita.
- Contract `CONTRACTS.results` (`fixture.ts:412`): read only; a suppressed number is not shown even to
  the AI.

## 2. What exists today

- `ResultsStep` (`ExecutionSteps.tsx:1399`) → `RunResults` (`:1412`) → `ResultsWorkspace`
  (`ResultsWorkspace.tsx:11`; views data, maps, analysis and report by hash, `:25-27`).
- Data: `AggregateView` (`ExecutionSteps.tsx:1793`, `#res-aggregate`), `ObjectComparison` (`:1765`),
  `Table` (`:1350`) and `IntervalBar` (`:1386`); banners `OriginBanners` (`:163`).
- `lib/result-reading.ts` (`readMeasure`, `compareObjects`, `citedMeasure`).
- The client-knowledge ask "Zeptat se na klientské znalosti" (`askAssistance`, `:1415`): an AI start.
- Route: `GET /research/runs/{run_id}/artifacts/{artifact_id}` (`routers/research.py:1688`). The
  screen reads the raw aggregate artifact and decides suppression in the browser
  (`evidence-integrity#6` names it).

## 3. Gaps

| # | Gap | Kind |
|---|---|---|
| R-1 | Admitted rows served by the API (`evidence-integrity#6`) | needs a new API (owned there) |
| R-2 | Means, intervals, Kish n, suppression reason and the reading line | data exists (`result-reading.ts`) |
| R-3 | The reopened note: the design moved after the run (`productization-coherence#PC5`) | data exists (the run's revision against the study's) |
| R-4 | Open answers: up to five raw answers, internal only (RQ1 = Q52 a) | needs a new API (the answers, served internal only) |
| R-5 | Coded counts (`assumptions-and-open-answer-coding#AOC8`) | needs a new API (owned there) |
| R-6 | Segment comparison: "V AIA zatím není" until `segment-maps-and-drilldown#10` | needs a new API (owned there) |
| R-7 | Charts (`research-lead-workbench#31`) and CSV/XLSX (`report-delivery#RD12`) | needs a new API (RD12) |
| R-8 | The filtered base of a routed question (`evidence-integrity#10`) | needs a new API (owned there) |
| R-9 | The Lead's targets on this screen (G11) | needs a new API (the target grammar) |

## 4. The Lead on this artifact

- **View operations:**
  - `open_stage(results)` (view `data`) and `focus(target)`;
  - `filter_support(all|reportable)` and `search(text)`: display only (audit B26).
- **Pointing:** `measure:<question id>`, `set:<id>`, `object:<set id>.<object>` and
  `open_question:<id>`. `#measure-<id>` exists today (`ResultsWorkspace.tsx:27`). `data-aia` is
  `results.<set or question>`.
- **Edit operations:** none (a frozen run).
- **Workers and cards:**
  - Interpretation Research targeted at a question or a battery object result (ADR 0021's target
    kinds; `lead-orchestration#LO5a.1`), as the request, running and finished cards
    (`research-lead-workbench#23b`, `#23c`);
  - `answer_memory` (advice).
- **Inline proposals:** none. External context is shown labelled, beside the number, never inside
  it.

## 5. Inputs and outputs

- **Reads:** the run's aggregate (artifact id + SHA-256), the specification (wording, scales), the
  run's metadata (origin, receipt) and the evidence table.
- **Hands on:** admitted claims by `evidence_ref` (ledger refs) to Analysis, the report's question
  tables (`report_tables.py:130`) and the Lead (`lead-orchestration#LO8`).

  The report reads the analysis evidence table, not the aggregate artifact itself, and its audit names
  no aggregate artifact (G5, `artifact-chain-to-draft-report#CHN6`).

## 6. Input interactions

- B26 (filters).
- Primitives: `ChoiceChips` (support), a debounced search and `Segmented` (views).

## 7. Chunks

**RES1. Contract.** `lib/artifacts/results.ts`. Depends on `research-lead-workbench#14`, `#16`.

**RES2. Admitted rows.** The screen reads `evidence-integrity#6`'s route; `readMeasure` takes its
rows. Test: a suppressed row arrives without a value and the screen cannot show one.

**RES3. Body.** Tests: `ExecutionSteps.test.tsx`: overlapping intervals give no order (audit F9); a
missing interval reads unknown.

**RES4. Původ a kvalita and the reopened note.** Test: a run on revision 3 with the study on 4 shows
the note. Depends on `productization-coherence#PC5`, and `evidence-integrity#3` for QC.

**RES5. Open answers.** RQ1 = Q52 (a): up to five raw answers per open question, labelled "data, ne
připuštěná evidence; nejsou kódované", internal only: never exported, never in a client deliverable
(RD0's no-drill-down rule). Coded counts after `assumptions-and-open-answer-coding#AOC8`. Test: at
most five answers show; no export or client report contains one.

**RES6. The Lead on Výsledky.**
- `ExecutionSteps.tsx:1415`'s ask is removed under `leadOwnsAiStarts`; an Interpretation Research
  card targets a measure.
- Test: the 26f guard.
- Depends on #550, `research-lead-workbench#23b`, `#26f`, `#26f.1` and `lead-orchestration#LO5a.1`.

**RES7. Journey.**
- Extends `tools/ui_workbench/research_journey.mjs` (`:115-128`, which stops at Data and Sociomapy:
  G8 of the chain plan) at 1440, 1100, 768 and 390 px:
  - a measure opened by hash;
  - the Lead focusing `measure:<id>`;
  - an Interpretation Research card on 12a's recorded web.
- Zero paid jobs. 768 and 390 px depend on `research-lead-workbench#26b`-`#26d`.

## 8. Owner questions

**RQ1. Do raw open answers show on Výsledky before they are coded?** **Settled 2026-10-21 via
/pmstatus Q52: (a).**
V2 shows example answers labelled "data, ne připuštěná evidence". AIA shows none today.
- (a) Up to five example answers per open question: internal only, never exported, never in a
  client deliverable (RD0's no-drill-down rule), labelled as data.
- (b) No raw answer until coding exists. The section shows the count answered and "nekódováno".
- (c) Every answer, behind a disclosure, internal only.

**Recommendation: (a).** A researcher needs to read some answers to judge the coding. The respondents
are AI (fictional or modelled), so nothing personal is exposed, and RD0 keeps it out of the client
deliverable.

## Doc follow-up

- Register this plan and its chunks.
