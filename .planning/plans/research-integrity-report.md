---
status: in-progress
chunks:
  - "[x] 1. Runnable is not answerable: each start decides whether the run can answer the research questions it states; a run with gaps starts only on a person's recorded acknowledgement of exactly those gaps (AIA_RESEARCH_ANSWERABILITY_GATE, off by default), and the report prints the frozen record"
  - "[x] 2. The literature chapter keeps credibility and relevance apart: every accepted claim beside its verbatim passage and the topic it was searched for, every source with what its domain says (proposed tiers labelled), a review resting on one publisher said so, a sparse review said once"
  - "[ ] 3. One report variant, the same draft in DOCX and PDF: the researcher chooses the run's own report or the report with one completed review; the worker renders the stored draft (report_pdf); both files say which variant they are and what they hold"
  - "[ ] 4. Local render and inspection, USD 0: both variants of a fictional run composed, DOCX and PDF compared chapter by chapter, citations, maps, limitations, repeated prose, table of contents and layout checked by eye"
  - "[ ] 5. Develop acceptance on the existing fictional Fio run, USD 0 (owner's call: needs the deploy): recompose the literature variant at contract -4, render its PDF in the worker image, compare with the DOCX"
  - "[ ] 6. The lineage matrix from frozen records only: research question | items by wording | start verdict | the research_questions module's answer | literature L# or none | chapter"
  - "[ ] 7. Statistical reading notes: the interval method and the fictional-donor caveat, Czech pair-status words with their n basis, the person-scaling null, Stress-1 beside each figure, the multi-select note"
  - "[ ] 8. Association questions and the analysis handoff: Comparison.ASSOCIATE (aia-answerability-2), hypotheses and item links in the analysis payload, one statement of what analysis did not receive"
  - "[ ] 9. Deep Research evaluation findings recorded with all six parts (topical relevance, student theses as academic), then the owner's call on ADR 0021 decision 7"
---
# Research integrity and report quality

Owner's request (2026-10-16, in session): treat the report as the traceable conclusion of one
connected research process. Find whether what is entered at each step is used downstream, whether
every handoff keeps the right data and revision, and whether the final report interprets the
evidence faithfully; then fix the first coherent handoffs.

