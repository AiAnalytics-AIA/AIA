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
  - "[ ] RPT8. The editor is Zpráva's main surface: the stored draft opened in ONLYOFFICE Docs (Q35), the researcher editing directly, every number code wrote a locked, tagged control whose edits are shown, never refused (ADR 0035, amended 2026-10-22; split 2026-10-22: RPT8a-d)"
  - "[ ] RPT8a. Every printed number a locked content control tagged with its source (the editor spike's F-ED1): ledger values in prose, table cells, captions (part 1); KPI tiles, figures, the evidence appendix, suppressed counts (part 2); the map, design, run and bundle spans (part 3; the map locked and tagged like the rest, the owner 2026-10-22)"
  - "[x] RPT8b. What a saved version changed: each tagged number edited or removed and each number typed outside one, shown as \"Upraveno ručně\", never refusing (changed 2026-10-22: the owner, ADR 0035 amended)"
  - "[x] RPT8c. The editor routes behind AIA_ONLYOFFICE_URL (unset: off): the config with its JWT and the docs ticket, the signed document URL, the callback storing every save as the next version (the hosting contract, report-editor-hosting); the internal draft and the report with literature"
  - "[ ] RPT8d. The pane opens the newest version in the editor from 768 px (view mode below), its doc bar naming the version and its \"Upraveno ručně\" changes; the read-only document stays where the editor is off"
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

*RPT8a, part 2 (`feature/report-locked-numbers-part2`):* the tags are one grammar, `domain/report/control_tags.py`
(builders and `parse_tag`), which the renderer writes and RPT8b's census will read. A KPI tile's value with its
marks is one control tagged with the ref, the line under it (base n, interval, "orientační") one more tagged
`<ref>#n` (P3); a chart's or a Sociomap's picture is locked, tagged `figure:<id>` (P5; its refs are the stored
figure's); every cell of an evidence appendix row is locked, tagged `appendix:<ref>#<column>` (P6: the appendix is
regenerated, never edited, ref ids hold digits, and a swapped cell is a changed one); a suppressed count in a
table's notes row or under a figure is locked, tagged `count:suppressed:<table or figure id>`, the owner a required
argument (P13). The contracts move
(`aia-internal-report-16`, `aia-client-report-6`, `aia-contextual-report-12`). Test: every sample kind
(client, final, internal, documentation), each value, number cell, KPI tile and figure tagged, each cited
ref's appendix row with an appendix, and every tag naming a source the document holds
(`test_report_docx_locked_numbers.py` `test_every_sample_kind_locks_every_ledger_number_it_prints`, `test_the_tag_grammar_reads_back_what_it_writes`). Furniture the
census must know stays unlocked: the SEQ, PAGE and TOC fields, the lists of figures and tables, and
cross-reference labels; a Sociomap caption's fit is the map's, part 3.

### Revision of 2026-10-22, evening: the researcher decides what the report says

The owner, in the Zpráva session (2026-10-22), on RPT8's save check: "lets not be so strict, at the end of the day
its the discression of the researcher what they want to include in the final report. lets get rid of these strict
gates." ADR 0035 is amended the same day: its admission rules are computed and shown, never refusing an edit or
blocking an approval. His other answers in the same session:

