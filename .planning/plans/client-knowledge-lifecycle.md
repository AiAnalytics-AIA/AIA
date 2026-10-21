---
status: in-progress
chunks:
  - "[x] K0. Audit current client knowledge intake, payloads, decisions and consumers at 67af44e"
  - "[x] K1. Draft the client knowledge structure, intake and acceptance contracts for review"
  - "[ ] K2. Deliver document, dataset and web intake through one source-to-reviewed-knowledge journey"
  - "[x] K2a. Client source store: immutable originals, dedupe per client, PDF/DOCX/TXT/MD read with locators"
  - "[x] K2b. Presentation and open/legacy document readers: PPTX, ODT, DOC"
  - "[x] K2c. Dataset intake: CSV, XLSX, XLS, ODS schema preview with row/column locators"
  - "[x] K2d. AI proposals from a document source, paid by the client's budget, every quote grounded"
  - "[x] K2d1. Extraction in the domain: closed contract, Czech prompt, segment batches, every quote grounded in its segment"
  - "[x] K2d2. Persistence: a client-work reading pinned by its SHA-256; AI-authored proposals written once per run"
  - "[x] K2d3. The client_source_proposals step: executor, workflow type, kill switch, parks by name; recorded-gateway tests under the real worker loop, charged to the client"
  - "[x] K2d4. Start and follow: POST /clients/{id}/sources/{source_id}/proposals, idempotent per reading; the run's state"
  - "[x] K2d5. Web: Navrhnout znalosti on a document's item and the intake sheet; waiting for budget with the lift; proposals land in Ke schválení"
  - "[x] K2d6. Burst, latency and money measured; develop activation is the owner's call"
  - "[ ] K2e. Web intake beneath a chosen study: one public URL captured, Deep Research evidence imported"
  - "[ ] K2f. Review payload with evidence beside each proposal; connected acceptance over all three families"
  - "[x] K3a. Refuse an edit written from an item revision that is no longer current (F-K1)"
  - "[x] K3. Implement typed knowledge revisions and decisions against the reviewed base revision"
  - "[ ] K4. Resolve a study's selected, eligible client knowledge into an immutable context snapshot"
  - "[ ] K5. Define and materialize executable dimensions through the existing population authority"
  - "[ ] K6. Implement correction, retirement, conflicts and dependent-study change visibility"
  - "[ ] K7. Prove all four consumers and reconcile the shared documentation after landing"
  - "[ ] K8. One semantics for Deep Research evidence entering client knowledge (an item or a proposal), and a document item's text visible to Deep Research"
  - "[ ] K7a. W5 MVP research consumer proof: intake, reviewed/frozen knowledge, executable dimension, admitted report and same-client reuse; Simulation extension stays in K7 after MVP"
  - "[ ] K9. A cross-client what-needs-me portfolio: every study waiting for the signed-in researcher, across clients (D-47)"
  - "[ ] K10. Project memory searches approved reports too, beside designs (D-47)"
  - "[ ] K11. Profil → Pravidla: the wallet ceiling, set by an OWNER or ADMIN, beside the posture setter deep-research-web-search 53 builds; both listed read-only in Settings (D-17)"
  - "[ ] K12. The Simulace tab and its new-simulation button hidden until simulation is built (MVP-31)"
---
# Client knowledge that studies can use correctly

**Owner:** client knowledge / data-library product integration. **Started:** 2026-10-08.
**Baseline:** develop `67af44e5b9431d6293347b581fde7a34b95ed44c`.

User direction: rethink and improve the types of knowledge bases created for clients,
their structure, input methods and approval methods. This proposal supplies the missing
product and semantic contract. The user authorized publishing this proposal as a draft
on 2026-10-08; publication does not accept its product/methodology decisions or authorize
implementation, migration or deployment. The MVP still requires all four areas.

## Problem and observed evidence

The existing foundation has client scope, item identity, append-only revisions, proposals
and decisions. Those should be retained. But a category is not a contract for how an item
may be used.

Anchors below are at the baseline SHA:

| Current behavior | Evidence | Consequence |
| --- | --- | --- |
| Every knowledge kind shares a generic content/provenance dictionary | `domain/knowledge.py:121-182`; `routers/workspace.py:385-405` | SOURCE, FACT, DIMENSION and DATASET have no distinct, required payload semantics here |
| The client intake form sends kind, title and summary | `KnowledgeArea.tsx:127-161` | Choosing DOCUMENT does not upload its bytes; choosing DIMENSION does not define its measure |
| Review cards show title, summary, origin study and decision buttons | `KnowledgeArea.tsx:85-117` | A reviewer does not inspect the source span, payload, exact revision diff or intended computational use in this view |
| Client dimension catalogue takes item id and title | `apps/web/src/research/persona.ts:52-61` | An accepted dimension label can appear without an executable definition or values |
| Client additions are immediately accepted by default; study proposals wait | `workspace.py:825-837`; `client_knowledge_repository.py:395-441` | Preserve ADR 0019: distinguish the person's declaration from a system-generated extraction; do not introduce mandatory approval by another person |
| New study retrieval selects active client items | `client_knowledge_repository.py:125-180` | Content availability alone is not an explicit relevance, freshness and permitted-use decision |
| Pending edits store item identity but no reviewed base revision | `client_knowledge_repository.py:250-296, 353-387, 516-527` | An earlier proposal can replace a newer correction when accepted later (F-K1) |

Two disposable audit reproductions passed against the baseline, using existing fictional
core fixtures and SQLite. They assert observed gaps, not the desired behavior:
`test_a_pending_edit_can_replace_a_newer_accepted_correction` and
`test_a_dimension_can_be_accepted_with_no_definition_or_values`.
Probe and sanitized JUnit are published in `.planning/evidence/client-knowledge-review/`.
No production file or existing test was changed by the audit. PostgreSQL concurrency and
deployed behavior were not tested.

## Product structure — one client workspace, several views

The proposed client workspace answers: what do we know, where did it come from, when does
it apply, what can it be used for, and what changed? It is not a collection of independent
knowledge engines. Organize the same versioned items into these user-facing views:

| View | Typical contents | Default use |
| --- | --- | --- |
| Client context | Organization, products/services, terminology, business constraints, objectives | Design and briefing context; a goal is not an observed fact |
| Sources | Uploaded documents, presentations, notes, captured pages and imported data | Originals and extraction evidence; storage is not acceptance of every statement |
| Market and customer knowledge | Competitors, customer needs, qualitative themes, audience descriptions | Cited context with population, geography and time scope |
| Data and measures | Datasets, variable definitions, instruments and materialized dimension versions | Computation only after applicable validation and eligibility checks |
| Findings | Accepted observations, research findings, modelled findings and explicit hypotheses | Preserve the evidence category; acceptance never changes synthetic evidence to measurement |
| Decisions and assumptions | Chosen actions, scenario assumptions and why they were chosen | Inputs to design/scenarios, distinguished from empirical findings |
| History and use | Superseded revisions, studies that consumed them, saved outputs and decisions | Project memory and impact review; originals remain reconstructible |

