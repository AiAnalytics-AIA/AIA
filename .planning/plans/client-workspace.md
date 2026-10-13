---
status: in-progress
chunks:
  - "[x] 0. Design on the canvas (Klient row of the research studio) and this plan"
  - "[x] C1. Client shell: Profil tab, counts on tabs, status in the bar, Přidat znalost beside Nový výzkum"
  - "[x] C2. Výzkumy as a table: status filters, where each study is, what it brought into knowledge; one search with project memory"
  - "[x] C3. Folders and labels: per-client folders, labels, an item in one folder with any labels (migration, repository, routes)"
  - "[x] C4. Knowledge library: views, folder tree, label and kind filters, the open item beside the list, revision history, bulk move and label"
  - "[ ] C5. Profile: the client record's fields, contacts, brands and competitors as entities, self-approval on the client"
  - "[ ] C6. Review queue: proposals grouped by source, with citation, diff and editable folder/labels; action-named buttons (needs lifecycle K3)"
  - "[ ] C7. Intake sheet: one way in for files, links and text; dataset or document; the paying study for AI extraction (needs lifecycle K2)"
  - "[ ] C8. Data area: datasets with column check, personal-data columns dropped, ownership and licence; use in a study says V AIA zatím není (needs lifecycle K2)"
  - "[ ] C9. Retire and restore an item from the library (needs lifecycle K6's contract)"
  - "[ ] C10. Přehled complete (Čeká na vás, feed, knowledge health); workbench journey at four widths; Doc follow-up"
---
# The client workspace: managing a client's knowledge and taking in its data

**Written:** 2026-10-13 against `develop` @ `5d545eb` · **Branch:** `feature/client-workspace`
· **Design:** the *Klient · pracovní plocha a příjem dat* row of the AIA desktop research studio
canvas (artboards `Client`, `ClientResearch`, `ClientKnowledge`, `ClientReview`, `ClientIntake`,
`ClientData`, `ClientProfile`).

## Problem

The page that opens when a person opens a client (`/app/clients/<client>`) shows the client's
work, but the person cannot manage what AIA knows about the client or bring the client's
material in:

| Today | Anchor @ `5d545eb` | Consequence |
|---|---|---|
| Knowledge cards have no action: no edit, history or retire | `apps/web/src/components/aia/clients/KnowledgeArea.tsx:27-59` | A wrong item can be neither corrected nor taken out of use from the page |
| The add form takes kind, title and description, with no file | `KnowledgeArea.tsx:130-164` | A DOCUMENT or DATASET item is a title, not the document or the data |
| Data is a read-only list of DATASET/ARTIFACT items | `DataArea.tsx:17-45` | A client's data has no way in |
| Uploads exist only on a study's brief | `apps/api/src/aia_api/routers/workspace.py:1105` (POST `/studies/{id}/workspace/attachments`), `study_workspace_repository.py:464` | Material that belongs to the client is filed under one study |
| Items have no grouping beyond the six fixed sections | `packages/aia_core/src/aia_core/domain/knowledge.py:85` (`KNOWLEDGE_SECTIONS`) | A client with a few hundred items is one long list per kind |
| The revision history route has no caller in the client UI | `workspace.py:830`; `apps/web/src/lib/api.ts:505` (`workspace.revisions`) | Who changed what is invisible |
| Client fields are id, slug, name, status, reference and self-approval | `domain/scope.py:526-543` | No industry, market, brands, competitors or contacts |
| A client's status is set only from Settings, by an administrator | `routers/scope.py:342-376` | Expected; the page should show the status, not hide it |
| Výzkumy is a plain list without columns, filters or row actions | `StudyList.tsx:27-73` | Finding a study among a client's dozen means scrolling |
| `RETIRED` exists on items and revisions, but no route sets it (grep finds no writer) | `infrastructure/tables.py:732, 769` | Retirement is half there |

## How this plan sits beside *Client knowledge that studies can use correctly*

[`client-knowledge-lifecycle.md`](client-knowledge-lifecycle.md) (in progress, K2 next) owns
**what knowledge means**:
- source revisions, extraction and its locators;
- typed payloads;
- base-revision checks on decisions (F-K1);
- retirement semantics;
- how studies consume knowledge.

This plan owns **the client page a person works in**:
- the shell, Přehled, Výzkumy and Profil;
- folders and labels;
- the library and review screens;
- the intake sheet and the Data area.

