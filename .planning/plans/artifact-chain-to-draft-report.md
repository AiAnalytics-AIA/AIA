---
status: planned
chunks:
  - "[ ] CHN1. The section-source manifest: every section of a stored report names its sources (artifact id with SHA-256, specification field, ledger refs, or fixed text), and the artifact outputs no section read, stored with the document model"
  - "[ ] CHN2. The brief in the draft: goal, decision_use, objectives and the briefing compiled into the specification as typed text, printed in the introduction and given to the analysis with the hypotheses"
  - "[ ] CHN3. Research questions traced into the report: each question's measures and tables, the findings answering it and its recorded gap, in the research-questions chapter"
  - "[ ] CHN4. The Design Research a design was built on, in the design chapter: accepted items by bundle id and SHA-256, labelled external context"
  - "[ ] CHN5. The audience in full: the specification keeps the stated description and filters, and the design chapter prints them"
  - "[ ] CHN6. The report's audit names every artifact it stands on: the aggregate, the map, the specification, the dataset, and the experimental Sociomapping draft when the run made one"
  - "[ ] CHN7. The UI workbench composes analysis and the internal report on recorded models, and runs the stage workers on recordings: local and test only"
  - "[ ] CHN8. Interpretation Research woven into the body (CQ4 = Q58 b): when literature is chosen, each accepted finding in the body section it bears on, labelled external (L class), never respondent evidence; one document, the separate with-research DOCX retired for new reports"
  - "[ ] CHN9. Metodika a způsob interpretace from the run's pins: aggregation methodology, support rule, Sociomap method and QC warnings, the reading guidance kept and labelled"
  - "[ ] CHN10. A module with no supported finding blocks the draft (MVPQ-04): composition, approval and export refuse; the module's diagnostic shown on Analýza and Výsledky and in the refusal's own words"
  - "[ ] CHN11a. The number census: a new scan of the stored document model's text, every numeric token classed as an admitted ledger ref, a value of the stored Sociomap artifact, or a design or document-control number with typed provenance; an unclassed token fails"
  - "[ ] CHN11. The chain over HTTP: a fictional study from brief to internal DOCX on recorded answers, every hand-off chunk's output (CHN1-CHN6, CHN8-CHN10, RD5a) asserted in the draft, every number in an accepted provenance class"
  - "[ ] CHN12. The chain in a browser: draft_report_journey.mjs on the UI workbench, brief through every stage to the internal DOCX at 1440 px, zero paid calls"
---
# The artifacts in one chain: brief to a draft research document

The product owner, 2026-10-21: "ensure they all work together to produce a draft research document".
This plan is the cross-artifact half of the eleven artifact plans
(`artifact-brief`, `-design`, `-questionnaire`, `-audience`, `-dimensions`, `-sample`, `-fieldwork`,
`-results`, `-sociomap`, `-analysis`, `-report`). Each of those plans names what it hands on; this one
shows how the hand-offs compose into **the internal report**:

- `application/report.py` `compose_internal_report` (`:129`);
- with `report_chapters.py:110`, `report_design.py:114`, `report_method.py:449`,
  `report_tables.py:130` and `report_maps.py:125`;
- and its variants `contextual_report.py` (with literature, `:864`) and `client_report.py` (`:94`).

Anchors are `file:line @ 25f26232` (origin/develop) unless stated.

## 1. The chain, hand-off by hand-off