Views may overlap and filter by topic, entity, study and time. They do not create copies.
Keep shared platform intelligence, this client's knowledge and a study's frozen context
separate as ADR 0015 requires. Organization-wide access is not permission to automatically
copy one client's findings into another client's context. No silent shared publication.

## Typed knowledge and relationships

Reuse existing ids, scopes, repository authority and revision history. Define versioned
payloads incrementally inside the existing knowledge subsystem, rather than building a
parallel graph/vector database or using free-form JSON as an executable contract.

| Record | Required meaning |
| --- | --- |
| Source revision | Immutable original/capture, byte hash, capture/import time, source publication date when known, origin and existing data classification; storage and extraction references |
| Evidence reference | Exact source revision plus page/section/quote or sheet/cell/row locator; preserve the span used by extraction and its interpretation limits |
| Knowledge assertion | Statement, assertion class, supporting/contradicting evidence, subject/entities, applicable geography/population/time, author/derivation; distinguish observation, person-declared claim, hypothesis and modelled result |
| Dataset revision | Data artifact, schema, row/field identities, source lineage, units/codes, missingness and quality results; respondent weighting and joint-claim constraints where applicable |
| Dimension definition | Stable id and version, construct, unit/scale/categories, valid range, missingness, operational definition, source variables/derivation, permitted roles and validation status |
| Dimension materialization | Definition version plus actual values, compatible population binding, coverage, donor/weight lineage and validation evidence; a definition alone has no respondent values |
| Audience definition | Versioned predicates over eligible, versioned fields; resolve eligible counts before use; description and executable predicate are distinct |
| Reusable artifact | Existing artifact id/hash and producing run, evidence/method/population identities, accepted reuse purposes and limitations |
| Decision/assumption | What was chosen or hypothesized, rationale, owner, applicable scope/time and related evidence; never disguise a decision as a measurement |

Relationship types include supported-by, contradicts, derived-from, defines, materialized-as,
supersedes and consumed-by. Use exact revisions, not a pointer to whichever item is current.
Existing artifact dependencies, knowledge revisions and admission policies remain their
authorities; typed relationships must bridge them rather than duplicate their decisions.

Keep three questions separate: processing succeeded; a person accepted this interpretation;
the intended use is eligible. Avoid one universal APPROVED flag implying all three. Formal
eligibility stays with the existing population/evidence rules, not with a knowledge UI.

## Input methods and one consistent intake journey

Proposed minimum input families: direct writing/pasting; supported document upload; URL capture
and Deep Research import; tabular dataset import; reuse from an existing study/artifact.
Format support must be explicit. An unsupported file or acquisition route has a named outcome;
it must not quietly produce a title-only knowledge card.

**User confirmation, 2026-10-08: all three families are integral.** Document/presentation/note
intake, spreadsheet/survey/dataset intake and URL/external-research intake are all required
in this design and its acceptance; there is no documents-only acceptance milestone counted
as completion. Specify concrete supported formats before implementation, and treat parser,
dataset mapping and web acquisition as bounded adapters to the same journey:

1. Select client and add material. Show what was stored, its origin and processing state.
2. Persist the original/capture as an immutable source revision. Deduplicate by content identity
   within scope while retaining import occurrence metadata. Never claim a successful parse
   when only upload succeeded. Follow the existing attachment, retrieval and paid-call boundaries.
3. Extract readable content or a schema preview with stable locators. Report partial extraction,
   unreadable pages, missing columns and unsupported formats. Preserve originals.
4. Propose knowledge: assertions, terms/entities, findings or dataset mappings. System output
   stays a proposal, even if triggered by a person clicking Upload.
5. Review exact proposals beside their evidence and intended uses. Accept selected items, edit
   explicitly, reject, or leave pending. Detect duplicate/conflicting assertions without silently
   picking a winner. A batch accept names the exact displayed proposal ids and versions.
6. Show accepted items, remaining gaps and where each item can be used. Each later stage has
   its own applicable validation; source acceptance never automatically creates population values.

Direct human-authored context follows ADR 0019 and can be saved immediately, labelled as the
person's declaration. Storing a pasted assertion does not certify that it was measured.
Human editing of a system-generated proposal records the derivation and the explicit accept;
it does not erase the original proposal/evidence.

## Acceptance actions and review interface

| Action | What the person is deciding | What does not follow automatically |
| --- | --- | --- |
| Add source / save authored context | Store material or record the person's statement | Truth of every sentence, AI transmission eligibility or computational usability |
| Accept extracted knowledge | Accept the displayed interpretation and scope for client context | Measured evidence, executable dimension, population promotion or deliverable approval |
| Validate a data mapping / dimension | Confirm definition and processing; existing domain checks determine eligible roles | Invented respondent values or permission for every statistical claim |
| Use in this study | Select exact eligible revisions for a declared purpose | Changing a completed run or accepting all future client knowledge |
| Promote a population revision | Explicitly select the validated new revision through PopulationAuthority | Promotion when a dimension is selected |
| Release a deliverable | Existing client-facing deliverable contract and release gate, once implemented | Knowledge acceptance substituting for report release |

Do not add extra Reviewer/Lead roles or mandatory peer approval: ADR 0019's two roles and
persisted independent-review override remain. A person's permission to accept and an item's
eligibility for a scientific use are separate decisions.

Each proposal review shows the source excerpt/data preview, proposed payload, scope/time,
origin (person / extraction / study / modelled result), supporting and conflicting sources,
current-versus-proposed diff, reviewed base revision and the requested use. Buttons describe
the action: Save context, Accept selected findings, Define measure, Use in study. Avoid an
unqualified Approve label that could mean all of these things.

## Consumption across the four MVP areas

**Research:** freeze a selected context manifest with item revisions, evidence hashes, use
roles and eligibility decisions at enqueue. Trace where context reached the actual request.
Missing materialization must remain explicit; no fictional roster substitution.

**Sociomapping:** consume declared ratings and eligible materialized descriptors through the
existing study-input contract. Context prose is not a numeric coordinate, rating or respondent
value. This plan supplies I0/I1/I3 in sociomap-formula-corrections, and changes no canonical math.

**Simulation:** bind an approved scenario and world model to eligible definition/value versions
and the existing population runtime. Specify units, bounds and allowed shifts before connecting
free-form scenarios to computation. PanelSchema currently names numeric/categorical fields but
not ranges (`domain/simulation/world_model.py:65-95`); scenario.py explicitly records that ranges
are unavailable (`:20-23`). Do not silently clip or invent a new methodology.

**Project memory:** retrieve accepted reusable items with original scope, source, method and
evidence category. Reuse proposes exact revisions for a new study and requires explicit accept.
Synthetic/modelled findings cannot return as independent measured evidence in their descendants.
Enforce the existing Deep Research leakage and evidence discipline rather than bypassing them.

## Corrections and lifecycle

