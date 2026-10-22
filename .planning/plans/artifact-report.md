---
status: in-progress
chunks:
  - "[x] RPT1. Zpráva's contract as data: view operations, pointable ids (section, paragraph, figure, claim) and V2's interaction contract"
  - "[x] RPT2. The document first: the draft rendered in the pane from its stored document model, paragraphs with claim chips opening the inspector, figures in place"
  - "[x] RPT3. The doc bar and the Approve and Export slot: which document, its draft number and state, approval as a modal naming it, exports after approval (split 2026-10-22: RPT3a, RPT3b)"
  - "[x] RPT3a. Approval on the document being read: Schválit in the pane's doc bar for the version shown, internal or client, one owner of the version approved; the report card keeps downloads only"
  - "[x] RPT3b. Exports after approval: decided 2026-10-22, not built: the owner answered Q73 (c), downloads stay free before approval"
  - "[x] RPT4. Záznam pokrytí, outside the text: what the report does not hold and why, from the chain manifest"
  - "[ ] RPT5. Draft revisions: the draft counter and the editor's version history, a report edit never reopening fieldwork (changed 2026-10-22: on the editor, RPT8)"
  - "[ ] RPT6. The Lead and the report writer on the draft (replaced 2026-10-22 by RPT9 and RPT10)"
  - "[ ] RPT7. Journey: Zpráva at 1440, 1100, 768 and 390 px, a fictional run's internal draft, zero paid jobs (extended by RPT9's suggestion step)"
  - "[ ] RPT8. The editor is Zpráva's main surface: the stored draft opened in ONLYOFFICE Docs (Q35), the researcher editing directly, every number a locked, tagged ledger ref checked on save (RD6, ADR 0035; split 2026-10-22: RPT8a-d)"
  - "[ ] RPT8a. Every printed number a locked content control tagged with its source (the editor spike's F-ED1): ledger values in prose, table cells, captions (part 1); KPI tiles, figures, the evidence appendix, suppressed counts, and the map, design, run and bundle spans (part 2)"
  - "[ ] RPT8b. The save census: an edited DOCX refused when it loses or changes a tagged control or breaks the numeric-token rule (F-ED1), a pure check over the stored document model"
  - "[ ] RPT8c. The editor routes behind AIA_ONLYOFFICE_URL (unset: off): the config with its JWT and the docs ticket, the signed document URL, the callback storing a save as a new draft once the census passes (the hosting contract, report-editor-hosting)"
  - "[ ] RPT8d. The pane opens the stored draft in the editor when it is configured; the read-only document stays where it is not"
  - "[ ] RPT9. The Lead edits the same document: inline suggestions as tracked changes under the Lead's own name, with why, accepted or rejected one by one or all; direct edits per the researcher's setting (Q13) still attributed; every edit through the edit ops, every number a ledger ref passing the sentence check before accept"
  - "[ ] RPT10. Literature by the Lead: Interpretation Research proposed on a plan card (target, QUICK or STANDARD depth, STANDARD by default, cost), approved by the researcher, findings woven into the text with their sources (Q58); the panel's own start, depth and refresh removed once typed starts exist (Q48, LO5a.3), its findings readable beside the text"
---
# Artifact: Zpráva (Report)

Umbrella: `research-lead-workbench#21` (with Analýza). The delivery rules are
[`report-delivery.md`](report-delivery.md); the chain that fills the draft is
[`artifact-chain-to-draft-report.md`](artifact-chain-to-draft-report.md). Anchors `@ 25f26232`;
prototype `@ 9b50963f`.

## 1. What it is, and its single job

**Its job: the draft research document, readable in place, approved as exactly the version a person
read.**

V2: `ReportArt` (`InterpretStages.tsx:103-162`).
- The doc bar: the "Fiktivní data" flag, "Interní zpráva · koncept N · neschváleno", Omezení,
  Schválit (disabled while changes are pending) and Klientská zpráva….
- The article: sections r1-r7 (`fixture.ts:375-396`), each paragraph an `Item` with claim chips
  (`:129-131`), the figures (`:133-140`) and a footer with draft, state, run and revision.
