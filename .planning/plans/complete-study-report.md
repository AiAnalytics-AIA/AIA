---
status: in-progress
chunks:
  - "[x] B1a. Per-question tables in the internal report: every question's numbers (option shares, scale mean, top-2-box) as NumberCells over claims admitted question by question through admit_numeric_claims; a question the gate refuses says why instead of blocking the report; suppressed cells removed and counted by the table"
  - "[x] B1b. The design in the report: the Design Revision's goal, research questions and comparable sets as a chapter, and the questionnaire (blocks, questions, options, scales) as an appendix -- words from the run's own specification, no numbers"
  - "[x] B1c. Method and respondents: who answered (fictional roster / AI respondents from population <version>), the persona source, the population binding the run recorded, the sample, the respondent system's identity -- from the run's records, never stated where unknown"
  - "[x] B1d. The report with Deep Research stored as an artifact (research_internal_docx with the bundle pinned) and a review_state, instead of rendered on every download"
  - "[ ] B2. Approve a report: a researcher-only route over ArtifactRepository.approve, recorded in the approval ledger, and the button on Výsledky"
  - "[ ] B3. PDF beside the DOCX: headless LibreOffice in the worker image, one artifact per report; time and size measured"
  - "[ ] B4. Sociomap methodology register (OI-17) replacing D6_OPEN: status per (methodology version, spec fingerprint); the owner's 2026-10-13 decision its first row (aia-sociomap-3); compose_map_sections takes the register's status"
  - "[ ] B5. Client report composer: client_report recipe over a CLIENT_FACING ledger admitting MODELLED_AI_PANEL under the owner's 2026-10-13 decision, every modelled number labelled"
  - "[ ] B6. Audience filters in a run: AIA_AI_POPULATION_PERSONAS_ENABLED on develop (operator call) once audience-catalogue-cpu chunk 4 has landed; dimensions stay with sociomap-formula-corrections I0/I1"
---
# The complete study report