| From | Hands on | Form | Read by |
|---|---|---|---|
| Zadání | `title`, `goal`, `decision_use`, `briefing.*`, attachments | typed fields of the working copy, frozen in the Design Revision | `analyze_brief`'s context; **no report section** (G1) |
| Návrh | `plan.research_questions` | typed list, by text (`domain/analysis/native.py:141`) | every module (`analysis_results.py:575`); report introduction and design chapter |
| Návrh | `plan.hypotheses`, `plan.objectives` | typed lists with stable ids (WCE1) | **nothing**: the analysis does not receive them (AOC3) |
| Návrh | Design Research accepted items | ledger ref (`design_research` row) + the Design Revision it made | **nothing in the report** (CHN4) |
| Návrh, Dotazník | sets, questions, links, scales | typed design items → `spec.batteries`, `spec.questions` (`research_design.py:408-418`) | design chapter, questionnaire appendix, question tables |
| Cílová skupina | `audience` (description, filters) | typed fields → `spec.audience`, only three flags kept (`research_design.py:910-914`) | design chapter's audience sentence (`report_design.py:100`) (G4) |
| Dimenze | `selection.dimensions`, `n`, a materialized child | typed fields; `population_version_id` pinned on the run | method chapter (`report_method.py:398`) |
| Vzorek | readiness, gaps, answerability, forecast | the run's metadata at start | method chapter (`report_method.py:176`); the introduction's gap marks (`report_method.py:151`) |
| Sběr dat | the dataset; population binding, `persona_source`, receipt, pinned methods | artifact id + SHA-256; the run's metadata | the analysis evidence; the method chapter |
| Sběr dat | QC flags, spend | (to come: RQC4; the ledger) | **nothing** (CHN9) |
| Výsledky | the aggregate | artifact id + SHA-256 | the analysis evidence table; **not cited by the report** (G5, CHN6) |
| Sociomapa | the Sociomap | artifact id + SHA-256, verified against dataset and specification (`report_chapters.py:70-107`) | map chapters, their figures, the audit |
| Sociomapa | the experimental Sociomapping | its own DOCX (`sociomapping_report.py`) | **not the internal report** (G6, CHN6) |
| Analýza | eight module results | artifact id + SHA-256 each; claims as ledger refs | eight chapters; the evidence appendix; the audit |
| Interpretation Research | the sealed bundle | bundle id + seal | today a literature chapter, **only in the with-literature variant** (G2); woven into the draft's body by CHN8 (Q58) |
| The Lead | edits to the working copy | working revisions, ledger rows (`lead_edit`) | the report only through a new Design Revision and a new run (ADR 0016) |
| The Lead | edits to the report | (to come: RD5a, RD6) | **no path today** |

## 2. The draft's sections and their sources

`compose_internal_report`, in the order it writes them (`report.py:170-292`, lines counted from
`:129`):

| Section (id) | Source | Gap |
|---|---|---|
| Úvod a rámec studie (`intro`) | Study and client names (`meta`); `research_questions` (Návrh); gaps recorded at start (Vzorek); frame text by data origin (Sběr dat); the aggregate's deviation | goal, decisions and objectives absent (G1, CHN2) |
| Návrh studie (`ch-design`) | the specification: RQs, batteries, n, audience (`report_design.py:114`) | audience is three flags (G4, CHN5); Design Research absent (CHN4) |
| Shrnutí pro vedení (`ch-1`) | EXECUTIVE module | — |
| Výzkumné otázky (`ch-2`) | RESEARCH_QUESTIONS module; gaps | measures and tables not traced per RQ (CHN3) |
| Literární rešerše a externí kontext (`literature`) | sealed bundle (`contextual_report.py:701`) | only in the variant today (G2); retired for new reports, its findings woven into the body sections (CHN8, Q58) |
| Metodika a způsob interpretace (`methodology`) | **fixed text** (`report.py:252-293`), plus the deviation | no source (G3, CHN9) |
| Respondenti a výpočet (`ch-method`) | the run's metadata (`report_method.py:449`) | QC warnings absent (CHN9) |
| Výsledky jednotlivých otázek (`ch-questions`) | the analysis evidence table, admitted per question (`report_tables.py:228`) | the aggregate artifact not cited (G5, CHN6) |
| Cílová skupina (`ch-3`) | AUDIENCE module | — |
| Srovnání sledovaných objektů (`ch-4`) | OBJECTS module | — |
| Sociomapy · <set> (`ch-native-map-n`) | the verified Sociomap (`report_maps.py:383`) | respondent and segment figures wait (`signed-off-sociomap-method#9`, `segment-maps-and-drilldown#9`) |
| Segmenty (`ch-5`) | SEGMENTS module | **no admitted segment producer** (`segment-maps-and-drilldown#10`), and a module with no supported finding blocks the draft once `evidence-integrity#9b` lands (MVPQ-04, CHN10) |
| Hypotézy (`ch-6`) | HYPOTHESES module | **no hypotheses input** (`assumptions-and-open-answer-coding#AOC3`) |
| Implikace pro rozhodnutí (`ch-7`) | IMPLICATIONS module | **no `decision_use` input** (AOC3, CHN2) |
| Limity (`ch-8`) | LIMITATIONS module; the deviation | — |
| Dotazník (`app-questionnaire`) | the specification | routing absent until `run-qc-and-checkpoint#RQC11` |
| Evidenční příloha (`app-evidence`) | the ledger | — |
| Audit (`app-audit`) | run id, evidence fingerprint, module SHAs | aggregate, specification and dataset ids absent (CHN6) |

