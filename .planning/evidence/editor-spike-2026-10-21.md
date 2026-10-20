# Editor spike: the study context file and the reports (research-lead-workbench#33)

Written 2026-10-20 (23:00-23:59 UTC) for the owner's go/no-go (page Q19). Nothing is adopted here and
nothing was installed into the product. The chunk is not ticked: the decision is the owner's.

**What this spike is and is not.** It is a desk comparison from web sources plus a reading of AIA's
own report renderer. The chunk also asks for a local run of each candidate on one fictional study
context file and one sample report, with ledger refs counted before and after a round trip. **That
run was not done.** This session's egress proxy refuses the vendors' hosts (for example
`api.onlyoffice.com:443`: `connect_rejected`, checked 2026-10-20 23:3x UTC), so no image or package
could be fetched. The run is the first step of every option below, and the recommendation depends
on it.

## How to read the citations

- **[F]** marks a page this session fetched and read itself.
- **[S]** marks a search-engine excerpt of a vendor or press page whose page could not be fetched
  (the egress refusal above).
- Every source was read on **2026-10-20**.
- A sentence marked *Inference* is my reasoning, not a sourced fact. An [S] claim is weaker than an
  [F] claim, and the local run should re-check each one it relies on.

## The owner's requirements (pages Q13 and Q19)

- **R1.** Researchers edit the study context file (`lead-orchestration#LO19`) and the reports
  (`report-delivery#RD6`).
- **R2.** A Lead's edits arrive in one of two modes, chosen per researcher:
  - tracked-change suggestions, the default;
  - direct rewrites that can be undone.
- **R3.** Every number stays a ledger ref.
- **R4.** The output exports to DOCX. The report pipeline is python-docx.
- **R5.** The editor is "as close to Microsoft Word or LibreOffice as possible". The owner finds
  Tiptap's UX poor.

## A finding in AIA's own code that decides R3, whichever editor wins

**F-ED1. A rendered report's DOCX does not record which ledger ref a number came from.**

- **Anchor:** `packages/aia_core/src/aia_core/infrastructure/report_docx/blocks.py:116-123 @
  e09a6c99`.
  - In the document model, an inline number is `Value(ref)` (`domain/report/model.py:40 @
    e09a6c99`).
  - `write_value` prints its text as a `NUMERAL`-styled run, then the grade mark and the
    disclosure.
  - No element carries the ref: no content control, no bookmark, no custom XML.
- **Reproduction:** render any sample report (`make report-preview`), unzip `word/document.xml`,
  and search it for a ledger ref id. There are no hits.
- **Consequence:** once a person edits the DOCX in any document editor, AIA cannot tell an evidenced
  number from a number someone typed. R3 cannot be checked through a DOCX round trip today.
- **Smallest fix (for RD6, not this spike):** wrap each `Value` in an inline content control
  (`w:sdt`). The control carries `w:tag` = the ref and `w:lock` = `sdtContentLocked`. On a save, a
  census refuses a document that lost a tagged control, changed one's text, or holds a number outside
  every control.
- **Test that would have caught it:** a renderer test that counts the `Value` refs in a
  `ReportDocument` and the `w:sdt/w:sdtPr/w:tag` values in its DOCX, and expects them to be equal.

**F-ED2. The study context file is Markdown.**

- **Anchor:** `.planning/plans/lead-orchestration.md:28 @ e09a6c99`, LO19: "a Markdown file per
  study, built by code".
