---
status: in-progress
chunks:
  - "[ ] RD0. The client deliverable's checks the owner set (MVPQ-09): an \"Interní dokument\" source, drill-down content, a number without an admitted claim, each shown as a warning in the approval dialog and recorded with the approval, never refusing (changed 2026-10-22)"
  - "[x] RD1. The client report PDF: extend `RENDERABLE_REPORTS`, the PDF is approved with its DOCX"
  - "[x] RD2. A reader for the approval ledger: "approved by whom, when" for a report and a snapshot"
  - "[ ] RD3. The Approve and Export panel: what is approved and by whom; exports after approval; the slot in the Report artifact"
  - "[ ] RD4. The map snapshot: an approvable object rendered server-side from the stored map and camera parameters, never browser bytes; one ledger shape"
  - "[ ] RD5. Report draft revisions: a separate draft counter, tracked changes per paragraph; a report edit never reopens fieldwork"
  - "[x] RD5a. The report's document model stored and served (W2, before RD5 and RD7): the ReportDocument as JSON beside each DOCX under the same fingerprint, with stable paragraph ids and claim refs, read by a VIEW_RESULTS route"
  - "[ ] RD6. The accept destinations for the report writer, the map interpreter and the straight-liner flags: an artifact type, the composer input and its fingerprint; and, before any semantic report edit exists, the ADR with its deterministic admission rule that ADR 0026 decision 4 requires"
  - "[ ] RD7. A sentence-level claim check: a sentence that claims a comparison with no admitted claim is marked at the sentence, in the pane and the approval dialog, never blocking (changed 2026-10-22)"
  - "[x] RD8. The producer of a client report is the run that composed it, not whoever first downloaded it"
  - "[ ] RD9. The report's assumptions chapter (W3, MVPQ-02): each tracked assumption with its status and its admitted or cited support, and nothing else"
  - "[ ] RD10. The report's open-answer coding chapter (W3, MVPQ-02): the codebook version, the coded counts as admitted claims with suppression named, and the method's limits"
  - "[ ] RD11. Deep Research context in the client report: accepted findings as cited context in its research-context chapter, labelled external, never respondent evidence (MVP-26)"
  - "[x] RD12. Export of a run's per-question tables as CSV and XLSX, every cell an admitted claim for the surface (D-41)"
---
# Report delivery: approval, export and the map snapshot

What makes a report deliverable: the approvals, the export panel, the client PDF, the snapshot and the worker accept paths. Written 2026-10-19 from `.planning/evidence/mvp-master-traces/trace-3-evidence.md`.

**Owner: S3.** Takes the gap rows G34, G35 (accept paths), G16 (accept destinations) and interfaces I12, I13, I14 of `mvp-master-plan.md` §6.1 and serves AC-13, AC-08 and gate I-3.
Every chunk below is **open**; a chunk is built from this file, not from the master plan.

## Decisions this plan carries (settled by the owner; not re-asked)

- Separate approvals for the internal report, the client report and each map snapshot; DOCX and PDF become available only after approval (F17).
- No unconditional second person: whether the producer may approve follows the client's existing self-approval setting (F17, withdrawn 2026-10-19).
- The client report is **DOCX and PDF**, carries only approved maps and labelled modelled and client-reported numbers and no analysis prose. Its checks are the ones the owner set on 2026-10-20 (MVPQ-09), replacing "the evidence audit and the legal source-use gate": a source marked "Interní dokument", drill-down content and a number without an admitted claim; **no separate legal-rights review** in the MVP. Since 2026-10-22 they warn and never refuse: the owner gave that explicit yes in the Zpráva session ("Relax RD0 too", then "Warnings for all of it" for the unadmitted number as well), RD0 below.

## Chunks

**RD0. The client deliverable's checks the owner set (MVPQ-09, 2026-10-20; warnings since 2026-10-22, below)**  
Three deterministic checks before approval, each refusing by name: no cited source marked "Interní dokument"; no drill-down content; no number without an admitted claim. No separate legal-rights review step: a source-class check is not a legal-rights determination, and the MVP does not claim one. A scientific check beyond admitted support stays the methodology owner's to add. Tests: a client report citing an internal source, carrying a drill-down field or an unadmitted number is refused by name and cannot be approved.