| Question | Answer |
|---|---|
| Build now or after the deploy | Now, behind `AIA_ONLYOFFICE_URL` (unset: off) |
| Which documents open in the editor | The internal draft and the report with literature; the client report stays composed by code |
| When an edit becomes a stored version | Every autosave the Document Server sends (its timed force-save, a close, the save button) |
| A number code wrote, edited or deleted | Allowed; marked "Upraveno ručně" in the pane and the approval dialog; never refused, never blocking |
| The client report's gate (RD0) | Relaxed too: every check a warning in the approval dialog, recorded with the approval; asked again about the unadmitted number alone: "Warnings for all of it" |
| Map values (OQ-ED1) | Locked and tagged like ledger numbers (`map:<battery>/<method>`), unlockable like them |
| Phones, under 768 px | Read-only |
| Two researchers at once | Live co-editing, ONLYOFFICE's own |
| The Lead's suggestions (RPT9) | After RPT8 works |
| Activation | The Zpráva session fixes F1 (`__Host-aia_session`); Route 53, SSM and the flag are the infra session's, on the owner's word |
| A recompose after edits (asked on /pmstatus) | (a) "Keep both, separate": the edited line keeps its history, a recomposed draft starts a line of its own, nothing merged (relayed by the coordinator, 2026-10-22) |
| Where the editor is served | Its own registrable domain, not `docs.<hostname>`: cookie tossing from it becomes impossible (#831's open finding) |
| What guards the editor's domain | ONLYOFFICE's own JWT: no docs cookie or ticket (a third-party cookie Safari blocks); every document session needs a config AIA signed; the static files public, the server-only and admin paths still refused |

The chunks, as built from here:

**RPT8a, part 3. The rest of the generated numbers locked and tagged.** Three PRs. A paragraph, callout, text cell,
table's notes or Sociomap caption fit that code writes whole from a stored source other than the ledger carries
`control`, the tag of the locked control its text prints in (`control_tags.source_tag`): the map's (P7-P9,
`map:<battery>/<method>`, the reading guide by the signed-off map its numbers come from), then the design's and the run's (P10-P12,
`design:<revision>`, `run:<run>`), then the literature bundle's and the audit's (P14, P15, `bundle:<run>`, the L-labels
inline). The lock is inline over the block's whole text (python-docx readers and the client-source reader `docx/2`
read inline controls; a block-level control would hide its paragraphs from them), the section's manifest naming the
source artifact by id and SHA-256. A lock is a guard against a stray keystroke, not a rule: ONLYOFFICE's
content-control settings unlock it and a deletion removes it. The stored document model carries each `control`
(`aia-report-document-4`). Test, per PR: every block of its chapters that prints a digit carries its source's control,
and that text sits in a locked control under the same tag in the DOCX; the contracts move.

**RPT8b. What a saved version changed ("Upraveno ručně"), never refusing.** A pure function over the stored document
model rendered again and a saved DOCX: each tagged control changed or removed (by the multiset of (tag, text), so a
moved paragraph is no change), and each numeric token typed outside a control, with the paragraph it sits in. Stored
with the version as its own small JSON; read by the pane (RPT8d) and the approval dialog. Tests: a saved DOCX with one
number retyped, one control deleted, one digit typed into prose and one paragraph moved reports exactly the first
three; a save with prose edits only reports nothing; a version with no stored model reads "nelze porovnat", never
"beze změn".

*RPT8b (`feature/report-saved-changes`):* `domain/report/saved_changes.py` compares two censuses (`compare`):
`changed`, `removed` and `added` controls by the multiset of (tag, text), paired per tag in document order, and
`typed` numbers outside every control, reported only where the save holds more of that number than the baseline
*and* holds it in a paragraph the baseline did not, so prose edited around a cover date or a heading's number is no
change, and neither is a number moved with its paragraph. No baseline is `no_baseline`, a baseline with no locked
control (rendered before RPT8a) `no_controls`: `comparable` false, never an empty list read as "beze změn". The
stored form is `aia-report-changes-1` (`changes_payload` / `read_changes_payload`, another contract refused);
RPT8c stores it beside each version, RPT8d draws it. `infrastructure/report_docx/census.py` (`census`) reads a
DOCX's body alone: controls whose tag is in the grammar, numbers outside them and outside every field's instruction
and cached result (a TOC page, a SEQ caption number an editor updates on its own). The baseline is the line's
koncept 1 as the composer stored it, which *is* the stored model rendered (the renderer is deterministic, RPT8a),
so nothing is rendered twice and a model whose figures are not in its JSON is never needed. A saved file is read as
a stranger's: `check_zip_bounds` and `refuse_dtd` before the parse, lxml without entities or network. Tests:
`test_report_docx_census.py` (`test_a_save_reports_the_retyped_the_deleted_and_the_typed_but_not_the_moved`,
`test_a_save_of_prose_edits_only_reports_nothing`, `test_a_fields_result_is_left_to_the_editor`,
`test_a_draft_rendered_without_controls_cannot_be_compared`, `test_a_saved_file_is_read_as_a_strangers`) and
`test_report_saved_changes.py`. Whether ONLYOFFICE keeps the tags as written is checked when RPT8c first opens a
draft.