The rules between the two:
1. **No second intake path.** C7 and C8 are the web side of K2's journey and wait for K2's API.
   This plan builds no extraction, storage or dataset parser of its own.
2. **Review and retirement follow the lifecycle plan's contracts.** C6 waits for K3's
   base-revision decision, and C9 waits for K6's retirement contract.
3. **What C1-C5 build is that plan's base, not a rival.** Folders, labels and profile fields are
   organization of the existing items and the client record. They change no payload and no
   decision rule.
4. **This plan never edits the lifecycle plan's file.** Anything that crosses goes under Doc
   follow-up, or to that plan's own PR.

## Decisions

| # | Decision | Who, when |
|---|---|---|
| D1 | **The study budget pays** for AI work on client material. A client has no budget; the extraction job is enqueued beneath a study the person picks in the intake sheet, and is reserved against that study's budget like any study job (`workflow_repository.py:1017` `reserve_budget`; jobs beneath a study, `routers/research.py:1233`). With no active study to pay, files are still stored and the sheet says extraction needs a study. The paying study is recorded in each proposal's provenance. | Owner, 2026-10-13 |
| D2 | **Folders are per client.** No organization-wide template. | Owner, 2026-10-13 |
| D3 | An item is in **at most one folder** and has **any number of labels**; no folder means *Bez složky*. Labels are per client, with a colour from a closed set of tokens. | Drawn in the design; not objected to. Confirm in the C3 review |
| D4 | **Folders and labels are organization, not knowledge.** AI does not see them, changing them writes no knowledge revision and does not advance `context_revision`, and each change is audited. A proposal may carry a suggested folder and labels, applied when it is accepted. | This plan |
| D5 | **Profile fields live on the client record** (`clients`), not as knowledge items; brands and competitors are kept as ENTITY items so studies can use them. | Proposed in the design; **open**, owner to confirm before C5 |
| D6 | Buttons say what is decided, never a bare *Schválit*: *Přijmout do znalostí*, *Upravit a přijmout*, *Zamítnout*. This follows the lifecycle plan's review interface ("Avoid an unqualified Approve label"). The canvas's Ke schválení artboard is updated in C6. | Lifecycle plan § Acceptance actions |
| D7 | Retiring never deletes. A retired item stays in history and in the studies that used it, and new studies do not see it. | Lifecycle plan § Corrections and lifecycle |
| D8 | Using a client dataset in a study is not built here. The Data area says *V AIA zatím není* where a person would expect it. | ADR 0018's rule for what AIA does not have |

## Chunks

Each chunk is its own PR into `develop`, small enough to review in one sitting.

### C1. Client shell (landed)

- **Profil tab:** `profile` in `AREAS` and `ClientArea`, with its route at
  `app/app/clients/[clientId]/profile`. Until C5 it shows the client record: name, status and
  your role. It says that the profile proper (industry, market, brands, competitors, contacts)
  is not in AIA yet, and offers no field that would save nowhere.
- **Counts on the tabs:** the client's tabs count its open studies by kind, proposals waiting
  for a decision (marked as waiting on a person) and datasets. A badge is drawn only for a
  count above zero. Each count is also said in words for a screen reader.
- **The counts come from `GET /clients/{id}`, not the overview.** The layout reads that route
  once per client, and every area shows the tabs. The overview reads up to 12 studies' artifacts,
  which is too heavy for every tab.
- **The counts in the API:** the response gains `counts`. It holds `research` and `simulations`,
  which leave archived studies out, and `pending_proposals` and `datasets`, which are null
  without `VIEW_CLIENT_KNOWLEDGE`: unknown, never zero.
- **Status chip:** the client's status sits in the bar. The one-line profile summary waits for
  C5's fields.
- **Přidat znalost:** shown beside *Nový výzkum* on every area to whoever may propose
  knowledge. It opens the existing add form on Znalosti (`?add=1`, read once and then removed
  from the URL). It is named *Přidat znalost*, not *Přidat podklady*, because the form takes no
  file yet; C7 renames it when the intake sheet lands.
- **Counts follow changes:** adding knowledge or deciding a proposal re-reads the client, so
  the counts follow.
- **Tests:**
  - API: `test_the_client_counts_its_open_studies_and_its_knowledge_for_the_tabs`;
  - web: `ClientFirst.test.tsx`, which covers the counts and their words, null counts drawn as
    nothing, the add action and the form it opens, its absence without permission, and Profil;
  - the UX journey visits `/profile`.

### C2. Výzkumy as a table (landed)

