---
status: in-progress
chunks:
  - "[x] 0. Design on the canvas (Klient row of the research studio) and this plan"
  - "[x] C1. Client shell: Profil tab, counts on tabs, status in the bar, Přidat znalost beside Nový výzkum"
  - "[x] C2. Výzkumy as a table: status filters, where each study is, what it brought into knowledge; one search with project memory"
  - "[ ] C3. Folders and labels: per-client folders, labels, an item in one folder with any labels (migration, repository, routes)"
  - "[ ] C4. Knowledge library: views, folder tree, label and kind filters, the open item beside the list, revision history, bulk move and label"
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

### C3. Folders and labels
- **Domain:** `domain/knowledge.py` gains `KnowledgeFolder` and `KnowledgeLabel`, with:
  - names unique per client, case-folded;
  - a closed `LabelColour` set mapped to existing tokens;
  - a depth limit of one: no nested folders until a client needs them.
- **Migration:**
  - `client_knowledge_folders` and `client_knowledge_labels`, both per client;
  - `client_knowledge_items.folder_id`, nullable, set to null when its folder is deleted;
  - `client_knowledge_item_labels`.
- **Repository:** `ClientKnowledgeRepository` stays the only reader and writer, so `make
  layer_check` keeps the rows inside it, and every change is audited.
- **Routes**, under `/clients/{id}/knowledge/`:
  - `folders` and `labels`: list, create, rename, delete;
  - `items/{id}/placement`: set an item's folder and labels;
  - `placement`: the bulk form, taking explicit item ids;
  - `GET …/knowledge` filters by `folder` (or `unfiled`) and `label`.
- **Permissions:** whoever may propose knowledge may organize it.
- **Tests:**
  - per-client uniqueness;
  - a folder from another client is refused (404, not 403);
  - deleting a folder leaves its items as *Bez složky*;
  - moving writes no revision and leaves `context_revision` unchanged (D4);
  - the bulk route is all-or-nothing.

### C4. Knowledge library
- **What it does** (`KnowledgeArea.tsx` rebuilt to the design):
  - views: Vše, Ke schválení, Bez složky, Starší než rok;
  - folder tree, label chips and kind chips;
  - the list as a table;
  - the open item beside the list;
  - bulk move and label.
- **Edits:** an edit goes through the existing proposal route with `item_id` (`workspace.py:885`),
  so a person's edit is a new revision under ADR 0019. History reads `workspace.revisions`.
- **Starší než rok:** compares `modified_at` with today, and is labelled exactly so.
- **Tests:** the filters as pure functions; the open item's revision list; keyboard order;
  every control labelled.

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