**RPT8c. The editor routes, behind `AIA_ONLYOFFICE_URL` and `AIA_ONLYOFFICE_JWT_SECRET` (both unset: every route
404, the product unchanged).** ONLYOFFICE is served from its own registrable domain and guarded by its JWT alone
(the decisions above): no docs ticket and no docs cookie (`aia_api.docs_pass.DocsPasses`, `docs_pass.py:51 @
a25d2435`, and the `/session/docs*` routes go with the hosting plan's change).
- **Lines and versions.** A line starts at a composed draft: its koncept 1 is the composer's artifact, its id the
  line's id. Each save the Document Server sends is the line's next version, koncept N+1, an artifact
  (`research_internal_docx_edit` or `research_internal_docx_with_research_edit`) depending on the version it was
  saved from, with RPT8b's changes beside it and its PDF rendered when `AIA_REPORT_PDF_ENABLED` is on. A recompose
  by code (an analysis retry, a new report contract) starts a new line whose koncept 1 is the new composition, and
  never touches another line's versions (/pmstatus (a)).
- **Which line opens.** The run's line with the newest version (by its stored time) opens by default; the doc bar
  lists every line of the run and variant, each with its newest koncept, and says when an edited line rests on an
  older composition than the newest one. Approval binds the exact version shown, of whichever line.
- **One session, one key.** A line's editing session has one document key, its line id and the SHA-256 of the
  version it opened on, within ONLYOFFICE's 128 characters of `[0-9A-Za-z._=-]`. Recorded per line (a small table,
  its migration in this chunk): opened when its first config is signed, closed by a status 2 or 4 callback, or by
  the next open once no callback came for 24 hours. While it is open every config for the line carries that key, so
  a second researcher joins the same co-editing session; a status 6 force-save stores the next version without
  changing the key; the next session after a close opens on the newest version, with a new key.
- `POST …/runs/{run_id}/report/editor` (`variant`: `internal` or `context` with `deep_research_run_id`, optional
  `line`): the editor config, signed with the JWT secret: the session's key, the document URL, the callback URL, the
  person's id and display name (never an e-mail), `mode: edit` for a study member (`view` below 768 px, RPT8d),
  `customization.forcesave: true`, co-editing `fast`. The client report is refused by name.
