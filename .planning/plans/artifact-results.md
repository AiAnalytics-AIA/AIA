---
status: in-progress
chunks:
  - "[ ] RES1. Výsledky's contract as data: view operations, pointable ids (measure, set, object row, open question) and V2's interaction contract"
  - "[ ] RES2. Results read admitted rows from the server: suppression and support decided there, no raw aggregate read by the screen"
  - "[ ] RES3. The body as V2 draws it: each set's means with intervals and Kish n, suppressed rows with their reason, the reading line (an order only where intervals part), shares with bases"
  - "[x] RES4a. The reopened note: 'Výsledky běhu z revize N; studie je na revizi M' when the study holds a newer Design Revision than the run's"
  - "[ ] RES4b. Původ a kvalita: run, revision, origin, suppression rule, QC count (QC after evidence-integrity#3)"
  - "[x] RES5a. Open answers on Results: up to five raw answers per open question, internal only and labelled as data (RQ1 = Q52 a)"
  - "[ ] RES5b. Their coded counts once coding exists (after assumptions-and-open-answer-coding#AOC8)"
  - "[ ] RES6. The Lead on Výsledky: Interpretation Research on a question or a set as a Lead card, the stage's own client-knowledge ask removed"
  - "[x] RES7a. Journey: Výsledky's Data view at 1440, 1100, 768 and 390 px on a fictional run (layout, the Lead's ids, a measure by hash), zero paid jobs"
  - "[ ] RES7b. The journey's Lead half: the Lead focusing measure:<id>, an Interpretation Research card on 12a's recorded web (after RES6)"
  - "[ ] RES8. CSV and XLSX export of the run's per-question tables, every cell an admitted claim, from the aggregate (report-delivery#RD12, moved here by the PM 2026-10-21)"
  - "[ ] RES4c. Výsledky's header pill 'Běh z … · revize n', the revision-moved link and 'Sociomapa ›' (reopens RES4a; spec sber V2; W2)"
  - "[ ] RES9. Výsledky without inner tabs in the workbench (spec sber V1; W2)"
  - "[ ] RES10. Research-question tiles VO1…VOn (spec sber V4; W2)"
  - "[ ] RES11. The familiarity base for a hidden object, the server: an object result answers how many respondents who know the object answered ('odpovědělo jen 18 lidí, kteří značku znají') (spec sber G6; W2)"
  - "[ ] RES12. The familiarity base beside a hidden object on Výsledky (W2, after RES11)"
  - "[ ] RES13. Evidence grades on screen: the report's glyph (measured, modelled, indicative, suppressed) beside every number, table cell and chart series on Výsledky, greyscale-safe, with a legend always visible; a modelled figure never looks measured (Nigel, 27 Oct 2026; W2)"
  - "[ ] RES14. After the MVP: Další krok · Ideální skupina, the classic stage route-next, NOT_IN_AIA in docs/migration/interface-screens.json (Nigel, 27 Oct 2026)"
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

RES4a, as built: `revisionNote` (`result-reading.ts`) over the study's Design Revisions
(`GET …/design/revisions`) and the run's `design_revision`; the note sits above the numbers. An unread
list says nothing (never "the design moved" on unknown). Compared with Design Revisions, not working
revisions: a run executes a Design Revision, and an edit not yet submitted has not moved its design.
The stage track's half is `productization-coherence#PC5`'s.