Still to come: assumptions (`report-delivery#RD9`), open-answer coding (`#RD10`), Deep Research
in the client report (`#RD11`).

**Outputs no section reads:**
- the brief's goal, decision_use, briefing and objectives;
- hypotheses;
- Design Research findings;
- the audience description and filters as stated (the method chapter prints them as applied);
- QC flags;
- the experimental Sociomapping;
- the Lead's study notes (`lead-orchestration#LO19`).

## 3. The gaps, owner by owner

G1-G11 were mapped by the integration coordinator at `25f2623` and verified here at `25f26232`.
G12-G17 are added by this plan.

| Gap | Claim, verified | Owner chunk |
|---|---|---|
| G1 | The briefing reaches no report section: compile keeps only title, n, questions, batteries, three audience flags and the selection (`domain/research_design.py:899-916`) | **CHN2** |
| G2 | The internal report never receives `context_sections`: the worker calls `compose_internal_report` without them (`apps/executors/src/aia_executors/report.py:101`); literature appears only in the variant (`contextual_report.py:864`) | **CHN8** (CQ4 = Q58 b: one document) |
| G3 | "Metodika a způsob interpretace" is fixed text (`application/report.py:252-293`) | **CHN9** |
| G4 | The report's audience is only `source_mode`, `strategy` and `has_filters` (`research_design.py:910-914`) | **CHN5** (`artifact-audience` hands it on) |
| G5 | The report does not cite the aggregate artifact; its tables come from the analysis evidence (`report_tables.py:103-130`) | **CHN6** |
| G6 | Sociomapping is left out of the internal report (no reference in `application/report*.py`) | **CHN6** (named in the audit and the coverage record; its content stays its own draft) |
| G7 | On the UI workbench analysis parks: `workbench_registry_for` composes no gateway (`apps/executors/src/aia_executors/workbench.py:158-176`), and without `AIA_AI_ANALYSIS_ENABLED` the template adds no report node (`domain/workflow_templates.py:227-236`) | **CHN7** |
| G8 | `tools/ui_workbench/research_journey.mjs` stops at Data and Sociomapy (`:115-128`) | **CHN12**; per stage `artifact-results#RES7`, `artifact-report#RPT7` |
| G9 | There are no recordings for the research_agent tasks: `recorded_models.py:60-79` knows analysis, respondent and lead tools only | **CHN7** |
| G10 | No test checks the DOCX's sections or sources: `tests/acceptance/test_acceptance_harness.py:245-316` asserts status codes (`:302-303`) | **CHN11** (built on that test) |
| G11 | The research screens carry no `data-aia` ids; Cílová skupina, Dimenze and Vzorek have no Lead targets (`FOCUS_ID`, `domain/research_lead.py:205`; `lib/lead.ts:422-433`) | `research-lead-workbench#16`, with each artifact's contract chunk (BRF1, DSN1, QST1, AUD1, DIM1, SMP1, FLD1, RES1, SOC1, ANL1, RPT1) |
| G12 | Hypotheses and `decision_use` never reach the analysis (`analysis_results.py:570-578`) | `assumptions-and-open-answer-coding#AOC3` (Q12); CHN2 adds goal and objectives beside them |
| G13 | Research questions reach the report by text only; no RQ is traced to its measures or tables | **CHN3** |
| G14 | Deep Research findings as labelled external context: design findings nowhere, interpretation findings only in the variant | **CHN4**, **CHN8**; `evidence-integrity#7` (module preparation) |
| G15 | The Lead's narrative edits cannot reach the report: no document model is stored (F-ED3, `aia_executors/report.py:101-146`; `domain/report/model.py:87`) | `report-delivery#RD5a`, then `#RD6`; UI `artifact-report#RPT6` |
| G16 | Q12's five hand-off gaps | `lead-orchestration#LO9d` (worker inputs), `assumptions-and-open-answer-coding#AOC3` (hypotheses), `working-copy-edit-ops#WCE7` (staleness on pending proposals), `lead-orchestration#LO7` (pending proposals in the Lead's context), `lead-orchestration#LO6` (a card-started job returns to the Lead) |
| G17 | All eight modules must complete or nothing is composed (`report.py:156-157`); SEGMENTS has no admitted producer, so once `evidence-integrity#9b` lands a study cannot reach a draft in one pass | **CHN10** (MVPQ-04: block); `segment-maps-and-drilldown#10` |

