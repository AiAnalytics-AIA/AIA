---
status: in-progress
chunks:
  - "[ ] RD0. Build the client deliverable's gate the owner set (MVPQ-09): no \"Interní dokument\" source, no drill-down content, no number without an admitted claim"
  - "[ ] RD1. The client report PDF: extend `RENDERABLE_REPORTS`, the PDF is approved with its DOCX"
  - "[x] RD2. A reader for the approval ledger: "approved by whom, when" for a report and a snapshot"
  - "[ ] RD3. The Approve and Export panel: what is approved and by whom; exports after approval; the slot in the Report artifact"
  - "[ ] RD4. The map snapshot: an approvable object rendered server-side from the stored map and camera parameters, never browser bytes; one ledger shape"
  - "[ ] RD5. Report draft revisions: a separate draft counter, tracked changes per paragraph; a report edit never reopens fieldwork"
  - "[x] RD5a. The report's document model stored and served (W2, before RD5 and RD7): the ReportDocument as JSON beside each DOCX under the same fingerprint, with stable paragraph ids and claim refs, read by a VIEW_RESULTS route"
  - "[ ] RD6. The accept destinations for the report writer, the map interpreter and the straight-liner flags: an artifact type, the composer input and its fingerprint; and, before any semantic report edit exists, the ADR with its deterministic admission rule that ADR 0026 decision 4 requires"
  - "[ ] RD7. A sentence-level claim check: a sentence that claims a comparison with no admitted claim blocks approval, the refusal naming it"
  - "[ ] RD8. The producer of a client report is the run that composed it, not whoever first downloaded it"
  - "[ ] RD9. The report's assumptions chapter (W3, MVPQ-02): each tracked assumption with its status and its admitted or cited support, and nothing else"
  - "[ ] RD10. The report's open-answer coding chapter (W3, MVPQ-02): the codebook version, the coded counts as admitted claims with suppression named, and the method's limits"
  - "[ ] RD11. Deep Research context in the client report: accepted findings as cited context in its research-context chapter, labelled external, never respondent evidence (MVP-26)"
  - "[ ] RD12. Export of a run's per-question tables as CSV and XLSX, every cell an admitted claim for the surface (D-41)"
---
# Report delivery: approval, export and the map snapshot

What makes a report deliverable: the approvals, the export panel, the client PDF, the snapshot and the worker accept paths. Written 2026-10-19 from `.planning/evidence/mvp-master-traces/trace-3-evidence.md`.

**Owner: S3.** Takes the gap rows G34, G35 (accept paths), G16 (accept destinations) and interfaces I12, I13, I14 of `mvp-master-plan.md` §6.1 and serves AC-13, AC-08 and gate I-3.
Every chunk below is **open**; a chunk is built from this file, not from the master plan.

## Decisions this plan carries (settled by the owner; not re-asked)

- Separate approvals for the internal report, the client report and each map snapshot; DOCX and PDF become available only after approval (F17).
- No unconditional second person: whether the producer may approve follows the client's existing self-approval setting (F17, withdrawn 2026-10-19).
- The client report is **DOCX and PDF**, carries only approved maps and labelled modelled and client-reported numbers and no analysis prose. Its gate is the one the owner set on 2026-10-20 (MVPQ-09), replacing "the evidence audit and the legal source-use gate": before a client deliverable can be approved, no source marked "Interní dokument", no drill-down content and no number without an admitted claim; **no separate legal-rights review** in the MVP. Dropping the PDF or weakening this gate is a scope override and needs the owner's explicit yes.

## Chunks

**RD0. Build the client deliverable's gate the owner set (MVPQ-09, 2026-10-20)**  
Three deterministic checks before approval, each refusing by name: no cited source marked "Interní dokument"; no drill-down content; no number without an admitted claim. No separate legal-rights review step: a source-class check is not a legal-rights determination, and the MVP does not claim one. A scientific check beyond admitted support stays the methodology owner's to add. Tests: a client report citing an internal source, carrying a drill-down field or an unadmitted number is refused by name and cannot be approved.