- Below it, "Záznam pokrytí (mimo text zprávy)": segments not done, coding state, the Lead's quick
  asks, the client report refused for a fictional run, and the export note.
- Contract `CONTRACTS.report` (`fixture.ts:415`): `propose(report, ops)`,
  `evidence.check(sentence)`, approval by a person.

## 2. What exists today

- `CompleteReport` (`CompleteReport.tsx:132`): version, format and variant as `Segment`s and `Select`
  (`:355, :369, :389`); "Schválit" (`:438`, no confirm, audit B22).
- `InternalReport` (`ExecutionSteps.tsx:1493`) shows the provenance; `ReportHolds` (`:1567`).
- Routes (`routers/research.py`):
  - `GET …/report` (`:1888`), `…/report/download` (`:2132`) and `…/report/pdf/download` (`:2064`);
  - `…/report/context` (`:2281`, `:2391`), `…/report/client/download` (`:2487`) and
    `POST …/report/approve` (`:2553`).
- `lib/report-status.ts`.
- **No document model is stored.** The worker renders DOCX bytes and drops the `ReportDocument`
  (`apps/executors/src/aia_executors/report.py:101-146`); `Paragraph.id` is optional
  (`domain/report/model.py:87`). This is F-ED3, `report-delivery#RD5a`.

## 3. Gaps

| # | Gap | Kind |
|---|---|---|
| P-1 | The document in the pane from the stored model (`report-delivery#RD5a`) | needs a new API (owned there) |
| P-2 | Claim chips per paragraph (the ledger is in the model) | needs a new API (RD5a) |
| P-3 | Approval modal naming the document (Q33, `input-interactions#6`, B22), and the Approve and Export panel (`report-delivery#RD3`, RD2's reader) | needs a new API (owned there) |
| P-4 | The client deliverable's gate (`report-delivery#RD0`), the client PDF (`#RD1`) | needs a new API (owned there) |
| P-5 | Draft counter and tracked changes (`report-delivery#RD5`) | needs a new API (owned there) |
| P-6 | The Lead's edits (`report-delivery#RD6`; Q13's tracked-or-direct setting; the editor is Q19, spike `research-lead-workbench#33`) | needs an owner decision (Q19) and a new API |
| P-7 | The sentence-level claim check (`report-delivery#RD7`) | needs a new API (owned there) |
| P-8 | Záznam pokrytí: what the report does not hold (`artifact-chain-to-draft-report#CHN1`) | needs a new API (the manifest) |
| P-9 | Chapters still to come: assumptions (`report-delivery#RD9`), coding (`#RD10`), Deep Research in the client report (`#RD11`) | needs a new API (owned there) |
| P-10 | Lead targets (G11) | needs a new API (the target grammar) |

## 4. The Lead on this artifact

- **View operations:** `open_stage(report)`, `focus(target)`, `show_tracked_changes(on|off)` and
  `show_variant(internal|client)` (display; which stored document is shown). Literature is woven
  into the internal draft (CQ4 = Q58, `artifact-chain-to-draft-report#CHN8`); a stored
  with-literature document stays downloadable.
