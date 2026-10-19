# Trace 3: Evidence, interpretation and delivery (Results, Sociomap, Analysis, Report)

Read-only audit. Code anchors are `file:line @ f7e80bb9` (HEAD of `chore/mvp-master-plan`); the MVP documents
anchor at `085abe0`/`769917f`, so a line in a document is cited as `doc:line` without SHA.
`◇` = I did not open the cited code, so the claim is a hypothesis. Paths in `packages/aia_core/src/aia_core/`
are shortened to `core/`; `apps/api/src/aia_api/` to `api/`; `apps/executors/src/aia_executors/` to `exec/`;
`apps/web/src/` to `web/`.

Status words: EXISTS, PARTIAL, MISSING (with the plan and chunk that should build it, or NONE), CONTRADICTION.

Documents read first: `CLAUDE.md` §2, `mvp-development-plan.md`, `mvp-target-architecture.md`,
`mvp-cohesion.md`, `plans/research-lead-workbench.md`, `docs/migration/mvp-acceptance.md`, plus
`evidence-integrity`, `segment-maps-and-drilldown`, `client-data-in-analysis`, `two-roles-human-ai-gates`,
`research-integrity-report`, `sociomap-formula-corrections` (front-matter and the parts cited), ADR 0021, 0027,
`mvp-master-plan.md` (its §5 and §6 are still empty placeholders: this file feeds them).

---

## 1. The aggregate and the admitted claim, reaching the Results screen