## 4. Chunks

**CHN1. The section-source manifest.**
- `domain/report/model.py`: `Section.sources`, a tuple of `SectionSource`:
  - `artifact(type, id, sha256)`;
  - `spec(field path)`;
  - `ledger(refs)`;
  - `fixed(text id)`.

  The composers fill them, and `report_sources(document)` returns them with the outputs no section
  read, from the run's artifacts.
- Stored with RD5a's document model and printed in the audit appendix. The Report artifact's
  "Záznam pokrytí" reads it (`artifact-report#RPT4`).
- Tests: every section of the four sample reports names at least one source; `fixed` is allowed only
  for `methodology`'s guidance; the manifest of `make report-preview`'s internal sample matches a
  committed fixture.
- Depends on `report-delivery#RD5a`.

**CHN2. The brief in the draft.**
- `ResearchSpecification` gains `brief: SpecBrief | None` (goal, decision_use, objectives,
  briefing), absent from the fingerprint when empty (the spec's rule for a declaration not made).
  This is a compiler version bump, so older runs are not reinterpreted.
- The introduction prints it as typed blocks (no numbers, RD0's design facts). `AnalysisInputs`
  carries goal, decision_use and objectives with AOC3's hypotheses, by `material_rules` (a design is
  Class B).
- Tests: a compiled spec keeps the goal; the introduction prints it; a changed goal changes the
  modules' input fingerprint; an empty brief leaves the fingerprint unchanged.
- Depends on `assumptions-and-open-answer-coding#AOC3`, and on CQ1.

**CHN3. Research questions traced.**
- The run records its `research_trace` at start (with the gaps it already records). The
  RESEARCH_QUESTIONS chapter prints per RQ its measures by wording and the question-table anchors
  that hold them; an RQ no finding answers says so.
- Tests: the measured and unmeasured RQs of `test_product_acceptance.py:271` read the same in the
  chapter; a dangling link is named.
- Depends on CHN1.

**CHN4. Design Research in the design chapter.**
- Accepted items from the `design_research` ledger rows of the run's Design Revision lineage: subject,
  finding, source and bundle SHA. They are labelled "Externí kontext k návrhu", never respondent
  evidence (ADR 0021).
- Test: a design built from an accepted item prints it with its bundle seal; a dismissed item does not
  print.
- Depends on `research-lead-workbench#7b`.

**CHN5. The audience in full.**
- `spec.audience` keeps the description and the filters as stated (bounds as typed design facts);
  `_audience_sentence` prints them beside the method chapter's "applied".
- Test: filters stated and applied are printed apart. A compiler bump.

**CHN6. The audit names every artifact.**
- The audit appendix lists the aggregate, specification, dataset and map (id + SHA-256), and the
  Sociomapping draft when the run made one. The coverage record names that draft as a separate
  document.
- Test: the audit of a run with Sociomapping lists its artifact id.

**CHN7. The workbench on recorded models.**
- `aia_executors.workbench` composes the analysis and report steps over `RecordedModels`
  (`recorded_models.py`), with the template's analysis nodes switched on for the workbench only.
- `recorded_models.py` gains recordings for the eight research_agent tasks, so a Lead card runs a
  worker at zero cost. Local and test only; `layer_check` forbids a deployment naming it (as
  `deep_research_recorded`).
- Tests (`apps/executors/tests/test_research_lead_workbench.py`): a fictional run on the workbench
  registry completes with a `research_internal_docx`; every recorded call is priced 0 in the usage
  ledger.
- Pairs with `research-lead-workbench#12a`.

**CHN8. Interpretation Research woven into the body** (CQ4 = Q58 (b), settled 2026-10-21 via
/pmstatus Q58: "The literature should be woven into the body of the report").
- One document. When an Interpretation Research run is marked "Použít ve zprávě", the internal draft
  is composed with its sealed bundle: each accepted finding is placed in the body section its target
  bears on (the research question, set, object or module the run was over: RESEARCH_QUESTIONS,
  OBJECTS, a map chapter, IMPLICATIONS), beside the respondent findings, never merged into them.
- Every woven statement is labelled external context (the L class), cites its finding and source
  from the bundle, and is never respondent evidence: it carries no ledger ref, enters no admitted
  claim and no module's input (ADR 0021). Its section's manifest (CHN1) names the bundle by id and
  seal. Unmarking the run composes the next draft without it.
- `research_internal_docx_with_research` (`contextual_report.py:864`) is retired for new reports:
  nothing composes one after this lands. Stored ones stay downloadable and approvable as they are.
- Tests: a draft with a marked run holds each accepted finding in its target's section, labelled L,
  with no ledger ref; a rejected finding does not print; no `research_internal_docx_with_research` is
  stored for a new report; a stored one still downloads by its artifact id; the census (CHN11a)
  refuses a number in a woven statement that is not the bundle's own quote.

**CHN9. The methodology chapter from the run's pins.**
- It prints the aggregation's `RoundingSpec` and methodology version, the support rule (Kish n
  floor), the pinned Sociomap methods with their register status, and the run's QC warnings
  (`evidence-integrity#3`). The fixed reading guidance stays, marked `fixed`.
