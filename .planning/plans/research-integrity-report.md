---
status: in-progress
chunks:
  - "[x] 1. Runnable is not answerable: each start decides whether the run can answer the research questions it states; a run with gaps starts only on a person's recorded acknowledgement of exactly those gaps (AIA_RESEARCH_ANSWERABILITY_GATE, off by default), and the report prints the frozen record"
  - "[x] 2. The literature chapter keeps credibility and relevance apart: every accepted claim beside its verbatim passage and the topic it was searched for, every source with what its domain says (the source table labelled a proposal not yet approved), a review resting on one publisher said so, a sparse review said once"
  - "[x] 3. One report variant, the same draft in DOCX and PDF: the researcher chooses the run's own report or the report with one completed review; the worker renders the stored draft (report_pdf); both files say which variant they are and what they hold"
  - "[x] 4. Local render and inspection, USD 0: both variants of a fictional run composed, DOCX and PDF compared chapter by chapter, citations, maps, limitations, repeated prose, table of contents and layout checked by eye"
  - "[ ] 5. Develop acceptance on the existing fictional Fio run, USD 0 (owner's call: needs the deploy): recompose the literature variant at the current contract, render its PDF in the worker image, compare with the DOCX"
  - "[ ] 6. The lineage matrix from frozen records only: research question | items by wording | start verdict | the research_questions module's answer | literature L# or none | chapter"
  - "[ ] 7. Statistical reading notes: the interval method and the fictional-donor caveat, Czech pair-status words with their n basis, the person-scaling null, Stress-1 beside each figure, the multi-select note"
  - "[ ] 8. Association questions and the analysis handoff: Comparison.ASSOCIATE (aia-answerability-2), hypotheses and item links in the analysis payload, one statement of what analysis did not receive"
  - "[x] 9. Deep Research evaluation findings recorded with all six parts (topical relevance, student theses as academic), then the owner's call on ADR 0021 decision 7 (the call: D4, 2026-10-17; the rules are chunks 10 and 11)"
  - "[x] 10. D4, topic: merge quarantines a grounded finding whose quote and source title name a sibling concept and not the topic's, an object topic's finding that does not name its object by its distinguishing words, and a research question's finding that shares fewer than two of its words (aia-dr-topicality-1 in aia-merge-3); a review stored under older rules is labelled in the report, never re-scored"
  - "[x] 11. D4, document types: merge quarantines a student thesis by declared host, path and title rules (aia-document-types-1), Client Knowledge exempt; the report labels one an older review accepted"
  - "[x] 12. D5, layout: the cover alone on page 1, the contents on a page of its own, chapters and appendices flow; a section only where orientation changes; headings and captions kept with what follows and never split; one contract bump for every report"
  - "[x] 13. D2, approval in the file: a report version states its status only in its footers; an approved version downloads stamped SCHVÁLENO with its date and version, DOCX and PDF alike; approving freezes the version and asks for its approved PDF"
  - "[x] 14. D1, the Run screen: each gap links to where it is fixed; an explicit Pokračovat s omezeními recorded as today; the gate on for develop, off in tests and the workbench; ADR 0025 Accepted"
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

## Chunks 10-14 — the owner's answers in code (design, 2026-10-18)

Mapped by five code readers and checked by two skeptics; anchors @ `c708721` (the code is byte-identical
to `53e2752`). One deploy carries all five: the merge-rule and report-contract bumps land once, so
in-flight Deep Research runs fail `composition_changed` once and prepared drafts read as earlier
once.

### Chunk 10 — does the finding support its topic (D4)

Today no gate reads the subject. Grounding (`grounding.py:264-332`), the source score
(`merge.py:231-246`) and the verifier (`agents.py:567-570`, which sees claim, quote and excerpt only,
`review.py:262-269`) all pass a grounded quote from a credible host whatever it is about.

- **Where:** a pure `domain/deep_research/topicality.py`, applied inside `merge_evidence` after the
  source score and before dedupe (`merge.py:248-250`). No model is called, and both verify modes
  start from `merge.candidates`, so an off-topic finding costs no verifier call.