An edit appends a revision. A proposal revising an item records the exact base revision/hash;
accept checks it atomically. If the item changed, return a conflict and show a rebase/diff before
accepting again. Approval must never silently replace a newer correction (F-K1).

Distinguish superseded, disputed, retired and unavailable-for-new-use knowledge from physical
deletion. Record why and who changed its availability. Current searches/selection stop offering
ineligible revisions; a frozen historical run keeps its consumed snapshot and a visible status
notice where appropriate. Do not retroactively rewrite an approved report or simulation.

Show dependent studies/artifacts and which are historical, in progress or candidates for reuse.
Propose new work when changed knowledge matters; do not automatically trigger paid reruns.
Distinguish a source correction from changing an interpretation, dimension definition or view.
Deletion/retention follows existing artifact and client-data policy, with explicit dispositions
for originals still referenced by historical outputs; no invented blanket forever-retention.

## Implementation slices and proof

K2 delivers the source-backed intake/review product path for each of the three required input
families, including document/presentation/note extraction, tabular schema/mapping preview, and
captured web/Deep Research evidence. Individual adapters may land in bounded implementation
slices, but K2 is not complete until all three paths pass connected acceptance.
K3 adds typed revisions and stale-decision checks to that path; its final typed contracts must
be written before implementation. These slices may be assembled together if their contracts
require it. Keep parsing/extraction in the worker, rules in domain/application and UI rendering.

K4 extends existing research context freezing instead of introducing a second context loader.
K5 owns knowledge-to-dimension definitions/materialization, delegates population loading and
promotion to existing authority, and coordinates feature-plan I0/I1/I3. K6 proves corrections
and reuse decisions. K7 uses the current MVP research journey and AC-10/12/13. The older four-area journey in mvp-workflow-assurance A4 includes Simulation, which is post-MVP; keep that extension open without making Simulation a hidden MVP prerequisite. Each bounded slice uses existing storage, jobs and provenance.

Required connected acceptance fixture: add fictional client documents/notes, a small dataset
and captured web/Deep Research sources; extract source-backed proposals from all three input
families; accept selected knowledge; define/validate a dimension; use
its eligible values in a frozen study; produce stored map/analysis artifacts; reuse an accepted
finding in a new study. The scenario over the same bound baseline remains the explicit post-MVP Simulation extension. Correct one source,
then show affected consumers while preserving the original results. The all-four path is a
future acceptance requirement, not code claimed to exist today.

Required failure cases include partial parse, duplicate source, contradictory findings, unknown
dimension definition, missing values, unavailable extraction runtime, wrong-client source,
stale proposal acceptance, retired source, synthetic-evidence reuse and interrupted processing.
Observe actual context reaching fieldwork; do not prove wiring merely by changing a hash.
Browser/API/worker/PostgreSQL/store acceptance and bounded deployment remain separate evidence.

No vector service or additional agent framework is selected by this plan. Start with typed
records, locators and scoped retrieval over existing infrastructure; add indexing only when a
representative retrieval task demonstrates the need. Migration must preserve existing ids and
generic historical records without inventing source spans or validated dimensions for them.

## K2 slicing (2026-10-13)

**Owner decisions, 2026-10-13:**
- **Formats.** The wider set:
  - documents: PDF, DOCX, DOC, ODT, TXT, MD and PPTX;
  - datasets: CSV, XLSX, XLS and ODS;
  - web: one public URL (HTML or PDF), plus import from a finished Deep Research run.
  - Images and video are stored with the named outcome *AI cannot read this*. Anything else
    is refused by name.
- **AI proposals are in K2.** They are paid by a study the person picks, under client-workspace
  D1. Nothing is accepted automatically.
- **URL capture runs beneath a chosen study.** It uses the existing `RetrievalGate`
  (`application/web_retrieval.py:529-560` @ 362f90e0) unchanged: fee-free, public Class C only.
  No client-level gate.

**Shape:**
- A **source** is the client's stored material: the original bytes, the hash, the occurrence
  (who added it, when, under what name) and what reading it produced.
- A source is **not knowledge**:
  - storing it accepts nothing (§ Acceptance actions, "Add source");
  - `for_study` never reads it;
  - knowledge comes from it only as proposals a person accepts.
- **Storage:**
  - bytes live in the `ArtifactStore` under a client prefix,
    `org/<org>/client/<client>/sources/<sha256>`, so a client-wide deletion stays a prefix
    operation (`storage.py:123-158` @ 362f90e0);
  - rows live in their own tables, read and written only by `ClientSourceRepository`
    (`make layer_check`);
  - the same bytes added twice are one source with two occurrences.
- **Deterministic reading** runs in the API at upload, bounded:
  - this is the precedent of a study brief's attachment
    (`study_workspace_repository.py:492` @ 362f90e0) and the questionnaire import;
  - it deviates from "keep parsing in the worker" (§ Implementation slices) because a worker job
    needs a study (`workflow_repository.py:248-255` @ 362f90e0), and D1 stores files without
    one;
  - the reading is a pure function over bytes, so moving it to a worker later changes no
    contract.
- **The reading's outcome** is `READ` / `PARTIAL` / `UNREADABLE` / `UNSUPPORTED` / `REFUSED`,
  each with its reason. Every readable segment carries a locator: page, paragraph, slide, sheet
  and row, or column.
- **Model-backed work** (K2d) and **outbound fetching** (K2e) run in the worker beneath the
  chosen study.
  - Each proposal's provenance names the source, the occurrence, the locator, the paying study
    and the run.
  - A quote is checked by code against the stored reading. One that is not there is dropped and
    counted, never shown.

**Slices.** Each is one PR-sized change with its tests.
- **K2a. The client source store.** *(Landed.)*
  - **Domain**, `domain/client_sources.py`:
    - `SourceFamily` by suffix, with the owner's list exactly; anything else is `UNKNOWN`
      and refused at upload;
    - `Locator`, which must place something; `Segment`;
    - `ReadingNote`, a code the page puts into words;
    - `SourceReading`, which refuses a complete reading that explains anything, an
      incomplete one without a reason, and segments on an unread outcome;
    - `reading_of_segments`: empty parts dropped, 250,000 characters kept, a scan named
      `no_text`;
    - `display_name`.
  - **Reader**, `infrastructure/source_reading.py`:
    - PDF through `document_text.read_pdf`: pages and its tables by row;
    - DOCX in body order: paragraphs numbered as a reader counts them, empty ones included,
      and tables by row;
    - TXT and MD by paragraph, at their first line;
    - an image or video `UNREADABLE`; DOC, ODT, PPTX and every dataset `UNSUPPORTED` /
      `reader_pending` until K2b and K2c.
    - `document_text.check_zip_bounds` (formerly `_zip_within_web_bounds`, now with the
      file's kind) runs before an Office ZIP is inflated.
  - **Storage:**
    - `client_sources` and `client_source_occurrences`, migration `b3d5f7a9c1e2`. Checked on
      PostgreSQL 16: upgrade, `alembic check`, downgrade, re-upgrade.
    - `ClientSourceRepository` is their only reader and writer (layer_check, four rules).
    - Bytes and reading go under `org/<org>/client/<client>/sources/<sha256>/`, read back
      against the kept hash.
    - The unique (client, sha256) constraint settles two requests racing with the same
      bytes: one source.
  - **Routes** (`routers/client_sources.py`):
    - `POST /clients/{id}/sources`: 201 when new, 200 with `created: false` for another
      occurrence;
    - `GET` the list, one source with its reading, and `…/original` as an
      `application/octet-stream` attachment with an RFC 5987 name.
  - **A name is kept as written.** The brief's `safe_filename` (18.6.6's rule) reduced
    "Zadání.pdf" to "Zad_n_.pdf". A source's name is only displayed, since its key is the
    hash, so `display_name` keeps accents and removes only the path and control characters.
  - **Tests:**
    - `test_client_sources.py`, 22 tests, on SQLite and PostgreSQL. Among them:
      `test_a_source_is_kept_once_by_its_bytes_with_every_occurrence`,
      `test_a_source_is_found_only_within_its_client`,
      `test_a_reading_altered_in_storage_is_refused`,
      `test_the_same_bytes_kept_by_another_request_first_is_one_source`,
      `test_a_source_is_not_knowledge_and_no_study_reads_it`;
    - `apps/api/tests/test_client_sources_api.py`, 5 tests.