*RD0, two of its three checks (`feature/client-deliverable-gate`):* `domain/report/client_gate.py` judges the stored
document model a client DOCX was rendered from (RD5a), at approval, so the version approved is the version judged:
`drill_down_content` (a respondent's verbatim quote, or a claim at `ClaimLevel.INDIVIDUAL`) and `unadmitted_number`
(a ref the stored ledger does not hold, or a ledger not on the client surface), each naming its block; a version with no
stored document, or one of an older contract (no claim levels), is `gate_unrecorded`, never passed. The stored document
is `aia-report-document-3` (each ledger entry's `level`); a document of an older contract is stored again on the next
download, not reused. `POST …/report/approve` answers 409 `client_gate_refused` with every refusal in
`details.refusals`. Tests: `test_client_gate.py`; `test_a_client_report_carrying_drill_down_content_cannot_be_approved`,
`test_a_client_document_of_an_older_contract_is_stored_again_on_download`,
`test_a_client_draft_with_no_stored_document_is_not_approvable`.

*RD0, changed 2026-10-22 (the product owner, in the Zpráva session: "lets get rid of these strict gates", the
relaxation reaching the client report too, and asked again about the unadmitted number alone: "Warnings for all of
it"):* the checks stay, their answer changes. `client_gate`'s findings (`domain/report/client_gate.py:28-31, 46 @
a25d2435`: `drill_down_content`, `unadmitted_number`, `gate_unrecorded`, and the "Interní dokument" check when RD11
gives it a source) are shown in the approval dialog, each naming its block, and never refuse
(`apps/api/src/aia_api/routers/research.py:3263 @ a25d2435` is the 409 that goes): `POST …/report/approve` approves
whatever they say and records the findings shown in the approval's ledger row, so who approved past which warning is
on record. 409 `client_gate_refused` goes. Tests become: a client report carrying drill-down content is approved with
the warning named in the dialog and in its ledger row; one with no stored document says "nelze ověřit" and is
approvable. Built in `artifact-report#RPT8d`'s PR set. What it changes beyond this plan: a client report could
then be approved while it prints a number its ledger does not hold for the client surface, which CLAUDE.md
("Evidence is a capability") and ADR 0024 §4 state can never reach a client; composition still admits only
client-facing claims, so this fires on a composer defect or a stale contract. Both documents change in that PR's
Doc follow-up.
The third check, `internal_source_cited`, waits for a chapter that cites a client source (RD11): no client report cites
one, so it would read nothing. RD0 stays open until it lands.

*RD0's change, built (`feature/client-report-warnings`):* `client_gate` returns findings (`GateFinding`), never
refusals; `application/client_report.py` `client_gate_findings` replaces `require_client_gate` and `ClientGateRefused`
(a version with no stored document is the `gate_unrecorded` warning, "nelze ji ověřit"); a ledger off the client surface is the
`ledger_not_client_facing` warning, and the block checks still run beside it (the PM, 2026-10-24: a warning about the
whole never hides one about a block). `approve_report` records them
on the approval's ledger row: `approval_decisions.warnings` (JSON, nullable: NULL where nothing is checked; migration
`3abba24ff47c`), read back as `ApprovalRecord.warnings` and answered in every approval's `approval.warnings`. `GET
…/report/client/document` answers the version's `warnings` before the approval; the pane's question names each with its
block ("Upozornění (n): …; Schválením je berete na vědomí"), and the doc bar says "přes n upozornění" after. 409
`client_gate_refused` is gone. Tests: `test_a_client_report_carrying_drill_down_content_is_approved_with_its_warning_on_record`,
`test_a_client_draft_with_no_stored_document_is_approved_as_unverifiable`, `report.test.ts` (approvalWords, warningsWords),
`ReportDocumentView.test.tsx` ("names the client checks' warnings in the question…").

**Findings (RD0).**
- *The prose-number half of G63 is not built.* A client report's prose is written by code alone and states design and
  method numbers: the scale's ends and the planned n (`application/report_design.py`), the day of the owner's decision
  (`domain/evidence/report_lift.py` `reader_note`). A digit scan of prose would refuse every client report, so a number
  reaches the gate only as a ref until those facts are typed blocks (G63); a sentence claiming a result without a ref is
  RD7's. Numbers printed as `TextCell` (no client chapter prints one) pass unchecked for the same reason.

**RD1. The client report PDF: extend `RENDERABLE_REPORTS`, the PDF is approved with its DOCX**  
The client report is DOCX only today (`report_variants.py:78`).

*RD1, done (`feature/client-report-pdf`):* `research_client_docx` is in `RENDERABLE_REPORTS`, so a `report_pdf` job
renders exactly the stored client report it names, and its PDF records `report_kind: client` from its DOCX
(`aia_executors.report.ReportPdfExecutor`; the run's own report's stays `internal`). `POST …/report/client/prepare` asks
for the draft's PDF where asking can start one (never refused for it), as preparing the report with literature does; so
approving the client report finds its draft's rendering ready and asks for the approved version's PDF under its review
(`report_approval.approve_report`, unchanged). `GET …/report/client/document` (and prepare) answer `pdf` and
`approval_renders_pdf`; `POST …/report/client/pdf` asks again, composing nothing (404 while none is stored);
`GET …/report/client/pdf/download` serves the rendering of exactly the version the DOCX download names
(`AIA-…-klient-<version>-koncept|schvaleno.pdf`, `X-AIA-Artifact-Id`). The PDF artifact keeps the type every report
PDF has (`research_internal_pdf`, the `report_pdf` template's target); its `report_kind` says whose it is. Tests:
`test_report_variant_api.py` `test_the_client_report_has_a_pdf_and_it_is_approved_with_its_docx` (fails before: no
draft PDF counted as ready, so the approval promised none); `test_report_pdf_executor.py`
`test_the_client_report_is_rendered_and_its_pdf_says_it_is_the_clients`. The download buttons are
`research-lead-workbench#31`'s.

**RD2. A reader for the approval ledger: "approved by whom, when" for a report and a snapshot**  


*RD2, done (`feature/report-approval-reader`):* `ArtifactRepository.approval_record` reads an artifact's newest
`APPROVED` ledger row within its scope (and `approval_of` reads it through that one query): when, the approver's
display name (`None` without one or for a person the store no longer knows; never their e-mail, which a report's
readers are not shown), the producer, whether it was self-approved and under which self-approval rule, and the note
(`test_an_approval_names_who_approved_and_under_which_rule`,
`test_an_approver_the_store_no_longer_knows_is_named_by_nothing`). The internal report's status, its document, the
client report's document and the approve route answer it as `approval` beside `review_state` (null for a draft;
`by_you` for the asker; an approval without its row is 409 `report_review_unrecorded`;
`test_a_person_approves_a_runs_stored_report_once_and_only_that`,
`test_the_client_report_is_read_as_its_document_beside_its_docx`). The web says it in words with the server's
`approved_on` (`lib/artifacts/report.ts` `approvalWords`, report.test.ts "who approved, in words (RD2)") on Zpráva's doc
bar (ReportDocumentView.test.tsx "who approved it (RD2)"). A map snapshot's approval reads the same once RD4 chooses its
ledger shape; the with-literature variant's status does not carry it (retired by Q58).

**RD3. The Approve and Export panel: what is approved and by whom; exports after approval; the slot in the Report artifact**  
S1 hosts the slot (`research-lead-workbench` 21), same wave. Tests: approvals name the exact artifact fingerprint; a stale-version download is refused; both self-approval settings; an unauthorised download is refused. Today drafts download freely and approval follows the download (`research.py:2395-2449`); the panel makes the client export follow approval. Interfaces I12.

*Q73 (c), the owner, 2026-10-22:* downloads stay free before approval; a draft's files say KONCEPT until their
version is approved. "Exports after approval" is not built (`artifact-report#RPT3b`, closed as decided), and line
28's "DOCX and PDF become available only after approval" is superseded for downloads. Approval moves to the
document being read, in Zpráva's doc bar (`artifact-report#RPT3a`).

*RD3, G66 (`feature/report-export-panel`):* `POST …/report/approve` answers `report_kind` (`internal`,
`with_review` or `client`, `application/report_approval.py` `REPORT_KINDS`), and `internal_only` is false for the
client report, which said `true` before. Test: `test_the_approved_client_report_downloads_stamped_and_is_read_once`
(and the internal approval test). The panel and the client export after approval stay open.

*RD3, the client draft read in AIA (`feature/report-client-pane`):* `POST …/report/client/prepare` composes and
stores the client report as its download would, once, and answers its document model; nothing leaves. Zpráva's
pane offers "Interní zpráva" / "Klientská zpráva" for a modelled run only, one document at a time, and
"Připravit klientskou zprávu" while none is prepared; prepare answers the document of exactly the version the
download hands over (`application/client_report.py` `prepare_client_report`, no bytes read). The report card reads
that version (GET …/client/document) and approves it with no download first. Tests:
`test_the_client_report_is_prepared_to_be_read_without_a_download`; `ReportDocumentView.test.tsx` ("the client
report, read here before it is approved"); `ExecutionSteps.test.tsx` ("approves the client report a person
prepared and read in AIA, with no download first"); `report_journey.mjs`. Next: deliverable downloads refused until
approval (F17, "no unapproved internal-draft exception").

**RD4. The map snapshot: an approvable object rendered server-side from the stored map and camera parameters, never browser bytes; one ledger shape**  
The existing approval writes subject `artifact` (`artifact_repository.py:568`) and M3 names `map_snapshot`; one is chosen and the other removed. S2 supplies the deterministic figure function. Interfaces I13.

**RD5. Report draft revisions: a separate draft counter, tracked changes per paragraph; a report edit never reopens fieldwork**  
The prototype's D6. The counter against ADR 0016's revision semantics is an owner clarification below.

**RD6. The accept destinations for the report writer, the map interpreter and the straight-liner flags: an artifact type, the composer input and its fingerprint**  
S3 defines the type, S1 writes the worker against it (`lead-orchestration#LO9b`). Interfaces I14.

**Prerequisite (ADR 0026 decision 4, Accepted):** semantic report edits get no command until their own ADR and a deterministic admission rule exist (a report is composed from admitted claims and frozen on approval). That the feature is wanted is settled (MVP-12); writing the ADR and the rule is this chunk's first step, and a wording edit never reopens completed fieldwork (an invariant, `RD5`).

**RD7. A sentence-level claim check: a sentence that claims a comparison with no admitted claim (marks it since 2026-10-22, below)**  
The prototype shows it (scenario M); the evidence validation checks numbers only. A new rule; its strictness is the owner's (MVPQ-09, 2026-10-20): it **blocks approval**, never a flag the reviewer may approve past, and the refusal names the sentence.
*Changed 2026-10-22 (the owner, as RD0 above; ADR 0035, amended):* a sentence the check refuses is marked at the sentence, in the pane and the approval dialog; it never blocks approval.

*RD7a, the check (`feature/sentence-claim-check`):* `domain/report/sentence_check.py` `sentence_findings` reads a stored
document model: each paragraph, list item and callout of a section written from an analysis module (its section
sources), split into sentences. Text and word lists are compared folded (lower case, no diacritics), so inflections
and capitals read alike. A sentence claims a comparison when it holds "než", a comparative in any inflection (vyšší,
vyššího, nižší, větší, menší, lepší, horší, delší, kratší, dražší, mladší, starší; "-ější"; častěji, silněji…), a
superlative ("nej…", not the negations nejsou / nejde / nejistota… nor nejen / nejprve / nejdřív / nejspíš /
nejpozději), "oproti", "ve srovnání", "v porovnání", "rozdíl…", "převyšuje", "převažuje" or "převládá" (not
většina / menšina, a share; "dvou nejvyšších bodů" is a metric's name); a sentence that asks ("…?", or "zda" / "zdali" /
"jestli": a research question or a study's goal restated, as the workbench's fictional draft does) claims nothing and
is not marked. **The word lists are PROVISIONAL** (the PM,
2026-10-24): AIA's starting reading, for the methodology owner (Aram) to review; the case file names a known
over-mark ("na větším vzorku", a comparative about the method). It is
supported when it prints a ledger number: a `value` inline, a `cross_ref` to a figure or table, or the printed text of
a number its block cites (analysis prose writes its numbers as text and cites their claims on the paragraph), the
numbers compared parsed, so a decimal point or comma and any thousands space read alike; a suppressed number supports
nothing. A sentence ends at its stop or after a closing quote or bracket that follows it. Anything else is `unsupported_comparison`, naming its block, its sentence's index
and its text. Not read: the composer's own text (map reading guides, method, the question chapter's intro, the
questionnaire), a lead-in and a `control` block. A reading rule, deliberately plain, not a methodology: it flags a
comparison stated without a number and says nothing of whether a cited number bears it out. The internal draft's,
the report with literature's and the client report's document routes answer the findings in `warnings` (the client's
beside RD0's), and `approve_report` records them on the approval's ledger row (RD0's mechanism); a version with no
stored document (a report-editor version, one stored before RD5a) records `NULL`, nothing checked, never "nothing
found". Migration `3abba24ff47c`'s downgrade now refuses only while a row holds at least one warning (`[]` holds none),
changed in place: Alembic runs a revision's downgrade from its file, so no later migration could change what it counts
(`test_approval_ledger.py`, the two `…downgrade` tests on PostgreSQL). Cases: `tests/fixtures/report_sentences/cases.json`. Tests: `test_sentence_check.py`; `test_research_api.py`
`test_a_sentence_comparing_in_words_alone_is_marked_and_approved_on_record`. RD7b, the pane marking the sentence and
the approval dialog naming it, follows.

**RD8. The producer of a client report is the run that composed it, not whoever first downloaded it**  
With self-approval off, the reviewer who opens it first cannot approve it today ◇.

*RD8, done (`fix/client-report-producer`):* the client report is stored on whoever's read first asks for it
(`application/client_report.py` `_client_report`), but code composed it from the run, so it is stored with
`ArtifactRepository.put(by_person=False)`, which records no person as its producer and can name no one else (the
producer is still never a caller argument). Its approval names the run's starter as its producer through
`approve(co_producers=)`, as the internal report's worker-written producer is the run's `triggered_by` (now on
`WorkflowRepository.get_run`): with independent review on, the starter may not approve it and the reviewer who
downloaded it first may. A draft stored before this keeps its downloader as producer until the run's sources change.
Test: `test_research_api.py` `test_the_client_report_is_the_runs_work_not_its_first_downloaders` (fails before: the
starter's approval went through and the downloader's was refused). No run reaches a client report without a starter: the one writer of a run row records `triggered_by=scope.actor_id` (`workflow_repository.py:630 @ ee20550f`), and every scope refuses an empty `actor_id` (`domain/scope.py:724 @ ee20550f`); the column is nullable only since the first workflow migration (`20260922_e0e14f1b5e3c`), and no row is written without it. Pinned by `test_the_client_report_is_the_runs_work_not_its_first_downloaders`, which reads the run's starter back.

**RD9. The report's assumptions chapter (W3)**  
Each assumption of `assumptions-and-open-answer-coding#AOC1` with its status, the person's accept that set it, and its support: admitted claims by reference, cited Deep Research findings as context labelled external. A status with no accepted decision or no support is not printed as established. Test: a report built from an assumption set to supported without support is refused by the composer.

**RD10. The report's open-answer coding chapter (W3)**  
The codebook version, each code's count as an admitted claim with its suppression stated, and the method's limits (`AOC4`); modelled answers are labelled modelled. Raw answer text is not printed as evidence. Test: a count not in the claim ledger cannot be composed.

## Q69 (a): the Lead's study notes stay out of the draft report (the owner, 2026-10-22)

"Even though it's a draft it should be as client ready as possible." No path that composes, stores,
renders or approves a report reads the Lead's turns, its files or its notes: their tables
(`study_lead_turns`, `researcher_leads`, `researcher_lead_revisions`, `researcher_lead_memories`), their
repositories, or the Lead's turn artifact (`research_lead_turn`, stored on the design project by
`apps/executors/src/aia_executors/research_lead.py:318-345 @ 05e475b5`, which every report module could list).
Checked 2026-10-22 @ 05e475b5: none did. Held by the import contract "no report path reads the Lead's notes (Q69)"
(root `pyproject.toml`, `make layer_check`) and by
`test_report_reads_no_lead_notes.py::test_the_import_contract_covers_every_report_module` and
`::test_no_report_module_names_the_leads_notes`; each was shown to fail on a planted read or a dropped module.
The API router is not a source (it serves the Lead's routes too and composes no report). The Lead may still
propose edits to the draft (Q56, `artifact-report#RPT9`); its notes never become the draft's text.

## Open: owner clarifications

- What the evidence audit and the legal source-use gate check (RD0).
- Settled by requirement, not asked: the report draft counter is separate from the Design Revision, and a report edit never reopens fieldwork (immutable runs, RD5).


## Execution predecessors (2026-10-20)

RD0-RD4 are W2; RD5-RD8 are W3. RD3's approval/export component and contract can land in W2;
the full Report artifact hosts it with workbench 21 in W3. A panel tested alone does not prove
the full artifact. RD6's semantic-edit ADR, immutable accept-result type and composer fingerprint
land before LO9b's report binding and any executable report-wording command. The snapshot
renderer must use the pinned methodology and stored numerical artifact; a camera edit is a view.
F17 settles approval before a deliverable download; master item 9 asks about check definitions,
not a choice to approve after download. Do not introduce an unapproved internal-draft exception.

## Cross-check additions (2026-10-20)

From the independent cross-check of the master plan against the code (`mvp-master-plan.md` §6.1, G47-G57). Anchors are `@ 085abe0`.

**RD5a. The report's document model stored and served (G50, X4).** The report steps store DOCX bytes only and discard the `ReportDocument` (`apps/executors/src/aia_executors/report.py:140-157`; `application/report.py:422`, likewise `client_report.py` and `contextual_report.py`), and `Paragraph.id` is optional (`domain/report/model.py:87`). RD5 (tracked changes per paragraph), RD7 (the sentence-level claim check), LO8's report-text context and the V2 document-first draft with claim chips have nothing to read. This chunk stores the `ReportDocument` as JSON (outline, stable paragraph ids, claim refs, ledger summary) beside each DOCX under the same fingerprint, for the internal, client and with-literature variants, and a `VIEW_RESULTS` route reads it. Test: the stored document renders to the same DOCX bytes, and paragraph ids are stable across a rerun with the same fingerprint.

*RD5a, done (Zpráva screen owner, `feature/report-document-model`):* the internal draft and the client report.
- `domain/report/document_model.py`: `document_payload` / `document_bytes` / `read_document_payload`, contract
  `aia-report-document-1`. Every section keeps the composer's id (`section-<n>` by position when it gave none);
  every block is `<section id>.<n>`, fixed once stored. The ledger carries each cited ref's printed text from
  `domain/report/numbers.py` (the functions `report_docx/blocks.py` prints with), its grade, support and origin;
  a suppressed ref carries only its reasons; an image only its SHA-256; run identifiers only in an internal kind.
  Tests: `packages/aia_core/tests/test_report_document_model.py`.
- The REPORT step stores it as `research_internal_document` beside the DOCX under the same input fingerprint,
  naming the DOCX by id and SHA-256 (`apps/executors/src/aia_executors/report.py`); a step that runs again finds
  the same document (`test_the_steps_pdf_renders_the_stored_docx_when_the_step_reuses_it`).
- `GET /studies/{id}/research/runs/{run_id}/report/document` (VIEW_RESULTS + EDIT_STUDY, as the internal draft's
  other routes): the document, the DOCX it is beside and the DOCX's review; 409 `report_document_not_stored` for
  a report composed before RD5a (its DOCX still downloads), 409 `report_artifact_invalid` for a document not
  beside this run's DOCX or of another contract (`apps/api/tests/test_research_api.py`).
- **Deviation from the test above, deliberately:** the stored form holds no image bytes (the DOCX holds them),
  so it cannot be re-rendered to the same DOCX bytes. What holds instead: it is serialized from the same
  in-memory `ReportDocument` the DOCX is rendered from, in the same step, and names that DOCX by SHA-256.
- The client report: its download (`stored_client_report`) stores the document beside the DOCX it stores or finds
  (`research_client_document`, same fingerprint); `GET …/report/client/document` (VIEW_RESULTS) reads the approved
  version's, else the newest stored draft's, and composes nothing; 409 `report_document_not_stored` for a version
  stored before RD5a (an approved one keeps its bytes and gets none). Tests:
  `test_the_client_report_is_read_as_its_document_beside_its_docx`,
  `test_a_client_report_stored_before_its_document_says_so`.
- The with-literature variant gets none: it is retired for new reports by Q58
  (`artifact-chain-to-draft-report#CHN8`); its stored DOCX stay downloadable.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

**New chunks.** RD11 (W3), already decided by MVP-26 and missing a chunk. RD12 (W3), D-41 in.

*RD12, done (`feature/question-tables-export`):* `GET …/research/runs/{run_id}/report/tables/{csv|xlsx}`
(`?document=internal`, the default, or `client`) exports the per-question tables of the run's stored report document,
read through its document route (the same checks, the same 404 and 409 answers; `EXPORT_DELIVERABLE`). The rows are
`domain/report/table_export.py` `question_rows`: the tables the composer anchors `tab-question-<n>`, one row per printed
number with the report's own text for the value, its interval where the table asks for it, the base, the evidence grade
(with "orientační" where the report prints it beside a low-support number) and "modelováno: AI respondenti z populace"
for a modelled-panel number; a table's rows left out for want of support are counted, never numbers; a question the
evidence gate refused, which has no table, is the row of the chapter's limitation callout (internal: the question and the
gate's reasons; client: how many), so no refused question is read as none. Nothing is computed or re-rounded, so every
cell is a claim that report admitted for its surface, and the client's export is the client report's alone. CSV is UTF-8
with its mark and `;` between cells, and a text cell a spreadsheet would read as a formula keeps a leading apostrophe
(numbers print U+2212, so none is touched); XLSX is one sheet of text cells, never formulas, without a guard, a character
XML cannot carry left out (`infrastructure/xlsx_writer.py`, the standard-library writer the questionnaire template now
shares, its bytes unchanged and pinned to `aia_sablona.xlsx`). The headers are every download's (`_review_headers`: the
version's id, SHA-256 and review). The internal export is the run's composed draft (koncept 1), as the internal DOCX
download is, even where a person approved an edited version of it (RPT8c); an edited version's tables wait for its
document model. 409 `no_question_tables` for a document with no question table and no refusal. The Results screen's
download control is
`research-lead-workbench#31`'s. Tests: `test_table_export.py`; `test_research_api.py`
`test_a_runs_question_tables_export_as_the_report_prints_them`.

**Existing chunks, changed.**

- **RD0 (G63, G64).** Result numbers are ledger refs; design and method facts (the planned n, scale
  ends, filter bounds) are typed blocks fed from the specification and exempt; the validator checks
  every other prose number. The "Interní dokument" mark is read from the frozen `KnowledgeSource`
  (`client-knowledge-lifecycle#K8`), and RD0 checks both deliverables.
- **RD3 (G66).** The approve response and review state carry the report's kind; `internal_only` is
  false for `research_client_docx`.
- **RD6 (D-35, Q6).** The Lead edits a report as the researcher asks: rewrite, merge or split
  paragraphs, move sections (the client report's chapters included), copy edits. **Every number stays
  an admitted ledger ref**: a merge unions the refs, a split divides them, and no typed number is
  accepted. The exact edited version is what a person approves. ADR 0035 is amended in this chunk's PR
  (ref-set equality per paragraph becomes "every number a ref"; `section_move` allowed on every
  chapter).

### After the editing and old-method answers (the owner's answers on the PM status page, 2026-10-20 20:50-21:04 UTC, relayed by the coordinator (page ids Q13 to Q18; `.planning/evidence/scope-freeze/answers-2026-10-20.md`, fourth table))

- **RD6 (page Q13: (a)).** A Lead's report edit reaches the document as the researcher has chosen:
  tracked-change suggestions by default, or direct, undoable rewrites (`lead-orchestration` § After
  the editing, departure and lookup answers). The editor is open (Wordcraft is being asked about).
- **Old-method reports (page Q17: (a)).** A report already **approved** from a `-1`/`-3` run stays
  downloadable as approved, unchanged.

## Findings (the coordinator's card review, 2026-10-20)

Found on the UI workbench at develop `237fd0a` (screenshots by the coordinator), anchored at
`242523e`. For the docs PR to number in `open-items.md`. Reproduction: `make ui-workbench` with
in-process scripted model answers and `AIA_AI_ANALYSIS_ENABLED=true`, then `make ui-fixtures`,
unless stated.

- **CR-5. The report card says "Modelovaná data" for a run of fictional respondents.**
  Anchor: `apps/web/src/components/rehome/research/CompleteReport.tsx:66 @ 242523e`, a static string
  in `reportParts` that never reads `runOriginKinds` (`lib/research-execution.ts:186-205`). Reproduce:
  `make ui-research` (fictional fieldwork), then Výsledky's report card. Consequence: a fictional run
  is labelled modelled, against the rule that every label reads the origin. Smallest fix: pass the
  run's origin kinds into `reportParts` and word the part by them (fictional, modelled, unknown or
  mixed). Test: a SIMULATED run's report card never shows "Modelovaná data".
  **Fixed in `04ed258f`** (branch `fix/report-card-origin-label`): `reportParts` takes the run's
  origin kinds (`runOriginKinds`, plus the stored report's `resultOriginKind`) and words the part by
  them through `originWords`: "Fiktivní data", "Modelovaná data", "Neznámý původ dat" (an unknown
  origin, or none stated yet), a mixed run every kind. Tests: `CompleteReport.test.tsx` "the report
  card's origin (CR-5)".

## Doc follow-up

- `CLAUDE.md`, "Evidence is a capability": after "admitted `CLIENT_FACING` under the owner's recorded lift
  (`MODELLED_CLIENT_REPORT_LIFT`, ADR 0024 §4 amendment) and the population certificate its run recorded, labelled
  modelled;" add: "Since 2026-10-22 (the product owner, "Warnings for all of it"; report-delivery RD0) the client
  gate's checks (`drill_down_content`, `unadmitted_number`, `gate_unrecorded`, and the Interní dokument check) warn in
  the approval dialog and are recorded in the approval's ledger row; none refuses. Composition still admits only
  `CLIENT_FACING` claims." Applied with RD0's change.
- `docs/architecture/adr/0024-*.md` §4: an amendment dated 2026-10-22 with the same text and the owner's words
  ("lets get rid of these strict gates"; "Relax RD0 too"; "Warnings for all of it"), applied with RD0's change.
- `CLAUDE.md` §2, the `research` router: "409 client_gate_refused" removed wherever it is described, with RD0's change.
- `open-items.md`: CR-5 is closed by `04ed258f` (number it closed, or not at all).
- `CLAUDE.md` § The map, `CompleteReport` entry: the report card's origin part reads the run's
  origin kinds (fictional, modelled, unknown, mixed), never a fixed "Modelovaná data".