**RES5. Open answers.** RQ1 = Q52 (a): up to five raw answers per open question, labelled "data, ne
připuštěná evidence; nejsou kódované", internal only: never exported, never in a client deliverable
(RD0's no-drill-down rule). Coded counts after `assumptions-and-open-answer-coding#AOC8`. Test: at
most five answers show; no export or client report contains one.

RES5a, as built: the raw answers were already in the aggregate (`verbatimy`, up to 200,
`research_aggregate.py:827`) and already shown, five at most, inside each open question's closed
details (`research-execution.ts` `resultTable`), unlabelled. §8 "AIA shows none today" was wrong.
The answers now show on the card itself, quoted, under "data, ne připuštěná evidence; nejsou
kódované", five at most (`OPEN_ANSWER_EXAMPLES`); a suppressed open question shows none, as
before. "Never exported, never in a client deliverable" is held by
`test_open_answers_stay_internal.py`: no Python module but the aggregate names `verbatimy`, so no
report, analysis prompt or export reads them; RES8's export test repeats it for the file.

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

**RES8. Export (report-delivery#RD12).** Moved here by the PM on 2026-10-21.
- A study-scoped route returns the run's per-question tables as CSV and XLSX: `question_tables(...)`
  (`report_tables.py:130`) over an evidence table built from the run's aggregate artifact (the same
  builder analysis uses), so a run whose analysis is parked still exports; `compose_question_tables`
  is unchanged (agreed with the integration coordinator, 2026-10-21; the report's own citation of
  the aggregate is the chain plan's G5).
- Every cell an admitted claim for the surface; a suppressed question named, not printed. The file
  records the aggregate artifact id and SHA-256. No raw open answer (RES5a).
- Not paid. Depends on RES2 (the same admitted rows the screen shows).
- Test: a suppressed cell never appears; the file's numbers equal the screen's; no `verbatimy`.

RES7a, as built: `tools/ui_workbench/results_journey.mjs` (`make ui-results`, after `make ui-research`). It
found F-R1 to F-R3 below, failed on each before its fix and passes after.

## Findings

Audit of Výsledky in a browser on the workbench's completed fictional run (persona fixture), 2026-10-21,
anchors `@ bfe6d15b`.

- **F-R1. The report card buries the data.** `ResultsWorkspace.tsx:51` renders the study's report card
  (`CompleteReport`) above every view, so `#data` (the `results` stage) opened two screens above the
  data at 1440 px and four at 390 px. Repro: `results_journey.mjs` on `bfe6d15b` fails "the study's
  report card is not shown on Data". Fix: the card shows on Přehled and Rešerše a zpráva only,
  hidden (kept mounted) elsewhere. Test: that journey check; `ExecutionSteps.test.tsx` "shows the
  internal draft…" asserts it hidden on Data.
- **F-R2. A measure's reading squeezed beside its chip.** `ExecutionSteps.tsx:1943` put the reading
  inside the title column beside the support chip, so it ran 78 % of the card at 1440 px and about
  half at 390 px. Fix: the reading runs the card's width under the title row. Test: the journey's
  "every reading runs its card's width" (≥ 90 %).
- **F-R3. A rated set's table wider than a phone.** `ExecutionSteps.tsx:1821` (`min-w-[30rem]`) made
  the table 480 px at 390 px; Interval and Kish n were reachable only by a sideways scroll. Fix: the
  interval band column is left out under 640 px, and the minimum width applies from 640 px. Test:
  the journey's "nothing of the data view is wider than the screen".
- **F-R4. A run's cost printed with a decimal point.** `ResultsWorkspace.tsx:62` (`toFixed(2)`) wrote
  "0.00 USD" among Czech numbers. Fix: cs-CZ, "0,00 USD". No test of its own (one formatter).
- **F-R6. A view opened by its address lands under the run's notices** (Sociomapa's audit,
  `artifact-sociomap`, relayed by the PM). `ResultsWorkspace.tsx:77` (the tablist) sits below the
  origin notices, the receipt and the run's header, so Sociomapa (`#maps`) and Výsledky (`#data`)
  opened with their view 989 px down a 900 px screen (1,329 px at 390 px; 2,174 px with the report
  card). Fix: a view named by the address scrolls its tabs into view and keeps them there while what
  sits above loads (3 s, until the person scrolls, touches or types). Tests: `ResultsWorkspace.test.tsx`
  "opens a view named by the address scrolled to its tabs"; the journey's "Data opens scrolled to its
  view" and "Sociomapa opens scrolled to the map" at four widths.
- **F-R5 (not Výsledky's).** `src/lib/artifacts/sample.test.ts` "keeps the pending ids pending only
  while the contract lacks them" fails on `bfe6d15b` (`[ 'sample:ready', true ]` against `false`);
  reported to the PM for Vzorek's owner.

Second pass, 2026-10-22, anchors `@ 9607ee09` (each detail opened, the tabs by keyboard, the search, a
study with no run):

- **F-R7. A choice question's answers in name order.** `research-execution.ts:388` listed the stored
  shares as the aggregate holds them, and the artifact store writes canonical JSON
  (`artifact_repository.py:434`, `sort_keys=True`), so a frequency scale read "Jeden až dva dny, Každý
  den, Méně často, Tři až čtyři dny". Fix: `resultTable(…, options)` lists the specification's options in
  the order asked, any other answer after them. Test: `research-execution.test.ts` "lists a choice
  question's answers in the order it asked them".
- **F-R8. "Výsledky zatím nejsou." and nothing else.** `ExecutionSteps.tsx:1630` said neither why nor
  where to go. Fix: no run says the study has not run and links to its run stage where the frame may
  edit; a run says why it has none in its state's words (`runState`: running, waiting with its reason,
  failed or cancelled, never "not finished" for a run that will never finish) and links to its Průběh.
  Tests: `ExecutionSteps.test.tsx`, the no-run retry test, "says why a run without results has none"
  and "never says a failed run is still going".
- **F-R9. A question's detail table spilled out of its card on a phone.** `ExecutionSteps.tsx:1552`
  gave the bar column 40 % at every width, so labels wrapped a word a line and a multi-option table ran
  past its card's edge at 390 px (inside the screen, so F-R3's check passed). Fix: the bar column is left
  out while the card is under 32rem, a container query on the card, so a narrow workbench pane is
  covered as well as a phone; the set table now reads its card's width the same way. Test: the
  journey's "nothing spills out of its measure card" (fails on `9607ee09` at 390 px). A choice
  question's reading now breaks ties in the asked order too (`result-reading.test.ts`).