- **Pointing:** `report:section:<id>`, `<id>` the composer's own section id (`intro`, `ch-design`,
  `ch-1`..`ch-8`, `literature`, `methodology`, `ch-method`, `ch-questions`, `ch-native-map-<n>`,
  `app-questionnaire`, `app-evidence`, `app-audit`; `artifact-chain-to-draft-report` §2), `report:para:<id>` (RD5a's stable ids), `report:figure:<id>` and
  `claim:<ref>`. `data-aia` is `report.<section>` (`InterpretStages.tsx:126`).
- **Edit operations** (RD6, after its ADR; every number stays a ledger ref):
  - Text: a paragraph rewrite whose ref set is unchanged.
  - Structure: merge (refs united), split (refs divided), section move, and a copy edit across
    paragraphs.
- **Workers and cards:**
  - the report writer (`lead-orchestration#LO9b`), a proposal card, its changes per paragraph;
  - the claim check, deterministic: a lookup, no card.
- **Inline proposals:** tracked changes per paragraph, accepted or rejected by a person.

## 5. Inputs and outputs

- **Reads:** the composed report, its document model (RD5a) with its ledger, the approval ledger
  (RD2), the stored report variants (`report-status.ts`).
- **Hands on:** the approved DOCX and PDF, by artifact id + SHA-256 (`requestStored`'s
  `X-AIA-Artifact-Id`), and the approval as a ledger row. Project memory reads the approved state
  (`lib/memory.ts` `runLabels`).

## 6. Input interactions

- B21 (version, format, variant), B22 (approval), C5 (a change reaching every client, for the
  Lead's cross-client note).
- Primitives: `Segmented`, `RadioCard` and an approval modal (I7b).

## 7. Chunks

**RPT1. Contract.** `lib/artifacts/report.ts`. Depends on `research-lead-workbench#14`, `#16`.

**RPT2. The document first.**
- The pane renders the stored model's sections, paragraphs, tables and figures as HTML in the
  report's print order, with claim chips. The DOCX stays the deliverable.
- Tests: Vitest: every chip resolves in the ledger; a block kind with no renderer says so.
- Depends on `report-delivery#RD5a`.

*RPT1 and RPT2, done (`feature/report-document-pane`):*
- `apps/web/src/lib/artifacts/report.ts` (pure): the stored document model's types (contract
  `aia-report-document-1`, refused otherwise), the pointable ids through the registry's `aiaId` --
  `report:<section id>`, `report:<section id>.<n>` for a block, `report:<block id>:<ref>` for a number's first
  chip in its block (the report's own kind: `claim:` is Analýza's, `claim:<module>:<claim_id>`, #605; none for a
  ref outside the id grammar, e.g. one carrying an answer's wording) -- and how a ref reads: the stored text only, a
  suppressed ref "potlačeno", an unknown one "?", an unknown grade or support unknown, never good.
  The view operations stay the registry's (`open_stage`, `focus`, `show_diff`); `show_tracked_changes` and
  `show_variant` wait for RD5 and RPT3 and are asked of the coordinator then.
- The web reads the serializer's own output: `packages/aia_core/tests/fixtures/report_document/internal.json`,
  pinned by `test_the_web_reads_the_document_model_this_writes` (rewrite with
  `AIA_WRITE_REPORT_DOCUMENT_FIXTURE=1`), read by `report.test.ts` and `ReportDocumentView.test.tsx`.
- `ReportDocumentView` on Zpráva (the report view's panel, first): every section and block in print order with
  its `data-aia`, no two elements sharing one; numbers as chips opening the claim in the item inspector (beside the draft in a wide pane, a
  sheet in a narrow one); tables without the rows the DOCX removes, with their count; a chart's numbers as a
  table (the DOCX draws the chart); a map figure's caption (the image is in the DOCX). Each route answer in
  words: not stored before RD5a, refused, none for a reader the internal draft is not for (403).
- Journey: `tools/ui_workbench/report_journey.mjs` at 1440, 1100, 768 and 390 px on the workbench's recorded
  run; zero paid jobs. RPT7 extends it.
- Not yet: the draft is first in the report view, but the stage still opens with the complete-report card and
  the run's notices above it; RPT3's doc bar replaces that card's place.

### Revision of 2026-10-22: Zpráva becomes the editor

The owner, relayed by the coordinator (2026-10-22): "in the last step Zprava, we need to rethink this,
this is where the document editor should live"; the literature panel "should be in the hands of the
lead researcher and the smarter model"; and, on Q56, "i want the suggestions to be in the text, sort of
like google docs has the suggestions feature". This revision reconciles that with what is decided:

| Decision | What it fixes here |
|---|---|
| Q35 | ONLYOFFICE Docs is the report editor (`research-lead-workbench#33`) |
| Q13 | per researcher, the Lead's edits arrive as suggestions or as direct edits |
| Q56 | code writes the first draft; the Lead proposes tracked changes |
| Q58 | literature is woven into the body (`artifact-chain-to-draft-report#CHN8`) |
| Q69 (a) | the Lead's study notes stay out of the draft (`report-delivery`, Q69) |
| ADR 0035 | every number stays an admitted ledger ref, enforced at the sentence (RD7) |
| Q44, Q46, Q47 | the Lead offers Interpretation Research targets; QUICK and STANDARD, STANDARD by default; it may chain fieldwork then IR |
| Q48 / rlw 26f.1 | the Deep Research start buttons go once typed starts exist (`lead-orchestration#LO5a.3`, DRL-8); their panels stay as readers |

What changes:
- **RPT3** splits. RPT3a (approval on the document being read) comes first, ahead of the editor; RPT3b
  (exports after approval) is closed as decided: Q73 (c), downloads stay free (2026-10-22).
- **RPT5** keeps the draft counter, now over the editor's saved versions (RPT8), still never reopening
  fieldwork.
- **RPT6 is replaced** by RPT9 (the Lead in the document) and RPT10 (literature by the Lead). Its tests
  move with them: a merge's refs are the union, a typed digit is refused, a sentence refused by RD7 is
  marked at the sentence.
- **RPT7** gains RPT9's suggestion step.

Order: RPT3a → RPT8 → RPT9 → RPT10 → RPT5 → RPT7 (RPT3b decided, not built: Q73 (c)).

Dependencies:
- RPT8: the ONLYOFFICE Docs integration (`research-lead-workbench#33`'s go; a self-hosted Document Server
  beside the develop stack, which is an operations change the coordinator schedules); `report-delivery#RD5a`
  (done) and `#RD6` (every number a locked, tagged content control, finding F-ED1); OQ-ED1 for the map's values.
- RPT9: RPT8; the edit operations (ADR 0029); `report-delivery#RD6`, `#RD7`; `lead-orchestration#LO9b`.
- RPT10: `lead-orchestration#LO5a.3` (typed Deep Research starts); `artifact-chain-to-draft-report#CHN8`.
- RPT3a: nothing new; it lands on today's pane.

**RPT3a. Approval on the document being read.** "Schválit" moves into the pane's doc bar, on the version
the pane shows (internal or client), through the same confirmation dialog (`approvalQuestion`); the
report card keeps the downloads. One component owns "the version approved", so the version read is the
version approved by construction. Tests: the doc bar approves the version shown and reads it again; the
card offers no approval; a client version is approved with no download; journey at the four widths.
Why (Findings, 2026-10-22, below): syncing a card and a pane that each held a client version failed four
ways.

*RPT3a, first part (`feature/report-docbar-approval`):* the pane's doc bar offers "Schválit k předání
klientovi" on the client version it shows, to a reader who may review and only while that version is not
approved; the dialog names that version (`approvalQuestion`) and what its file carries (`reviewLine`),
`POST …/report/approve` sends its id once (the button held while in flight), and the server's answer
updates the document in place, never reloading it. A question, a flight and a refusal belong to the
version they named: another document on screen shows none of them. The pane then fires
`aia:report-approved` with the server's answer, and the report card says what was approved without
approving: the card no longer approves the client report at all
(`ReportDocumentView.test.tsx` "approved on the document being read, in the doc bar (RPT3a)";
`ExecutionSteps.test.tsx` "offers the client report only for modelled data, says why when refused, and
leaves its approval to the doc bar", "hears an approval of another run as nothing (RPT3a)").

*RPT3a, second part (`feature/report-docbar-internal-approval`):* the internal draft is approved in the doc
bar too ("Schválit pro interní použití"). Approving it also approves its PDF, so the run's report is read when
the person asks, never remembered: the question names the PDF as that report states it now
(`pdfStatesReview`); a report naming another version than the one shown, or none, or a failed read is said
in words and nothing is asked. An internal draft the pane cannot show (stored before its document, or
refused) is approved on its notice as the version the run names, as the card approved it before. The card
approves neither the internal nor the client report: it says where they are approved, hears the pane and
reads the report again, so it follows the approved PDF being made (`ReportDocumentView.test.tsx` "approves
the internal draft it shows, naming the PDF the approval renders as the run states it at the ask…", "asks
nothing while the run's report names another version, and says why…", "approves an internal draft it cannot
show on the version its run names…"; `ExecutionSteps.test.tsx` "says the internal draft approved in the doc
bar once the pane answers…"; `report_journey.mjs` "approval in the doc bar, none on the card"). 

*RPT3a, third part (`feature/report-with-literature-in-pane`), closing it:* the report with a completed
literature review is a document of the pane too ("Zpráva s rešerší", one per completed Interpretation
Research of the run, read for a reader who may review). Its document model is stored beside its DOCX when it
is prepared (`contextual_report.py` `CONTEXT_REPORT_DOCUMENT_ARTIFACT_TYPE`, `contextual_report_document`,
RD5a's `store_document_beside`; a draft stored before gets it on its next preparation) and read by
`GET …/runs/{id}/report/context/document?deep_research_run_id=` (409 `context_report_not_prepared`,
`report_document_not_stored`). It is prepared, read and approved in the doc bar, its question naming the
review and the PDF as the variant's status states it at the ask. The card approves nothing: it keeps the
downloads and says where each report is approved; a version approved elsewhere is told to it too
(`test_analysis_executor.py` `test_native_ai_study_connects_a_populated_map_to_admitted_report_inputs`;
`test_report_variant_api.py` `test_the_document_is_the_prepared_drafts_and_says_when_none_was_stored`;
`ReportDocumentView.test.tsx` "reads, prepares and approves the report with a completed literature
review…"; `ExecutionSteps.test.tsx` "…and leaves its approval to the doc bar").

**RPT3b. Exports after approval.** Decided 2026-10-22, not built: the owner answered Q73 (c), keep
today's free downloads. A draft's DOCX and PDF stay downloadable before approval, each file stamped
KONCEPT until its version is approved (RD2). F17's "available only after approval" is superseded for
downloads; approval still names the exact version (RPT3a).

**RPT8. The editor is the surface.** The stored draft opens in ONLYOFFICE Docs (Q35) inside Zpráva's pane;
the researcher edits it directly. Every number is a locked, tagged content control naming its ledger ref,
checked on every save (the spike's save check: whole numeric tokens per paragraph); a save that changes
one is refused at the sentence (ADR 0035, RD7). A save is a new draft (RPT5), never a new run. The read-only
pane of RPT2 stays as the fallback where the editor is not configured. Test: a save that edits a number is
refused; a save that edits prose stores a new draft with every ref intact; the DOCX round trip keeps every
ref (the spike's count before and after).

*RPT8a, part 1 (`feature/report-locked-number-controls`):* `ooxml.locked_inline(paragraph, tag)` wraps what is
written inside it in one inline `w:sdt` with `w:lock sdtContentLocked` and `w:tag` the source. A value in prose
(P1: its number, interval, grade mark, disclosure and "orientační"), a table's number cell and its interval line
(P2, the interval line tagged `<ref>#interval`) and a caption's base n (P4, tagged `<ref>#n`) are each one
control; the prose and labels around them stay editable (ED-R1's direction). python-docx's `Paragraph.text`
does not read inside a control, so the client-source reader reads a control's runs too
(`document_text.paragraph_text`, reader `docx/2`): a past AIA report uploaded as a client source keeps its
numbers. The brief's attachment reader stays the unit's (parity), which reads none. The three report contracts move (`aia-internal-report-14`,
`aia-client-report-5`, `aia-contextual-report-10`), so a draft rendered before is never reused for one an editor
opens (`test_report_docx_locked_numbers.py`). Left for part 2 and RPT8b, from review: the KPI tile through the
one locked writer (write_value), digits in cross-reference labels and footnote numbers (furniture the census
must know), and a ref printed more than once or in two forms (prose holds the interval in its control, a cell
in `#interval`): RPT8b compares the saved controls with the stored document rendered again as a multiset of
(tag, text), so a deleted or changed duplicate is found without an id, and a moved paragraph is not a
change. Whether ONLYOFFICE keeps a long `w:tag` as written is checked when RPT8c first opens a draft.

**RPT9. The Lead in the document.** The Lead, on its own model (STUDY_LEAD), edits the same document
through the edit operations:
- **Suggestions (default, Q56, Q13):** each edit lands in the text as a tracked change under the Lead's
  own author name, with when, and a short note saying why. Insertions and deletions are marked in place.
  The person accepts or rejects one suggestion, or all. There is never a separate list or panel to
  compare against the text.
- **Direct edits (the researcher's Q13 setting):** applied at once, still shown afterwards as the Lead's
  change in the history.
- A suggestion touching a number passes the ledger and sentence check (ADR 0035) before it can be accepted;
  a typed digit is refused; a merge's refs are the union; a split divides them.
- The Lead's study notes never reach the draft (Q69 (a)). When the Lead edits the report document, keep
  that path in `domain/edit_ops` and the report modules' own apply step, so the import contract "no
  report path reads the Lead's notes (Q69)" (#719) still holds. If RPT9 ever needs something from
  `research_lead`, move that piece into `edit_ops` rather than loosening the contract.

Acceptance (journey step): the Lead proposes two edits; both show in the text as its suggestions; one is
accepted and one rejected; the version then approved (RPT3a) holds exactly the accepted one. Open: how
ONLYOFFICE's track-changes mode carries an edit written by AIA under the Lead's author name (the spike's
OOXML revisions, `w:ins` / `w:del` with `w:author`), proved on a fictional draft before RPT9 starts.

**RPT10. Literature by the Lead.** The Lead offers an Interpretation Research target (Q44) on a plan card:
the target, the depth (QUICK or STANDARD, STANDARD by default, Q46), the cost; it may chain fieldwork then
IR (Q47). The researcher approves the card; the accepted findings come back woven into the text with
their sources, labelled external (Q58, CHN8), as the Lead's suggestions (RPT9). The panel's own start,
depth and refresh controls go once typed starts exist (Q48, LO5a.3); what a run found stays readable
beside the text (Záznam pokrytí or the inspector), never a second start path.

**RPT3. Doc bar and approval.** Tests: approval sends the artifact id shown; a stale version is
refused. Depends on `report-delivery#RD2`, `#RD3`, `input-interactions#6`.

*RPT3, the approval modal (`feature/report-approval-modal`; input-interactions#6, B22, Q33):* "Schválit pro interní
použití" and "Schválit klientskou zprávu" on `CompleteReport` ask first, in the shared `AskDialog`: the document and
its variant (the review it carries), the stored version and its format (`approvalQuestion`, `lib/report-variant.ts`),
that approval cannot be undone, then the card's own line on what the file will carry (never promised by the
question). The focus starts on Zrušit (I7), Esc answers the dialog alone (D21), and "Schválit" sends exactly the id the
question named. Tests: `report-variant.test.ts` (`approvalQuestion`), `ExecutionSteps.test.tsx` (every approval
confirms the dialog naming its version, the client's included; the context variant's focus, Esc and Zrušit);
`report_journey.mjs` at 1440 and 390. Still open: the doc bar and the export panel (RD2's approval line, RD3).

**RPT4. Záznam pokrytí.** Test: a design that asks for a segment comparison lists "Segmenty:
neprovedeno". Depends on `artifact-chain-to-draft-report#CHN1`.

*RPT4 (`feature/report-coverage`):* "Záznam pokrytí (mimo text zprávy)" under the stored draft in
`ReportDocumentView`, outside the article, from `lib/artifacts/report-coverage.ts` (`coverageRecord`, pure): the
run's recorded answerability (`ResearchRun.answerability`: each gap by its question, verdict and why, a segment
comparison as "Segmenty: neprovedeno", pending questions as not verified) and the stored manifest's `unread` (CHN1:
each output no section read, in words by step or type). Neither recorded (a run from before answerability, a -1
document) reads "nezaznamenáno", never covered. Tests: `report-coverage.test.ts`, `ReportDocumentView.test.tsx`
("Záznam pokrytí, outside the text"); `report_journey.mjs` at 1440, 1100, 768 and 390. V2's other lines join with
the chunks that make them: the coding state with `report-delivery#RD10`, the client report's refusal and the
export note with `#RD3`; the Lead's quick asks with RPT6.

**RPT5. Draft revisions.** Depends on `report-delivery#RD5`.

**RPT6. The Lead and the writer.** Tests: a merge's refs are the union; a typed digit is refused; a
sentence refused by RD7 is marked at the sentence. Depends on `report-delivery#RD6`, `#RD7`,
`lead-orchestration#LO9b`, and the editor choice (`research-lead-workbench#33`).

**RPT7. Journey.**
- At 1440, 1100, 768 and 390 px, on the chain's recorded run (`artifact-chain-to-draft-report#CHN7`):
  - the draft read in the pane;
  - the Lead focusing `report:para:<id>`;
  - approval through the modal, by a second fictional member where self-approval is off.
- Zero paid jobs. 768 and 390 px depend on `research-lead-workbench#26b`-`#26d`.

## Findings

- **F19 (research-lead-workbench, from #778's journey): fixed on `fix/report-states-the-brief`.** The
  internal draft never said what the person asked for: "Návrh studie" printed only how the study
  measured. Now `NativeSources.brief` (`analysis_results.Brief`: the Design Revision's goal and decision
  use, each `None` when empty) is carried on `RunAnalysis`, and `compose_design_sections` opens with "Cíl
  studie" and "Rozhodnutí, které má výzkum podpořit" (the Brief's own title for the field, web `cs.ts`
  `decisionTitle`) in the internal report and the report with literature, the chapter naming the Design
  Revision as its source (`RunSource("metadata.design_revision_id")`, CHN1). An empty field reads "V zadání
  neuvedeno." (code's words, never a template's placeholder), so not stated is never read as not shown;
  a character XML cannot hold is left out (a vertical tab becomes a line), so a pasted brief never fails
  the draft. The
  contracts move (`aia-internal-report-15`, `aia-contextual-report-11`). Deliberately not done, from
  review: the cover keeps the study's record, because a brief's title is the template's "Nový výzkum"
  until edited and a reused design carries the earlier study's; the client report is unchanged, because
  its internal-marker scan would refuse a person's own brief words (e.g. a goal naming an AI product).
  Tests: `test_report_design.py` `test_the_chapter_opens_with_what_the_brief_asked_for_before_how_it_was_measured`,
  `test_an_empty_brief_field_is_said_not_stated_never_left_out`, `test_a_control_character_in_the_brief_never_fails_the_report`; `test_analysis_executor.py`
  `test_native_research_start_and_worker_complete_the_composed_analysis_graph` (the stored draft's design
  chapter and its source).

- **F-RPT-1 (2026-10-22): two owners of "the client version" cannot be kept in step.** On
  `fix/report-client-pinned-read` (`df1fb276`, `0bb8ebbe`, pushed, no PR), the report card and the pane
  each held a client version and were synced by events; two `/code-review high` passes found that the
  card could approve a version the person had not read:
  1. a toggle after a download put the card back on an older pinned draft;
  2. the card missed the pane's one-shot event when it mounted after the read, and could not approve;
  3. a version from another run leaked across a change of run;
  4. the pane, pinned to the first version it read, never showed a version approved through the card.
  Cause: two components owning one decision. Fix: RPT3a (one owner, approval on the document read).
  Test that would have caught it: RPT3a's "the version approved is the version shown" at every width.

## 8. Owner questions

- Q73 (decided 2026-10-22, (c)): downloads stay free before approval; RPT3b is closed, not built.
- Hosting ONLYOFFICE Document Server beside develop (RPT8): an operations change, for the coordinator to
  schedule with the owner (AGPL obligations named in the spike).


The editor choice (Q19) stays open. Settled 2026-10-21 via /pmstatus: CQ1 = Q55 (b), today's
report with its gaps closed, plus RD9/RD10, plus literature when chosen, in today's order; CQ2 = Q56 (b), code drafts and the Lead proposes tracked changes (RPT6);
CQ4 = Q58 (b), one document with the literature woven into its body (CHN8). A module with no supported finding is settled: MVPQ-04 blocks composition, approval and export
(`artifact-chain-to-draft-report#CHN10`).

## Doc follow-up

- Register this plan and its chunks.