- A page-based word processor edits DOCX/ODT.
- *Inference:* a Word-like editor fits the reports and fits the context file badly. Two ways out:
  - edit only its prose part ("Poznámky ke studii") in the editor, as a small DOCX that AIA converts;
  - keep a plain editor for the context file, which LO19 already plans until the choice is made
    (`research-lead-workbench.md`, chunk 33's paragraph).

## Candidates and the comparison

The five candidates:

- Wordcraft;
- ONLYOFFICE Docs;
- Collabora Online;
- Tiptap, the baseline;
- CKEditor 5, the extra strong candidate.

Lexical was considered and dropped. A search found no tracked-changes or DOCX capability for it
([S] search "Lexical editor track changes suggestions DOCX export", results only for other
editors). Euro-Office is a 2026 fork of ONLYOFFICE, led by Nextcloud and IONOS. It is noted under
ONLYOFFICE's risks rather than scored, because its first stable release is only months old.

### Comparison table

Legend: ✓ verified · ~ partly or with conditions · ✗ absent · ? unverified. Sources follow the table,
numbered.

| Criterion | Wordcraft | ONLYOFFICE Docs | Collabora Online | Tiptap (baseline) | CKEditor 5 |
|---|---|---|---|---|---|
| **Word-like UX (R5)** | ✓ "a clean-room reimplementation of Microsoft Word", with a ribbon [1] | ✓ an MS-Office-style page editor (*inference* from the product; no screenshot set yet) | ✓ LibreOffice's Writer in the browser, rendered as server-side tiles [14] | ✗ a web rich-text field; the owner rejected its UX | ~ a web editor; page layout needs a premium plugin (*inference*) |
| **Licence for a SaaS** | ✓ MIT or Apache-2.0 [1] | ~ AGPL v3 [5], with a disputed §7 logo term [10][11] | ✓ MPL 2.0 [12]; a commercial subscription for production [13] | ✓ MIT core [18]; track changes and DOCX import are paid [16][17] | ~ GPL-2.0-or-later or commercial [21]; track changes is premium [22] |
| **EU self-hosting on one Docker host** | ~ native and WASM builds [2]; no server, no embed API documented [2] | ✓ Docker; since 9.4 one process, with no RabbitMQ or database [6] | ✓ the `collabora/code` Docker image, WOPI [15] | ~ the editor runs in the browser; DOCX import needs Tiptap Cloud [17] | ~ the editor runs in the browser; the Word converters run on-prem in Docker with a licence key [23] |
| **Tracked changes and suggestions (R2)** | ~ track changes, accept/reject, compare [2]; gaps in moves and table/section revisions [3] | ✓ review mode; review changes driven from the API [8] | ✓ LibreOffice "Record Changes"; toggled with `.uno:TrackChanges` [14b] | ~ a $249/month add-on, "under active development" [16] | ✓ premium track changes with a suggestion API [24] |
| **An API for the Lead to propose edits** | ~ an MCP server over stdio, 422 commands, tracking toggled by command, headless or driving a running app [4] | ~ in-editor plugins (`callCommand`) are free; host-page control (Automation API) is Developer Edition only, at extra cost [7] | ~ the PostMessage `Send_UNO_Command` [14b] | ~ an editor-side JS API (*inference*) | ✓ `addSuggestion`, `markInsertion`, `markDeletion` [24] |
| **Protected inline fields (R3)** | ? content controls are kept and edited; binding is absent [3]; locking is not documented | ✓ content controls with `SetLock("sdtContentLocked")` [9] | ? LibreOffice's content controls; DOCX `w:lock` handling not found [19] | ~ custom atomic nodes (*inference*) | ~ widgets and restricted editing (*inference*; not checked) |
| **DOCX round trip (R4)** | ~ opens and saves .docx [1]; "DOCX never tested on real-world files" [3] | ✓ OOXML is its native model (*inference*) | ~ converted to and from LibreOffice's model; lossy at the edges (*inference*) | ~ export is client-side Pro; import is in the cloud and beta [17] | ~ import keeps comments and tracked changes, partly in tables [23] |
| **Czech** | ✓ Czech UI and spelling [2] | ✓ cs-CZ, 87 % translated [20] | ✓ LibreOffice's Czech locale (*inference*) | ✓ (*inference*: the UI is ours) | ✓ `cs.ts` in core [25] |
| **Accessibility** | ✗ canvas UI; "no NVDA, VoiceOver or Orca run yet" [3] | ~ screen-reader support in beta since 7.5 [26] | ~ ARIA client-side dialogs; screen reader opt-in by the administrator; the document itself is image tiles [14] | ✓ it is our DOM (*inference*) | ✓ WCAG 2.2 A/AA claimed, with a VPAT [27] |
| **Maintenance and health** | ~ 15.1k stars, 1,020 commits, 35 commits on 18-20 Oct 2026, alpha at "about 60 %" [1][2] | ✓ 7.0k stars [5]; 10.0.0 released 12 Oct, 9.4.0 on 19 May [6b] | ✓ 3.4k stars; developed on Gerrit [12b] | ✓ 38.8k stars [18] | ✓ a mature commercial vendor (*inference*) |
| **Cost** | free | free for Community since 9.4 [6]; Developer Edition is sold per connection tier [28] | CODE free but capped at "10 documents, and 20 connections" [13]; subscription about €3/user/month (third-party figure) [13b] | Cloud from $49/month, plus track changes at $249/month [16] | the commercial price is by quote [22] |
| **Effort with Next.js 16 / React 19** | high: a WASM app with no embed API [2] | low-medium: the Apache-2.0 React wrapper renders the Document Server iframe [29] | medium: we write a WOPI host (CheckFileInfo/GetFile/PutFile) [14] | low | medium |

### Sources

Every source below was read on 2026-10-20.

1. [F] <https://github.com/storytold/wordcraft>: MIT/Apache-2.0, alpha, "clean-room reimplementation of
   Microsoft Word in pure Rust", Review tab with track changes, 15.1k stars, 1,020 commits.
2. [F] <https://raw.githubusercontent.com/storytold/wordcraft/main/README.md>: browser via
   WebAssembly (`trunk serve`), no embedding API, MCP and JSON control channel, "about 60% ready for
   real work", Čeština in the UI, Czech Hunspell spelling, "native egui on the GPU". Commit dates from
   [F] <https://github.com/storytold/wordcraft/commits/main>: 3 on 20 Oct, 31 on 19 Oct, 1 on 18 Oct.
3. [F] <https://raw.githubusercontent.com/storytold/wordcraft/main/docs/gaps.md>:
   - "no real-time co-authoring" (#22);
   - track changes still missing "drag-and-drop moves" and "tracked style-definition changes and
     table/section changes" (#5);
   - content controls kept, but "binding evaluation remains absent";
   - "DOCX never tested on real-world files." (#1);
   - "no NVDA, VoiceOver or Orca run yet" (#18).
4. [F] <https://raw.githubusercontent.com/storytold/wordcraft/main/docs/mcp.md>:
   - MCP over stdio;
   - a headless session by default, or `--connect` to drive a running app;
   - `review.trackChanges {"value": true}`;
   - changes recorded under `--author`.
5. [F] <https://github.com/ONLYOFFICE/DocumentServer>: "licensed under the GNU Affero Public
   License, version 3.0"; 7.0k stars; Community "up to 20 recommended" users; no clustering.
6. [F] <https://raw.githubusercontent.com/ONLYOFFICE/DocumentServer/master/CHANGELOG.md>: 9.4.0
   "Removed the limitation of 20 simultaneously opened documents", "Consolidated components into a
   single process", "Removed dependency on RabbitMQ"; 10.0.0 removed the deprecated `trackChanges`
   customization parameters and added `customization.ai.disabled`. 6b. [F]
   <https://github.com/ONLYOFFICE/DocumentServer/releases>: v10.0.0 on 12 Oct and v9.4.0 on 19 May.
7. [S] <https://api.onlyoffice.com/editors/connector>: the connector (Automation API) "is
   available only for ONLYOFFICE Docs Developer Edition" and is "available at extra cost". [S]
   <https://community.onlyoffice.com/t/react-embed-jump-to-existing-bookmark-bookmark-goto-plugin-loads-but-host-command-doesn-t-trigger/18050>:
   plugins run only inside the editor iframe.
8. [S] <https://api.onlyoffice.com/docs/docs-api/samples/automation-api/working-with-review-changes/>:
   `AcceptReviewChanges`, `RejectReviewChanges`, `GetReviewReport`. [S]
   <https://community.onlyoffice.com/t/track-changes-behaviour-issues/18474/2>:
   `SetTrackRevisions(true)` inside `callCommand`.
9. [S] <https://api.onlyoffice.com/docs/office-api/usage-api/text-document-api/ApiInlineLvlSdt/Methods/SetLock>:
   the lock values are unlocked, contentLocked, sdtContentLocked and sdtLocked; `sdtContentLocked`
   means the content cannot be edited and the container cannot be deleted.
10. [S] <https://ie-forum.nl/artikelen/the-logo-trap-onlyoffice-s-agplv3-gambit-and-what-it-means-for-free-and-open-source-compliance>:
    the §7 logo-retention term, and the FSF's view that it is a "further restriction".
11. [S] <https://alternativeto.net/news/2026/4/onlyoffice-ends-its-partnership-with-nextcloud-over-new-unauthorized-euro-office-fork>
    and [S] <https://heise.de/-11228123>: the Euro-Office fork (Nextcloud and IONOS, March 2026), and
    ONLYOFFICE ending its Nextcloud partnership over branding. [S] <https://heise.de/-11322160>: the
    first stable Euro-Office release.
12. [F] <https://raw.githubusercontent.com/CollaboraOnline/online/master/COPYING>: "subject to the terms
    of the Mozilla Public License, v. 2.0". 12b. [F] <https://github.com/CollaboraOnline/online>:
    3.4k stars; "Active development of Collabora Online has moved to our Gerrit instance".
13. [S] <https://help.nextcloud.com/t/collabora-document-limitation-by-purpose-10docs-20connections/4425>:
    the CODE banner says "This development build is limited to 10 documents, and 20 connections". 13b.
    [S] <https://gappsy.com/tools/collabora-online/>: about €3 per user per month on-premise. This is a
    third-party figure, not Collabora's price list.
14. [S] <https://www.collaboraonline.com/blog/finding-a-secure-document-editor-for-your-organisation-part-3/>:
    the document is rendered into "heavily compressed, unique image tiles". [S]
    <https://forum.collaboraonline.com/t/screen-reader-support-in-collabora-online-featurefriday/4687>:
    screen reader opt-in with `accessibility.enable=true`, ARIA client-side dialogs. 14b. [S]
    <https://forum.collaboraonline.com/t/code-how-enable-track-change-on-code-by-default/3191>:
    `Send_UNO_Command` with `uno:TrackChanges`. [S]
    <https://www.collaboraonline.com/blog/how-to-track-and-manage-changes-in-collabora-online/>.
15. [S] <https://sdk.collaboraonline.com/docs/installation/CODE_Docker_image.html>: the `collabora/code`
    image; `aliasgroup1` restricts the WOPI hosts.
16. [S] <https://tiptap.dev/docs/tracked-changes/getting-started/install> and
    <https://tiptap.dev/pricing>: Tracked Changes is a paid add-on in no plan, at $249/month; the docs
    say it is under active development; Cloud plans start at $49/month.
17. [S] <https://tiptap.dev/docs/conversion/import/docx/editor-import>: DOCX import uses a JWT from
    Tiptap Cloud Convert and is beta; export (`@tiptap-pro/extension-export-docx`) runs client-side.
18. [F] <https://github.com/ueberdosis/tiptap>: MIT; Pro Extensions "need a valid subscription";
    38.8k stars.
19. [S] <https://www.libreoffice.org/bugzilla/show_bug.cgi?id=137466>: DOCX SDT support is "still far
    beyond perfect". No source on `w:lock`.
20. [S] <https://helpcenter.onlyoffice.com/docs/docs-available-languages.aspx>: "Czech | cs-CZ | 87%".
21. [F] <https://raw.githubusercontent.com/ckeditor/ckeditor5/master/packages/ckeditor5/LICENSE.md>:
    "GNU General Public License Version 2 or later", or commercial terms from CKSource.
22. [S] <https://unpkg.com/@ckeditor/ckeditor5-track-changes@48.3.1/README.md>: track changes "is a
    premium feature". [S] <https://docs.ckeditor.com/ckeditor5/latest/support/licensing/license-key-and-activation.html>:
    for self-hosting, contact sales.
23. [S] <https://docs.ckeditor.com/cs/latest/onpremises/docx-onpremises/overview.html>: on-prem Word
    import/export on Docker, Kubernetes or Podman, with a licence key. [S]
    <https://ckeditor.com/docs/ckeditor5/latest/features/import-word/features-comparison.html>: import
    keeps comments and tracked changes; tables are partial.
24. [S] <https://ckeditor.com/docs/ckeditor5/latest/features/collaboration/track-changes/track-changes-custom-features.html>
    and the `TrackChangesEditing` API page: `addSuggestion`, `markInsertion`, `markDeletion`,
    `enableCommand`.
25. [F] <https://github.com/ckeditor/ckeditor5/tree/master/packages/ckeditor5-core/lang/translations>:
    `cs.ts` is present.
26. [S] <https://onlyoffice.com/blog/2023/10/screen-readers-in-onlyoffice>: screen readers in beta
    from 7.5. [S] <https://www.onlyoffice.com/blog/2026/10/accessibility-conformance>: work on
    screen-reader support continues.
27. [S] <https://ckeditor.com/docs/ckeditor5/latest/features/accessibility.html>: WCAG 2.2 A and AA
    and Section 508; VPAT v44.3.0.
28. [S] <https://www.componentsource.com/product/onlyoffice-docs-developer/prices/buy/0cb8-135634>:
    Developer Edition tiers of 250, 500 and 1,000 connections, annual. The prices were not shown.
29. [F] <https://github.com/ONLYOFFICE/document-editor-react>: Apache-2.0; the component lets
    ONLYOFFICE Docs replace a placeholder "with its own iframe"; needs Docs 9.0 or later.

## The shape that makes the choice reversible

This part is *inference*, and it is the recommendation's core. Two choices make the editor a surface
and not the store.

**1. The Lead's edits are written by AIA, not by the editor's API.**

- AIA already holds the report as data (`ReportDocument`) and renders it with python-docx.
- A Lead suggestion becomes OOXML revisions (`w:ins` / `w:del`, author "Vedoucí") written into the
  DOCX by AIA's renderer. The editor only shows them and lets the person accept or reject them.
- A direct rewrite is applied, and the previous version is kept as the one-step undo.
- No editor API is needed for R2, and no paid Automation API.
- Any DOCX editor that shows tracked changes then serves both modes.

**2. Numbers are locked, tagged content controls, and AIA checks every save (F-ED1's fix).**

- The editor saves back to AIA (a callback or WOPI PutFile).
- AIA runs a ref census:
  - every tagged control is present, with its text unchanged;
  - no digit appears outside a control in evidenced prose.
- If the census fails, AIA refuses the save by name.
- R3 is then enforced by AIA, whatever the editor does.

## Recommendation

**A conditional go for ONLYOFFICE Docs Community (9.4+/10.x), self-hosted and unmodified, for
the reports, built in the shape above.**

- It is the most Word-like of the candidates.
- It edits OOXML natively.
- It documents locked content controls [9].
- Since 9.4 it runs as one process with no connection cap [6], which suits the one develop host.
- Before any build work, a one-day local proof must pass: AIA's sample report with tagged
  `sdtContentLocked` refs is opened, edited with suggestions on, saved back, and the census shows
  every ref intact. If the proof fails, the fallback is Collabora Online (MPL 2.0) under the same
  proof.
- **No-go for Wordcraft now.** The reasons:
  - it is alpha [1];
  - its DOCX has not been tested on real files [3];
  - it has no embedding API [2];
  - it has no co-authoring [3];
  - its canvas UI has not been run with a screen reader [3].

  Look again at its beta: its MCP server [4] and permissive licence fit the Lead well.
- **No-go for Tiptap.** The owner rejected its UX. Its track changes is a $249/month add-on still
  under active development [16]. Its DOCX import needs an outside cloud [17].
- **CKEditor 5 is the alternative** if accessibility and an in-browser suggestion API [24][27]
  matter more than Word-likeness. It needs a commercial licence at an unknown price [22].
- **The study context file** (F-ED2) keeps the plain editor LO19 already plans, unless the owner
  wants its prose part in the same Word-like editor.

**The trade-off.** We take on AGPL obligations, a disputed logo term [10] and a supplier in a
licence dispute [11]. In return we get the closest thing to Word that is free to self-host, and we
keep the Lead's rules in AIA, so the editor can be replaced.

## Risks

1. **AGPL.** *Inference, not legal advice:* running an unmodified Document Server as a separate
   service that AIA talks to over HTTP does not put AIA's code under the AGPL. Modifying the server
   obliges us to offer its source to its users (AGPL §13). Keep it unmodified and keep the logo. A
   lawyer should confirm before production.
2. **The §7 logo term and the Euro-Office dispute.** The supplier is in an open licence dispute with
   Nextcloud [10][11]. *Inference:* Euro-Office could become an EU-governed drop-in, because it is
   the same codebase. It is too young to choose today.
3. **Supplier and data-flow review.** Documents stay on our host. The image's telemetry and update
   checks must be confirmed off in the local proof (unverified).
4. **Accessibility.** ONLYOFFICE's screen-reader support is beta [26]. Collabora's is opt-in and its
   document is image tiles [14]. Neither is as accessible as a DOM editor. This matters if a
   researcher relies on a screen reader.
5. **F-ED1 is real work, whichever editor wins.**
   - the renderer must emit tagged, locked controls;
   - RD6 must parse a saved DOCX back into an accept result;
   - the save census must exist.
6. **Host load.** A document server on the one develop host adds memory and CPU (not measured). The
   local proof should measure resident memory with one open report.
7. **Unverified claims.** Every [S] claim and every *inference* above is to be re-checked in the
   local proof, in particular content-control locks surviving an edit, and Czech in the review UI.

## Go/no-go question for the owner

> The editor for reports. Shall we adopt ONLYOFFICE Docs (free, self-hosted on our server; the
> closest to Word; AGPL licence, with a supplier in a licence dispute) behind a one-day proof that
> every number survives an edit and a save?

| Option | What it means | Cost |
|---|---|---|
| **(a) Go: ONLYOFFICE Docs** *(recommended)* | The proof first; then RD6 builds on it, and the Lead writes suggestions as Word tracked changes | no licence fee; AGPL obligations; one-day proof; F-ED1 work |
| **(b) Go: Collabora Online** | LibreOffice in the browser, MPL licence; the same proof | Production needs a Collabora subscription (CODE is capped at 10 documents and 20 connections [13]); weaker DOCX fidelity (*inference*) |
| **(c) Go: CKEditor 5 (commercial)** | A web editor, not Word, with the best accessibility and suggestion API | A commercial licence by quote; less Word-like |
| **(d) Wait for Wordcraft's beta** | Keep the plain editor behind the edit operations until Wordcraft reaches beta, then re-run this spike | No Word-like editing for now |
| **(e) No-go: keep the plain editor** | LO19 and RD6 ship with the plain editor they already plan | Not Word-like |

Whichever option is chosen, the study context file keeps the plain editor unless the owner says
otherwise (F-ED2).
