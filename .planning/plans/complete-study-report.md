---
status: in-progress
chunks:
  - "[x] B1a. Per-question tables in the internal report: every question's numbers (option shares, scale mean, top-2-box) as NumberCells over claims admitted question by question through admit_numeric_claims; a question the gate refuses says why instead of blocking the report; suppressed cells removed and counted by the table"
  - "[x] B1b. The design in the report: the Design Revision's goal, research questions and comparable sets as a chapter, and the questionnaire (blocks, questions, options, scales) as an appendix -- words from the run's own specification, no numbers"
  - "[x] B1c. Method and respondents: who answered (fictional roster / AI respondents from population <version>), the persona source, the population binding the run recorded, the sample, the respondent system's identity -- from the run's records, never stated where unknown"
  - "[x] B1d. The report with Deep Research stored as an artifact (research_internal_docx with the bundle pinned) and a review_state, instead of rendered on every download"
  - "[x] B2. Approve a report: a researcher-only route over ArtifactRepository.approve, recorded in the approval ledger, and the button on Výsledky"
  - "[x] B3. PDF beside the DOCX: headless LibreOffice in the worker image, one artifact per report; time and size measured"
  - "[x] B4. Sociomap methodology register (OI-17) replacing D6_OPEN: status per (methodology version, spec fingerprint); the owner's 2026-10-13 decision its first row (aia-sociomap-3); compose_map_sections takes the register's status"
  - "[x] B5a. A panel run records the CORE_JOINT_STATUS certificate of the population its respondents were drawn from (text, SHA-256, the panel SHA-256 the loader verified), and its evidence is judged under it, re-hashed on read; every other run stays uncertified"
  - "[x] B5b. The owner's recorded lift of -2's INTERNAL_ONLY for the client report only (2026-10-13): support, intervals, the certificate and the no-predictive-validity rule still apply; client-facing analysis modules stay blocked until the holdout"
  - "[x] B5c. Client report composer: the client recipe over a CLIENT_FACING ledger of admitted modelled numbers, every one labelled 'modelováno: AI respondenti z populace', approved maps only; a route, a stored artifact and the button on Výsledky"
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
- B2: `application/report_approval.py` `approve_report(session, scope, store, run_id=,
  artifact_id=, note=)`: a stored report of the run (the internal report or the report with
  literature, VALID, its metadata naming the run) approved through
  `ArtifactRepository.approve` -- SIGN_OFF_DELIVERABLE, the scope's self-approval policy,
  a row in approval_decisions; an approved report is returned as it is, never a second row.
  `POST …/research/runs/{run_id}/report/approve` {artifact_id, note}: 404 for a run or
  report the study cannot see, 409 report_not_approvable, 403 separation_of_duties. The
  internal report's card on Výsledky gains "Schválit pro interní použití" (not in a
  read-only frame). Approval is internal; it makes nothing client-facing. Tests:
  `test_a_person_approves_a_runs_stored_report_once_and_only_that`, ExecutionSteps
  "approves the stored draft for internal use…". The report with literature has no
  button yet: the web reads its artifact id from `X-AIA-Artifact-Id` once #382's
  CompleteReport lands (it is not on develop).
- B3: `infrastructure/report_pdf.py` `LibreOfficePdf` (headless soffice, a private profile
  per conversion, timeout, `%PDF` checked) behind `AIA_REPORT_PDF_ENABLED` (off when unset;
  on without soffice stops the worker). The report step renders the DOCX it stored and
  stores `research_internal_pdf` beside it (`rendering_of` the DOCX, depending on it,
  fingerprinted by the DOCX's SHA-256 and the converter's version); a conversion that fails
  is said in the step's output (`pdf: {state: FAILED, reason: pdf_conversion_failed}`)
  and fails nothing. The report status carries `pdf` (READY / FAILED / INVALID / null) and
  `GET …/report/pdf/download` serves it only as that run's DOCX's rendering. Výsledky gains
  "Stáhnout PDF". The worker image installs LibreOffice only with the build arg
  `AIA_WORKER_PDF=true` (default false). Measured: 1.7-2.0 s per conversion of a 1.5 MB
  report (LibreOffice 24.2.7, cold profile), PDFs 250-360 kB; the image cost is estimated
  from the host install (/usr/lib/libreoffice 313 MB), not measured -- the sandbox's
  Docker build could not reach Debian's mirror. Tests: test_report_pdf.py (a stand-in
  soffice), the three PDF tests in test_analysis_executor.py, the two in
  test_research_api.py, ExecutionSteps "offers the report's PDF…".