- Test: a run pinning `aia-sociomap-5` names it and its status.
- Depends on `evidence-integrity#3` for QC.

**CHN10. A module without a supported finding blocks the draft** (MVPQ-04, settled 2026-10-20).
- The owner's answer (`mvp-owner-decisions.md:87-99`): "Block the report until resolved." While any
  of the eight modules is BLOCKED or has no supported finding, composition of the internal report,
  its approval and every export (internal DOCX and PDF, with literature, client) refuse. That refusal
  is `evidence-integrity#9b`; the existing all-eight-modules rule (`report.py:156-157`) is the same
  rule stated once.
- The structured "no finding, reason and coverage gap" diagnostic (`evidence-integrity#9a`) is
  diagnostic output only. It never satisfies the gate, is never counted as a finding, and no draft is
  composed with it in a chapter.
- This chunk carries the diagnostic to where a person meets the refusal:
  - Analýza and Výsledky show each blocked module's diagnostic: the module, its reason codes and what
    would resolve it (a same-data retry through `retry_analysis`, a changed design, more data), with
    `artifact-analysis#ANL4`;
  - the refusal itself, in the API error and on Zpráva (`artifact-report`), names the module and gives
    the diagnostic's reason and way out in its own words.
- SEGMENTS (G17): until `segment-maps-and-drilldown#10` gives it an admitted producer, a study whose
  SEGMENTS module has no supported finding does not reach a draft. That is the decided behaviour, not
  a gap this chunk works around; no "not requested" bypass is planned without a new owner decision.
- Tests: a run with one module BLOCKED stores no `research_internal_docx`, and composition, approval
  and every export refuse by name; the refusal's body carries the module, its reason codes and the way
  out; Analýza and Výsledky show the diagnostic; a diagnostic patched into a chapter as a finding is
  refused by the citation gate.
- Depends on `evidence-integrity#9a`, `#9b`; `artifact-analysis#ANL4`.

**CHN11a. The number census** (new work).
- `domain/report/validation.py` validates the refs a block declares explicitly (`_prose_refs`,
  `_data_refs`: unknown, suppressed, interval-less client estimates). It does not scan a paragraph's
  or a table cell's text for numbers, so a number typed as text passes it today. Scanning text is new
  code, and this chunk owns it.