The trigger is a fictional end-to-end test on develop: study `STU-b58afeef95d64e`, run
`RUN-9b6e0f5e6e0e4345`, **200 fictional respondents**. Nothing here is a fact about Fio Banka or
its customers. The test record (`QA.md`) is on the owner's machine and was not readable in this
session; the run itself was not readable either (no network path to develop). Every claim below
about that run comes from the owner's account and the external review of its PDF; every claim
about code is anchored @ `357d779` (develop when this branch was cut) unless it says `wt` (this
branch's working tree).

## Constraints this work keeps

- No new 200-person run, nothing above the study's remaining budget, no source or organization
  approval broadened, the fictional report never approved, no deploy from this pass.
- No claim that the end-to-end problem is fixed until the downloaded artifacts are inspected
  (chunks 4 and 5).
- The Deep Research engine is frozen (ADR 0021): chunk 2 changes the report around it, never
  merge, verify or grounding.

## Diagnosis

Three handoffs failed in the Fio run, ranked by research validity, then report completeness,
then user trust.

1. **A runnable design was taken for an answerable one.** Readiness decides whether a design can
   run (`research_design.py` `assess_readiness`, `ready = not any(FAIL)`). Whether it can answer
   its research questions was traced (`research_trace.py`, run-recovery-and-truth 3a-3e) but only
   as a WARN that a start never reads (`research_trace.py:353-360`, "It never FAILs"). The Fio
   design predates the questionnaire agent's links (harness 3, 3e), so no item declared a research
   question: every research question read `unlinked_design`, UNKNOWN, and the run started. The
   analysis then had to answer four research questions from marginals of items that did not
   measure them (`domain/analysis/prompt.py:147-169`: research questions and evidence rows, no
   mapping between them).
2. **Accepted literature was credible by domain, not relevant by topic.** A finding is accepted
   on grounding (the quote verbatim in a captured source, its numbers in the quote), a source
   score from the host table, and a verifier that reads only claim, quote and excerpt
   (`apps/executors/.../deep_research/review.py:262-269`; `merge.py:3-16`). No code compares a
   claim with its research question, population, place or period; `vse.cz` scores
   `ACADEMIC_INSTITUTION` 0.75 for any page, student theses included (`sources.py:138, 350`); bank
   and finance-portal hosts are absent from the table and score 0.2, below the 0.55 threshold
   (`sources.py:61`). The engine did what ADR 0017 specifies; the Fio result is an
   **evaluation-finding candidate**, not a defect (chunk 9).
3. **The two documents were two compositions.** The worker composes and renders the base report
   at run end (`apps/executors/.../report.py`, `research_internal_pdf`); the report with
   literature was composed on request in the API, which has no converter, so it never had a PDF
   (`application/contextual_report.py` `stored_contextual_report`). The card that offers PDF knew
   only the base report and hard-coded the literature row as pending
   (`CompleteReport.tsx:39 @ 357d779`, "čeká na běh nebo výběr"), while the selected review lived
   in another component (`InterpretationResearch.tsx:25`). So the native PDF was the 33-page base
   report and the 40-page DOCX the other variant.

## Lineage matrix (code paths; the Fio run's own records not read)

| Boundary | Consumed | Persisted ids / revisions | Passed forward | Dropped, stale, substituted or display-only |
|---|---|---|---|---|
| Brief and client context → proposal | brief title, goal, decision use, briefing; approved Client Knowledge frozen at job enqueue (`research_agents.py` `context_snapshot`) | agent job run id, snapshot hash; acceptance in the approval ledger (gate 1) | `research_plan`: research questions (plain strings, no ids), objectives, hypotheses | hypotheses never reach analysis (`prompt.py:147-169`); objectives only as a fallback for research questions (`native.py:130-146`) |
| Research questions → questionnaire | the plan's research questions | per item `research_questions` by text (`research_design.py`, 3a) | links into the specification | optional; designs before harness 3 have none (Fio); editing a research question's text leaves its links dangling (3b "Not done") |
| Questionnaire → specification | sections, n, audience, title, dimensions, links | Design Revision id + content SHA-256; specification fingerprint | `ResearchSpecification` | a section's `purpose`, a question's `topics` are read by nothing |
| Audience, dimensions, population → run | the selection; the persona source chosen at start | `metadata.selection` (5b), `metadata.population` with `read_by_fieldwork`, the population binding row | the run's receipt | a roster run applies no filter or dimension; the population is recorded, not read. **The report's method chapter said they were "stored" even when the run recorded no selection** (`report_method.py:209-226`, fixed in chunk 1) |
| Readiness → start | the compiled specification, pinned readiness limits, the forecast | `metadata.readiness` (pin) | `ready` | research-question coverage was a WARN (fixed: chunk 1 decides answerability at start and records it) |
| Fieldwork | specification, response pin, persona source | dataset artifact with `data_origin` | answers | fictional donors are random labels (`ai_respondent.py:295-300`) |
| Aggregation | dataset, support and aggregation pins | aggregate artifact | shares, means, intervals, effective n | the interval is a donor-cluster bootstrap and nothing prints its method; the stored note says "reálné donor clustery" for fictional labels and is read by nothing (`research_aggregate.py:205-207`, chunk 7) |
| Sociomapping | dataset, pinned methods | map artifact, method fingerprints | maps, Stress-1, pair status | per-person scaling makes unrelated ratings correlate negatively at k=4; pair status read at n rows, not donors (chunk 7) |
| AI analysis | research questions as strings, the evidence table (marginals) | eight module artifacts, harness version | admitted prose | no respondent-level pairs, so no association can be answered; each module restates what it lacks (chunk 8) |
| Interpretation Research | the pinned analysis artifact (frozen lineage), subjects built by code from it | Deep Research run id, bundle SHA-256 | accepted findings | relevance unchecked after extraction; credibility by host only (chunk 2 discloses; chunk 9) |
| Report | eight modules, the map, the run's chapters; with literature, the selected review's bundle | `research_internal_docx` (contract -7, now -8) and `research_internal_docx_with_research` (-3, now -4) | DOCX | the variant with literature had no PDF; the card did not know the selected review (fixed: chunk 3) |
| DOCX → PDF | the stored DOCX | `research_internal_pdf` with `rendering_of` | PDF | the table of contents keeps empty cached page numbers that LibreOffice does not update (fixed: chunk 3) |

## Chunk 1 — runnable is not answerable

- `domain/answerability.py`: from the research trace, one decision: **capable**, or the gaps. A
  research question is a gap when it is UNANSWERABLE for any reason, when the design links nothing
  at all (`unlinked_design`), when its declared comparison is unknown, or when every measure is an
  open question or excluded from analysis. A question whose support is decided only by fieldwork
  is **pending**, never a gap and never "answerable": the report says so in those words. A design
  with no research question is one gap. The digest names the exact gaps.
- `ResearchRuns.start` computes it under the support and aggregation the run pins. With
  `AIA_RESEARCH_ANSWERABILITY_GATE` on, a start with gaps is refused
  (`ResearchQuestionsUnanswerable`, 409 `research_questions_unanswerable`) unless the person
  acknowledges the digest readiness showed, with a reason (10-1000 characters). Off (the default,
  tests and the workbench), the run starts and records its gaps unacknowledged. Either way the
  run records `metadata.answerability`; a new acknowledgement is also an approval-ledger row
  (subject `answerability`, migration `d2f4a6c8e0b3`, APPROVE_GATE). A retry inherits an
  acknowledgement of the same digest; an analysis retry over collected data is never refused and
  records that it was exempt.
- Readiness answers `answerability` with `acknowledgement_required` (the switch on and gaps), so
  the browser asks exactly when the server would refuse: turning the switch off restores the old
  behaviour end to end.
- The method chapter prints the frozen record: each research question, its measures, its state at
  start, and the decision that let a run with gaps start. The client report prints the gaps as a
  plain limitation, without the reason, the person or a run id.

Trade-off: a design without links (every design made before harness 3) needs an acknowledgement
on its first run while the gate is on. That is the point; it is also friction, and the gate ships
off until the owner turns it on (decision D1).

## Chunk 2 — the literature chapter

What code checked is said (verbatim quote, numbers in the quote, the verifier's reading of claim
against passage) and what nobody checked (same concept, population, place, period). Every
accepted claim prints beside its quote and the research topic it was searched for, so a mortgage
claim under a current-account topic is visible as that. The source table prints each source's
domain and the type the proposed source table assigns it, and says what AIA does not record
(author, method, sample, measured concept). A review whose accepted findings all come from one
publisher (domain/deep_research/triangulation.py `publisher_identity`) says so in a callout.
Counts say how much was captured against how little was cited; rejection reasons in words;
acquisition gaps grouped by reason. Nothing in `domain/deep_research/` changes.

## Chunk 3 — one report variant

- `report_pdf` workflow type, one deterministic step (`research_report_pdf`): renders a stored
  report DOCX named by artifact id and SHA-256, refuses any other, fails by name without a
  converter (`pdf_disabled`). A person preparing the variant again after a failed or invalid job
  starts a new one.
- `POST …/research/runs/{id}/report/context?deep_research_run_id=` composes and stores the
  variant once and asks for its PDF; `GET …/report/context` reads where it stands, composing
  nothing; `GET …/report/context/download` and `…/pdf/download` serve the prepared draft and its
  rendering, both naming the draft's artifact id and review state. A download changes no state.
- Both documents print their variant and their chapters; the table of contents carries page
  numbers in the PDF.
- The card on Výsledky chooses the variant (base, or one completed review), held by the results
  page and shared with the literature panel, which offers "Použít ve zprávě" instead of a second
  download. One place downloads and approves; the document approved is the one downloaded.
- Every internal download names its draft (`X-AIA-Artifact-Id`, the base DOCX included, which sent
  none @ 357d779 `routers/research.py` `download_run_report`); the card names the draft before
  download, hands over a file only when it is that draft (`downloadMismatch`), reads a variant
  only as the chosen review's (`currentVariant`), and undoes a choice only against a list of
  reviews read after it was made. Every server PDF state has its words; a failed PDF can be asked
  for again ("Vytvořit PDF znovu", the same draft, a new job). The card says that approval is
  AIA's record about the stored file, which keeps its draft footer (D2).
- The Run screen shows the gaps whenever the run has them and asks for the acknowledgement only
  where readiness says `acknowledgement_required` (the switch, so off restores the old start end to
  end); a confirmation names the digest it was given for and a changed design asks again; each gap
  says whether the run will not (UNANSWERABLE) or may not answer it; every `GapReason` has words,
  pinned by `test_the_web_words_exactly_the_reasons_a_gap_can_have`; a retry's gate clears once
  the retry succeeds.

## Findings

- **F1 (evaluation-finding candidate, chunk 9). Off-topic literature is accepted when grounded.**
  Claim: a finding whose quote is verbatim in a credible-domain source is accepted whatever its
  topic. Anchors: `merge.py:3-16`, `review.py:262-269`, `sources.py:138, 350` @ 357d779.
  Reproduction: not yet; needs the Fio run's bundle SHA-256, its three evidence ids and subject
  keys, then a recorded-fixture test. Consequence: three findings about choosing a mortgage
  provider stood as the literature on digital current-account trust. Smallest fix: owner's call
  (a relevance verdict in verification is an engine change, ADR 0021). Test: a recorded bundle
  whose off-topic finding is not accepted. **Hypothesis until reproduced.**
- **F2 (confirmed, fixed in chunk 1). The method chapter claimed a selection a run never
  recorded.** `report_method.py:209-226 @ 357d779` printed "jsou s během uložené" whatever
  `metadata.selection` held. Test: `test_report_method.py` "a run that recorded no selection".
- **F3 (confirmed, fixed in chunk 3). The table of contents has no page numbers in a PDF.**
  `report_docx/layout.py:377-381 @ 357d779` wraps prefilled PAGEREF results in a TOC field;
  LibreOffice keeps the empty cached results (measured 0 of 17 entries numbered). Test:
  `test_report_renderer.py` contents assertion.
- **F4 (confirmed, chunk 7). The interval method is never printed.** The aggregate's interval is
  a donor-cluster bootstrap (`research_aggregate.py:480-510`); for a fictional roster the donor
  labels carry no dependence, so its width is that of 200 rows, printed beside "efektivní n 62"
  (distinct donors). Reproduction: `/tmp/.../wf/ci_repro.py` (cluster 7.9 pp, Wilson at n=62
  15.2 pp). Consequence: a reader concludes the uncertainty is understated and cannot check how it
  was computed. Smallest fix: a sentence from the pinned AggregationSpec; the estimator is parity
  pinned (OI-62).
- **F5 (confirmed, chunk 7). Map pair status in English, at the wrong n.** `report_maps.py:174`
  prints `str(status)`; "4 objektů" at `:112`; status read at Kish n of rows.
- **F6 (confirmed, chunk 7). A multi-select table whose shares sum past 100 % says nothing.** The
  unit printed a note (`pozn`); `report_tables.py:178-189` does not.
- **F7 (hypothesis, chunk 9). A withheld gap need could print its internal marker.**
  `contextual_report.py:375-383 @ 357d779` printed `gap.need` without `text_withheld`.
- **F8 (open, OI-9 / complete-study-report F1). Fictional rows print "modelováno".** Confirmed
  in the chunk 4 render: Appendix B of a `SYNTHETIC_AI_FICTIONAL` run, whose own method chapter
  says "Odpovídali smyšlení respondenti", prints "modelováno" / "Modelováno" in Základ, Síla
  evidence and Upozornění on every row; the words are `domain/report/copy.py:78, 93, 101 @
  357d779`. Reproduction: the chunk 4 render above. Not changed here; it belongs to
  complete-study-report F1.

## Decisions for the owner

- **D1.** Whether the answerability acknowledgement is a recorded precondition (proposed: ADR 0025)
  or a fourth gate under ADR 0019; whether independence is enforced when self-approval is off; and
  when `AIA_RESEARCH_ANSWERABILITY_GATE` is turned on for develop (this branch ships it off).
- **D2.** How approval reaches a file: the stored draft always prints "KONCEPT — NESCHVÁLENO",
  approval lives in the ledger. A certificate beside the draft, or an approved rendering?
- **D3.** Whether to spend on an analysis retry of the Fio run so its base report is composed at
  contract -8 (chunk 5 needs nothing paid for the literature variant).
- **D4.** Chunk 9's engine change (ADR 0021 decision 7) and the source-table tier of student
  theses (ADR 0022 approval).
- **D5.** Layout: one chapter per page, or short chapters sharing a page.

## Relation to other plans

- run-recovery-and-truth: chunk 1 builds on 3a-3e (the trace) without editing them; chunk 2 covers
  the **report side** of chunk 4 (the passage per claim, rejection reasons), not source diversity;
  chunk 3 covers the card part of 6e (one report rule for the card and Interpretation Research).
- complete-study-report: chunk 3 generalises B3 (a PDF for every stored report variant) and
  supersedes B1d's "literature stays pending, since it joins only through a chosen review".
- research-lane-redesign B1: its "Deep Research variant stored as an artifact with a review_state"
  was B1d's and is now offered in both formats.

## Doc follow-up

- `CLAUDE.md` § 2, domain: `answerability.py  Runnable is not answerable: from the research trace,
  capable, pending (support decided at fieldwork) or the gaps (unanswerable, unlinked design,
  unknown comparison, only open or analysis-excluded measures, no research question), with a
  digest; Acknowledgement (digest + reason); answerability_note: what a run records`.
- `CLAUDE.md` § 2, application: `report_variants.py  the report with a chosen review: prepared
  once, its PDF asked of the worker (report_pdf), read without composing`; `research.py`: "start
  decides answerability and, with AIA_RESEARCH_ANSWERABILITY_GATE, refuses gaps no person
  acknowledged (ResearchQuestionsUnanswerable); request_report_pdf".
- `CLAUDE.md` § 2, executors `report.py`: "store_pdf_rendering; ReportPdfExecutor
  (research_report_pdf): a stored report DOCX rendered as PDF".
- `CLAUDE.md` § 2, routers/research: "readiness answers answerability (acknowledgement_required);
  start and retries take acknowledge_research_questions; POST/GET …/report/context,
  …/report/context/pdf/download".
- `CLAUDE.md` § A research run: the answerability paragraph and the new key.
- `ARCHITECTURE.md` § 4: "A run records whether it can answer what it asks"; narrow the "no
  override field" sentence (:422) to evidence gates, which this acknowledgement is not.
- `docs/architecture/adr/README.md`: ADR 0025.
- `AGENTS.md`: LibreOffice does not update a TOC field's cached PAGEREF results on conversion; a
  PDF made headless needs the page references outside the TOC field.
- `CLAUDE.md` § 2, web: `lib/answerability.ts` (the Run screen's gaps, the acknowledgement bound
  to its digest, GAP_REASONS pinned to the domain), `AnswerabilityGate.tsx`,
  `lib/report-variant.ts` (currentVariant, every PdfState in words, downloadMismatch), and
  CompleteReport's variant choice; `lib/api.ts`: the internal report downloads read
  `X-AIA-Artifact-Id` (requestStored) in both formats.
- Contracts: `aia-internal-report-8`, `aia-contextual-report-4`, `aia-client-report-2`,
  `aia-answerability-1`; workflow type `report_pdf`; ledger subject `answerability`.
