---
status: in-progress
chunks:
  - "[x] 1. Runnable is not answerable: each start decides whether the run can answer the research questions it states; a run with gaps starts only on a person's recorded acknowledgement of exactly those gaps (AIA_RESEARCH_ANSWERABILITY_GATE, off by default), and the report prints the frozen record"
  - "[x] 2. The literature chapter keeps credibility and relevance apart: every accepted claim beside its verbatim passage and the topic it was searched for, every source with what its domain says (the source table labelled a proposal not yet approved), a review resting on one publisher said so, a sparse review said once"
  - "[x] 3. One report variant, the same draft in DOCX and PDF: the researcher chooses the run's own report or the report with one completed review; the worker renders the stored draft (report_pdf); both files say which variant they are and what they hold"
  - "[x] 4. Local render and inspection, USD 0: both variants of a fictional run composed, DOCX and PDF compared chapter by chapter, citations, maps, limitations, repeated prose, table of contents and layout checked by eye"
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
| Audience, dimensions, population → run | the selection; the persona source chosen at start | `metadata.selection` (5b), `metadata.population` with `read_by_fieldwork`, the population binding row | the run's receipt | a roster run applies no filter or dimension; the population is recorded, not read. **The report's method chapter said they were "stored" even when the run recorded no selection** (`report_method.py:89-106 @ 357d779`, fixed in chunk 1) |
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

## Chunk 4 — what the local render showed

Rendered 2026-10-16 at USD 0: `test_native_ai_study_connects_a_populated_map_to_admitted_report_inputs
[deep-research-and-internal-report]` (fictional respondents, recorded web, scripted models) run
with a scratch pytest plugin that saves every DOCX `DocxRenderer.render` returns, then each
converted by `LibreOfficePdf` (LibreOffice 24.2.7.2), the worker's own converter.

- **Variants.** Base 26 pages, with literature 28. The literature variant's contents are the
  base's 37 entries plus the five of "Literární rešerše a externí kontext"; none missing. Outside
  that chapter the two texts differ only in the variant sentence, one introduction sentence that
  points to the literature, and chapter, table and page numbers: every result line is the same.
- **DOCX against PDF.** Every word of each DOCX is in its PDF except tokens the PDF wraps across
  lines (hashes, one URL): no content lost in conversion. Maps are embedded as figures (two per
  map), with the AIA cover, lockup and draft footer kept.
- **Contents.** Page numbers on every entry in the PDF (F3).
- **Fixed from the render:** the literature table's date broke at "2025-10-"; the scope sentence
  read "3 stran", "z 1 citovaných zdrojů" (now "label: number", no agreement to get wrong); the
  front matter's "Balíček" was the bundle artifact's SHA-256 while the chapter's "Otisk" was the
  seal -- two hashes under one name, now "Pečeť balíčku" in both places and the artifact's
  SHA-256 named as such (`test_native_ai_study_…` asserts the seal printed twice); the gaps
  callout repeated one reason after every question below the table that had just given it, and
  read "Česku?; Proč" (now quoted questions sharing one statement of their reason,
  `test_questions_with_the_same_reason_share_one_statement_of_it`).
- **Seen, not changed here:** F8 below (Appendix B prints "modelováno" on a fictional run), the
  appendix's internal evidence keys (`sekce_2_obj_ovesny_napoj.effective_n`), and short chapters
  alone on a page (D5). The module prose in this render is the test's scripted model, not AIA's
  wording, so it says nothing about the Czech of real analyses.

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
  recorded.** `report_method.py:89-106 @ 357d779` printed "jsou s během uložené" whatever
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
  `contextual_report.py:248 @ 357d779` printed `gap.need` without `text_withheld`.
- **F8 (open, OI-9 / complete-study-report F1). Fictional rows print "modelováno".** Confirmed
  in the chunk 4 render: Appendix B of a `SYNTHETIC_AI_FICTIONAL` run, whose own method chapter
  says "Odpovídali smyšlení respondenti", prints "modelováno" / "Modelováno" in Základ, Síla
  evidence and Upozornění on every row; the words are `domain/report/copy.py:78, 93, 101 @
  357d779`. Reproduction: the chunk 4 render above. Not changed here; it belongs to
  complete-study-report F1.