- **The table:** Výzkumy and Simulace list the client's studies as a table. Columns: the study
  (its name, linking to where it stands, and the stage line); its status; what it brought into
  the client's knowledge; when it changed.
- **Filters:** *Aktuální* is the default and leaves out archived and cancelled studies. The
  others are *Rozpracované*, *Ke kontrole*, *Předané* and *Archiv*, each with its count. An
  unknown status falls under *Rozpracované* rather than nowhere.
- **Orders:** newest change first, or by name in Czech order (`localeCompare("cs")`: *č* after
  *c*, *ch* after *h*).
- **Search:** stays the existing project-memory search above the table (`MemorySearch`). From
  two characters it searches the studies' designs; below that it says to type more. The plan's
  "filter names below two characters" was not built: one search, one behaviour.
- **What a study brought:** `GET /clients/{id}/studies` gives each study `knowledge`, holding
  `approved`, `proposed` and `rejected`. It comes from the new
  `ClientKnowledgeRepository.proposal_counts_by_study`, one grouped query.
  - Present only for a caller who may read the client's knowledge; otherwise the column is not
    drawn.
  - A person's own addition counts against no study.
  - The cell shows *přijato: n* and *čeká: n*. A turned-down proposal is not counted as
    brought.
- **Tests:**
  - core: `test_each_study_counts_what_it_proposed_by_status_within_its_own_client`;
  - API: `test_the_studies_list_says_what_each_study_brought_into_the_clients_knowledge`;
  - web: `lib/study-table.test.ts` (filters, counts, orders, unknown versus nothing), plus two
    rendering tests in `ClientFirst.test.tsx`.

### C3. Folders and labels (landed)

- **Domain** (`domain/knowledge.py`):
  - `KnowledgeFolder`, `KnowledgeLabel` and the closed `LabelColour` set: BLUE, TEAL, GREEN,
    ORANGE, VIOLET and SLATE, the design system's wayfinding hues. A label never borrows a status
    colour.
  - `organizer_name` stores a name trimmed and with inner whitespace collapsed, at 1-80
    characters. `organizer_key` compares names: case and spacing do not count, accents do,
    because in Czech they change the word.
  - `OrganizerNameTaken` is raised for a name the client already uses.
  - `KnowledgeItem` gains `folder_id` and `label_ids`.
  - Folders are flat: no nesting until a client needs it.
- **Migration** `f2a4c6e8b0d9`: `client_knowledge_folders` and `client_knowledge_labels`, each
  unique on (client, name key); `client_knowledge_item_folders`; `client_knowledge_item_labels`.
  - **Changed from the plan:** an item's folder is its own table, not a column on
    `client_knowledge_items`. That row's `modified_at` has `onupdate`, so filing an item would
    have moved its date and made it look edited. That would also corrupt *Starší než rok* (C4).
    Filing now touches neither the item's revision nor its date.
  - Checked on PostgreSQL 16: `alembic upgrade head`, `alembic check` (no drift) and a downgrade
    with re-upgrade.
- **Repository:** `ClientKnowledgeRepository` stays the only reader and writer of these tables.
  - Methods: `folders` and `labels` (each with its count of active items);
    `create_folder`/`rename_folder`/`delete_folder`; `create_label`/`update_label`/`delete_label`;
    `place`.
  - Behaviour of `place`: it is all-or-nothing, at most 200 items. `KEEP_FOLDER` leaves the
    folder as it is, `None` takes items out of their folder, and a label both added and removed
    is refused.
  - `items()` filters by `folder_id`, `unfiled` and `label_id`, and only this workspace read
    carries the filing. `for_study` never does (D4), and both study consumers
    (`context_snapshot`, `freeze_knowledge`) pick explicit fields.
  - Every change writes an `access_audit` row (`CLIENT_KNOWLEDGE_FOLDER_*`,
    `CLIENT_KNOWLEDGE_LABEL_*`, `CLIENT_KNOWLEDGE_ORGANIZED`).
  - Organizing needs `PROPOSE_CLIENT_KNOWLEDGE`; reading needs `VIEW_CLIENT_KNOWLEDGE`.