- B4: `domain/sociomap_register.py` replaces PROGRESS D6's global `D6_OPEN`: a
  `MethodApproval` names a method id **and** its spec fingerprint, so an edited version,
  a changed preset or a version with replaced formulas is never approved by an entry
  written for another; a method absent from the register is INTERNAL_ONLY. First and only
  entry: aia-sociomap-3 at `e16dc0d0…f241` (the code preset's fingerprint, pinned by
  `test_the_owners_decision_approves_aia_sociomap_3_exactly_as_the_code_computes_it`),
  CLIENT_FACING, the owner's 2026-10-13 decision, with a printed note that the
  methodology is provisional. Status is read from the register whenever a map is read,
  from the method id and fingerprint the run recorded beside its maps (`methods`), so it
  applies to every run that computed exactly the approved method. The drawn contract-2
  map (aia-sociomap-1) stays INTERNAL_ONLY (not in the register), so the stored
  `methodology_status` of every run is unchanged. `compose_map_sections` prints each map's
  status (the approval's note or "interní, čeká na schválení") and sets the figure's
  status; a client render still refuses any figure that is not CLIENT_FACING.
  `GET …/research/sociomap-register` serves the register; Výsledky' object map shows
  "Metodika schválena pro zprávy" with the note for an approved map, the internal chip
  otherwise (`mapApproval` in lib/object-map-view.ts: an unread register is internal).
  Tests: test_sociomap_register.py (6), the populated-map executor test (the stored report
  prints the approval), the register route test, `mapApproval` and ObjectMapView tests.
- B5 owner decisions (2026-10-13, asked in session): (1) modelled data enters the **client
  report only** under a recorded owner lift of ADR 0024 §4's holdout requirement -- support,
  intervals, the joint certificate and "no predictive-validity claim" still apply, and the
  client-facing analysis modules stay blocked until a holdout validation; (2) the joint
  certificate is met by a panel run **recording** its population's certificate, not waived.
- B5a: `RuntimePopulation.joint_certificate` (the certificate's verified bytes and the panel
  SHA-256 the loader checked it against, `PopulationRuntime` fills it at load);
  `panel_source.joint_certificate_record` writes it to the fieldwork dataset's metadata
  (`JOINT_CERTIFICATE_METADATA`, the text without a BOM, its SHA-256, the panel SHA-256);
  `analysis_results._joint_certificate` re-hashes it on read (a mismatch is refused,
  never read as none) for a modelled origin only; `native_evidence(joint_certificate=)`
  loads it with `load_joint_status` against the recorded panel hash. The certificate enters
  the system fingerprint, so a panel run's analysis modules are judged afresh once (cost:
  one re-run of the eight modules per panel run analysed after this lands; fictional runs
  are unchanged). Whether develop's LIVE certificate certifies its panel is the population's
  recorded `joint_state` (`population_ops status`); if it does not, nothing client-facing
  passes, as before. Tests: test_modelled_joint_certificate.py (6), the panel fieldwork
  test asserts the recorded certificate.
- B5b: `domain/evidence/report_lift.py` `MODELLED_CLIENT_REPORT_LIFT`, the owner's decision as
  data (id, surface CLIENT_REPORT, decided 2026-10-13, record, the note every client report
  prints). `instrument_policy(..., report_lift=)` drops `INTERNAL_ONLY` from `-2` only for a
  modelled run that recorded its respondent system and only where no holdout already lifted
  it; the lift's id enters the declaration's identity; simulated answers refuse it. Only the
  client composer passes it, so client-facing analysis modules stay blocked
  (`test_client_facing_analysis_stays_blocked_because_it_never_passes_the_lift`).
