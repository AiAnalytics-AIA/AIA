---
status: planned
chunks:
  - "[ ] RPT1. Zpráva's contract as data: view operations, pointable ids (section, paragraph, figure, claim) and V2's interaction contract"
  - "[ ] RPT2. The document first: the draft rendered in the pane from its stored document model, paragraphs with claim chips opening the inspector, figures in place"
  - "[ ] RPT3. The doc bar and the Approve and Export slot: which document, its draft number and state, approval as a modal naming it, exports after approval"
  - "[ ] RPT4. Záznam pokrytí, outside the text: what the report does not hold and why, from the chain manifest"
  - "[ ] RPT5. Draft revisions: the draft counter and tracked changes per paragraph, a report edit never reopening fieldwork"
  - "[ ] RPT6. The Lead and the report writer on the draft: paragraph rewrites, merges, splits and moves as proposals, every number a ledger ref, the sentence check's refusals at the sentence"
  - "[ ] RPT7. Journey: Zpráva at 1440, 1100, 768 and 390 px, a fictional run's internal draft, zero paid jobs"
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

**RPT3. Doc bar and approval.** Tests: approval sends the artifact id shown; a stale version is
refused. Depends on `report-delivery#RD2`, `#RD3`, `input-interactions#6`.

**RPT4. Záznam pokrytí.** Test: a design that asks for a segment comparison lists "Segmenty:
neprovedeno". Depends on `artifact-chain-to-draft-report#CHN1`.

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

## 8. Owner questions

The draft's sections (the chain plan's CQ1, Q55) and the editor choice (Q19) stay open. Settled
2026-10-21 via /pmstatus: CQ2 = Q56 (b), code drafts and the Lead proposes tracked changes (RPT6);
CQ4 = Q58 (b), one document with the literature woven into its body (CHN8). A module with no supported finding is settled: MVPQ-04 blocks composition, approval and export
(`artifact-chain-to-draft-report#CHN10`).

## Doc follow-up

- Register this plan and its chunks.