The backend half of the research lane redesign
([research-lane-redesign.md](research-lane-redesign.md), PR #382: the interface).
The owner (2026-10-13): at the end of a study a person downloads the full, AIA-branded
report -- Deep Research, AI respondents, Sociomaps, "the whole shabang".

What exists (anchors @ 04c8830):

- `compose_internal_report` (application/report.py:117) is the only production composer:
  intro, the eight analysis modules' prose, the methodology section, Deep Research
  context sections, map sections, an evidence appendix and an audit. It prints no
  per-question numbers: the modules cite the rows they chose.
- The run's evidence table (domain/analysis/native.py:443 `native_evidence`) already
  holds one row per option share, scale mean and top-2-box of every question and
  tracked object, refs `<question>.pct.<n>` / `.mean` / `.top2box`, with its suppressed
  refs kept by name.
- A report prints a number only as a ref into its EvidenceLedger, built only from
  AdmittedClaims (domain/report/evidence.py:1-24); `admit_numeric_claims`
  (domain/evidence/admission.py:306) is the only minter and admits all or none.

## Rules this plan keeps

- No number enters a report except through `admit_numeric_claims` and the ledger.
- A claim set is admitted per question, so one refused question does not hide the
  rest; the refusal is printed, never silently dropped.
- Unknown stays unknown: a run that did not record a fact (population, persona
  source) says so; nothing is stated from a default.
- Reports stay deterministic bytes (DocxRenderer) and pass `lint_docx`.

## Owner decisions

Recorded in research-lane-redesign.md (2026-10-13): the current Sociomap methodology
may appear in the report (B4); modelled data is admitted to the client report, each
number labelled (B5); stages before backend (done in PR #382).

## Progress notes

- B1a: `application/report_tables.py` `compose_question_tables(run, items, source=)` makes
  the chapter "Výsledky jednotlivých otázek" (after the methodology): one table per
  question and tracked object, estimates first then the counts, every cell a NumberCell
  over a claim admitted per question for INTERNAL. `compose_internal_report` takes it as
  `question_tables=` and refuses a claim outside the run's evidence. The report step
  reads the run's own specification (the one the map depends on) for the questions'
  order and words; contract `aia-internal-report-5`.
  Tests: `test_every_question_prints_its_numbers_through_admission_after_the_methodology`,
  `test_a_question_the_gate_refuses_is_named_and_the_others_keep_their_tables`
  (test_analysis_results.py); the stored DOCX carries the chapter after the methodology
  (test_analysis_executor.py, the end-to-end report test).

- B1b: `application/report_design.py` `compose_design_sections(spec, research_questions)`:
  the chapter "Návrh studie" right after the introduction (research questions, each
  comparable set with its objects, question and scale, the sample the design asked for,
  the audience strategy and filters as stated) and the appendix "Dotazník" before the
  evidence appendix (every question with its type, options or scale; each set). From
  the run's own specification only; a design that states no sample or audience says
  so. Whether a run applied the filters belongs to the method chapter (B1c). Contract
  `aia-internal-report-6`. Tests: test_report_design.py (3), and
  `test_the_report_states_the_design_it_ran_and_appends_its_questionnaire`; the stored
  DOCX orders design < methodology and the questionnaire after the question tables.

- B1c: `application/report_method.py` `compose_method_section(meta, origin)`: the chapter
  "Respondenti a výpočet" after the methodology and before the question tables -- who
  answered by the dataset's origin kind (fictional / modelled from the population /
  unknown), the population the run recorded and whether fieldwork read it, whether the
  audience filters were applied (a panel run's are; dimensions are not yet), and a table
  of the methods the run pinned (`run_methods`, an unreadable pin says so). What the run
  did not record is said to be unrecorded. Contract `aia-internal-report-7`. Tests:
  test_report_method.py (4), `test_who_answered_comes_after_the_methodology_and_before_the_numbers`;
  the stored DOCX orders methodology < respondents < question tables.
- B1d (first part): `application/report_chapters.py` `report_chapters(repo, run, analysis,
  map_artifact_id=, run_id=)` is the one place both reports take their run-derived chapters
  from -- the map verified as this run's (`research_sociomap`, VALID, derived from the
  analysed dataset and specification), the question tables, the design and the method.
  The worker's report step and `contextual_report` both call it; the report with
  literature now carries the design, method, question and questionnaire sections too
  (it had only the maps). Contract `aia-contextual-report-3`. Test: the interpretation
  journey in test_analysis_executor.py asserts the four section ids on the combined report.
- B1d (second part): `contextual_report.stored_contextual_report` composes the report with
  literature from its verified sources, fingerprints them (contract, both run ids, the eight
  analysis artifacts' SHA-256, the map's, the bundle's, the printed names and date) and
  renders and stores it only when no valid artifact has that fingerprint
  (`research_internal_docx_with_research`, stage REPORT, on the Study's design project,
  `review_state` DRAFT_UNAPPROVED, depending on the analysis and map artifacts). The
  download route serves the stored bytes and names the artifact
  (`X-AIA-Artifact-Id`, `X-AIA-Review-State`), so B2 can approve the document a person
  read. Test: the interpretation journey downloads twice and gets the same artifact.

## Findings

- **F1 (hypothesis until the governance call is made). Fictional data prints the grade
  "modelováno".** Every native evidence row has basis MODELED
  (domain/analysis/native.py, `_Rows.add`, `basis=ClaimBasis.MODELED` @ 04c8830), and
  `grade_of` prints MODELED as "modelled" always (domain/report/evidence.py:59 @
  04c8830), so a SYNTHETIC_FIXTURE run's table captions read "(n = 56; modelováno)".
  Reproduction: render `test_every_question_prints_its_numbers_through_admission_after_the_methodology`'s
  DOCX. Consequence: on an internal draft of fictional data the caption says modelled,
  while the report's frame callout says synthetic; the frame is right. Smallest fix: a
  print grade for a non-evidence origin (SIMULATED), chosen by `origin_kind` beside the
  basis. Owner of the call: analysis-governance (OI-9). Test that would catch it: a
  caption assertion on a SYNTHETIC_FIXTURE table.

## Doc follow-up

- CLAUDE.md § 2 map, application/: `report_tables.py  compose_question_tables: every
  question's numbers as tables, each cell an admitted claim (per question; a refused
  question is named)`; report.py's line gains "per-question tables after the
  methodology".
- CLAUDE.md § 2 map, application/: `report_design.py  compose_design_sections: the design
  the run executed (questions, sets, sample, audience as stated) and its questionnaire as
  an appendix, from the run's specification`.
- CLAUDE.md § 2 map, application/: `report_method.py  compose_method_section: who answered
  (by origin kind), the population recorded and read, filters applied or not, the methods
  pinned; from the run's record, unrecorded said so`.
- CLAUDE.md § 2 map, application/: `report_chapters.py  report_chapters: the map, question,
  design and method chapters from the run's verified sources; the worker's report and the
  report with literature both take them from here`; contextual_report.py's line gains "the
  same chapters as the internal report (report_chapters)".
- CLAUDE.md § 2 map, contextual_report.py: "stored once per exact source set as
  research_internal_docx_with_research (DRAFT_UNAPPROVED; stored_contextual_report); the
  download serves that artifact and names it in X-AIA-Artifact-Id / X-AIA-Review-State".
- open-items.md: F1 to be numbered there.