- Over the stored document model (RD5a), every numeric token in a paragraph, callout, table cell,
  caption or chart label is put in one of three accepted provenance classes:
  - (a) **an admitted evidence-ledger ref**: the token is printed from a ref the ledger admits (a
    `NumberCell`, a KPI, a caption's base n, a chart series);
  - (b) **a value derived from the stored Sociomap artifact**: a pair's signed r, n and Kish n, the
    credibility metrics (split-half agreement and its threshold, reliable pairs, the uncertainty
    radius), object, profile and donor counts, Stress-1 (`.planning/evidence/editor-spike-2026-10-21.md:53-55`,
    paths P7-P9, `application/report_maps.py`). The token is tagged `map:<artifact_id>` and must equal
    the value the artifact holds. Whether these become ledger refs stays open as OQ-ED1
    (`artifact-sociomap`); the census accepts this class until OQ-ED1 is answered and changes with it;
  - (c) **a design or document-control number with typed provenance**: n, scale points, question
    numbers, dates, version and page numbers, written from a typed specification field or the
    document's metadata (RD0's design facts), each naming its field.
- A token in no class fails, named with its section and block. Numbers are not required to be ledger
  refs beyond class (a).
- Tests: each of the four sample reports passes; a number typed into a paragraph fails; a map value
  that differs from its artifact fails; a design number without its field fails.
- Depends on `report-delivery#RD5a`; class (b)'s tags on the editor spike's P7-P9 regions.

**CHN11. The chain over HTTP** (the acceptance test, part 1).
- Extends `tests/acceptance/test_acceptance_harness.py:245-316`. A fictional study is walked over
  HTTP with recorded models:
  1. brief saved;
  2. Design Revision;
  3. run on fictional fieldwork;
  4. analysis;
  5. internal DOCX.
- It reads the stored document model (RD5a) and asserts:
  - every section is present with the source CHN1 names;
  - each hand-off chunk's output reaches the draft:
    - CHN2: the brief's goal, decision_use and objectives in the introduction;
    - CHN3: each research question's measures and table anchors in the research-questions chapter;
    - CHN4: the accepted Design Research item, labelled external context, with its bundle seal;
    - CHN5: the audience's stated description and filters beside those applied;
    - CHN6: the aggregate, specification, dataset and map ids in the audit;
    - CHN8: with an Interpretation Research run marked, its accepted findings in their body sections,
      labelled external (L), and no separate with-research document stored;
    - CHN9: the run's pinned methods and support rule in the methodology chapter;
    - CHN10: the same walk with one module BLOCKED stores no draft, and the refusal carries the
      module's diagnostic;
    - RD5a: the stored document model renders to the downloaded DOCX's bytes;
  - every explicit ref passes `domain/report/validation.py` (refs only; it scans no text), and every
    numeric token passes CHN11a's census in one of its three classes;
  - design facts are typed blocks;
  - the usage ledger holds no paid row.
- One record line in the harness (`mvp-acceptance-harness#6`). It is AC-08's and AC-15's evidence on
  this path, and reuses `mvp-acceptance-harness#16`'s per-number walk; it does not duplicate it.
- Depends on CHN1, CHN2, CHN3, CHN4, CHN5, CHN6, CHN7, CHN8, CHN9, CHN10, CHN11a and
  `report-delivery#RD5a`. Once `evidence-integrity#9b` lands, the walk reaches a draft only if the
  fictional design's SEGMENTS module has a supported finding, so it also depends on
  `segment-maps-and-drilldown#10` (G17).

**CHN12. The chain in a browser** (the acceptance test, part 2).
- `tools/ui_workbench/draft_report_journey.mjs`, after `make ui-workbench` + `make ui-fixtures`, at
  1440 px:
  - Zadání typed;
  - the scripted Lead's `analyze_brief` card approved on recordings;
  - Návrh, Dotazník, Cílová skupina and Dimenze accepted;
  - Vzorek ready;
  - Spustit výzkum;
  - Průběh to done;
  - Výsledky, Sociomapa and Analýza read;
  - Zpráva shows the draft;
  - the DOCX downloaded and its manifest checked as in CHN11.
- It fails on any paid usage row or a request to a path the unit served. It is the browser line of
  `mvp-acceptance-harness#10`, kept apart from CHN11's HTTP line.
- Depends on CHN7, CHN11 and each artifact's journey chunk.

## 5. Order