**RD1. The client report PDF: extend `RENDERABLE_REPORTS`, the PDF is approved with its DOCX**  
The client report is DOCX only today (`report_variants.py:78`).

**RD2. A reader for the approval ledger: "approved by whom, when" for a report and a snapshot**  


*RD2, done (`feature/report-approval-reader`):* `ArtifactRepository.approval_record` reads an artifact's newest
`APPROVED` ledger row within its scope: when, the approver's name (display name, else e-mail, else `None` for a
person the store no longer knows: unknown, never a guess), the producer, whether it was self-approved and under which
self-approval rule, and the note (`test_an_approval_names_who_approved_and_under_which_rule`,
`test_an_approver_the_store_no_longer_knows_is_named_by_nothing`). The internal report's status, its document, the
client report's document and the approve route answer it as `approval` beside `review_state` (null for a draft;
`by_you` for the asker; `test_a_person_approves_a_runs_stored_report_once_and_only_that`). The web reads it in words
(`lib/artifacts/report.ts` `approvalWords`: the day in Prague) on Zpráva's doc bar. A map snapshot's approval reads
the same once RD4 chooses its ledger shape; the with-literature variant's status does not carry it (retired by Q58).

**RD3. The Approve and Export panel: what is approved and by whom; exports after approval; the slot in the Report artifact**  
S1 hosts the slot (`research-lead-workbench` 21), same wave. Tests: approvals name the exact artifact fingerprint; a stale-version download is refused; both self-approval settings; an unauthorised download is refused. Today drafts download freely and approval follows the download (`research.py:2395-2449`); the panel makes the client export follow approval. Interfaces I12.

**RD4. The map snapshot: an approvable object rendered server-side from the stored map and camera parameters, never browser bytes; one ledger shape**  
The existing approval writes subject `artifact` (`artifact_repository.py:568`) and M3 names `map_snapshot`; one is chosen and the other removed. S2 supplies the deterministic figure function. Interfaces I13.

**RD5. Report draft revisions: a separate draft counter, tracked changes per paragraph; a report edit never reopens fieldwork**  
The prototype's D6. The counter against ADR 0016's revision semantics is an owner clarification below.

**RD6. The accept destinations for the report writer, the map interpreter and the straight-liner flags: an artifact type, the composer input and its fingerprint**  
S3 defines the type, S1 writes the worker against it (`lead-orchestration#LO9b`). Interfaces I14.

**Prerequisite (ADR 0026 decision 4, Accepted):** semantic report edits get no command until their own ADR and a deterministic admission rule exist (a report is composed from admitted claims and frozen on approval). That the feature is wanted is settled (MVP-12); writing the ADR and the rule is this chunk's first step, and a wording edit never reopens completed fieldwork (an invariant, `RD5`).

**RD7. A sentence-level claim check: a sentence that claims a comparison with no admitted claim blocks approval**  
The prototype shows it (scenario M); the evidence validation checks numbers only. A new rule; its strictness is the owner's (MVPQ-09, 2026-10-20): it **blocks approval**, never a flag the reviewer may approve past, and the refusal names the sentence.

**RD8. The producer of a client report is the run that composed it, not whoever first downloaded it**  
With self-approval off, the reviewer who opens it first cannot approve it today ◇.

**RD9. The report's assumptions chapter (W3)**  
Each assumption of `assumptions-and-open-answer-coding#AOC1` with its status, the person's accept that set it, and its support: admitted claims by reference, cited Deep Research findings as context labelled external. A status with no accepted decision or no support is not printed as established. Test: a report built from an assumption set to supported without support is refused by the composer.

**RD10. The report's open-answer coding chapter (W3)**  
The codebook version, each code's count as an admitted claim with its suppression stated, and the method's limits (`AOC4`); modelled answers are labelled modelled. Raw answer text is not printed as evidence. Test: a count not in the claim ledger cannot be composed.

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

- `open-items.md`: CR-5 is closed by `04ed258f` (number it closed, or not at all).
- `CLAUDE.md` § The map, `CompleteReport` entry: the report card's origin part reads the run's
  origin kinds (fictional, modelled, unknown, mixed), never a fixed "Modelovaná data".