**Verdict.** The chain from dataset to admitted claim is complete and fail-closed for the AI analysis, the internal
report and the client report. It stops short of the Results screen: Results reads the raw aggregate artifact and
hides suppressed cells in the browser, so "every number in a result is an admitted claim" (AC-08) is true of the
report path only. The plan for "findings cite all claims" misdescribes the code it tightens, and the plan for "one
field-policy authority" acts on a path no production number takes.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Fieldwork dataset to aggregate (support, donor bootstrap intervals, stored places) | EXISTS | `core/domain/research_aggregate.py:430-467` |
| Aggregate to an evidence table (rows removed with reasons: support, fidelity refusal, missing interval) | EXISTS | `core/domain/analysis/native.py:301-357, 454-545` |
| Admission: every claim or none, `AdmittedClaim` sentinel, metric, unit, exact value, interval for client-facing, origin allowlist | EXISTS | `core/domain/evidence/admission.py:221-331` |
| Instrument policy chosen by origin kind (`-1` simulated, `-2` modelled, anything else refused) | EXISTS | `core/domain/evidence/instrument.py:170-196` |
| Dictionary-derived 400-field policy book (the population contract's 115 fields) used by a production number | PARTIAL | `from_dictionary_rows` / `from_policy_document` have no caller outside tests (grep of `apps`, `packages/aia_core/src`); only `instrument_policy_book` is built in production (`native.py:493-500`). Plan: `evidence-integrity` 5 |
| Every key finding cites an admitted claim | PARTIAL | `core/domain/analysis/draft.py:116-118` (`claim_ids` defaults to `()`), `:270-276` (only numbers in prose are checked). No 95 % threshold exists in AIA code. Plan: `evidence-integrity` 1 (W0, S2) |
| A module must state at least one finding (second half of ANL-4) | MISSING | `docs/architecture/analysis.md:196-199` says AIA admits "a module with no finding"; `evidence-integrity` 1 names findings only. NONE |
| Repair loop, `BLOCKED` stored, nothing softened | EXISTS | `core/application/analysis.py:181-219` (`MAX_REPAIRS` 2, line 64) |
| Stored outcome re-admitted whenever read | EXISTS | `core/application/analysis_results.py:1-29` |
| Results screen reads admitted claims only | MISSING | Results reads the aggregate artifact through the generic route (`api/routers/research.py:1601-1646`; `research_aggregate` is in neither `_RESEARCHERS_ONLY` `:163` nor `_NEVER_INLINED` `:156`); suppression is the browser's (`web/lib/research-execution.ts:373-374`). Plan: NONE (`research-lead-workbench` 20 says "re-layout") |
| Evidence marks on Results (PrintGrade per row) | MISSING | `PrintGrade` is read by no API or web file (grep). Plan: NONE (`research-lead-workbench` 20, "Missing: —") |
| Run QC (straight-lining, collapse) as warnings, stored, shown on Fieldwork/Results | MISSING | `evidence-integrity` 2-3 (W1, S2); parity `analysis.qc` NOT_STARTED |
| Support forecast and question outlook before a run | EXISTS | `core/domain/support_forecast.py`, `question_outlook.py` per CLAUDE.md §2 ◇ |
| Evidence handed to the Lead as ResultsContext | MISSING | See capability 8 |

## 2. The Sociomap: object map, respondent and segment maps, register, pins, lock

**Verdict.** The object map is built, pinned, registered and in the client report. Everything else in MVP-16/17 has
no data to stand on: the stored fieldwork dataset carries no respondent attributes, the engine's respondent block is
"not computed", "dimensions" are persona topics and not segmentation variables, and the hard lock has no plan chunk.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Object map engine, contract 3 (`aia-sociomap-3`) | EXISTS | `core/domain/sociomap/engine_v2.py:292-440`, `models_v3.py:279-330` |
| Methods pinned at run start, retry keeps the pin | EXISTS | `core/domain/research_sociomap.py:318-346` |
| Register: approval by exact method and spec fingerprint, absent means `INTERNAL_ONLY` | EXISTS | `core/domain/sociomap_register.py:56-100` |
| Register entries for new methods | PARTIAL | The register is a Python tuple (`:56`); each entry is a code PR plus the method owner's decision (`segment-maps-and-drilldown` 0 and 4). A stored methodology edit (`aia-sociomap-3+e1`) matches no entry (`:78-87`), so an administrator's Metodika edit silently drops the maps from the next client report |
| Object map on Results with register status and snapshot | EXISTS | `web/components/rehome/research/ObjectMapView.tsx:63`, `ExecutionSteps.tsx:1919-1939` |
| "X of Y placed" line | EXISTS | `core/domain/sociomap/models_v3.py:262-275` (`placed`, `not_placed`), `engine_v2.py:249-263`, `web/i18n/cs.ts:2983` |
| Respondent map (placement of respondents) | MISSING | `models_v3.py:313` `respondents: NotComputed`; `sociomap-formula-corrections` 3 (open, W2 S2), gated by 0b (open) |
| Respondent attributes stored for segmenting, filtering and drill-down | MISSING | `FieldworkRespondent` is id, donor, weight, answers only (`core/domain/fieldwork.py:172-181`); persona profile and per-draw details are not stored on the main path (`exec/ai_fieldwork.py:327` returns `details`, used only by `exec/validation.py:289`; provenance `:461-474` holds counts, not per-respondent data). Plan: NONE (`sociomap-formula-corrections` I3 is "eligible descriptors into regions", not storage; `segment-maps` 1, 5, 6 assume them) |
| Segments "defined by the study's dimensions" | CONTRADICTION | `segment-maps-and-drilldown` 1: "a segment is a cell of the selected dimensions (`DIMENSION_TOPICS` / `persona_topics.py`)". `core/domain/persona_topics.py:313-320`: a dimension is a persona topic (`ekologie` to `eko`), an allowlist of profile facets, not a variable that partitions respondents |
| Segment map step, pinned method id, in the run graph and in the report's `depends_on` | MISSING | `segment-maps` 2 (W2 S2). The graph (`core/domain/workflow_templates.py:216-270`) has no node; `report` depends on the eight modules and `sociomap` only (`:231-242`) |
| Clustering option | MISSING | `segment-maps` 3, blocked on method owner (0) |
| Filters route (aggregates only) and drill-down route (`EDIT_STUDY`, never exported) | MISSING | `segment-maps` 5, 6. Datasets are never inlined (`api/routers/research.py:156`), so the drill-down needs a new reader of `research_fieldwork_dataset` and, per the row above, data that is not there |
| Drag changes the view only | EXISTS | `core/domain/sociomap/view.py` per CLAUDE.md §2 ◇ |
| Hard lock on Set 1 and the rating question, recorded unlock (`sociomap_unlock`) | MISSING | Only `mvp-target-architecture.md` §3.8, §5 and `mvp-development-plan.md` M3. No plan file mentions "unlock" (grep). Workbench 17 only displays the lock |
| Lock cannot be bypassed by a whole-copy save | PARTIAL | `apply_edit_ops` is the planned only writer (target-arch §3.1, §8) but the whole-copy route stays (`§3.1` last paragraph); today every stage saves through `PUT /studies/{id}/workspace/content` (`api/routers/workspace.py:2029-2044`) |
| Straight-liner handling | PARTIAL | Three unrelated definitions: map excludes a respondent whose rated items are all equal (`core/domain/sociomap/relations.py:340-347`); unit QC counts a rate of respondents answering all scales identically (`legacy/npc-panel-18.6.6/app/qc.py:200-207`); MVP-12's worker flags "identical battery answers". See C3 |
| Map snapshot (print camera, server) | EXISTS | `core/infrastructure/report_docx/object_map_figure.py:19-60`, `core/application/report_maps.py` |
| Map snapshot as an approvable object | MISSING | `research_map_snapshot` is named only in target-arch §3.8; two-roles 5b.4 chunk is "New", unwritten. The web snapshot is a browser canvas export (`web/components/rehome/research/ObjectMapView.tsx:577-628`), a different renderer |
| Lead can open Sociomap and focus an element | PARTIAL | `Stage` includes `sociomap` (`core/domain/research_lead.py:142-154`); focus ids only `question\|section\|brief\|plan` (`:176`). `research-lead-workbench` 14-16 |

## 3. The eight analysis modules, retry, the three registers

**Verdict.** Modules, repair, retry and re-admission on read are built. The three registers exist as three
separate places and never meet in one object; the external-context register is not connected to the modules at all
even though two documents say it is.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Eight modules, one step each, in the research graph when `analysis_enabled` | EXISTS | `core/domain/workflow_templates.py:229-243`, `exec/analysis.py:495-523` |
| Preflight before spend, BLOCKED with 0 calls | EXISTS | `core/domain/analysis/native.py:552-621` |
| Retry of failed modules as a linked run over the frozen dataset | EXISTS | `api/routers/research.py:1497, 1535`, `core/application/analysis_results.py` (`retry_failed_modules`) |
| Register 1, deterministic (aggregate, maps) | PARTIAL | Shown raw (see §1), no admitted view |
| Register 2, AI interpretation (module text, claims cited) | EXISTS | `api/routers/research.py:1648-1700`, `web/components/rehome/research/ExecutionSteps.tsx:1585` |
| Register 3, external context into the modules | CONTRADICTION | `core/domain/analysis/prompt.py:172` and `modules.py:143-170` consume `external_context`; `core/application/analysis_results.py:570-578` builds `AnalysisInputs` without it; `core/domain/deep_research/quarantine.py:251` `analysis_context` has no caller outside a test. `docs/architecture/deep-research.md:260` and `research-journey.md:265` say the bundle "reaches analysis as `external_context`" |
| A Lead interpretation as an unapproved register entry | MISSING | `research-lead-workbench` 21 names it, no storage or artifact type in target-arch §3.8 |
| Module class for a modelled run | PARTIAL | Class A for any non-fictional run (`core/domain/analysis/harness.py:190-203`), so every module parks until the route is widened; the master plan's activation row lists "every design job" only (`mvp-master-plan.md` §4) |
| Report needs all eight modules complete | EXISTS | `core/application/report.py:155-157`. With MVP-23 tightened (A1) one uncitable module blocks the whole internal report: no plan states this trade-off |
| Module with a stale docstring | CONTRADICTION | `native.py:20-34` says a native run has no certificate, the map is `INTERNAL_ONLY` while D6 is open and Deep Research "is not integrated"; code at `:515-519` takes the certificate, D6 is decided, Interpretation Research exists |
| Three new workers (`interpret_map`, `polish_report`, `flag_straightliners`) | MISSING | `research-lead-workbench` 11 (worker row, W0) and 21 (W3). Existing actions are design-only (`core/domain/research_agents.py:37-44`); accept merges into the design working copy (`core/application/proposal_accept.py:92`), which has no target for a map reading or a report wording |

## 4. Interpretation Research: Deep Research results into Analysis and Report

**Verdict.** The link into the report is built and complete; the link into analysis, and into the Lead, is not
built and no plan builds it. The development plan schedules as W4 work something that already exists.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Start over a result of the Study's own run, lineage pinned by id and SHA-256 | EXISTS | `api/routers/deep_research.py:550`, `core/application/deep_research.py:382, 538` |
| Typed target (module, battery object, pair) and mission built by code | EXISTS | `core/domain/deep_research/interpretation.py` per CLAUDE.md §2 ◇ |
| Bundle sealed, accepted quote grounded in a captured source | EXISTS | `core/domain/deep_research/quarantine.py:251` (context), grounding per ADR 0017 ◇ |
| Bundle into the report with literature (DOCX and PDF, approvable) | EXISTS | `core/application/contextual_report.py:94-96`, `api/routers/research.py:2195-2398` |
| Results panel starts it and selects the review | EXISTS | `web/components/rehome/research/InterpretationResearch.tsx:31` |
| Bundle into the analysis modules | MISSING | NONE (see register 3 above) |
| Bundle and accepted findings in the Lead's results context | MISSING | NONE: F4's list omits it (`mvp-cohesion.md:186-191`) |
| "The report's research-context chapter; Deep Research's sealed bundle into the report" (W4, S3) | CONTRADICTION | `mvp-development-plan.md:173` vs `contextual_report.py:94` and plan `deep-research-reports` (done 4/4) |
| Overlap: `interpret_map` worker and Interpretation Research both interpret a battery, object or pair | PARTIAL | Different registers (internal vs external), but no document says so; `research-lead-workbench` 21 says "A Lead interpretation as an unapproved register entry" |
| Live acceptance on the full design | MISSING | `deep-research-web-search` 27 (W4, S2) |

## 5. Reports: internal, with literature, client, DOCX and PDF

**Verdict.** The internal report, the report with literature and the client report exist. The client report has no
PDF, and two criteria of AC-13 ("evidence audit", "legal source-use gate") name capabilities with no code and no plan.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Internal report composed by a worker from eight re-admitted modules and the map | EXISTS | `core/application/report.py:155-168`, `exec/report.py` |
| DOCX renderer, deterministic, linted | EXISTS | `core/infrastructure/report_docx/renderer.py` per CLAUDE.md §2 ◇ |
| PDF beside the DOCX (internal, with literature) | EXISTS | `core/application/report_variants.py:78` (`RENDERABLE_REPORTS`) |
| Client report: modelled run only, numbers `CLIENT_FACING` under the owner's lift, approved maps as figures, no analysis prose | EXISTS | `core/application/client_report.py:94-239` |
| Client report composed and stored by a GET in the API | PARTIAL | `client_report.py:277-334` (composition on download); every other report is a worker step |
| Client report as PDF | CONTRADICTION | `docs/migration/mvp-acceptance.md:40, 88` and `overview.md:332` say DOCX and PDF; `report_variants.py:78` "the client report is DOCX only", web `CompleteReport.tsx:221` agrees. NONE builds it |
| "Evidence audit" gate on a delivered report | MISSING | parity `governance.evidence_audit` NOT_STARTED and `mvp_path`; no plan. ◇ whether `domain/report/validation.py` is what the criterion means |
| "Legal source-use gate" on a delivered report | MISSING | parity `governance.legal` NOT_STARTED, `mvp_path` (`parity-matrix.json`); the unit's module is non-blocking by default (`legacy/npc-panel-18.6.6/app/legal_gate.py:1-12`); AIA's `licence.py` is a model-transmission gate, a different thing. `research-journey.md:569` still cites it as "AC-11" (old numbering). Plan: NONE |
| Report writer worker (`polish_report`) and where an accepted wording lives | MISSING | `research-lead-workbench` 21, worker row 11; no artifact type or composer input (target-arch §3.8 lists none). See C7 |
| Report marks for a third evidence kind | MISSING | `PrintGrade` has five values (`core/domain/report/evidence.py:41-56`); `client-data-in-analysis` 5 names "marks" only |
| Parity ledger says report generation is not started | CONTRADICTION | `parity-matrix.json` `reports.generation` NOT_STARTED, empty `implementation`; code above |

## 6. Approval and export

**Verdict.** One approval mechanism serves the three report types and is independent only where self-approval is off.
"Exports only after approval" is not built and contradicts the review workflow; map-snapshot approval has no object, no
route and an inconsistent ledger subject; the target architecture says both "second person" and "no second person".

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Approve a stored report (internal, with literature, client), freeze, ask for the approved PDF | EXISTS | `core/application/report_approval.py:43-83`, `api/routers/research.py:2461-2506` |
| Independence follows the scope's self-approval policy; ledger row with policy and source | EXISTS | `core/infrastructure/artifact_repository.py:554-579`, `core/domain/scope.py:403-441` |
| Approved export stamped SCHVÁLENO with date and version, DOCX and PDF | EXISTS | `core/application/report_export.py:123-167` |
| Client report and internal report approved as separate acts | EXISTS | distinct artifact types (`client_report.py:62`, `report_approval.py:34-36`) |
| Producer of a client report | PARTIAL | Composed under the first downloader's scope (`client_report.py:297-334`), `produced_by_user_id = scope.actor_id` (`artifact_repository.py:384`); with self-approval off, the reviewer who opens it first becomes its producer and cannot approve it (`:556-560`). The web approves only after a download (`web/.../CompleteReport.tsx:205`). Derived by reading, not run |
| "DOCX and PDF available only after approval" | CONTRADICTION | `mvp-cohesion.md:506-508`, target-arch §7 line 405 vs `api/routers/research.py:2395-2449` (client report: "its approved version, else a draft") and `:2044-2066`; `productization-coherence.md:1008` "downloads ungated". The review step is a download of the draft |
| Map snapshot approval | MISSING | `two-roles-human-ai-gates` 5b.4 (still reads "blocked: the client-facing report contract does not exist", `:13`); dev plan W2 S3 says "New chunk" |
| Ledger subject for a snapshot | CONTRADICTION | M3 adds `map_snapshot` (`mvp-development-plan.md:192`, check constraint now at `core/infrastructure/tables.py:1709-1712`); target-arch lines 230-231 say a snapshot is "approved through the existing artifact approval", which writes subject `artifact` (`artifact_repository.py:568`) |
| Approve and Export panel "showing by whom" | PARTIAL | `ReviewMark` has the date only (`core/domain/report/review.py:54-64`); `approval_of` returns a time (`artifact_repository.py:582-600`); no reader of the ledger (`productization-coherence.md:1020`) |
| Second person for the client report | CONTRADICTION | `mvp-acceptance.md:40, 88` ("approved by a second person", "a reviewer other than the producer"), target-arch §7 lines 403-405 ("unconditional for client-facing") vs target-arch §1 line 25 and `mvp-cohesion.md:511-516` (withdrawn) and Q21. The route's 403 text is unconditional (`api/routers/research.py:2478-2485`) |
| Approval of a client report returns `internal_only: true` | PARTIAL | `api/routers/research.py:2505` for any artifact type |

## 7. The client-reported origin and client data in analysis (ADR 0027, planned)

**Verdict.** Nothing is built beyond the dataset preview (K2c). The plan's chunk order is sound; the ADR and the plan
disagree on how personal columns are handled, the analysis path is single-origin by construction, and nothing places
client numbers in the run, the pipeline or the model classification.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Dataset preview, personal hints (masking) | EXISTS | `core/domain/client_datasets.py:9-14, 70, 144` ◇ lines as cited by the plan |
| `CLIENT_REPORTED` origin and fourth reading | MISSING | `client-data-in-analysis` 1; `core/domain/fieldwork.py:88, 143-152` (allowlist, "no fourth kind"); `instrument.py:184-196` refuses any other origin. Contract owner S2, chunk assigned S3 (B16) |
| Policy for a client column | MISSING | `client-data-in-analysis` 0 (owner decision deferred); `mvp-cohesion.md:167-169` |
| Data contract type, accept route, ledger row `data_contract` | MISSING | `client-data-in-analysis` 2; M8 and M3 (W3, S3); ADR 0027 is Proposed |
| Allowlist copy of columns (fail closed) | CONTRADICTION | ADR 0027 decision 3: "a column with a `PersonalHint` is left out ... a person may clear a false flag" (blocklist) vs plan chunk 3 and target-arch §3.7 (allowlist, "hints, not a rule") |
| Deterministic computations (descriptive tables, benchmark gaps) | MISSING | `client-data-in-analysis` 4; step kinds `client_data_prepare`/`client_data_compute` (target-arch §4), no graph node, no pin of the contract version on the run, no `IMPACT_ROOTS` entry (`core/domain/pipeline.py:137-166`) |
| Admission and grade beside modelled numbers | MISSING | `client-data-in-analysis` 5. `AnalysisInputs` holds one table, one book, one surface (`core/application/analysis.py:90-102`); `native_evidence` requires the aggregate's origin to equal the dataset's (`native.py:486-500`) |
| Results screen shows client-reported figures beside modelled | MISSING | NONE (workbench 20 names no such row) |
| Report marks and "z dat klienta" label | MISSING | `client-data-in-analysis` 5; `PrintGrade` (`report/evidence.py:41-56`), `marks.py`, tokens and the design-system package all change |
| One report for a run, data that belongs to a study | PARTIAL | `client_report.py:94-122` is per run via `native_sources`; client computations are study-level artifacts (target-arch §3.8). No document says which run's report carries them |
| Class of material when client-reported numbers reach a model | MISSING | `classify_analysis_material` knows only respondents (`harness.py:190-203`); `MaterialRule.CLIENT_SOURCE` is A (`core/domain/material_rules.py:59-69`); `client-data-in-analysis` 7 names no class or lineage |
| Client's own survey map through the existing engine | MISSING | `client-data-in-analysis` 6 (S3) on S2's `domain/sociomap/` surface |

## 8. The Lead reading results; report-writer and map-interpreter workers

**Verdict.** The Lead infrastructure is real (turns, grounded edits, numbers only from the context). Its context holds
no results, the contract that would add them is unwritten and absent from the workbench plan's chunk list, and the
three gates a results context touches (class, licence, accept target) have no owner.

| Link | Status | Anchor or plan chunk |
|---|---|---|
| Lead turn, grounded edits, ledger rows, `open_stage` over all eleven stages | EXISTS | `core/domain/research_lead.py:142-154`, `core/application/research_lead.py:555-618` |
| Lead may not quote a number its context lacks | EXISTS | `core/domain/research_lead.py:469` (`lead_contract`) |
| Runs layer in the Lead's context | PARTIAL | run id, status, design revision only (`core/application/research_lead.py:882-888`) |
| `ResultsContext` (admitted claims with origin kind, pair statuses, module text, report draft ids, QC), bounded and classified | MISSING | `mvp-development-plan.md:158-159` (S1 owner, contract before W2); `mvp-cohesion.md` F4 "adopted" says chunks are added to `research-lead-workbench`; its front-matter (chunks 11-25) has none |
| Licence lineage on a Lead request that holds panel-derived numbers | MISSING | `lead_request` sets lineage only from knowledge kinds (`core/domain/research_lead.py:984-986`); a results layer added without a lineage change reaches the model with `DataLineage.none()`, outside the panel determination (`licence_determinations.py:40`). Test named only in `segment-maps` 7 |
| Class of the results layer | MISSING | `MaterialRule` has nine rules and none for results, module text, map or report text (`material_rules.py:59-69`). NONE |
| Lead can point at a result element (a measure, an object, a pair, a module, a report section) | MISSING | `FOCUS_ID` admits four kinds (`research_lead.py:176`); `research-lead-workbench` 14-16 (W1) and 20 |
| Worker row (id, task, context layer, class, reservation, prompt pin, switch, card kind, result kind) | MISSING | `research-lead-workbench` 11 first deliverable (W0, S1) |
| Map interpreter, report writer, straight-liner check: accept target | MISSING | See §3 last row and C7; `research-lead-workbench` 21 and `evidence-integrity` 4 |
| Route class for all of the above | PARTIAL | The route is Class C only until an operator widens it (`mvp-development-plan.md:72-79`); results-reading steps are Class A by the harness rule, but the activation matrix names design jobs |

---

## A. GAPS (a link MISSING with no plan)

1. **No respondent attributes are stored.** `FieldworkRespondent` (`core/domain/fieldwork.py:172-181`) and the dataset provenance (`exec/ai_fieldwork.py:461-474`) hold no profile or dimension values, so segment maps, filters, the drill-down and respondent placement have nothing to read. Owner: S2, a new chunk in `segment-maps-and-drilldown` before 1 (what is stored, its class, who may read it).
2. **"Segments by the study's dimensions" has no variable.** A dimension is a persona topic (`persona_topics.py:313-320`); a cell of topics is undefined. Owner: S2 with the method owner (chunk 0): name the segmentation variables (population fields, a materialized child's column) and where their per-respondent values live.
3. **The Sociomap hard lock and `sociomap_unlock` route have no plan chunk.** Only target-arch §3.8 and M3 name them; workbench 17 only draws the lock. Owner: S1 (the lock rule in the edit vocabulary) with S3 (ledger row), written into `research-lead-workbench` and `evidence-integrity`-adjacent plan before W1.
4. **No API returns the admitted evidence table or marks for Results.** Results shows raw aggregates with browser-side suppression (`research-execution.ts:373`). Owner: S2 (provider over `native_evidence`), S1 artifact 20; this is also the `ResultsContext` source.
5. **External context never reaches the analysis modules.** `analysis_context` (`quarantine.py:251`) and `AnalysisInputs.external_context` are two unconnected ends. Owner: S2 decides wire (fingerprint change for all modules) or retire, and fixes the docs.
6. **AC-13's "evidence audit" and "legal source-use gate" have no implementation and no plan** (`governance.evidence_audit`, `governance.legal` NOT_STARTED). Owner: S3: define each as a testable check or drop it from AC-13.
7. **No client report PDF** (`report_variants.py:78`), yet AC-13 requires one. Owner: S3, one chunk in `research-integrity-report` (extend `RENDERABLE_REPORTS`, approval asks its PDF).
8. **Map-snapshot object, renderer, storage and route do not exist.** Browser canvas and server print camera are two renderers. Owner: S3 with S2; decide server-rendered from stored map plus camera parameters, never browser bytes.
9. **The three new workers have no accept target.** `proposal_accept` merges design items only. Owner: S1 with S3: result kinds and where an accepted wording, interpretation or keep/replace lands.
10. **No `MaterialRule` for results, module text, maps or report text.** Owner: S1 with the data owner, in `domain/material_rules.py`, before the Lead's results layer, `polish_report` or `interpret_map`.
11. **Class and lineage for client-reported numbers going to a model, and a multi-origin analysis input.** Owner: S2 (`AnalysisInputs`, `native_evidence`) with S3; add to `client-data-in-analysis` 5 and 7.
12. **Client-data steps are not placed in the run.** No graph node, no contract-version pin on the run, no impact root, no statement of which run's report prints them. Owner: S3 with S2 (`workflow_templates.py`, `pipeline.py:137`).
13. **No reader of the approval ledger, so "approved by whom" cannot be shown.** Owner: S3 in the Approve and Export panel chunk.
14. **ANL-4's second half ("a module states a finding") is in no chunk.** Owner: S2, `evidence-integrity` 1.
15. **Run QC and the worker's replacement semantics for a straight-liner are undecided** while the map already excludes such respondents. Owner: S2 (see C3).

## B. CONTRADICTIONS

1. `evidence-integrity.md` "What exists" says AIA passes a draft "when 95 % of the findings cited" and calls MVP-23 a threshold tightening; `draft.py:8-12` describes the unit. AIA has no threshold: a finding with no claim ids and no number passes (`draft.py:116-118, 270-276`; `analysis.md:196-199`). The chunk is a new rule, and the parity cases `finding-without-evidence` and `no-finding-at-all` flip.
2. Second person for the client report: `mvp-acceptance.md:40, 88`, target-arch §7:403-405 vs target-arch §1:25, `mvp-cohesion.md:511-516`, Q21 (withdrawn). The route text (`research.py:2478-2485`) is unconditional.
3. "Exports only after approval" (`mvp-cohesion.md:506-508`, target-arch §7:405, AC-13) vs drafts downloadable by design and approved after download (`research.py:2395-2449`; `CompleteReport.tsx:205`).
4. AC-13 and `overview.md:332` say client report DOCX and PDF; `report_variants.py:78` says DOCX only.
5. `ARCHITECTURE.md:395-398` says the research Sociomap is `INTERNAL_ONLY` while D6 is open and every client surface refuses it; the register approves `aia-sociomap-3` since 2026-10-13 and the client report prints approved maps (`sociomap_register.py:56-76`). `native.py:20-34` carries the same stale statements.
6. `deep-research.md:260` and `research-journey.md:265` (analysis receives the bundle) vs `analysis_results.py:570-578` (it does not).
7. `evidence-integrity` 5 and MVP-29 ("two lists decide what may back a client-facing claim") vs the code: the dictionary-derived book has no production caller, the only live authority is the instrument policy (`native.py:493-500`).
8. ADR 0027 decision 3 (drop what a `PersonalHint` flags) vs `client-data-in-analysis` 3 and target-arch §3.7 (allowlist the contract names).
9. Target-arch §3.8 (snapshot approved through the existing artifact approval) vs M3's `map_snapshot` ledger subject; the existing approval writes `artifact` (`artifact_repository.py:568`).
10. `mvp-development-plan.md:173` (W4: report's research-context chapter) vs `contextual_report.py:94` and `deep-research-reports` (done).
11. `two-roles-human-ai-gates` 5b.4 and `mvp-master-plan.md` §3.1 ("needs a client-report contract") vs `client_report.py:62`.
12. `sociomap-formula-corrections` front-matter: 5b and 2d unticked, yet `report_maps.py:159-161` prints Stress-1 and `engine_v2.py` computes `aia-sociomap-2`; `mvp-master-plan.md` §3.1 names "method owner (0a)" while 0a is `[x]` and 0b is `[ ]`.
13. `parity-matrix.json`: `reports.generation` NOT_STARTED with built code; AC-08's matrix wording ("on every client-facing number") differs from `mvp-acceptance.md:83` ("every number in a result").
14. `mvp-cohesion.md` F18 ("the placed line needs chunk 3, until then not shown") vs `models_v3.py:262-275` and `cs.ts:2983`, which already show placed and not-placed respondents.
15. Workbench chunk 20 lists "Missing: —" for Results (evidence marks, support, suppression) while no API or web file reads `PrintGrade` or the evidence table.
16. Ownership: `mvp-development-plan.md` §2 gives `domain/fieldwork.py`, `domain/evidence/` and `domain/sociomap/` to S2, §3 W3 gives `client-data-in-analysis` 1 (origin) and 6 (survey map) to S3.
17. Target-arch §8 ("the working copy is written only by `apply_edit_ops`") vs §3.1 (the whole-copy route stays); the hard lock lives only in the first.

## C. INTERFACES crossing plans or sessions with no owner

1. **`ResultsContext`**: type owned by S1, providers by S2 (maps, QC, claims) and S3 (report drafts, client data); class, licence lineage and bound are unspecified. Proposed owner: S1 writes the contract in W1 (not W2), including a `MaterialRule` and the lineage test.
2. **Approve and Export panel** (S3, W2) sits inside the Report artifact (S1, W3, `components/workbench/`). Proposed owner: S1 hosts a slot; S3 supplies the panel; order in one wave.
3. **"Straight-liner" is defined three times** (sociomap `relations.py:340-347`, unit QC `qc.py:200-207`, the worker). Proposed owner: S2 writes one definition in `domain/` that the map, QC and the worker all call; the map's exclusion and "replace starts a new run" must then agree.
4. **Single-origin analysis input** (`AnalysisInputs`, S2) vs client-reported numbers (S3). Proposed owner: S2 designs a two-table input and its fingerprint before S3 chunk 5.
5. **Snapshot renderer vs snapshot approval** (S2/web vs S3). Proposed owner: S3 owns the approvable artifact, S2 the deterministic figure function with camera parameters.
6. **Segment and respondent map nodes** (S2) must be added to the run graph, the report's `depends_on` and the client report's map chapter (S3), each with a register entry. Proposed owner: S2 for the node, S3 for the chapter, one PR pair.
7. **Report wording and map readings** (S1 workers) vs the composer (S3): where accepted text is stored and how it enters a report's fingerprint. Proposed owner: S3 defines an artifact type and composer input; S1 writes the worker against it.
8. **Pipeline stages vs V3 stages**: `RESEARCH_STAGES` has no Sociomap stage (`pipeline.py:100-114`) and `IMPACT_ROOTS` no segment, lock or contract entry, yet AC-07 and the stage track depend on them. Proposed owner: S2 (`pipeline.py`) with S1 (`lane.ts`).
9. **Lock, declarations and ledger**: S1's `apply_edit_ops` enforces, S2's `sociomap_rating`/`context_objects` declare, S3's ledger records. Proposed owner: S1, with a test that the whole-copy route cannot change a locked item.
10. **Route class widening** reaches the Lead's results layer, all eight modules, the report writer and the map interpreter, not only design jobs. Proposed owner: S3 (activation matrix row, `mvp-master-plan.md` §4).
11. **Register entries** are code (S2) decided by the method owner; Metodika edits make a method `INTERNAL_ONLY` (`sociomap_register.py:78-87`). Proposed owner: S2 states the rule on the Settings page and in the client report's missing-map sentence.

---

Not verified: whether `RELIGION` is refused client-facing end to end (only found in tests and `audience.py`); `view.py`,
`interpretation.py` and the DOCX renderer files were taken from the CLAUDE.md map; the producer-order defect in §6 is
derived by reading, not reproduced; I did not run any test.