- **F9 (confirmed, fixed in chunk 3). A run that resumed by itself finished unseen.** Claim: the
  Progress and Výsledky pages stop reading a run in phase WAITING, though a run waiting on a
  provider's quota or capacity resumes without anyone acting (`domain/workflow.py:152 @
  357d779`). A run parked for the AI runtime (`WAITING_PROVIDER`, `ai_runtime_unavailable`) does
  not: `resume_due` never resumes it (`domain/workflow.py:797 @ 357d779`) and only a person's retry
  reopens it, so the page does not read it (review 2, F33). Anchor:
  `apps/web/src/lib/research-execution.ts:70-72 @ 357d779` (`shouldPoll`: QUEUED or RUNNING
  only), its test asserting "a parked run does not move by itself". Reproduction:
  `research-execution.test.ts` "keeps reading only while something can change on its own" (fails
  on 357d779's `shouldPoll` for a `WAITING_PROVIDER` run with `needs_attention: false`).
  Consequence: the run completes and the page still says it waits; results and the report card
  appear only after a reload. Smallest fix: read a WAITING run whose `needs_attention` is false,
  every 10 s (`pollMs`). Test: the same.

### Found by the branch review (2026-10-16), all fixed on this branch

An adversarial review of the branch, six lenses with a skeptic per finding. Its verifiers and four
lenses stopped at a session limit, so every finding below was checked against the code here and
each fix carries a test that fails without it.

- **F10. An open question beside one the run will not answer passed the gate.**
  `domain/answerability.py:166 @ 56a5fe4` judged by the trace's verdict, the best over every
  measure, so an open question (AT_RISK, never cited) lifted one the run refuses to answer
  (`fidelity_refused`, UNANSWERABLE): the run started unacknowledged and the report claimed a
  citable measure. (A conditional question cannot show it: readiness fails
  `conditional_questions` first, `research_design.py:868-875 @ 56a5fe4`.) Now only measures the run
  answers and the analysis cites decide. Test:
  `test_an_open_question_beside_one_the_run_will_not_answer_is_still_a_gap`.
- **F11. The same ranking hid support left to fieldwork.** `:169 @ 56a5fe4`: pending read the
  trace's verdict, so an open question's AT_RISK recorded an unknown measure as at risk. Test:
  `test_support_left_to_fieldwork_is_pending_even_beside_an_open_question`.
- **F12. An acknowledgement given for a revision that already had a run was kept nowhere.**
  `ExecutionSteps.tsx:691 @ 56a5fe4` moved on to Progress whatever the start returned; a start
  returns the revision's existing run. The page now checks the run holds the acknowledgement,
  and says so when it does not. Test: "says nothing new started when the revision already had a
  run".
- **F13. The setting's comment said the gate is on for develop** (`config.py:95 @ 56a5fe4`); it
  ships off everywhere until D1.
- **F14. A delivered study could not get the report with a review in any format.**
  `report_variants.py:156 @ 1e696ac` found a draft only through its PDF job, and a closed study
  starts none (`workflow_repository.py:509 @ e57c3b8`, `require_open_study`). Drafts are found as
  themselves; on a closed study the PDF says `study_closed`. Tests:
  `test_a_closed_study_finds_its_draft_and_says_why_its_pdf_waits`,
  `test_a_closed_study_asks_for_no_pdf_and_says_why`.
- **F15. A corrupt or missing PDF could never be rendered again.** `research.py:869 @ 1e696ac`
  started a new job only after a failed one; a corrupt PDF's job had succeeded. Asking after an
  INVALID PDF starts a new job, and the reason says `pdf_corrupt` apart from
  `pdf_not_this_report`. Test: `test_a_pdf_whose_bytes_went_bad_is_rendered_again_when_a_person_asks`.
- **F16. Asking for a PDF again recomposed the whole report**, which a later deploy can refuse
  (`CompleteReport.tsx:209 @ 1e696ac`). `POST …/report/context/pdf` asks for the stored draft.
  Test: `test_asking_again_renders_the_prepared_draft_once_and_never_composes`.
- **F17. The run's own report could never get a PDF its step did not make**
  (`routers/research.py:1681 @ 1e696ac` read only the step's output). `POST …/report/pdf`
  renders its stored DOCX; the status and the download fall back to that rendering. Test:
  `test_the_runs_own_report_gets_its_pdf_when_a_person_asks`.
- **F18. The report with a review waited on the run's own report**
  (`CompleteReport.tsx:311 @ 1e696ac`: `disabled={!report …}`), a regression from 357d779, where
  Interpretation Research offered it whenever the analysis was complete. Test: "prepares the
  report with a review although the run's own report failed".

Every PDF's state now says whether asking starts a rendering (`askable`), and the card offers
"Vytvořit PDF znovu" exactly then, for the run's own report and a variant alike.

### Found by the second review (2026-10-16, on 78baf5c), all fixed on this branch

The same six lenses over the branch after F10-F18; each fix carries a test that fails without it.

- **F19. The report answered every gap research question as if measured.** The answers chapter
  (`application/report.py:328 @ 78baf5c`) printed each answer under its question, and the gap was
  said only in "Respondenti a výpočet", chapters later. Each answer to a recorded gap, and the
  introduction's list, now say so where they are read (`research_question_gaps`). Test:
  `test_an_answer_to_a_research_question_the_run_could_not_answer_says_so_where_it_is_read`.
- **F20. The client report's method chapter pointed to answers and an analysis it does not
  contain** (`report_method.py:127-128 @ 78baf5c`). Test:
  `test_the_client_report_points_to_no_analysis_or_answers_it_does_not_contain`.
- **F21. The method table printed the trace's verdict, not the decision's.** A pending question
  read "at risk" beside text saying fieldwork decides it, and a question measured only by open
  items read "could answer with risk". The note records each question's decided verdict, and a
  question with no citable measure is UNANSWERABLE (`domain/answerability.py:190 @ 78baf5c`).
  Tests: `test_every_research_question_records_the_verdict_decided_for_it`,
  `test_a_pending_question_beside_an_open_one_reads_as_left_to_fieldwork`,
  `test_a_question_only_an_open_question_measures_reads_as_unanswerable`.
- **F22. The Run screen contradicted itself:** coverage PASS and a trace "S rizikem" beside a gap
  "Běh na ni neodpoví" (`research_trace.py:353 @ 78baf5c`). Readiness and the trace carry the
  decision (`with_answerability`, `decided_trace`). Test:
  `test_readiness_shows_one_verdict_and_never_passes_beside_a_gap`.
- **F23. An acknowledgement's digest was not bound to the design revision**
  (`answerability.py:208 @ 78baf5c`). Test:
  `test_an_acknowledgement_read_for_one_revision_never_covers_another`.
- **F24. A ranking whose tracked set the run cannot answer was given a false reason.** New
  `comparison_set_unanswerable`. Test: `test_a_ranking_whose_set_the_run_will_not_answer_says_so`.
- **F25. The method chapter's words:** a singular pronoun for several questions, pending
  questions unquoted and dropped beside gaps, "no research question" said twice, "Měřeno: nic" for
  an unlinked design, unmatched dimensions named as applied, a misplaced clitic ("neuplatnily
  se", `report_method.py:252-256 @ 78baf5c`), and an unreadable record called older than the
  check. Tests: the `test_report_method.py` cases added with this fix.
- **F26. A report-with-review draft of an older contract was served as ready for ever**
  (`report_variants.py:205 @ 78baf5c`), so the page never prepared it again. Only drafts of the
  current contract are the variant (`prepared_drafts`). Test:
  `test_a_draft_of_an_older_composition_contract_is_prepared_again_never_served`.
- **F27. Prepare asked for one draft's PDF and served another** when the composed sources matched
  an older draft (`routers/research.py:1988 @ 78baf5c`). The draft just composed is stored again
  as the newest. Test: the interpretation journey in `test_analysis_executor.py`.
- **F28. Past 100 jobs, asking for a PDF again returned the failed job**
  (`research.py:877 @ 78baf5c`, a capped count). The round is the newest job's. Test:
  `test_asking_again_after_a_hundred_failed_jobs_still_starts_a_new_one`.
- **F29. A corrupt or missing PDF of the run's own report read as another report's rendering**
  (`routers/research.py:1749 @ 78baf5c`). Test:
  `test_a_step_pdf_gone_bad_or_missing_is_said_as_what_it_is`.
- **F30. A start that found the revision's run left the page on "Spouštím…"**
  (`ExecutionSteps.tsx:708 @ 78baf5c`), and "found" was read from the acknowledgement's text, not
  the run's `created`. Tests: "says nothing new started when the revision already had a run",
  "follows a run the start created, whatever it recorded".
- **F31. A start refused for its research questions showed the server's English message**
  (`ExecutionSteps.tsx:697 @ 78baf5c`). Test: "says a start refused for its research questions in
  Czech, beside the gaps read again".
- **F32. A refused retry's gate stayed for whatever run was shown next**
  (`ExecutionSteps.tsx:1112 @ 78baf5c`). Test: "keeps a refused retry's gaps only while their run
  can still be retried".
- **F33. A run parked for the AI runtime was read every 10 s for ever**
  (`research-execution.ts:84 @ 78baf5c`). Test: "keeps reading only while something can change on
  its own".
- **F34. The gate called a design runnable that readiness refused, and every confirmation said
  "běh neodpoví"** (`cs.ts:2480, 2499 @ 78baf5c`). Test: "calls the gate runnable only where
  readiness lets the design run".
- **F35. The card under-stated and over-promised:** a prepared variant's parts read "čeká na
  přípravu" after a failed report step (`CompleteReport.tsx:49 @ 78baf5c`), a PDF was promised on a
  closed study or with the converter off (`:244`, `InterpretationResearch.tsx:169`), and the panel
  below kept a stale PDF line (`ExecutionSteps.tsx:1510`). Test: "claims the run-derived parts of a
  prepared variant whatever the run's own report step did".
- **F36. The literature chapter's words:** "jednom zdroji" over several sources of one publisher,
  a page's age blamed on its domain, withheld gaps and sources merged into one, a singular
  sentence before several titles, and the source table not called a proposal
  (`contextual_report.py:104, 297, 370, 401 @ 78baf5c`). Tests: `test_contextual_report.py`.
- **F37. ADR 0025 decision 4 said the report names who acknowledged**; it prints why, and the
  ledger holds who. Corrected in the ADR.

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
  POST …/report/context/pdf (asks for the prepared draft's PDF again, composing nothing),
  …/report/context/pdf/download; POST …/report/pdf (the run's own report's PDF, when its step
  made none or one failed); every report PDF state says askable".
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
  `X-AIA-Artifact-Id` (requestStored) in both formats; `research-execution.ts` `shouldPoll` /
  `pollMs`: a wait that clears by itself is read every 10 s.
- Contracts: `aia-internal-report-8`, `aia-contextual-report-4`, `aia-client-report-2`,
  `aia-answerability-1`; workflow type `report_pdf`; ledger subject `answerability`.