- **Routes**, under `/clients/{id}/knowledge/`:
  - `GET`/`POST folders`, `PUT`/`DELETE folders/{KNF-…}`;
  - `GET`/`POST labels`, `PUT`/`DELETE labels/{KNL-…}`;
  - `PUT placement` with `item_ids`, `folder_id` (left out keeps the folder, `null` takes items
    out) and `add_labels`/`remove_labels`;
  - `GET …/knowledge?folder=KNF-…|unfiled&label=KNL-…`;
  - items carry `folder_id` and `label_ids`.
  - Errors: a name clash is 409 `name_taken`; a folder, label or item of another client is 404;
    a bad shape is 422.
  - **Changed from the plan:** there is no per-item placement route. The bulk route with one id
    does the same.
- **Tests:**
  - core, `test_client_knowledge.py`, seven new tests:
    - name rules per client;
    - filing writes no revision and moves no dates;
    - filters by folder, by label and for items in no folder;
    - deleting a folder or label keeps the items;
    - all-or-nothing and never across clients;
    - what a study reads carries no filing;
    - permission and audit.
  - These run on SQLite and on PostgreSQL 16.
  - API, `test_client_api.py`: filing end to end, and across clients with all-or-nothing.

### C4. Knowledge library (landed)

**The page.** `KnowledgeArea` is now the library.

- **The side panel** (`Pohledy, složky a štítky`) holds the views, the folders and the labels:
  - **Views:** *Všechny znalosti*; *Ke schválení*, with the client's pending count; *Bez složky*;
    *Starší než rok*.
  - **Folders,** each with its count.
  - **Labels** as toggles, each with its count.
  - Creation: *Nová složka* opens a prompt; *Nový štítek* opens an inline name-and-colour form.
  - A note says AI and studies never see folders or labels, and that filing writes no revision.
- **The main column:**
  - the view's heading, with *Přejmenovat* and *Smazat složku* on a folder;
  - the active label, with its colour, *Přejmenovat*, *Smazat štítek* and *Zrušit filtr*;
  - kind chips (*Vše*, *Zdroje a dokumenty*, *Fakta, zjištění, pojmy*, *Dimenze*, *Audience*,
    *Data*), which replace the old section tabs;
  - search;
  - the items as a table: tick box, the item, kind, folder and labels, revision, change.

`KnowledgeLibrary` holds the table, the bulk bar and the open item.

- **Bulk bar:** acts on the ticked items that are still shown, so nothing hidden moves unseen.
  It can move them to a folder or to *Bez složky*, and add or remove a label. Every action is
  one `PUT …/placement`.
- **The open item,** beside the list and wrapping below it on narrow screens:
  - **Edits:** name and summary are edited into a new revision through the existing proposal
    route with `item_id` (ADR 0019). Where the client turned self-approval off, the panel says
    the edit waits for someone else.
  - **Filing:** a folder select, label chips that can be removed, and a select to add a label.
  - **History:** from `GET …/items/{id}/revisions`, newest first, each revision with its origin
    in words: from a study, written by a person, or a decided proposal.
  - **Reading only:** without `PROPOSE_CLIENT_KNOWLEDGE` the page offers nothing that would
    write (no tick boxes, new folder, add or edit), and the folder select is disabled.

**Logic in `lib/knowledge-library.ts`, pure and tested:**
- what each view asks the API for;
- *Starší než rok* means more than 365 days since the last change. An item with no date is not
  called old, because that would be a guess. "Now" is fixed when the library opens.
- `atCap`: a full page of 200 says *Zobrazeno prvních 200 …* rather than looking complete;
- the selection helpers;
- `LABEL_DOT`, which maps each label colour to its hue token.

**Changed from the design:**
- *Předchozí studie* left Znalosti. Výzkumy's *Předané* filter (C2) shows the same studies, with
  more.
- Folder and label management lives in the side panel and the view's heading, not a separate
  settings page.

**Found on the way, fixed:**
- I first removed strings that Přehled still reads (`aia.knowledge.sections.*`). `t()` falls back
  to the key silently, so nothing failed. The strings are restored, and `ClientFirst.test.tsx`
  now asserts the four section names on Přehled.
- C3's `Result.tuples()` is deprecated since SQLAlchemy 2.1; fixed in its own commit.

**Tests:**
- `lib/knowledge-library.test.ts`: views, the year rule, the cap, selection.
- `clients/KnowledgeLibrary.test.tsx`, eight rendering tests:
  - filed rows and counts;
  - the API asked by folder, by *Bez složky* and by label;
  - the old view;
  - bulk move, label and un-file, each checked by its request body;
  - the open item: history, an edit as a new revision, re-filing, removing a label;
  - an edit waiting under independent review;
  - creating a folder, and the Czech message when its name is taken;
  - a reader without the right to propose.
- `ClientFirst.test.tsx`: updated for the new controls.