- **K2b. PPTX, ODT, DOC.** *(Landed.)*
  - **PPTX:** read slide by slide in `presentation.xml`'s own order, a paragraph a line.
    An empty slide is left out and the others keep their numbers.
  - **ODT:** headings and paragraphs numbered in body order, including inside lists and
    sections; tables by row. `text:s`, tabs and line breaks are kept; footnotes and comments
    are not part of a paragraph.
  - **XML parts:** PPTX and ODT parts are read with the stdlib after
    `document_text.check_zip_bounds`. A part over 50 MiB, or one that declares a DTD or
    entity, is refused before it is parsed; neither format ever has one.
  - **DOC:** `olefile` (BSD, pure Python, now in the `documents` extra) opens the compound
    file. `piece_text`, AIA's own code, reads the main text from the FIB and the CLX piece
    table ([MS-DOC] 2.5, 2.9.38): compressed pieces as cp1252, the rest as UTF-16LE, up to
    `ccpText`.
    - A field's code is dropped and its result kept.
    - An encrypted file is `document_encrypted`, anything before Word 97 is
      `document_too_old`, and anything out of bounds is `document_malformed`.
    - **A DOC's table is read as Word counts it:** each cell and each row-end mark is a
      paragraph. An empty cell and a row's end are the same `\x07`, told apart only by
      paragraph properties, so no row number is guessed.
  - **Fixtures:** `tools/source_fixtures.py write` has LibreOffice convert one fictional
    OpenDocument text into DOC, ODT and DOCX, and one presentation into PPTX. The outputs
    are pinned by SHA-256 in `fixtures/client_sources/index.json`, and `verify` checks them.
  - **Tests:** `test_source_readers.py`, 14 tests, on SQLite and PostgreSQL. Among them:
    - `test_an_odt_reads_as_its_docx_does`;
    - `test_a_doc_reads_its_cells_as_the_paragraphs_word_counts`;
    - `test_compressed_and_unicode_pieces_are_read_in_order_up_to_the_main_text`
      (a synthetic piece table, since LibreOffice writes only UTF-16 pieces);
    - `test_a_part_declaring_a_dtd_is_refused_before_it_is_parsed`;
    - `test_a_zip_that_inflates_far_past_its_size_is_refused`.
- **K2c. Datasets.** *(Landed.)*
  - **Readers.** CSV and XLSX use `document_text.read_csv` / `read_xlsx`. XLS uses `xlrd`
    (BSD, pure Python, in the `documents` extra); a date cell becomes its ISO date, and an
    encrypted workbook is `document_encrypted`. ODS uses the stdlib, a DTD refused as in K2b.
    - In ODS, repeated rows and cells are counted, never materialized past the grid bounds: an
      empty repeat (the rest of a sheet) only moves the numbering.
    - All four go through `document_text.grid_from_rows`, so every format has the same bounds
      and the same cell text.
  - **Segments.** One per row, located by sheet and row; a row ends at its last filled cell.
  - **Preview.** `domain/client_datasets.py` builds the `DatasetPreview` on
    `SourceReading.dataset`.
    - Per column: the header, the kind (NUMBER / DATE / TEXT / MIXED / EMPTY), how many cells
      are filled, the distinct values (counted up to 1,000), and five samples.
    - **The header rule:** row 1 is the header when it is all text and a number or a date is
      below it; otherwise the columns go by their letters.
    - A phone number reads as TEXT: it is an identifier.
  - **Personal data.** A column is flagged from its header (e-mail, phone, birth number, name,
    address; accent-folded, a five-letter stem matching Czech endings) or when a third of its
    values look like an e-mail, a Czech phone or a birth number (date and mod-11 checked).
    - Its samples are masked.
    - The patterns are pinned by fictional values in `fixtures/client_datasets/personal.json`.
    - **For K2d:** a flagged column is never sent to a model.
  - **OI-110, closed here.** `ClientSourceRepository.reread` and
    `POST /clients/{id}/sources/{source_id}/reading` read a source again when its format's current
    reader is not the one that read it.
    - So does adding the same bytes again.
    - The original never changes, and the new reading is stored beside the old one.
    - Audited as `CLIENT_SOURCE_REREAD`.
  - **Fixtures:** `tools/source_fixtures.py write <name …>` now writes only the named
    outputs and merges their pins, so the K2b fixtures keep theirs. One fictional export goes to
    ODS, XLSX and XLS (with a date style), plus a Czech CSV (BOM, semicolons, decimal comma,
    fictional phones).
  - **Tests:**
    - `test_source_datasets.py`, 24 tests, on SQLite and PostgreSQL;
    - `test_client_sources.py::test_every_format_on_the_owners_list_has_a_reader`;
    - two API tests: the dataset's masked columns, and the re-read route.