- **Rules (`aia-dr-topicality-1`), first deciding wins; terms from `filters.relevance_terms`:**
  - R1 *object named* (OBJECT, CROSS): the quote or source title names the object by its
    distinguishing phrase, contiguous: the label's terms in order from the first to the last that
    no other tracked object's label shares; the whole label when every term is shared or the object
    is tracked alone. One word of a longer name never names it (F50).
  - R4 *concept swap*: the quote or source title names a sibling concept of a declared family and
    not the topic's own. Families: a small table seeded with retail-banking products (běžný účet,
    spořicí účet, hypotéka, úvěr, kreditní karta, pojištění, investice, penzijní spoření, stavební
    spoření), each entry with its own test, plus the run's tracked objects as a family. A family
    may declare one concept a kind of another: a mortgage is a loan, so a loan topic keeps a
    mortgage source, never the other way round (F53).
  - R3 *topic words* (QUESTION, CROSS): claim, quote and source title together share at least two
    of the topic's terms (all of them when it has fewer), after the client's names (client name and
    slug; a study's name stays topic words), question words, an interpretation subject's own framing
    (matched as its template, the slot text kept: F51) and digits are taken out. One word was the
    first design; measured, it kept 29 of 149 irrelevant corpus pairs (F55).
  - The word lists, framings, the `-ov` fold and R3's threshold are pinned with the version (F54).
  - No terms left to judge by: `topic_undetermined`, quarantined. Unknown is never good.
  - R1 and R4 read only code-held text (quote, source title): the investigator's own claim never
    decides a rule against it. A study-title rule was considered and dropped: client terms carry
    the study's name, which empties it, and it rejects object findings that do not repeat the title.
- **Result:** quarantine `off_topic` / `topic_undetermined`, the evidence kept, the detail in Czech
  words as written (never stems). No new field on candidates or accepted evidence: the sealed
  bundle's bytes do not move, and `bundle.versions["merge"]` says the check ran.
- **Versions:** `MERGE_RULES_VERSION = aia-merge-3/{WORKS_VERSION}/{TOPICALITY_VERSION}/
  {DOCUMENT_RULES_VERSION}`. The merge step checks the full composition (as verify does,
  `review.py:221`), not only the source table (`review.py:101-102`). HARNESS_VERSION, GROUNDING_VERSION
  and the verification keys do not move: reused tracks are judged again by the run-scoped merge.
- **Older reviews:** a start on an unchanged target returns the completed run
  (`application/deep_research.py:618-622, 699`), so an existing review is never judged again by the
  engine. The report labels, never removes: for a bundle whose merge version predates the rules, each
  accepted finding today's rules would quarantine is marked so, at USD 0. The Fio review is that case
  (D3: no paid re-run).
- **Report:** the relevance paragraph branches on the bundle's merge version by prefix
  (`aia-dr-topicality-`), so a later version does not read as "nobody checked".
- **Reproduction:** a fictional F1 test: a current-account trust topic, a grounded mortgage-thesis
  quote on a credible academic host, sharing bank, trust and client words; R4 rejects it on its title.
  The real Fio items stay a hypothesis until read (no network path to develop).

### Chunk 11 — document types (D4)

`vse.cz` is ACADEMIC_INSTITUTION for any page (`sources.py:350`); `is.vse.cz/zp/…`, `is.muni.cz/th/…`
and `dspace.cuni.cz/…` score 0.70 undated, accepted, T2 (measured, read-only
`score_web_source(..., table=SOURCE_TABLE_V1)`).

- **A merge rule, on the retraction precedent** (`merge.py:212-230`): a pure
  `domain/deep_research/document_types.py` (`aia-document-types-1`): `STUDENT_THESIS` or
  `UNDETERMINED`, from declared whole-host thesis registers, path prefixes on declared university
  hosts (never `/th/` on any host), whole path segments (`zaverecne-prace`, …) and whole title
  segments (`bakalářská práce`, `diplomová práce`, `disertační práce`, …). A WEB_PAGE finding typed
  STUDENT_THESIS is quarantined `student_thesis` with its signal and rules version; Client Knowledge
  is never typed, and neither is a page of an encyclopedia (`wikipedia.org`), whose article on a
  genre bears its name (F52).
- **Not a new source table:** V1's pinned hash, the ADR 0022 catalogue and every existing pin stay
  as they are; the approved table is literally the same table, and a thesis on it is refused as a
  retracted article on an approved host is.
- **Doctoral dissertations count as theses** in this version, a choice the owner can revisit.
- **Coverage, said plainly:** a thesis on a host or path no rule declares, with a title that does
  not name its genre, is still accepted; the report keeps "může jít i o studentskou práci" for an
  academic host the rules leave undetermined. A DOI is not a document type (repositories mint them
  for theses), so no "scholarly" type is printed. Company pages and news versus opinion are the next
  rules, not this version.
- **Report:** a review stored before the rules has its accepted web sources typed at composition,
  shown in the source table's type cell, with one callout naming the L# labels; the rules version
  enters the composed draft's identity.

### Chunk 12 — layout (D5)

Today `Heading 1` and `AIA Appendix Heading` break the page (`styles.py:177, 180`), and the renderer
opens a section for the first appendix even when portrait (`renderer.py:96`).

- A page breaks only where the page furniture changes: after the cover, before the body (page
  numbers restart; a continuous section cannot, measured), at every orientation change. The contents
  keeps its own page (letting it flow saves no page and splits "Obsah").
- `page_break_before` off for chapters and appendices; `keep_lines` added to the paragraph spec and
  set on headings, captions, callout and finding titles; widow control pinned on every style.
- `doc-h1` gets 24 pt above (the guideline's 32 px), so a flowing chapter opens with more air than a
  section.
- Dead renderer state (`ctx.running`) removed.
- Measured in memory: internal 17 → 9 pages, client 16 → 9, final 18 → 9, documentation 11 → 7.
- **One contract bump for every report**, shared with chunks 10, 11 and 13: the reuse keys do not
  cover the renderer, so without it a recompose would return a stored page-per-chapter draft.

### Chunk 13 — approval in the file (D2)

Today no production path sets `ReportMeta.approvals` (`model.py:407`), so every stored report prints
"KONCEPT — NESCHVÁLENO" (footers, cover, document control: `layout.py:160-172, 244-268, 316-326`), and
after approval every download sends `X-AIA-Review-State: APPROVED_INTERNAL` over those bytes, under
a "draft" file name (`routers/research.py:1795-1802, 1832, 1884`).

- **A version** is one stored DOCX artifact (id + SHA-256). A draft exports its stored bytes. An
  approved version exports the same bytes with only the footers' status runs replaced: "SCHVÁLENO
  <date> · verze <id>". The renderer therefore states status only in footers.
- **One function decides the mark**: approved only with `is_approved` and its ledger row; otherwise
  draft. A version stored before this layout is served unstamped and the card says so; never a
  partial stamp.
- **PDF:** the approved PDF renders the stamped bytes under its own job key (never a prefix of a
  draft key: the lookup is a literal `startswith`, `workflow_repository.py:673-674`); a draft PDF is
  never served for an approved version.
- **Approving** freezes the version and asks for its approved PDF.
- **Not done here:** certificates, other approval workflows (D2); the client report's compose-on-
  download, which can serve a new draft after a contract change (`client_report.py:249-260`), is its
  own chunk.

### Chunk 14 — the Run screen (D1)

Today the card has one link, to the questionnaire's root, for every gap (`AnswerabilityGate.tsx:55`,
`ExecutionSteps.tsx:767`), and develop never asks (`docker-compose.yml:139-142`, default false), so
the owner's "record that choice" was not met there.

- Each gap links to where it is fixed: no research questions → Návrh; unlinked or unmeasured →
  the questionnaire's links; comparison reasons → the comparison card; a set the run will not
  answer → that set; a measure the run will not answer → that question, or Dimenze for support.
  An unknown reason keeps the questionnaire link, never hidden.
- The choice is named "Pokračovat s omezeními", the start button reads "Spustit s omezeními" once
  it is chosen, and the record is unchanged (digest, reason, ledger row).
- The gate is on for develop through its compose default, still off in code, tests and the
  workbench (§8); CI proves an SSM `false` still turns it off.
- ADR 0025 Accepted with D1's words.

### What landed, and what it measured (2026-10-18)

Three tracks in worktrees, each reviewed adversarially and its findings fixed before integration
(F50-F68 below), then a cross-cutting review of the whole branch (F69 on). All at USD 0, on
fictional data; nothing ran against develop.

- **Chunk 10.** `topicality.py` (`aia-dr-topicality-1`), the gate in `merge_evidence`
  (`merge.py:299-315 @ d8a70f5`), `merge_evidence(topics=)` with no default and only tests passing
  `None` (a `layer_check` rule), the merge step refusing any composition change
  (`review.py:105 @ d8a70f5`), `DeepResearchRuns.frozen_request`
  (`application/deep_research.py:837 @ d8a70f5`) for an older review's labels. Measured on the
  filters' labelled fictional corpus (`test_measured_topicality`): 22 of 27 relevant pairs kept,
  148 of 149 irrelevant set aside. The recorded journeys: the almond track's copy of the oat fact
  is now `off_topic`; every other count unchanged.
- **Chunk 11.** `document_types.py` (`aia-document-types-1`), quarantine before the score
  (`merge.py:267 @ d8a70f5`), the encyclopedia exemption, words in the report and on the web,
  every source class in words beside a finding (`InterpretationResearch.tsx`).
- **Chunk 12.** Pages, base sample reports (`tools/report_preview.py`): internal 17 to 9, client
  16 to 9, final 18 to 9, documentation 11 to 7 (+35 % prose: 10, 9, 10, 7). The fictional run's
  base report 27 to 20 pages, the report with literature 29 to 22. In every render, no page ends
  with a heading, caption, title or research-question lead-in (`ParagraphRole.LEAD_IN`, from the
  render: F66). Contracts once: `aia-internal-report-9`, `aia-contextual-report-5`,
  `aia-client-report-3`, `aia-sociomapping-report-4`.
- **Chunk 13.** `domain/report/review.py`, `infrastructure/report_docx/review_stamp.py`,
  `application/report_export.py`, `ArtifactRepository.approval_of`, the approved PDF under
  `report_pdf:approved:…`, approval freezing the version. Stamping a sample report: median
  143-188 ms; the draft and approved PDFs of one version have the same pages and the same text
  but the status runs. The approved copy of the fictional base report differs from its draft only
  in its footers ("SCHVÁLENO 18. 10. 2026 · verze ART-…").
- **Chunk 14.** `gapFixes`, the compiled-id port with its shared fixture
  (`apps/web/src/lib/fixtures/compiled-ids.json`, checked against Python by
  `test_compiled_ids_web_fixture.py`), the named choice, the develop compose default `:-true`.
- **Checks on the integrated head** (`d8a70f5`): mypy 414 files; layers and exposure; core 7256,
  API 518, worker 80, executors 527 (SQLite); executors 529 against a local PostgreSQL 16, the
  fan-out process tests included (F65 was found there); web 1671 tests, `tsc`, eslint.

**Limits, said plainly (not fixed here).**
- The real Fio items are not judged: no network path to develop. Under these rules the report
  labels such findings; whether the three mortgage findings fall to R4 depends on their topic text
  naming a declared concept (chunk 5 can read them, read-only, at USD 0).
- R3 misses a relevant finding that shares one word with its question: a headline, a synonym,
  another language, or a topic whose only distinguishing mark is a number beside a generic noun
  ("ukazatel 7": F65). Such a finding is set aside `off_topic` with the shared word named, never
  lost. R1 accepts an object finding on its distinguishing word alone ("Ovesné vločky" under
  "Ovesný nápoj").
- Thesis coverage: `dspace.cuni.cz`, `dspace.vutbr.cz`, `.edu` repositories and any undeclared host
  stay undetermined; the declared URL shapes were not checked against live pages (no network).
- Older bundles still reach Design Research with their thesis findings as academic
  (`quarantine.py design_input`): only the report labels them.
- A short table can still split after its first row, its notes on the next page (cross-review,
  being fixed); Word itself was not opened, only LibreOffice.
- After the deploy: check that SSM holds no `aia_research_answerability_gate=false`, or develop
  stays off. Rolling back past this release leaves reviews merged after it unreadable
  (`off_topic`, `topic_undetermined`, `student_thesis` are new closed enum values) until a
  roll-forward; no data is lost.

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
  `test_report_docx_render.py::test_the_contents_lists_the_outline_with_a_pageref_per_entry_and_no_toc_field`.
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
  not: `resume_due` never resumes it (`domain/workflow.py:797 @ 357d779`), it waits until a person
  acts, so the page does not read a run held only by one (review 2, F33; review 3, F43). Anchor:
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
  introduction's list, now say so where they are read (`research_question_gaps`): the reason once,
  at the first answer, and a one-line limitation at every later one (the fictional render had
  every module answer, and a full callout under each repeated one reason 16 times). Test:
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
- **F26. A report-with-review draft of an older contract was served as current for ever**
  (`report_variants.py:206-217 @ 78baf5c`), so the page never prepared it again. The first fix hid
  every such draft; the third review showed that lost a prepared, possibly approved, report
  whenever composing it again is refused (F40). An earlier contract's draft now stays the report,
  said to be earlier (`contract_current: false`), and the card offers to prepare it anew. Test:
  `test_a_draft_of_an_earlier_contract_stays_the_report_and_says_it_is_earlier`.
- **F27 (defensive, kept because it is six lines). Prepare could ask for one draft's PDF and
  serve another** when the composed sources matched an older draft while a newer one existed
  (`routers/research.py:1988 @ 78baf5c`). Its verifier showed no code renames a study or a client;
  since F26 compares drafts of one contract, only composed sources of one contract that change and
  change back would reach it, and no known path does. The draft just composed is stored again as
  the newest, so prepare's PDF is always the served draft's. Test: the interpretation journey in
  `test_analysis_executor.py`.
- **F38. Across origins, every internal report download was refused**: CORS exposed only
  X-Request-ID (`main.py:129 @ 78baf5c`), so the card read the draft header as null. Same-origin
  develop is unaffected. Test: `test_a_browser_on_another_origin_reads_which_draft_a_report_download_is`.
- **F39. Tests did not reach what the plan cites them for:** the prepare route's success path
  (`test_preparing_answers_the_stored_draft_and_asks_for_its_pdf_once`), F17's READY fallback and
  download (`test_the_runs_own_report_gets_its_pdf_when_a_person_asks`, extended), a contents test
  named for the TOC field it asserts is absent (renamed), and F3's and ADR 0025's anchors (a test
  file that does not exist, a working-tree anchor; both corrected).
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
  (`ExecutionSteps.tsx:695-698 @ 78baf5c`). Test: "says a start refused for its research questions in
  Czech, beside the gaps read again".
- **F32. A refused retry's gate stayed for whatever run was shown next**
  (`ExecutionSteps.tsx:1112 @ 78baf5c`). Tests: "keeps a refused retry's gaps only while their run
  can still be retried" and, for the binding to its run, `answerability.test.ts` "keeps a refused
  retry's gaps for the run they were refused for alone" (`refusalFor`; review 3, F47).
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

### Found by the third review (2026-10-17, on 82c4b25), all fixed on this branch

The same five lenses over the second review's fixes, two skeptics per finding. Their verifiers
ran while the fixes below landed, so most refutations read "already fixed at HEAD", which confirms
them; each fix carries a test that fails without it.

- **F40. Hiding an earlier contract's draft lost the report** whenever composing it again is
  refused (`contextual_report.py:573 @ 244259a`): status, both downloads and preparing all refused.
  See F26 for the fix. Test: `test_a_draft_of_an_earlier_contract_stays_the_report_and_says_it_is_earlier`;
  web: "keeps a report with a review prepared under an earlier composition, says so, and prepares
  it anew".
- **F41. Every gap was said to rest on no measure the run answered** (`report.py:360`,
  `report_method.py:303 @ 3533f67`), false for a comparison gap whose measure was answered; the
  client report said "z nich odpověď nevyplývá" for gaps only unverified, called a pending
  question's measure one the run "mohl odpovědět", spoke of one gap in the plural, and printed
  "předem nešlo ověřit" with no object. Each now says what the record holds ("Bez doložené
  odpovědi"). Tests: `test_a_comparison_gap_is_never_said_to_rest_on_no_measure`,
  `test_one_gap_is_said_in_the_singular_and_an_unverified_one_never_as_a_no`,
  `test_the_client_report_never_calls_a_pending_question_one_the_run_could_answer`.
- **F42. An unknown comparison hid that a question has no citable measure**
  (`answerability.py:212 @ 815f592`): an open-only question read UNKNOWN. Test:
  `test_an_unknown_comparison_never_hides_that_nothing_measures_it_citably`.
- **F43. A run with a step parked for the AI runtime was no longer read even while another step
  ran** (`research-execution.ts:87 @ 0a921c4`). Test: research-execution "keeps reading only while
  something can change on its own".
- **F44. The refusal and the confirmation said more than the gate** (`cs.ts:2502, 2509 @
  0a921c4`): "návrh nedokáže odpovědět", the gaps "níže" and "as the server reads them now" after a
  re-read that may have failed. The refused gaps are shown as the server sent them. Test: "shows
  the gaps the server refused even when reading readiness again fails".
- **F45. A found run that already held this acknowledgement was reported as saving it nowhere**
  (`ExecutionSteps.tsx:707 @ 0a921c4`). Test: "follows a found run that already holds this very
  acknowledgement".
- **F46. The PDF's reason was visible nowhere** once the panel's line went
  (`CompleteReport.tsx:334 @ 244259a`). Test: "says why there is no PDF as text on the card, once on
  the page"; F35's PDF promise is now asserted in the variant and Interpretation Research tests.
- **F47. Tests that could not fail:** the readiness route's wiring and the revision in the digest
  (`test_readiness_carries_the_decided_verdict_and_a_digest_of_its_own_revision`), the stored
  reports' gaps (the executor journey), the decided verdict (`test_every_research_question_records_
  the_verdict_decided_for_it`, now with verdicts that differ), F32's binding (`refusalFor`), F36's
  title, note and withheld count (`test_contextual_report.py`), and F10's test, which used a
  conditional question its entry rules out (now a fidelity-refused item).
- **F48. The source table was always called unapproved**, though a priced live review runs only
  once its pinned settings sign it off (`contextual_report.py:385 @ 57b3190`). The note reads the
  review's pin. Test: `test_the_source_table_is_called_approved_only_where_the_review_pinned_its_
  approval`; the journey checks the composed report reads its review's pin.
- **F49. Withheld items were "další" and "nedostupné", and robots.txt claimed several websites**
  (`contextual_report.py:82, 452 @ 57b3190`). Test:
  `test_three_withheld_sources_of_one_reason_are_three_in_the_plural`.

### Found by the reviews of chunks 10-14 (2026-10-18), all fixed on this branch

Each track's adversarial reviewer, then the integration. Every fix has a test that fails without
it; an anchor is where the defect was on the pushed branch, and a defect the track review caught
before integration is named by its test.

- **F50. One word of a tracked object's name named it.** "v Česku" named Česká spořitelna, so a
  question about banks swapped a Fio fact out with a false detail, and "Banky v České republice"
  passed R1 for Česká spořitelna (found by the review before integration, so the defect never reached the pushed branch). An
  object is named by its distinguishing phrase, contiguous. Tests:
  `test_a_word_of_a_longer_name_names_no_tracked_object`,
  `test_a_word_another_tracked_object_shares_names_no_object`.
- **F51. The analysis modules' names were stop words for every run**: "Kdo je cílová skupina?" kept
  no topic words (found by the review before integration, so the defect never reached the pushed branch). A framing is matched as its template, its
  slots kept. Test: `test_a_subject_loses_its_own_framings_words_and_no_other`.
- **F52. Wikipedia's article "Diplomová práce" was typed a student thesis**
  (found by the review before integration, so the defect never reached the pushed branch). Encyclopedia hosts are never typed. Test:
  `test_an_encyclopedia_article_on_the_genre_is_not_a_thesis`.
- **F53. A loan topic set aside mortgage-loan findings** (found by the review before integration, so the defect never reached the pushed branch). A family
  declares kinds; a mortgage is a loan. Test: `test_a_kind_of_the_topics_concept_is_no_swap`.
- **F54. The topicality version pinned only the concept table**, not the word lists, framings or
  fold that also decide (found by the review before integration, so the defect never reached the pushed branch). Test:
  `test_the_declared_rules_are_the_version_they_name`.
- **F55. One shared word was not a topic check.** R3 kept 29 of 149 irrelevant corpus pairs, each on
  one generic word (`topicality.py:621-628 @ d7fcf09`). Two shared words (all when fewer): 1 of 149;
  relevant kept 22 of 27 instead of 25, the three more set aside with the one word named. Test:
  `test_measured_topicality` (22, 1, 5, 148), `test_a_question_finding_shares_two_words_of_its_topic`.
- **F56. The card promised an approved PDF where approving makes none** (a closed study with a
  ready draft PDF; no converter). `approval_asks_pdf` / `approval_renders_pdf`
  (`report_variants.py:123, 134 @ d8a70f5`) decide it once. Tests:
  `test_a_draft_promises_an_approved_pdf_only_where_approving_makes_one`,
  `test_approving_promises_a_pdf_only_once_the_drafts_own_was_rendered_here`.
- **F57. The client report was approved with "Schválit pro interní použití" and then stamped
  SCHVÁLENO for the client.** Its button reads "Schválit k předání klientovi"
  (`CompleteReport.tsx:420 @ d8a70f5`). Test: "says what approving the client report does to the
  file the client receives".
- **F58. Approving while the draft's PDF job waited failed that job as SCHEMA_VIOLATION**, an error
  report merged with real integrity faults. It ends SUPERSEDED (`executors/report.py:354 @ d8a70f5`).
  Test: `test_the_approved_pdf_renders_the_stamped_version_and_refuses_a_changed_review`.
- **F59. A client report download read its DOCX twice** (`export_docx(data=)`,
  `report_export.py:93 @ d8a70f5`). Test: `test_the_approved_client_report_downloads_stamped_and_is_read_once`.
- **F60. Approving a variant and downloading an approved client report had no test.** Tests:
  `test_approving_a_prepared_variant_asks_for_its_approved_pdf_under_its_review`, and F59's.
- **F61. Card and cover words**: an older approved version in the future tense; "vytvořit znovu" for
  a PDF never made; "Revize" (the design) beside "verze ART-…". Test:
  `test_the_revision_a_report_prints_is_named_as_its_designs` and the card's vitest cases.
- **F62. The report step's PDF rendered fresh bytes, not the stored DOCX, when the step reused it**
  (`executors/report.py:114, 161-164 @ 5116784`). Test:
  `test_the_steps_pdf_renders_the_stored_docx_when_the_step_reuses_it`.
- **F63. After approval, every download sent `X-AIA-Review-State: APPROVED_INTERNAL` over bytes
  printing "KONCEPT — NESCHVÁLENO"** in every footer, on the cover and in document control, under
  a "-draft" name (`routers/research.py:1795-1802, 1832, 1884 @ 5116784`; `layout.py:160-172,
  244-268, 316-326 @ 5116784`): D2's defect. Test:
  `test_an_approved_versions_docx_says_approved_and_names_the_version`.
- **F64. A gap's measure link never reached its question**: the server slugs item ids
  (`Q_wb1` -> `q_wb1`), Dotazník draws the raw ones (found by the review before integration, so the defect never reached the pushed branch). The web
  ports `_slug`/`_unique` and walks the compiler's order; the shared fixture is checked on both
  sides. Tests: `test_the_server_compiles_the_fixture_to_the_ids_it_lists`, QuestionnaireStep's
  "opens on the place a link from the Run stage names".
- **F65. A fixture finding sharing one word was set aside, on PostgreSQL only.** "Ukazatel 7
  dosáhl…" under "Jak se vyvíjí ukazatel 7 v Česku?" shares one word once digits are out; CI's
  PostgreSQL step failed `test_fifty_tracks_across_four_processes_never_exceed_either_limit`
  (`apps/executors/tests/fan_out_world.py:63 @ d8a70f5`). The fixture's finding names its place; the
  miss itself is one of R3's stated limits.
- **F66. A research question ended a page apart from its answer** once chapters flowed
  (`application/report.py:345 @ d7fcf09`, a bold body paragraph). `ParagraphRole.LEAD_IN`, style
  "AIA Lead-in" (keep with next, never split). Test: the gaps test in `test_analysis_results.py`
  and `test_headings_captions_and_figures_keep_with_what_follows`.
- **F67. A gap's measure link chose an open question beside the one the run will not answer** (F10's
  case), and never Dimenze for support (found by the review before integration, so the defect never reached the pushed branch). Only citable measures
  are chosen. Test: "sends a measure the run will not answer to one the analysis may cite, never to
  an open question beside it (F10)".
- **F68. The card said a measurement was missing for every gap**, false for comparison gaps and an
  unlinked design (found by the review before integration, so the defect never reached the pushed branch). It says AIA cannot show the answer.

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

### The owner's answers (2026-10-17, in session, MVP approach)

Verbatim:

- **D1 Answerability.** "Clearly show missing measurements, offer a way to fix them, and allow an
  explicit 'continue with limitations.' Record that choice. No additional approval role."
- **D2 Report approval.** "Keep a simple draft/approved status tied to a specific report version.
  Export that version consistently. Defer separate certificates and additional approval
  workflows."
- **D3 Paid retry.** "Skip it until the quality fixes are ready to evaluate together."
- **D4 Literature quality.** "Prioritize this. Check whether sources actually support the
  research topic and distinguish document types. Start with a small, tested set of rules."
- **D5 Layout.** "Make a sensible editorial choice and move on. It doesn't need an owner decision.
  Remove automatic page breaks before chapters. Keep headings with the following text, avoid
  orphaned lines, and keep figures with their captions where practical. Give the branded cover
  its own page; let the report body and appendices flow without forcing each chapter onto a new
  page."

What follows from them:

- D1 settles ADR 0025 decision 3 as proposed: a recorded precondition, not a fourth gate, and no
  second person when self-approval is off. ADR 0025 is Accepted.
- D3: no analysis retry of the Fio run. Its base report keeps its earlier contract until the
  quality fixes below are evaluated together; chunk 5 needs nothing paid.
- D4 is the evaluation finding ADR 0021 decision 7 asks for (F1), and the owner's call on it: the
  engine changes, by a small set of deterministic rules, each with a test.

### The owner's answer of 2026-10-25

RIR-5 (a), the audit page, relayed by coordinator 3: go. Chunk 5 (develop acceptance on the
existing fictional Fio run, USD 0) may run on the deploy; it is not ticked until it has.

### The owner's answer of 2026-10-26

RIR-5, Nigel, 26 Oct 2026 (relayed by the PM coordinator; `prototype-build.md`): the literature check is **paid, capped by the study budget**. Chunk 5's own acceptance run stays USD 0 as written; a literature check a person starts in a study is held against that study's budget like any other paid work, never free and never above it.

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
- Contracts: `aia-internal-report-9`, `aia-contextual-report-5`, `aia-client-report-3`,
  `aia-sociomapping-report-4` (one bump for chunks 10-14), `aia-answerability-1`,
  `aia-review-stamp-1`, `aia-merge-3/…/aia-dr-topicality-1/…/aia-document-types-1`; workflow type
  `report_pdf` (an approved rendering under `report_pdf:approved:…`); ledger subject `answerability`.
  `ARCHITECTURE.md`:385, 400, 406 name older contract strings.

Chunks 10-14 (2026-10-18):

- `CLAUDE.md` § 2, domain/deep_research: `topicality.py  does a grounded finding support the topic it
  was searched for (D4, F1): R1 an object named by its distinguishing words in quote or source
  title; R4 no sibling concept of a declared family named instead (retail-banking products, a kind
  of a concept allowed; the run's tracked objects); R3 a research question's finding shares two of
  its words (all when fewer) once the client's names, question words, its framing and digits are
  out; off_topic / topic_undetermined (aia-dr-topicality-1); judged_topic(merge version);
  declared_rules pinned with the version`; `document_types.py  a student thesis by declared
  registers, archive paths on declared university hosts, whole path or title segments, else
  undetermined (aia-document-types-1; encyclopedias and Client Knowledge never typed; a DOI is no
  type); document_rules_of`; merge.py's acceptance order: retracted, student thesis, score, topic
  gate, dedupe, confirmation, verifier (aia-merge-3); `merge_evidence(topics=)` has no default and
  only tests pass None (layer_check); the merge step refuses any composition change.
- `CLAUDE.md` § 2, application: `deep_research.py frozen_request`; `contextual_report.py`: the
  relevance paragraph by the bundle's merge version; an older review labelled by today's rules at
  composition (never removed, re-scored or recounted), the rules' versions in the draft's identity;
  `report_export.py  review_mark (approved only with is_approved and its ledger row), export_docx
  (a draft its stored bytes, an approved version stamped, an older one as stored)`;
  `report_approval.py approve_report freezes the version and asks for its approved PDF where one
  will be made`; `report_variants.py approval_asks_pdf / approval_renders_pdf, RENDERABLE_REPORTS`.
- `CLAUDE.md` § 2, domain/report: `review.py  ReviewState, ReviewMark, approved_words (SCHVÁLENO
  <date> · verze <id>, the Prague day), REVIEW_STAMP_CONTRACT`; `model.py ParagraphRole.LEAD_IN`
  (a line that titles what follows); `ReportMeta.approvals` is gone.
- `CLAUDE.md` § 2, report_docx: `review_stamp.py  stamp_review: an approved version's footers'
  status runs replaced, every other part byte for byte as stored; NotStampable`; `layout.py` (a
  page breaks only where the furniture changes; status only in footers, one AIA Status run each;
  the contents as PAGEREF entries on a page of its own); `styles.py` (only the contents' heading
  breaks a page; headings, captions, titles and lead-ins keep with what follows and never split;
  widow control on every style).
- `CLAUDE.md` § 2, executors report.py: `ReportPdfExecutor re-derives the review; a draft job whose
  version was approved ends SUPERSEDED`; the step's PDF renders the stored DOCX when it reuses it.
- `CLAUDE.md` § 2, routers/research and API main.py: report downloads named
  `AIA-<study>-<run>-<variant>-<version>-<koncept|schvaleno>`, `X-AIA-Artifact-Sha256` and
  `Content-Disposition` exposed by CORS; statuses carry `approved_on`, `stamped`,
  `approval_renders_pdf`.
- `CLAUDE.md` § 2, web: `lib/answerability.ts gapFixes, compiledPlaces / questionnairePlace (ports
  research_design _slug/_unique; lib/fixtures/compiled-ids.json is checked by
  test_compiled_ids_web_fixture.py)`; Dotazník and Návrh read `#qedit_<id>`, `#qset_<id>`,
  `#q-comparisons`, `#plan-understanding`; the named choice "Pokračovat s omezeními";
  `lib/report-variant.ts reviewLine, pdfStatesReview`; InterpretationResearch's source class in
  words (`research.deep.sourceClass`).
- `CLAUDE.md` § A research run and `deploy/develop/README.md`: `AIA_RESEARCH_ANSWERABILITY_GATE` is on
  for develop by its compose default (D1); SSM `aia_research_answerability_gate=false` turns it off.
- `docs/architecture/adr/README.md`: ADR 0025 Accepted.
- `AGENTS.md` § DOCX: headless LibreOffice honours style-level `pageBreakBefore`, `keepNext`,
  `keepLines` and `widowControl`; a continuous section start cannot change orientation, restart or
  reformat page numbers, or change the header (wrong: `w:type continuous` to let the body flow;
  right: a section only where size, numbering or header change); space before a paragraph applies
  at the top of a page too.
- `.planning/open-items.md`: the limits listed under "What landed".