- `GET /report-editor/document?token=…` (the Document Server's routes are outside the study tree, part 2): the version's DOCX, the token short-lived and naming that artifact alone;
  the Document Server's JWT checked as well.
- `POST /report-editor/callback?token=…`: the JWT checked (header and body); status 2 and 6 store the file, 1
  marks the session open, 4 closes it with nothing stored, 3 and 7 are logged. The file is fetched by GET from
  `AIA_ONLYOFFICE_URL`'s exact origin only, at a path under `/cache/files/` (the Document Server's own link, signed
  by its secure link with `md5` and `expires`, which Caddy lets past alone, #829), never another host or path, never
  a redirect, bounded in size, and must be a DOCX that opens; its users are
  the version's authors. Answers `{"error": 0}` once stored, an error otherwise, so the Document Server retries. A
  version already stored under the same SHA-256 is not stored twice.
- Approval (`POST …/report/approve`) takes an edited version's id; the dialog shows its "Upraveno ručně" changes.
- "Every autosave" is the Document Server's timed force-save (`services.CoAuthoring.autoAssembly`, every 5 minutes;
  the infra session's #829, `deploy/develop/docs/local-production-linux.json`).
- Tests: the config is signed and names no e-mail; an unsigned or wrongly signed callback is refused; a callback
  naming a file on another host is refused unfetched; status 6 stores koncept N+1 depending on N with RPT8b's
  changes and keeps the session's key; a second config while the session is open carries the same key; status 2
  closes it and the next config has a new key; the same bytes twice store once; a recompose after an edit leaves the
  edited line's koncept N unchanged and opens a new line whose koncept 1 is the composer's; the client report is
  refused; with the URL unset every route is 404.

*RPT8c in four PRs.* Part 1, the lines and sessions; part 2, the config and document routes; part 3, the callback
(the fetch guard, the version stored with RPT8b's changes, a Document Server restart's 403 said in words, never
stored); part 4, approval of an edited version.

*RPT8c, part 1 (`feature/report-editor-lines`):* `domain/report/editor.py` holds the rules, pure: the document key
`<line>.<version SHA-256, 40 hex>.<session number>` (`document_key`, within `[0-9A-Za-z._=-]{1,128}`), what each
callback status asks (`callback_action`: 1 open, 2 store and close, 4 close, 6 store, 3 and 7 logged, any other
refused), when an open session is joined (`reuse_session`: open, and seen within `SESSION_IDLE`, a day) and the
line that opens by default (`default_line`: newest version by stored time; ties by koncept, then id). Two tables
(migration `75f40e2e74dd`): `report_editor_versions` (a line's koncepts, unique per line by koncept and by SHA-256,
so the same bytes are never stored twice) and `report_editor_sessions` (one key per session, at most one open per
line, the people a config was signed for, and why its newest save was not stored, `last_problem`, for the pane
to say); every artifact a row names cascades to it, so client deletion needs
nothing of its own. `infrastructure/report_editor_repository.py` is their only reader and writer, scoped by the
study; `session_by_key` alone reads unscoped, for a callback, which names a key and no person.
`application/report_editor.py` (`ReportEditor.open`): the current composition's line started as koncept 1 if it has
none, the line asked for or the default, and its session: the open one joined (the line's newest version, which a
force-save under the same key holds), else one started on the newest version under a new key, an idle one closed
first; the client report, another type or another run's draft refused (`NotEditable`), a line of another run or
variant `LineNotFound`. Tests: `test_report_editor.py` (SQLite and PostgreSQL), among them a second researcher
joining under the same key, a new key after a close, a day's idle, and a recompose after an edit leaving the edited
line's koncept 2 and starting a line whose koncept 1 is the composer's.

*RPT8c, part 2 (`feature/report-editor-routes`):* `AIA_ONLYOFFICE_CALLBACK_BASE`, AIA's public https origin as the
Document Server reaches it (report-editor-hosting decision 4: the public hostname, never the internal network,
agreed with the infra session 2026-10-23), validated like `AIA_ONLYOFFICE_URL`; `Settings.report_editor_on` needs it,
the editor's origin and its secret, else both routes are 404. `aia_api/editor_tokens.py`: ONLYOFFICE's JWT (HS256
under the secret itself: the config signed, the Document Server's requests read) and AIA's URL tokens (HS256 under
a key derived from it, so neither is ever the other: a document URL names one session's one version for 30
minutes, a callback URL one session for a week; the clock passed in). `routers/report_editor.py`: `POST
…/runs/{run_id}/report/editor` (`variant` internal or context with `deep_research_run_id`, `line`, `mode` edit or
view) opens the line through `ReportEditor.open` and answers the signed config (the session's key, the document
and callback URLs on the public origin, the person's id and display name, never an e-mail, `forcesave`, co-editing
`fast`) with the run's lines; `client` is refused by name (409 `client_report_not_editable`). `GET
/report-editor/document?token=` (the Document Server's routes are not under a study: the token's session names
it, and a route under `/studies/{study_id}` is a person's, which MVP-ACCEPT AC01 sweeps as another organization)
serves the version to the Document Server alone: its JWT in `Authorization` and
the URL token both checked (403 otherwise), the session read by its key and the scope resolved for the person who
opened it, the artifact a version of that session's line (404 otherwise), `Cache-Control: no-store`. Tests:
`test_report_editor_api.py` (SQLite and PostgreSQL): the config signed as the Document Server checks it with no
e-mail anywhere, the version fetched, a second researcher under the same key, an unsigned fetch and a token signed
with the editor's own secret refused, a key no session has 404, the client report refused, every route 404 with the
public origin unset, the setting an https origin only. From review: the config's own JWT expires (`CONFIG_LIFETIME`, 12 hours); a JWT
shaped as a config (`document`, `editorConfig`) is never read as the Document Server's, and the document fetch's
must name the URL fetched (`url` or `payload.url`: its path and its query's token), so the browser's config token
cannot stand in for the Document Server; the URL token never reaches a log: `deploy/develop/Caddyfile` deletes
`token` from the query in the product's access log and the default logger, and `tools/caddy_routes.py`
(`logs_drop_token`) refuses a Caddyfile that writes it. The develop Compose file hands the API `AIA_ONLYOFFICE_CALLBACK_BASE:
https://${AIA_PUBLIC_HOSTNAME}` (the worker none); the editor stays off there until SSM sets its URL and secret
(`test_the_report_editor_reaches_the_api_on_its_public_origin_and_stays_off_until_set`). Tests: the browser's config token, a JWT for another URL, an
expired document token, a callback token, another line's version and a key no session has are each refused.

*RPT8c, part 3 (`feature/report-editor-callback`):* `POST /report-editor/callback?token=` (the Document Server's,
beside its document route; token and body optional, the body read in the route, so anything that is not a JSON
object is unsigned: 403, or 404 while off, never 422): ONLYOFFICE's JWT, which it sends once, in the body (`inBody`:
the body's fields beside `iat`/`exp`) or in the header (the body as `payload`, which it may trim), read by
`EditorTokens.read_callback`; both, when sent, agree on each of `key`, `status`, `url`, `users` that each carries,
and only those signed fields are read; the URL token naming this session, the signed key the token's (403
otherwise); each status as `callback_action` says, any other `{"error": 1}`. A session already closed takes nothing:
a late or replayed save for it is `{"error": 1}` (`session_closed`), any other status `{"error": 0}`. A save (6, or 2,
which then closes the session) is stored by `application/report_editor_saves.py` `store_save`, one at a time per line
(the line's composed row held first, as `open` does; the session read again under it): its authors each one a
config was signed for (`unknown_author`), the file's URL on the editor's exact origin under `/cache/files/`
(`infrastructure/editor_fetch.py` `allowed`, checked before any fetcher is called, `not_the_editors_file`), fetched
by `LiveSaveFetcher` (urllib3, the egress fence's newest named exit in `pyproject.toml`: no retry, no redirect, 64
MB, a 403 `document_server_restarted`, a break while the body streams `document_server_unreachable`), a DOCX that opens (RPT8b's `census`, `save_unreadable`), then koncept N+1
(`research_internal_docx_edit` / `…_with_research_edit`) depending on koncept N, produced by its first author, with
RPT8b's changes against koncept 1 beside it (`research_report_changes`); the same bytes again store nothing. A save
not stored answers `{"error": 1}` (the Document Server tries again) and stays on the session (`last_problem`), which
the config answers as `problem` for the pane to say; the next stored save clears it. Not here: the edited version's
PDF, which needs the PDF job to take an edit artifact (part 4). Tests: `test_report_editor_api.py` (SQLite and
PostgreSQL): a force-save stores koncept 2 depending on koncept 1 with the changed number named, under the same key,
and the same bytes twice once; status 2 closes and the next config has a new key; a file on another host, path or
port refused unfetched; a restarted Document Server's save not stored and said; an author no config was signed for
refused; an unsigned, wrongly signed or other-key callback 403; a version stored as its author's.
`test_editor_fetch.py`: the origin rule, and the live fetcher refusing before sending anything.

*RPT8c, part 4 (`feature/report-editor-approval`):* `POST …/report/approve` takes an edited version
(`report_approval.EDITED_REPORT_KINDS`, kind internal or with_review; `APPROVABLE_KINDS` is both), approved and frozen
as exactly that version, of whichever line; `REPORT_ARTIFACT_TYPES` stays the composed reports the 2026-10-18 freeze
migration names. Where self-approval is off, no author of any version of the line up to the one approved may approve
it (an edited version records one producer, its save's first author). `GET …/report/editor/versions/{artifact_id}`: the
version's provenance (authors, `edited_from`), its review and approval as the run's report status says them, and what it
changed, as stored beside it (`report_editor_saves.version_changes`; `changes` null for koncept 1; a version of another
run or study 404), for the doc bar and the approval dialog (RPT8d); `…/download`: exactly its DOCX with the report
download's headers (`X-AIA-Artifact-Id`, `X-AIA-Review-State`), named `schvaleno-v-aia` once approved (it keeps the
draft footer). Both answer with the editor off. `GET …/report` and the report with literature's status (`GET`/`POST
…/report/context`) name the run's approved edits of that report beside its composed draft (`approved_edits`), which an
approved edit leaves a draft; a version row whose artifact is gone is skipped there and 404 on its own route. Every author of the line is a producer for the ledger too
(`ArtifactRepository.approve(co_producers=)`): a co-author approving where self-approval is on is recorded as self-approving.
Noted, older than RPT8c: two concurrent first approvals of one report take no row lock between them (the stand-in's P3 on
#869); not changed here. Tests: `test_an_edited_version_says_what_it_changed_and_is_approved_as_itself`,
`test_no_author_of_an_edited_version_approves_it_where_self_approval_is_off`.

*RPT8c, part 5 (`feature/report-editor-pdf`), the chunk's last:* an edited version is a report the worker renders
(`report_variants.RENDERABLE_REPORTS` holds both `EDIT_ARTIFACT_TYPES`): `POST …/report/editor/versions/{artifact_id}/pdf`
asks for its PDF by the one rule (`request_pdf`), `GET …/pdf/download` serves it with the DOCX's review headers, and the
version route answers its `pdf`. Each save is tried with the review stamp as every stored report is
(`report_export.review_stamp_record`, ~200 ms a save) and keeps its composition's `report_contract`: approved, a version
whose footers the editor kept says SCHVÁLENO there, in its DOCX and its approved PDF (asked on approval where its draft
PDF is ready, `approval_asks_pdf`); one whose footers changed is served as saved, `schvaleno-v-aia`. Tests:
`test_an_edited_version_renders_its_pdf_and_approved_says_so_in_its_footers`,
`test_a_version_saved_in_the_report_editor_is_rendered_like_the_report`.

**RPT8d. The pane opens the editor.**
- 768 px and wider, with the editor configured: Zpráva's pane loads the Document Server's `api.js` from
  `AIA_ONLYOFFICE_URL` and opens the default line's newest version (RPT8c) with the config the API signed.
- Below 768 px: the newest version in the editor's view mode; with the editor off, RPT2's read-only draft, as today.
- The doc bar names the version shown ("koncept N, uloženo <kdy> · <kdo>") and its line, and lists the run's other
  lines (RPT8c). Its "Upraveno ručně" count opens the list,
  each change linked to its paragraph. "Schválit" approves that version, the dialog listing its changes and, for the
  client report, RD0's warnings.
- `next.config` CSP: `frame-src` and `script-src` add `AIA_ONLYOFFICE_URL`'s origin, and only it.
- A Document Server that does not answer leaves the read-only draft and says so, never a blank pane.
- Tests: Vitest for the config's use, the doc bar and the change list; the journey (`report_journey.mjs`) at 1440,
  1100, 768 and 390 px against a stand-in Document Server (`tools/ui_workbench`: it serves a stub `api.js` and drives
  the callback with a fictional edited DOCX), zero paid jobs. A real Document Server is checked once on develop after
  activation.

Order: F1 (its own small PR) → RPT8a part 3 → RPT8b → RPT8c → RPT8d → RD0's change → activation (infra: the
editor's own domain, its Caddy site without the docs gate, Route 53, SSM, the flag) → RPT9.

*RPT8a, part 3, the map (`feature/report-locked-facts-map`):* a paragraph, callout, text cell, table's notes or
Sociomap caption fit that code writes whole from a stored source other than the ledger carries `control`
(`domain/report/model.py`), the tag of the locked control its text prints in; `control_tags.source_tag` builds
the `map:` tag and `parse_tag` reads it back (the design's, run's and bundle's kinds join with their PRs). The renderer locks the block's whole text
inline (`ooxml.locked`), so python-docx's readers and `docx/2` still read it. `report_maps` tags every block it writes
from a stored map `map:<battery>/<method>` (P7-P9: support and credibility prose, the weak-map and method callouts, the
respondent reading, the pair table's r, n, Kish n, state and notes, the caption's fit, the methodology note beside it
left out) and the reading guide by the signed-off map its numbers come from. A ledger value inside a controlled block
is refused (`controlled_value`): a control within a control, which the client-source reader would lose. The stored document model carries each `control` (`aia-report-document-4`); the contracts move
(`aia-internal-report-17`, `aia-client-report-7`, `aia-contextual-report-13`). Test:
`test_report_map_snapshots.py` `test_every_number_the_map_writes_is_locked_under_its_map` (under `-3` and `-5`),
`test_report_docx_locked_numbers.py` `test_a_block_written_from_a_stored_source_holds_no_ledger_value`.

*RPT8a, part 3, the design and the run (`feature/report-locked-facts-design`):* the design chapter and the
questionnaire appendix lock every block printing a number code wrote from the specification (a set's scale and count,
the planned n and audience bounds) under `design:<the specification fingerprint's first 16 hex>` (Word keeps a tag to
64 characters; the manifest pins it whole; `report_design.compose_design_sections`, P10), a list's items included
(`BulletList.control`, stored since `aia-report-document-5`). The questionnaire appendix is the questionnaire as asked,
a record, so its question lists are locked whole; what the person wrote alone in the chapter (research questions, item
names, the brief) stays as it is. The method chapter and the methodology rules go under
`run:<run>` through `domain/report/controls.py` `under` / `under_blocks` (every block printing a digit, holding no
ledger value and no control yet; P11), applied where `report_chapters` assembles them; the methodology deviation the internal report
prints is under the run too. The client report locks none of these (`compose_design_sections(locked=False)`, its method
chapter as it was): it never opens in the editor, and a tag would carry the run id or the specification's fingerprint
into the client's file, which holds no identifier (review of #857). P12's refused count is the client report's and is
left as it is. The contracts move (`aia-internal-report-18`, `aia-contextual-report-14`; the client report unchanged). Tests:
`test_report_design.py` `test_the_designs_numbers_print_under_the_specification_it_came_from`, `test_report_controls.py`,
and `test_analysis_executor.py`'s composed report carrying `design:` and `run:` controls.

*RPT8a, part 3, the literature and the audit (`feature/report-locked-facts-bundle`), closing part 3:* the literature
chapter, written whole from the sealed bundle, goes under `bundle:<Deep Research run>` through `controls.under` (its
counts, dates, L-labels and seal; P14), and the audit's values under `run:<run>` (`AuditBlock.control`, P15).
`sources.with_source_audit` keeps the audit's control when it appends its rows. The stored model is
`aia-report-document-6` (the audit's `control`); the contracts move (`aia-internal-report-19`,
`aia-contextual-report-15`; the client report has neither chapter). Tests: `test_contextual_report.py`
`test_every_number_the_bundle_writes_is_locked_under_its_review`, `test_report_controls.py`
`test_the_audits_values_print_locked_and_the_source_audit_keeps_them`.

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
- **F-RPT-2 (2026-10-22): a control character a person typed failed the whole draft.** A research question
  (or a question's wording, a study's name) holding a character XML 1.0 cannot hold (a bell, a lone
  surrogate, Word's vertical tab from a pasted line break) reached python-docx as written, and lxml refused
  the run ("All strings must be XML compatible"): no draft at all
  (`infrastructure/report_docx/renderer.py:53 @ 09571504`, found by the #792 stand-in review); only the
  brief was cleaned (#792). Fix (`fix/report-xml-illegal-text`): one pure rule, `domain/report/printable.py`,
  applied by the renderer before it writes and by the document model before it is stored, so the stored
  model holds the text the DOCX printed (a choice's label in the stored ledger's metric too). Word's breaks
  print as a space, since text also runs into one-line places (the running head, headings, captions), and its
  non-breaking hyphen as a hyphen; the rest are dropped; what names something (ids, refs, targets, the ledger,
  the manifest) is untouched. #792's own regex in `report_design._paragraphs` is replaced by `xml_text`: it keeps Word's line
  break as a line for its paragraph split, and a brief field of nothing but such characters still reads
  "V zadání neuvedeno." Tests:
  `test_report_design.py::test_a_control_character_a_person_typed_never_fails_the_render`,
  `test_report_printable.py`.

## 8. Owner questions

- Held at the feature freeze (the owner, 2026-10-22, 16:5x UTC: "stop developing new features, let's get the
  new deploy up and running"): RPT8a part 3 and RPT8b-d. Lifted for RPT8 by the owner in the Zpráva session the
  same evening ("Lift the freeze for RPT8 now"); RPT9 and RPT10 stay after it.
- Decided on /pmstatus (2026-10-22, relayed by the coordinator): a recompose after edits keeps both, separate (a);
  RPT8c's line model above.

- Q73 (decided 2026-10-22, (c)): downloads stay free before approval; RPT3b is closed, not built.
- Hosting ONLYOFFICE Document Server beside develop (RPT8): an operations change, for the coordinator to
  schedule with the owner (AGPL obligations named in the spike).


The editor choice (Q19) stays open. Settled 2026-10-21 via /pmstatus: CQ1 = Q55 (b), today's
report with its gaps closed, plus RD9/RD10, plus literature when chosen, in today's order; CQ2 = Q56 (b), code drafts and the Lead proposes tracked changes (RPT6);
CQ4 = Q58 (b), one document with the literature woven into its body (CHN8). A module with no supported finding is settled: MVPQ-04 blocks composition, approval and export
(`artifact-chain-to-draft-report#CHN10`).

## Doc follow-up

- Register this plan and its chunks.