- **K2d. AI proposals from a source.** *(Re-planned 2026-10-15.)*
  - **Who pays changed.** The owner decided on 2026-10-15 that the client has a budget of its
    own for work on the client itself (`client-budget.md`, CB1-CB4 @ f50d2532). K2d runs as the
    client's own work: a `client_sources` project with no study, a `ClientWorkContext` issued
    against the lease, every hold and charge on the client's budget. It no longer runs beneath a
    chosen study. That also makes `:263-265` ("a worker job needs a study") no longer true.
  - **Documents first** (owner, 2026-10-15). A `DOCUMENT` source (PDF, DOCX, DOC, ODT, PPTX,
    TXT, MD) is extracted. A `DATASET` is refused by name (`dataset_not_extracted`) until a
    column-aware slice leaves out its personal-data columns cell by cell: its segments today are
    whole rows joined with ` | ` (`infrastructure/source_reading.py:575-577` @ f50d2532), so a
    flagged column cannot be removed from them safely. `IMAGE` / `VIDEO` have no text.
  - **What is sent.** The stored reading's segments, pinned by the reading's SHA-256 at enqueue
    (a re-read stores a new reading beside the old, `:374-379`), in batches of whole segments
    up to a bounded size. Each segment carries its index; the model never sees a locator it
    could alter. The material is Class A (`domain/residency.py:48-69`), so a route not approved
    for Class A refuses it at egress before anything leaves, and the step parks by name.
  - **The contract.** Closed (`extra="forbid"` throughout): a list of proposals, each `kind`
    (FACT / FINDING / TERM / ENTITY), `title`, `summary`, `quote`, `segment` (the index it
    quotes). One schema repair, as every agent.
  - **Grounding, by code.** A quote is kept only when `locate_quote`
    (`domain/deep_research/grounding.py:116-123`, NFKC and punctuation folded, case kept) finds
    it in the text of the segment it names. Otherwise it is dropped and counted; a dropped
    proposal is never shown. The locator written is that segment's, never the model's.
  - **What is written.** Each kept proposal becomes a client knowledge *proposal* (never an item),
    through a new `ClientKnowledgeRepository.propose_from_client_work(ClientWorkContext, …)`:
    `content` holds the quote and its locator (not `source_id`: `source_ref` refuses it on these
    kinds, `domain/knowledge.py:213-225`); `provenance` names `authored: "ai"`, the source, the
    occurrence, the reading's SHA-256, the locator, the run, the agent, prompt and harness. A run
    writes its proposals once: the step's retry finds them by run and writes none twice.
  - **Off by default** behind `AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED`; without it the step parks
    `client_source_proposals_unconfigured` and calls nothing. A client budget of 0 parks it
    `AWAITING_BUDGET` until a person lifts it (client-budget CB4).
  - **Burst, latency and money** measured before merge (CLAUDE.md § 8): requests per document
    (bounded by the 250,000-character reading cap and the batch size), tokens and the
    reservation per request at the model's prices; live latency is the owner's activation run.
  - **K2d1 landed** (2026-10-15): `domain/source_proposals.py`. `require_extractable` (a
    `DOCUMENT` with segments; `dataset_not_extracted`, `no_text`, `nothing_read` by name);
    `batches` (whole segments in order, at most `BATCH_MAX_CHARS` = 12,000 characters, a longer
    segment in pieces keeping its locator; deterministic, so at most 21 requests per document);
    `proposal_request` (`FAST_EXTRACTION`, Class A, `SourceProposals` closed, one schema repair,
    the segments numbered and no locator sent); `ground` (a quote kept only when `locate_quote`
    finds it in the segment it names; its locator is that segment's; `quote_not_found` and
    `unknown_segment` counted). Tests: `packages/aia_core/tests/test_source_proposals.py` (4).
  - **K2d2 landed** (2026-10-15): `ClientSourceRepository.reading_pin` (a person's scope, at
    enqueue: family, reader, the reading's SHA-256) and `pinned_reading` (the worker's
    `ClientWorkContext`, `RUN_WORKFLOW`: exactly that reading, verified, else
    `SourceReadingChanged`; another client's source not found);
    `ClientKnowledgeRepository.propose_from_client_work(ClientWorkContext, run_id=, drafts=)`
    files `ProposalDraft`s (`domain/knowledge.py`) as proposals with `authored: "ai"` and the
    run, `proposed_by` the person who started it; once per run (a retry gets back what was
    filed). `client_knowledge_proposals.run_id` and its index (migration `a9c1e3b5d7f2`,
    checked on PostgreSQL 16: upgrade, downgrade, upgrade, `alembic check` clean). Tests:
    `packages/aia_core/tests/test_client_work_proposals.py` (2, SQLite and PostgreSQL).
  - **K2d3 landed** (2026-10-15): `aia_executors/client_source_proposals.py`, the
    `client_source_proposals` workflow type (one step, `extract`, `max_attempts=1`;
    `domain/workflow_templates.py`). The executor takes the worker's `ClientWorkContext` (a
    study's scope is refused, `not_client_work`), reads the pinned reading (`reading_changed`
    when it moved), refuses a source it does not extract by name, preflights, then asks batch by
    batch through `StepModelCaller` (each request held against and charged to the client's
    budget) and files what `ground` keeps, once per run. Kill switch
    `AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED` (off; with `…_MAX_OUTPUT_TOKENS` and
    `…_RESERVATION_USD`, which must cover two calls at the model ceilings, as research's), which
    binds `FAST_EXTRACTION` on the route's model; unset, the step parks
    `client_source_proposals_unconfigured`. Class A: the route must name
    `CLASS_A_CLIENT_CONFIDENTIAL` and state its retention, else egress parks it
    (`egress_route_not_approved_for_class`, `egress_retention_unspecified`) before any call. The
    develop Compose passes the three keys, off. Tests:
    `apps/executors/tests/test_client_source_proposals.py` (9: grounded proposals filed and the
    client charged, the study not; unconfigured; both egress parks; a dataset refused; a $1 client
    budget waits `AWAITING_BUDGET`, a lift to $5 lets it finish -- client-budget CB5's proof
    under the real worker loop; the settings' binding and reservation floor).
  - **K2d4 landed** (2026-10-15): `application/source_proposals.py`:
    `start_source_proposals(session, client, work, store, source_id)` (the person's
    `ClientContext` with `PROPOSE_CLIENT_KNOWLEDGE` and their `ClientWorkContext`, the same
    person and client) pins the current reading and queues the run as the client's own work.
    One run per reading: its idempotency key is
    `client_source_proposals:<source>:<reading sha256>:<harness>:<n>`, and asking again returns
    the newest run for that reading unless it `FAILED` or was `CANCELLED`, when run `n+1` is
    queued. A dataset, a source without text or a document nothing was read from is refused by
    the step's own names before anything is queued. `latest_source_proposals`: the newest run
    about the source, any reading, with `current` (its reading is still the source's), the
    step's state, `reason` (the step's waiting reason or its last attempt's error reason) and,
    once it succeeded, its output. `WorkflowRepository.list_runs(key_prefix=)` matches a key's
    start literally (`_` and `%` are characters). Routes: `POST
    /clients/{id}/sources/{source_id}/proposals` (202 new, 200 an existing run, 422 by name,
    404 another client's source) and `GET` the same (the newest run, or null). Tests:
    `apps/api/tests/test_client_sources_api.py` (3: once per reading, a retry after a failed
    run, no study named; a dataset refused with nothing queued; another client's source 404) and
    `test_client_work_start.py::test_runs_are_listed_by_their_keys_prefix_matched_literally`.
  - **K2d5 landed** (2026-10-15). The web:
    - `lib/source-proposals.ts` (pure): `canPropose` (a document something was read from; never
      a table), `proposalsPhase` (the step's state: queued, running, budget, waiting, done,
      failed; a state it does not know is a wait, never done), `mayAsk`, `proposalsLine` and
      `proposalsReason` (the step's reasons in words, an unknown one as its code).
    - `components/aia/clients/SourceProposals.tsx`: Navrhnout znalosti on a document's file on
      the open item (`SourceCard ai=`, from `KnowledgeArea`: ask with
      `PROPOSE_CLIENT_KNOWLEDGE` + `RUN_CLIENT_WORK`, lift with `MANAGE_CLIENT_BUDGET`). It uses
      the AI button with a client-budget title. It reads the run again every 2 s while it is
      queued or running; it says why a run waits; a run waiting for the budget offers the lift
      (`workspace.liftClientWork`). A finished run says how many proposals wait and links to Ke
      schválení, and a run about an older reading says so.
    - The intake sheet's "Navrhnout znalosti z textu" is live: ticked, it asks about each
      document once its item is made and the batch filed. Asks still owed are kept for a retry
      after a failed filing. A refusal is named per file and stops no other. The sheet stays
      open to say what was asked.
    - Ke schválení: an AI proposal shows its quote, where the quote stands and the document
      (`ProposalResponse.from_source`: source, run, quote, locator, only for a proposal with
      `authored: "ai"` in the shape the step writes), says "Navrhla AI z dokumentu", and drops
      "Váš návrh".
    - `latest_source_proposals`' reason is the step's own (its last attempt's error reason)
      rather than the worker's general `ai_runtime_unavailable`; while waiting for budget it is
      the budget.
    - Tests: `source-proposals.test.ts` (7); `KnowledgeLibrary.test.tsx` (5: asked, followed to
      Ke schválení, paid by the client; the budget lift; a parked reason with nothing offered to
      a person who may not run; not offered for a table; the review card); `IntakeSheet.test.tsx`
      (3: documents asked only after their items exist, never a table; a refusal named; nothing
      asked unticked); the API's `test_an_ai_proposal_shows_its_quote_and_where_it_stands_for_review`;
      the executor tests now start through `start_source_proposals` and read the parked reason
      back. `tools/ui_workbench/intake_journey.mjs`: the box starts unticked and no proposals are
      asked.
    - In a browser, on the workbench at 1440 and 390 px: a TXT file added with the box ticked;
      the sheet said "AI navrhne znalosti z 1 dokumentu"; the item said "Čeká: AI návrhy z
      podkladů nejsou v tomto prostředí zapnuté." (the workbench worker has no gateway); no
      overflow, no page error.
  - **K2d6 landed** (2026-10-15). Measured, and two defects found and fixed (F-K4):
    - **Batches are bounded by the bytes they send**, not characters: `BATCH_MAX_BYTES` =
      24,000 bytes of the segments' JSON per request, a longer segment in pieces keeping its
      locator (`domain/source_proposals.py`, harness `aia-source-proposals-2`).
    - **A document takes at most `MAX_REQUESTS` = 42 requests**, else `too_many_requests`
      before any is sent. Whole-segment packing leaves at most half a batch empty, so 42 =
      2 x ceil(500,000 / 24,000) covers 250,000 characters of two-byte text.
    - **The hold is sized to the request, not the model.** `request_window_tokens(out)` is the
      fixed part (2,060 bytes) + 24,000 + 5 x out + 2,048, which is 48,588 tokens at 4,096 out.
      The settings' floor is two calls at that window (`reservation_usd`): **$0.4144** at
      $3 / $15, down from $1.32 at the model's 200,000. The executor checks every request
      fits (`window_fits`) before preflight.
    - Measured at develop-like settings ($3 / $15 per MTok, 4,096 output tokens), at the
      250,000-character reading cap, fictional Czech text from the reader fixture:

      | Shape | Requests | Largest request | Est. cost* | Ceiling** |
      |---|---|---|---|---|
      | 6,976 short paragraphs | 20 | 26,059 B | $0.81 | $2.75 |
      | 83 pages of 3,000 chars | 12 | 25,649 B | $0.48 | $1.65 |
      | 41 pages of 6,001 chars | 14 | 22,180 B | $0.51 | $1.77 |

      \* ~3 bytes per input token and 1,000 output tokens per request; the usage ledger records
      the real counts. \*\* The gateway's own bound: one token per byte and the full 4,096
      output tokens, no repair.
    - The absolute ceiling for any document: 42 requests x $0.4144 = **$17.40**.
    - Requests are sequential, one held at a time, so the client's budget needs **$0.42**
      free to start.
    - Local cost per run: batching 5-135 ms and grounding 8-270 ms for a whole document;
      the step writes once per run.
    - **Not measured: live latency per request.** It needs Bedrock on develop with
      `AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED`, which is the owner's activation. The route
      must name `CLASS_A_CLIENT_CONFIDENTIAL` and state its retention.
    - Tests: `test_source_proposals.py` (bytes-bounded batches for short lines and for two-,
      four- and six-byte characters, every request within its window; the request cap at 42
      and refused at 43; a reading at the character cap of Czech text within it);
      `test_client_source_proposals.py`
      (`test_the_reservation_covers_two_calls_at_the_request_window_not_the_models`: $0.41
      refused, $0.42 accepted;
      `test_a_document_over_the_request_cap_is_refused_before_any_call`: 50,000 four-byte
      paragraphs refused, nothing sent or spent).
- **K2e. Web intake.**
  - URL capture is one fetch through `RetrievalGate` beneath the chosen study. The snapshot is
    stored as a client source with `origin=web`, the URL and the retrieval time.
  - Deep Research import: from a finished run of a study of the same client, the person picks
    accepted evidence. Each becomes a proposal whose locator is the snapshot and the quote.
    There is no model call.
  - A run of another client's study is refused (404).
- **K2f. Review and acceptance.**
  - The review payload: the proposal beside its source excerpt at the locator, its origin and the
    paying study.
  - Batch accept names exact proposal ids.
  - The connected acceptance test at API, worker and PostgreSQL level covers documents, a dataset
    and web, and the plan's failure cases:
    - partial parse;
    - duplicate source;
    - unavailable extraction runtime;
    - wrong-client source;
    - interrupted processing;
    - a quote not found.
  - The screens are client-workspace C6, C7 and C8 on the client-workspace plan. K2 is complete
    when they pass the same journey in a browser.

**Not in K2:** typed revisions and base-revision checks (K3), study context selection (K4),
dimensions (K5) and retirement (K6).

## K3 contract (2026-10-21, written before the code)

K3a (F-K1) made an approval compare an edit's `base_revision` with the item's current revision.
K3 makes the records typed, so that who wrote a revision, what a person decided and against which
revision is a column read by one rule, not a provenance key a reader has to know about.
What was decided, and why:

- **Author** (`domain/knowledge.py` `KnowledgeAuthor`: PERSON, STUDY, AI). It is stored on
  `client_knowledge_proposals.author` when the proposal is filed:
  - `add` and `propose`: PERSON. A `ClientContext` is only ever a person's.
  - `propose_from_study`: STUDY.
  - `propose_from_client_work`: AI.

  A row from before the column is read by `author_of` from what its provenance says outright
  (`authored: "ai" | "person"`, a `study_id`), and otherwise as UNKNOWN. Nothing is backfilled.
  A person's `propose` before K3 carried no marker, so it reads UNKNOWN. We do not presume it
  was a person's.
- **Decision** (`KnowledgeDecision`: AUTHORED, ACCEPTED, ACCEPTED_OVER, REJECTED), stored on
  `client_knowledge_proposals.decision`. A CHECK ties it to the status it settled. A decision
  made before the column reads null (unknown). We do not reconstruct it from the note.
- **The reviewed revision** (`client_knowledge_proposals.reviewed_revision`) is the item revision
  the reviewer named, recorded as named and null when they named none. We never fill it in with
  the current revision, because that would claim they saw it. `reviewed_decision` is the one
  rule an approval passes, under the item's `FOR UPDATE` lock:
  - a named revision that is not the current one is stale, whatever the edit's base. The reviewer
    read an older item than the one the accept would change. This widens F-K1: K3a let such an
    accept through when the base was current;
  - a base equal to current is ACCEPTED;
  - any other base, unknown included, is ACCEPTED_OVER when the reviewer named the current
    revision, and stale otherwise.

  A rejection is never stale and records the revision it names. Naming a revision for a new item
  is refused by name: `NoRevisionToReview`, API 422 `no_revision_to_review`. The 409
  `knowledge_proposal_stale` details now carry `reviewed_revision`.
- **A typed revision.** `KnowledgeRevision` carries `author`, `decision`, `base_revision`,
  `reviewed_revision`, `evidence` and `sha256`. They are read through the revision's proposal row
  in the same scope, one more query per page. The same fields are on
  `GET …/knowledge/items/{id}/revisions` and on every proposal response.
  - `evidence` (`RevisionEvidence`) is an AI revision's grounding, whole or not at all: the
    source, its SHA-256, the reading's SHA-256, the segment, the quote, the locator and the run.
    This is F089's data half: an accepted AI item keeps its quote, locator and document.
  - `sha256` (`revision_sha256`) is the SHA-256 of the revision's title, summary and content as
    canonical JSON (sorted keys, no spaces, UTF-8), pinned by a test. K4's frozen context names
    the exact text it read by it. It is computed when read, not stored: a revision row is
    append-only, and a stored hash would be one more value to keep equal to it.
- **Not typed here**, on purpose:
  - per-kind payload schemas: assertion class, scope and time (K6); dimension definitions (K5);
  - a dataset's schema (`client-data-in-analysis`);
  - batch accept naming displayed versions, and the review screen (K2f, C6).

  `content` stays the shape it is. The provenance JSON is unchanged, and tests still assert it
  exactly.
- **No switch.** Nothing a model sees changes. A person meets the new behaviour in one case only:
  an accept that names a revision the item is no longer at. That was a stale screen accepting
  over a newer correction (F-K1), and refusing it is the fix. The web sends `reviewed_revision`
  only from "Schválit místo revize N", with N read from the 409.

## Findings

**F-K1 — A pending item revision can replace a newer accepted correction.**
1. Claim: approval does not test whether the item changed after the proposal was created.
2. Anchor: `client_knowledge_repository.py:250-296, 353-387, 516-527 @ 67af44e`; ProposalCreate
   and DecisionRequest in `routers/workspace.py:385-405` carry no reviewed base revision.
3. Reproduction: create a FACT at revision 1; queue a study proposal editing it; save a newer
   human correction at revision 2; approve the earlier proposal. It succeeds at revision 3 and
   the earlier text becomes current. The two earlier revisions remain in history.
4. Consequence: a validly authorized acceptance can unintentionally undo a newer correction;
   revision history alone does not provide conflict protection.
5. Smallest fix: pin base revision/hash on a revising proposal and compare under the existing
   item lock before changing current content; return a named stale-proposal conflict.
6. Test: disposable `test_a_pending_edit_can_replace_a_newer_accepted_correction` reproduces
   current behavior. Implementation must add an ordinary regression expecting refusal and a
   separate explicit rebase/accept case, with a PostgreSQL contention case where required.

**Disposition (K3a, 2026-10-14).** Fixed as the smallest fix above, ahead of the rest of K3:
- A revising proposal records `base_revision`, the item revision it was written from
  (`client_knowledge_proposals.base_revision`, migration `d4f6a8c0e2b5`). An edit sent with an
  older `base_revision` is refused before it is filed; without one it is written from the
  revision current then.
- An approval locks the item and compares (`_require_current_base`). A base that is not the
  current revision raises `StaleKnowledgeProposal` and changes nothing; the API answers 409
  `knowledge_proposal_stale` with `item_id`, `base_revision` and `current_revision`.
- The explicit accept: a reviewer who names the current revision as `reviewed_revision` approves
  the edit over it, and the new revision's provenance records `base_revision` and
  `accepted_over_revision`. A rejection needs neither.
- A pending edit filed before the column has a null base: unknown, so stale, never current.
- The web: an item edit sends the revision it showed; a refused save says the item changed; the
  pending card, on a refused approval, says which revision the edit came from and which is
  current, and offers "Schválit místo revize N".
- Tests: `test_an_edit_written_before_a_newer_correction_is_refused_and_changes_nothing`,
  `test_a_reviewer_who_names_the_current_revision_accepts_the_edit_over_it`,
  `test_a_stale_edit_can_still_be_rejected`,
  `test_a_persons_edit_from_an_older_revision_is_refused_before_it_is_filed`,
  `test_an_edit_filed_before_its_base_was_recorded_is_treated_as_stale` (core);
  `test_an_edit_written_from_an_older_revision_is_a_409_until_the_reviewer_names_the_current`
  (API); `staleEdit` and two KnowledgeLibrary tests (web). On PostgreSQL the item row is locked
  with `FOR UPDATE` across the check and the write; no separate contention test was added,
  since the lock is the same one `_apply` already took.
- Not done here: typed revisions, rebase with a merge view, and conflict notices to dependent
  studies stay in K3 and K6.

**F-K2 — Knowledge classification is being used as a dimension catalogue entry.**
1. Claim: a title-only DIMENSION can be accepted and offered as a selectable client dimension.
2. Anchor: `KnowledgeArea.tsx:127-161`, `domain/knowledge.py:121-138`, `clientDimensions` in
   `apps/web/src/research/persona.ts:52-61 @ 67af44e`.
3. Reproduction: add DIMENSION with title only; study retrieval returns it with empty content;
   the catalogue adapter exposes every DIMENSION by item id and title.
4. Consequence: the UI can suggest a usable measure without a definition or materialization.
   Fieldwork currently declares selection unapplied, so this is not a claim of silent numeric use.
5. Smallest fix: separate dimension definition from materialization/use eligibility; display
   draft/non-executable definitions honestly and allow computational selection only when resolved.
6. Test: disposable `test_a_dimension_can_be_accepted_with_no_definition_or_values` pins the
   current behavior; connected acceptance must refuse execution with an unresolved definition.

**F-K4 — A document's requests were bounded neither in number nor in size** (fixed in K2d6).
1. Claim: K2d1's batching packed by characters, so the "at most 21 requests per document"
   it stated did not hold. A request's bytes were not bounded either.
2. Anchor: `batches` in `domain/source_proposals.py @ 4b15e6f6` (`BATCH_MAX_CHARS` = 12,000,
   whole segments, a batch closed when the next would pass it).
3. Reproduction:
   - 41 pages of 6,001 characters made 41 requests.
   - 12,000 one-character lines made one request of 338,949 bytes, over the model's 200,000
     tokens. Each short segment carries ~28 bytes of JSON.
4. Consequence: the burst and the money a document could cost were not what the plan said.
   A document of short lines would have been refused by the gateway, after its hold was taken.
5. Fix: batches bounded by bytes (`BATCH_MAX_BYTES`), a request cap (`MAX_REQUESTS`, refused
   by name before any call), and the hold sized to the request's window (K2d6).
6. Tests: `test_a_batch_is_bounded_by_the_bytes_it_sends_whatever_the_text`,
   `test_a_document_needing_more_than_the_request_cap_is_refused_before_anything_is_sent`.

**F-K5 — A step stopped between batches paid for its answered batches again** (fixed;
Codex review of #446).
1. Claim: a document's answers lived only in the attempt's memory. A step parked at the
   client's budget, or released by its worker, restarted at batch 0 when it resumed and
   re-sent the batches already paid for.
2. Anchor: the batch loop in `aia_executors/client_source_proposals.py @ 43e20119`.
3. Reproduction: `test_a_document_parked_between_batches_resumes_without_paying_twice`
   makes 3 requests without the journal and 2 with it.
4. Consequence: every lifted or released multi-batch document billed its first batches
   twice.
5. Fix: `client_work_journal` (migration `c5e7a9b1d3f6`) keeps each answer the moment it
   returns, under the lease. It is keyed by the client and a fingerprint of exactly what
   was sent (request, policy, output limit, harness), so a resumed step, or a new run over
   the same reading, replays what was answered and preflights only if something is
   unanswered. The step reports `sent` and `replayed`.
6. Tests: the one above; `test_client_work_journal.py` (2).

**F-K6 — A run stopped for recovery could never be asked again** (fixed; Codex review of #446).
1. Claim: with one attempt, a retryable failure whose outcome is known ends in
   `RECOVERY_REQUIRED` (`max_attempts_exhausted`), not `FAILED`. Asking again counted only
   failed and cancelled runs as ended, so it returned the stuck run forever.
2. Anchor: `_ENDED_WITHOUT_RESULT` in `application/source_proposals.py @ 43e20119`.
3. Reproduction:
   `test_a_run_stopped_for_recovery_restarts_only_when_no_paid_call_is_uncertain`.
4. Consequence: a document could not be proposed from again until an operator intervened.
5. Fix:
   - A run is `restartable` when it failed, was cancelled, or stopped for recovery with
     every paid call's outcome known; asking again then starts a new run, which replays
     the journal.
   - A run left with a paid call of unknown outcome
     (`paid_external_call_side_effect_uncertain`) is never restarted from here.
   - The API answers `restartable`, and the web's ask-again follows it.
6. Test: the API test above; `source-proposals.test.ts`.

**F-K3 (hypothesis) — A web test failed once under the full suite.**
`ExecutionSteps.test.tsx` › "offers the report's PDF when the run stored one, and says why when
it could not" failed once in `npx vitest run` (1 of 1511, 2026-10-15, while K2d5 was written).
It passed alone twice and in the next full run. There is no reproduction, so it is a
hypothesis. The file is not touched by K2d. Next step: run the full suite repeatedly and, if it
recurs, capture the assertion and its timing.

## Doc follow-up

After each slice lands, update CLAUDE's knowledge modules/routes and input/review surfaces;
ARCHITECTURE's knowledge consumption and revision-conflict boundary; client-first/data-model/
artifact documentation where the implemented contracts change; open-items with F-K1/F-K2 and
their actual dispositions. Record exact edits in each PR; no shared file is edited here.
Reconcile old MVP-ACCEPT-1 and its machine-readable criteria with the owner's all-four scope
and ADR 0019, preserving existing checks rather than dropping inconvenient requirements.
Do not mark this plan's proposal as an approved product decision in those documents.

## Decisions still open

- Supported formats are settled by the 2026-10-13 decisions in K2 slicing above; they are not asked again. Unreadable image/video outcomes remain explicit.
- Representative client/study example for review of the proposed structure and use roles.
- Where individual dimensions may be materialized, with licensed/data/methodology restrictions
  resolved through their existing owners rather than by a generic knowledge accept.
- Correction and retirement user wording and the exact dependent-study notice contract.
- Scientific eligibility remains with canonical methodology and current evidence contracts;
  accepting this product structure cannot approve a new scientific rule.

## Review outcome

Draft prepared for authorized publication with code anchors and two reproduced gaps.
The publication base is develop `4d8f07d934e88a9d15b9da47c78c42a1b01ca019` (PR 194's
documentation follow-up); the audited runtime code remains the baseline above.
No production redesign, migration, independent review or client acceptance has occurred.

## Added by the master plan (2026-10-19)

**K8.** Three plans own evidence into knowledge today: `verified_sources.py` ("Ověřeno, přidat zdroj"),
K2e here and `deep-research-web-search` 37. They disagree on whether the result is an item or a proposal,
and a document item holds only `source_id`, so Deep Research never sees the file text
(`knowledge_access.py:75-90`). K8 decides once and gives `freeze_knowledge` the text snapshot. This plan
owns the knowledge side; S2 supplies the bundle reader. Gap G36; interface I19.


## Execution predecessors (2026-10-20)

K2e/K2f, K3, K4 and K8 are W1. K4 extends the existing immutable context loader before the
Lead/run consumes reviewed knowledge; K8's capture/import semantics precede the web/Deep Research
intake consumers. K5 is W2 with an actual own-dimension consumer; K6 is W3, and K7a's research
acceptance is W5. K7 cannot be completely ticked while its separately retained Simulation coverage
is open; K7a records the MVP subset evidence and leave the remaining extension visible.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

**New chunks.** K9 (W3), K10 (W3), K11 (W1, with `lead-orchestration#LO1`;
the wallet ceiling only: the posture setter and its Profil UI are `deep-research-web-search#53`'s, G37,
and K11 places the ceiling beside it in the same Pravidla card; both are listed read-only in Settings, I15), K12 (W1; #513 proposed `client-workspace#C10`, which is taken).

**Existing chunks, changed.** K8 freezes the "Interní dokument" mark on the frozen `KnowledgeSource`
at enqueue (G64; a bundle-contract change needing ADR 0021's defect note). The fold of
`client-workspace` C6-C9 lands here: C6 → K2f/K3, C8 → `client-data-in-analysis#2/2a/3` with its UI
chunk `client-data-in-analysis#10`, C9 → K6; C7 is closed as superseded by `client-budget`.