- B5c: `application/client_report.py` `compose_client_report` (a modelled run only, else
  `ClientReportRefused("not_modelled")`; nothing admitted is refused too, naming the gate's
  reasons): the run's evidence judged under the lift and the recorded certificate; every row
  carries the scope disclosure because every table prints the scope (`AI respondenti
  sestavení z populace <label>; modelováno: AI respondenti z populace`) and its base n;
  `question_tables(..., surface=CLIENT_FACING)` (a refused question left out, counted, its
  internal reasons not printed); `compose_map_sections(client=True)`: approved maps only, as
  figures with their fit, no support paragraph or pair table (numbers outside the ledger);
  the design chapter, "Respondenti a výpočet", the questionnaire appendix; a METHOD callout
  with the lift's note; ReportKind.CLIENT, CLIENT_CONFIDENTIAL, no run identifiers;
  `require_valid` passes. `stored_client_report`: `research_client_docx`, DRAFT_UNAPPROVED,
  stored once per exact sources; approvable (B2's `REPORT_ARTIFACT_TYPES`).
  `GET …/report/client/download` (409 `client_report_refused` with its reason); Výsledky:
  "Stáhnout klientskou zprávu" for a modelled run only. `verified_map` is the one map check
  both composers use; `question_tables` the one admission loop. Tests: the panel-run journey
  in test_ai_fieldwork.py (composes, validates, renders, labels, stores once, approves; a
  fictional run refused), test_modelled_joint_certificate.py (8), the route test, the web
  test.
- PDFs on for develop (owner, 2026-10-13): `AIA_WORKER_PDF=true` in the worker image build
  (.github/workflows/deploy-develop.yml) and `AIA_REPORT_PDF_ENABLED` defaulting to true in
  the develop worker's Compose environment (deploy/develop/docker-compose.yml, env.example).

- One place to download and approve (2026-10-13, after #385 and the docs PR #390): the
  "Kompletní zpráva studie" card on Výsledky (CompleteReport.tsx) is where a report is
  downloaded and approved: Verze Interní / Pro klienta (the client option disabled, with
  why, unless the run's data_origin_kind is MODELLED), Formát DOCX / PDF (PDF disabled for
  the client version, for a failed rendering and for a run that made none), "Stáhnout
  zprávu", and "Schválit pro interní použití" for exactly the document downloaded: the
  internal report by its status's artifact_id, the client report by the X-AIA-Artifact-Id
  its download named (lib/api.ts `requestStored`). Its part list now claims respondents,
  per-question tables and the design appendix once the report step succeeded (B1a-B1c);
  literature stays pending, since it joins only through a chosen review. The report panel
  below shows provenance only and points up to the card; the report with literature
  (InterpretationResearch.tsx) gains its approve button after its download. Tests:
  ExecutionSteps.test.tsx "Internal report" (card downloads, client refused then downloaded
  and approved, PDF and a failed PDF, separation of duties, read-only has neither),
  "Interpretation research" (the downloaded context report approved by its artifact id),
  CompleteReport.test.tsx (parts), MemoryStudy.test.tsx (project memory offers neither).

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
- CLAUDE.md § 2 map, application/: `report_approval.py  approve_report: a person approves a
  run's stored report (internal or with literature) through ArtifactRepository.approve,
  once`; routers/ research: "POST …/report/approve, a stored report approved for
  internal use (ADR 0019 self-approval policy)".
- CLAUDE.md § 2 map, infrastructure/: `report_pdf.py  LibreOfficePdf: a stored DOCX rendered as
  PDF (headless soffice, private profile, timeout); AIA_REPORT_PDF_ENABLED (off by default)`;
  executors/report.py's line gains "and, with AIA_REPORT_PDF_ENABLED, its PDF rendering
  (research_internal_pdf)"; deploy/docker: "worker build arg AIA_WORKER_PDF installs
  LibreOffice Writer".
- CLAUDE.md § 3 commands or deploy/develop README: how to turn PDFs on (both switches).
- CLAUDE.md § 2 map, domain/: `sociomap_register.py  SOCIOMAP_REGISTER: which Sociomap method,
  at which exact spec fingerprint, is approved (MethodologyStatus); absent is INTERNAL_ONLY;
  aia-sociomap-3 approved by the owner 2026-10-13`; research_sociomap.py's line: "INTERNAL_ONLY
  while D6 is open" becomes "a map's status is the Sociomap register's for its method";
  CLAUDE.md § 2 prose "The Sociomap is computed but INTERNAL_ONLY while D6 is open" becomes
  "A Sociomap's status is the register's for the exact method that computed it
  (aia-sociomap-3 approved 2026-10-13; aia-sociomap-1 internal)"; report_maps.py: "each map
  with the register's status"; routers/research: "GET …/research/sociomap-register";
  web lib/object-map-view.ts: "mapApproval".
- overview.md PROGRESS D6: the global switch is replaced by the register; D6 stays open for
  aia-sociomap-1's four declarations; OI-17 (the register) is closed by B4.
- AGENTS.md § mypy: an incremental `.mypy_cache` reported three `create_model` arg-type
  errors in domain/ai_respondent.py (pydantic 2.14.1, mypy 1.20.2) after an unrelated
  module changed; the same tree with a fresh `--cache-dir` is clean (382 files). Wrong:
  chase the errors. Right: `rm -rf .mypy_cache` and re-run before believing them.
- CLAUDE.md § 2 map: domain/fieldwork.py gains JOINT_CERTIFICATE_METADATA; panel_source.py
  gains joint_certificate_record; population/runtime.py gains joint_certificate.
- CLAUDE.md § 2 map: domain/evidence/report_lift.py (`MODELLED_CLIENT_REPORT_LIFT`: the
  owner's 2026-10-13 lift of -2's INTERNAL_ONLY for the client report only); application/
  client_report.py (`compose_client_report` / `stored_client_report`: a modelled run's client
  report, admitted numbers labelled modelled, approved maps only; refused by name otherwise);
  report_tables.py gains `question_tables(..., surface=)`; report_chapters.py gains
  `verified_map`; routers/research gains `GET …/report/client/download`. CLAUDE.md § 2 prose
  "Evidence is a capability": add that a modelled number reaches a client only in the client
  report, under the recorded lift, the run's certificate and every other gate.
- ADR 0024 §4 amendment (docs PR): the owner's 2026-10-13 lift for the client report, ahead
  of the holdout; client-facing analysis still waits for the holdout.
- open-items.md: F1 to be numbered there.

Applied by the docs PR #390, except what follows (the report buttons, after it):

- CLAUDE.md § 2 map, apps/web: `src/lib/api.ts` (or the rehome/research line): a stored
  report's download reads `X-AIA-Artifact-Id` / `X-AIA-Review-State` (`requestStored`), so
  the document approved is the one downloaded; rehome/research: "CompleteReport, the one
  place a run's report is downloaded (internal / client, DOCX / PDF) and approved;
  InternalReport shows its provenance; InterpretationResearch approves the report with
  literature it downloaded".