1. CHN7 (the workbench can make a draft at all), CHN6, CHN5, CHN9.
2. With RD5a: CHN1, then CHN11a.
3. CHN2 (with AOC3, after CQ1), CHN3, CHN4 (with 7b), CHN8 (Q58: woven into the body) and CHN10 (with
   `evidence-integrity#9a`, `#9b`; MVPQ-04 is settled).
4. CHN11, once every chunk of steps 1-3 and `segment-maps-and-drilldown#10` have landed.
5. CHN12 last; it grows with the artifact journeys.

## 6. Owner questions about the draft document's shape

**CQ1. Which sections must a draft research document contain at MVP?** Open (Q55).
- (a) Today's internal report as composed (§2), with its gaps closed: the brief, the full audience,
  traced RQs, the run's methods.
- (b) (a) plus the chapters already planned to be added: assumptions (RD9), coding (RD10), and the
  literature woven into the body when chosen (CHN8, Q58).
- (c) V2's seven-part document (`fixture.ts:375-396`): Shrnutí a rozhodnutí; Cíle a odpovědi na
  výzkumné otázky; Klíčová zjištění; Sociomapa; Interpretace a doporučení; Metodika a omezení;
  Příloha. Today's chapters are mapped into it.

**Recommendation: (b), in today's order.** Every chapter has a producer and a test. V2's order is
reachable later through RD6's section moves, without a second composer.

**CQ2. Who writes the narrative sections?** **Settled 2026-10-21 via /pmstatus Q56: (b).** Code
writes the first draft; the report writer (`lead-orchestration#LO9b`) and the Lead then propose
tracked changes a person accepts (RD6, `artifact-report#RPT6`). The options as asked: Q13 settled how a Lead's edit reaches a report: tracked or
direct, per researcher. The editor is Q19's spike.
- (a) Code only: the draft is composed from the admitted module texts, as today, with no rewrite
  path.
- (b) Code composes the first draft. The report-writer worker (`lead-orchestration#LO9b`) and the Lead
  then propose rewrites as tracked changes that a person accepts (RD6), every number a ref.
- (c) The Lead writes each narrative section itself, from the admitted claims, as the draft.

**Recommended and chosen: (b).** The draft stays reproducible from its sources (CHN1), and the wording
improves through accepted, recorded edits. (c) makes the first draft a model's output with no
deterministic baseline to compare an edit against.

A module with no supported finding is not an open question here: MVPQ-04 settled it on 2026-10-20
("Block the report until resolved"), and CHN10 plans it. CQ3 is withdrawn; the remaining questions
keep their numbers.

**CQ4. Does the draft carry the literature chapter?** **Settled 2026-10-21 via /pmstatus Q58: (b),
against the recommendation below.** One document: "The literature should be woven into the body of
the report." CHN8 weaves the findings into the body sections, labelled external; the separate
with-research document is retired for new reports, stored ones stay downloadable. The question as
asked: today it is a separate variant composed on request (G2).
- (a) Two documents, as today: the draft without literature, and the variant with it, once an
  Interpretation Research run is marked "Použít ve zprávě".
- (b) One draft: it gains the literature chapter when a run is marked, and loses it when unmarked.

**Recommendation (not taken): (a).** Each approval binds to one document (`requestStored`), and the two evidence
bases stay visibly apart. The Report artifact shows both and names which is which.

## Doc follow-up

- `mvp-master-plan.md` §3: list this plan and the eleven artifact plans. Their chunks need register
  rows in `mvp-execution-contracts.md` (named in the PR body). `tools/master_check.py` fails until
  they are there.
- `mvp-owner-decisions.md`: open, CQ1 (Q55) and QQ1 (artifact-questionnaire, Q53); settled 2026-10-21
  via /pmstatus, CQ2 = Q56 (b), CQ4 = Q58 (b), SQ1 (artifact-sample) = Q54 (b) and RQ1
  (artifact-results) = Q52 (a); CQ3 withdrawn (MVPQ-04 settles it).
- `docs/migration/mvp-acceptance.md`: CHN11 and CHN12 as the draft-report chain's lines under AC-08,
  AC-13 and AC-15.
- `CLAUDE.md` § 2, when CHN1 and CHN7 land: `Section.sources` and `report_sources`; the workbench's
  recorded analysis and agent recordings.