- **F-R10. Přehled read a cost with an unknown part as the run's exact cost.**
  `apps/web/src/components/rehome/research/ResultsWorkspace.tsx:88 @ 382b418a` showed `actual_cost_usd`,
  the attempts' recorded cost (`apps/api/src/aia_api/routers/research.py:1141-1147 @ 382b418a`). An
  attempt that ends with a paid call dispatched and never answered is charged its whole hold as exposure
  (`packages/aia_core/src/aia_core/infrastructure/workflow_repository.py:1581-1582 @ 382b418a`,
  `_settle_uncertain`), an upper bound; while the call is still out, the attempt's cost leaves it out.
  Either way the figure read as exact. The run's spend (#774, `research.py:1742 @ 382b418a`) counts
  such a call as `uncertain_calls`, and Průběh's Náklady says so. Fix: the line reads "Utraceno" from
  `run.spend` through Průběh's own rule (`spendRows`), naming unpriced calls beside the sum with
  Průběh's running or ended note; no spend reads Průběh's "AIA nyní nezjistí", never "not reported yet"
  to a caller who will never see a figure. Tests: `ResultsWorkspace.test.tsx` "reads what the run spent
  from its spend…", "names a call the run could not price…" and "says the cost cannot be told…" (all
  fail on `382b418a`). The API half, fixed beside it: `actual_cost_usd` on a research run, an agent job and a Deep
  Research run is the run's spend fold (`ActivitySpend.known_usd`: the total, null while a call's outcome
  is unknown), not its attempts, which keep a completed step's exposure and never see a resolution. Tests:
  `apps/api/tests/test_unknown_attempt_cost_api.py` (13, each fails on `a25d2435`) and
  `test_spend_attribution.py` "a page of runs is read at once…". Open beside it (the spend fold's, not
  this screen's): a priced tool call still out counts as held, not uncertain.

Checked and sound (pass 3, 2026-10-22 @ `382b418a`): Přehled, AI analýza and Rešerše a zpráva at 1440 and
390 px in light and dark, no page overflow (the tab row and the report's claim table scroll inside
their own boxes); the one 404 is `design/source` on a study that reuses no design (`useResource`: nothing
here). Pass 1 and 2: the view tabs by arrow keys, Home and End, the focus ring (2 px), the search's
"Žádný výsledek neodpovídá filtru", no page error.

## 8. Owner questions

**RQ1. Do raw open answers show on Výsledky before they are coded?** **Settled 2026-10-21 via
/pmstatus Q52: (a).**
V2 shows example answers labelled "data, ne připuštěná evidence". AIA already showed up to five,
unlabelled, inside a closed detail (corrected under RES5a).
- (a) Up to five example answers per open question: internal only, never exported, never in a
  client deliverable (RD0's no-drill-down rule), labelled as data.
- (b) No raw answer until coding exists. The section shows the count answered and "nekódováno".
- (c) Every answer, behind a disclosure, internal only.

**Recommendation: (a).** A researcher needs to read some answers to judge the coding. The respondents
are AI (fictional or modelled), so nothing personal is exposed, and RD0 keeps it out of the client
deliverable.

## Doc follow-up

- Register this plan and its chunks.
- `report-delivery`: RD12 (the CSV/XLSX export) is built here as RES8; RD12 points to it.

## From the research build spec (2026-10-26)

Source: the research build spec (https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy), checked chunk by chunk against this plan's front-matter at
develop `bd0d1ad6` in the research chunk register (26 Oct 2026); waves recorded in
`.planning/mvp-execution-contracts.md`. Lane and order: [`prototype-build.md`](prototype-build.md).
A spec id carries its section prefix (`navrh/`, `vzorek/`, `sber/`, `szz/`, `lead/`), because the
ids repeat across sections. A ticked chunk the spec reopens is never unticked: its rework is a
follow-up chunk below.

**RES4c. Header pill** (spec `sber/V2`; reopens RES4a; W2, lane F). On `research-lead-workbench#36`.

**RES9. No inner tabs** (spec `sber/V1`; W2, lane F).

**RES10. Research-question tiles** (spec `sber/V4`; W2, lane F). Pairs with `artifact-analysis#ANL2b`; the research-question list on the compiled specification is a hypothesis until anchored.

**Notes.**
- RES3 carries `sber/V5`, `V6`, `V7`; RES4b `V3`, `V8`; RES2 `V9`; RES6 `V10`.
- Awaiting the methodology owner: "Efektivní n" is Kish's, as RES3 says (OQ8), and a set's scale follows the board's presets (OQ9).

## From the unplanned-features inventory (2026-10-27)

Source: the five inventories of 27 Oct 2026 (the Lead, the client pages, Settings, the research stages and the
prototypes, each compared with develop `dbaa7720`) and the product owner's decisions on them (Nigel, 27 Oct 2026,
~01:10-01:40 UTC, in the PM coordinator's chat: "lets turn these into chunks", then an answer to every decision
question). The research build spec cited is <https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy> (spec v6,
prototype v78); its ids carry their section prefix (`navrh/`, `vzorek/`, `sber/`, `szz/`, `lead/`). Waves are in
`.planning/mvp-execution-contracts.md`; a chunk marked **after the MVP** has the wave POST there. Ids are only
added, never renumbered; a ticked chunk a decision reopens gets a follow-up chunk.

**RES11-RES12. Familiarity base** (W2, lane F). Spec `sber/G6`: whether the familiarity base is on the object result is
not known (a **hypothesis**: only `donors` and `effective_n_kish` are read, `R/ExecutionSteps.tsx:2108-2111 @
bd0d1ad6`). RES11 checks and serves it from the aggregate; RES12 prints it beside a hidden object. Test: a suppressed
object answers and shows its familiarity base; an unknown base reads unknown.

**RES13. Evidence grades on screen** (W2, lane F). Nigel, 27 Oct 2026: the same glyph the report prints
(`infrastructure/report_docx/marks.py`: one glyph per grade, unknown "?") beside every number, table cell, chart series
and map node; greyscale-safe; the legend always visible; a modelled figure never looks measured. One web component and
legend from the grades the result API already carries (RES2's admitted rows), shared with
`artifact-sociomap#SOC15` and `artifact-analysis#ANL13`. Test: a modelled cell carries the modelled glyph, the legend is
present, and the page passes `make web_design`'s contrast check in greyscale.

**RES14. Další krok · Ideální skupina** (after the MVP). The classic route `next` (`docs/migration/interface-screens.json`,
`route-next`, NOT_IN_AIA, "The stage says it is not in AIA"). Nothing is built in the MVP.