### C5. Profile
- **Depends on:** D5 being confirmed first.
- **Migration:** `clients` gains short code, industry, market, description and research language.
  `client_contacts` holds name, role, e-mail and whether they receive reports; AI never sees
  contacts.
- **Brands and competitors:** written as ENTITY items through the repository.
- **Self-approval:** `allow_self_approval` (`domain/scope.py:541`) becomes a switch on the
  profile, behind the same permission Settings uses for it. Status is shown and stays the
  administrator's (`routers/scope.py:342`).
- **Profile history:** read from the audit.
- **Tests:**
  - contacts never appear in any payload built for a model. Assert it on the study context the
    research agents freeze (`domain/research_agents.py`);
  - a member without the permission cannot change self-approval;
  - archive and status are unchanged.

### C6. Review queue
- **Depends on:** lifecycle K3.
- **What it does:**
  - proposals grouped by source (file or study);
  - each shows its citation (K2's locator), its suggested folder and labels, editable before
    accepting;
  - a change to an existing item shows as a diff against the reviewed base revision;
  - a stale proposal shows K3's conflict;
  - batch accept names the displayed proposal ids;
  - when self-approval is off, a person's own proposal says why they cannot accept it;
  - action-named buttons (D6).
- **Canvas:** update the Ke schválení artboard's labels in the same PR.

### C7. Intake sheet
- **Depends on:** lifecycle K2's client-level source API.
- **What it does:**
  - one sheet from **Přidat podklady**, or from files dropped anywhere on the client;
  - reading progress per file;
  - a table asks *Datová sada* or *Dokument*;
  - an image says AI cannot read it;
  - folder and labels for the batch, or per file.
- **Navrhnout znalosti z textu:** an opt-in choice, needing a paying study (D1); a picker of the
  client's active studies, with that study's remaining budget. The results go to Ke schválení,
  never straight into knowledge.
- **Tests:** web: the sheet's state machine as pure functions, and no paid job without an
  explicit study. API and worker tests belong to K2.

### C8. Data area
- **Depends on:** lifecycle K2's tabular contract.
- **What it does:**
  - a datasets table;
  - per-column meaning: Identifikátor, Demografie, Odpověď, Váha, Čas/vlna, Vypustit;
  - sample values masked where a column looks like personal data, and such a column must be
    *Vypustit* before saving;
  - ownership, licence and data class, with a dataset without a licence not usable;
  - *Použití ve studii: V AIA zatím není* (D8);
  - the *Sdílená data AIA* card kept.
- **Tests:** web: the column-check rules as pure functions; the personal-data detector's
  patterns pinned by a fixture of fictional values.

### C9. Retire and restore
- **Depends on:** lifecycle K6's contract.
- **What it does:** *Vyřadit* and *Vrátit do použití* on the open item, each with a reason; the
  retired view. Retirement writes `status = RETIRED` on the item and a revision (D7).
- **Tests:** a retired item is absent from a new study's context and present in a frozen run's,
  and restore brings it back.

### C10. Přehled, the journey, Doc follow-up
- **Přehled:** *Čeká na vás* (pending proposals, datasets to check, studies waiting on the
  person), the intake and knowledge-change feed, and knowledge health (starší než rok, bez
  složky).
- **Journey:** `tools/ui_workbench/client_journey.mjs`, which:
  - creates a fictional client;
  - adds folders and labels;
  - edits and moves items;
  - reviews proposals;
  - runs at 1440/1024/768/390;
  - makes zero paid jobs.

## What this plan deliberately does not do

- No extraction, parsing, dataset storage or web capture of its own (lifecycle K2).
- No change to how a study consumes knowledge (lifecycle K4) and no dimension materialization (K5).
- No client budget (D1), and no organization-wide folder template (D2).
- No search index or vector store. Folder and label filters are SQL over the repository.

## Findings

None yet.

## Doc follow-up

For the docs PR after each chunk merges:
- **`CLAUDE.md` § 2:**
  - `routers/workspace` gains the folder, label and placement routes (C3) and the profile
    routes (C5);
  - `components/aia/clients/` gains the library, review, intake and profile screens;
  - `ClientKnowledgeRepository` stays the only reader and writer, now of folders and labels too.
- **`ARCHITECTURE.md`:** folders and labels are organization, not knowledge (D4); AI never
  sees contacts (C5).
- **`docs/migration/interface-screens.json`:** the client area screens' states, if any classic
  screen maps to them.
