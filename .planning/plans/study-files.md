---
status: planned
chunks:
  - "[ ] SF1. Folders inside folders, the server: client_knowledge_folders.parent_id (migration), a name unique within its parent instead of within the client, a folder moved into another folder (a cycle refused by name), each folder's path in the folder routes' answers; every folder there today becomes a root folder (W2)"
  - "[ ] SF2. Deleting a folder deletes what is inside it: the subfolders go and every file's knowledge item is retired (Vyřazeno), after a preview that counts the folders and files; audited, one transaction; the retired state lands here, ahead of client-knowledge-lifecycle#K6 (W2, after SF1)"
  - "[ ] SF3. The folder tree on screen (canvas v6): the library's folders as a tree, a folder dragged into a folder, a file dragged onto a folder and moved at once with Vrátit for 8 s, a 'Přesunout do…' dialog for keyboard users, a new subfolder opening with its name selected, the delete confirmation naming how many files go; renaming waits on the owner's open Q1 (W2, after SF1 and SF2)"
  - "[ ] SF4. A source occurrence names its study: client_source_occurrences.study_id (migration; null for every occurrence before), written by every writer that adds a file from inside a study (W2)"
  - "[ ] SF5. Each study's folders, made by AIA: Studie / <název studie> / Vstupy and Výstupy, made for a new study and, for a study from before, when its first new file arrives; files there today stay where they are (W2, after SF1)"
  - "[ ] SF6. Brief files filed: a file attached on Zadání is kept as one of the client's sources with this study's occurrence and its knowledge item filed in the study's Vstupy (W2, after SF4 and SF5; with artifact-brief#BRF7's class rule)"
  - "[ ] SF7. Chat files filed: a file given to the Lead (lead-orchestration#LO18a) is filed in the study's Vstupy (W2, after LO18a, SF4 and SF5)"
  - "[ ] SF8. A file a person moved stays moved: AIA writes a file's placement only when it first files it, never again; one test over every filing path (W2, with SF6)"
  - "[ ] RA1. The AI respondents' answers with their probabilities: check whether research_fieldwork_dataset stores each answer's probabilities, and store them if it does not (W2)"
  - "[ ] RA2. The answers as two files: an XLSX with the sheets Odpovědi, Kódovník and O datech (run, date, model, cost, n, and on every copy that the answers are modelled or fictional) and the JSON original with its SHA-256 (W2, after RA1)"
  - "[ ] RA3. Filed when the run finishes: both answer files in the study's Výstupy as client sources, once per SHA-256 (W2, after RA2, SF4 and SF5)"
  - "[ ] RA4. Every download filed: a file a person downloads from a study (a report's DOCX or PDF, any version, the answer files) is filed in the study's Výstupy as a client source, once per SHA-256; an approval files nothing (W2, after SF4 and SF5)"
  - "[ ] SF9. Výstupy on screen: the answers' downloads (XLSX, JSON) on Výsledky, and every study download saying where it was filed (W2, after RA3 and RA4)"
  - "[ ] SF10. Data folded into Znalosti: the Data tab gone, a dataset a kind of knowledge item shown by the library's kind filter, the old Data address opening that view, one folder tree (W2)"
  - "[ ] SF11. The 'Sdílená data AIA' note moves from Data to Společenská inteligence (W2, with SF10)"
  - "[ ] SF12. Journey: a study's folders made, a brief file and a chat file filed in Vstupy, a file moved and left moved, a run's answers and a download filed in Výstupy, a folder with a subfolder deleted with its count; zero paid jobs (W2)"
---
# Study files: per-study folders, nested folders and filing

Written 2026-10-27 on `chore/plan-unplanned-gaps` from `origin/develop @ dbaa7720`. Every anchor below is
`@ dbaa7720` unless it names another ref.

## Context

The client pages prototype (canvas <https://claude.ai/artifact/4dP7Y43dtHcJFkJLD31hFo>, v5 to v7, board "5 ·
Znalosti jako Disk (Data sloučena)", 34 function rows at v7; v6 draws Znalosti as a Google Drive, v7 gives every
client board four tabs, Přehled / Výzkumy / Znalosti / Profil, and the Studie / <studie> / Vstupy, Výstupy tree) and the research stages build spec (<https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy>,
`lead.md` §3.4, spec v6) draw a client library where every study has its own folder holding Vstupy (what people
give the study) and Výstupy (what the study hands out). No plan held it. Today:

- Folders are flat: one level, unique by name across the client
  (`packages/aia_core/src/aia_core/infrastructure/tables.py:1336-1355`, `uq_client_knowledge_folders_name` at
  `:1354`; `packages/aia_core/src/aia_core/domain/knowledge.py:479`).
- Deleting a folder leaves its items in no folder
  (`apps/api/src/aia_api/routers/workspace.py:1749-1752`).
- A source occurrence says who added the file, when and how, but not from which study
  (`packages/aia_core/src/aia_core/domain/client_sources.py:314-324`).
- A brief's files are artifacts of the study's working project, not client sources
  (`apps/api/src/aia_api/routers/workspace.py:2323`).
- A Lead message carries no file (`apps/api/src/aia_api/routers/lead.py:111`, `TurnPost`); `lead-orchestration#LO18a`
  plans it.
- A download stores nothing (`apps/api/src/aia_api/routers/report_editor.py:662-692`,
  `apps/api/src/aia_api/routers/research.py:2907-3658` for the report downloads).
- The AI respondents' answers are stored only as the run's `research_fieldwork_dataset` artifact
  (`apps/executors/src/aia_executors/research.py:113`); whether each answer's probabilities are in it is not
  checked (a **hypothesis** either way; RA1 checks it).

## The owner's decisions (Nigel, 27 Oct 2026, ~01:10-01:40 UTC, in the PM coordinator's chat)

- **Real nesting.** Folders get a parent (a migration), there is a tree in the browser, and folders move into
  folders. Each study gets "Studie / <name> / Vstupy, Výstupy" created automatically. "all current files can stay
  where they are, this will count for new files after the build".
- **Deleting a folder** with subfolders and files deletes everything inside. Its files are retired (their
  knowledge items set to Vyřazeno). A confirmation names how many files go.
- **Downloads.** Every file downloaded from a study is filed in its Výstupy as one of the client's sources, once per
  SHA-256. Approval files nothing (Nigel, earlier: "not approved, downloaded").
- **Chat files.** A file given to the Lead is kept as a client source in the study's Vstupy. A person may move it,
  and AIA never moves it back.
- **Brief files** are filed into the study's Vstupy as client sources.
- **AI respondents' answers.** Two files per run, filed in Výstupy when the run finishes: an XLSX with the sheets
  Odpovědi, Kódovník and O datech (run, date, model, cost, n, and that the answers are modelled or fictional on
  every copy), and the JSON original with its SHA-256. First check whether each answer's probabilities are stored
  with `research_fieldwork_dataset`; store them if not. RA-1 is the check and store, RA-2 the XLSX, RA-3 filing on
  finish, RA-4 downloads filed in Výstupy (here `RA1` to `RA4`: a chunk id carries no hyphen).
- **Data is folded into Znalosti.** A dataset is a kind of knowledge item, so Data becomes a filter or view, and
  the "Sdílená data AIA" note moves to Společenská inteligence.

## Prerequisites

- **Migrations:** SF1 (`parent_id`, the unique constraint replaced) and SF4 (`study_id` on an occurrence), each its
  own Alembic revision, one migration head at a time (the serial migration lane, ARCHITECTURE.md §8).
- **Retirement:** SF2 retires knowledge items, and no retired state exists yet (`domain/knowledge.py` has none).
  `client-knowledge-lifecycle#K6` (retirement, correction, conflicts) is W3, after SF2's W2, so SF2 lands the
  retired state itself: an item set Vyřazeno by a new revision with provenance, read as retired, never offered to a
  study's context. K6 keeps correction, conflicts and dependent-study visibility, and a single item's Vyřadit. Both
  are S3's (proposed here, planning, 2026-10-27; K6's owner confirms).
- **The file in a Lead turn:** SF7 after `lead-orchestration#LO18a`.
- **The brief file's class:** SF6 with `artifact-brief#BRF7` (a brief's files Class A by rule, "Veřejné" by a
  person), so a brief file kept as a client source keeps the class BRF7 gives it.
- **The library's screen:** SF3 and SF10 are drawn inside the Drive-style browser of
  `client-pages-redesign#CPR17`; whichever lands first leaves the other a slot.

## Chunks

**SF1. Folders inside folders, the server** (W2). `parent_id` (nullable, a root folder when null) on
`client_knowledge_folders`; the name unique within its parent (`(client_id, parent_id, name_key)`, a root's parent
read as one value so two roots cannot share a name); `PUT …/knowledge/folders/{id}` takes a new parent, a move
into the folder itself or one of its descendants refused by name (`folder_cycle`); every folder answer carries its
path (root to the folder, names and ids). Every folder there today is a root folder, nothing renamed. Test: a
folder moved under another answers its path; a cycle is refused; two folders of one name under different parents
are allowed, under one parent refused.

**SF2. A folder deleted with what is inside it** (W2). `GET …/knowledge/folders/{id}/deletion` counts the
subfolders and files that go; `DELETE` removes the subtree and retires every file's knowledge item (Vyřazeno, a
new revision with provenance; the source's bytes kept), one transaction, audited with the counts.
Replaces today's rule (items stay, in no folder, `workspace.py:1749-1752`). Test: deleting a folder with one
subfolder and three files retires three items, and the preview said three.

**SF3. The folder tree on screen** (W2; canvas v6, "Znalosti drawn as a Google Drive"). The library's folder pane
as a tree; drag a folder onto a folder and a file onto a folder (the existing `PUT …/knowledge/placement`,
`workspace.py:1853`, for files), the move made at once with Vrátit for 8 s; a "Přesunout do…" dialog for keyboard
users (arrow keys in the tree, `lib/roving.ts`); a new subfolder opens with its name already selected; the delete
confirmation names the count SF2's preview gives ("Smazat složku a 3 soubory"), with the files' retirement in words.
The breadcrumb drop targets, the row and tile view and the details panel are `client-pages-redesign#CPR17`'s.
**Open (the owner's Q1):** does renaming a file create a new knowledge revision? Folder renames exist today; a file
rename is not built until it is answered. Test: a component test for the tree's keyboard, the dialog, Vrátit after
a move and the confirmation's count.

**SF4. An occurrence names its study** (W2). `client_source_occurrences.study_id`, null for every occurrence
before (never guessed). Written by the study-side writers this plan adds (SF6, SF7, RA3, RA4) and by any existing
one that adds a file from inside a study. Test: a file added from a study names it; one added from the client
workspace names none.

**SF5. Each study's folders** (W2). AIA makes "Studie" (once per client), "<název studie>" under it and "Vstupy"
and "Výstupy" under that, and remembers their ids on the study, so a rename of either folder by a person keeps
filing there. For a study from before, the folders are made when its first new file arrives. A person may delete
them; the next file makes them again (decided by default, planning, 2026-10-27; Nigel may override). Nothing
already filed moves. Test: a new study has the four folders; a study from before has none until a file comes, then
has them.

**SF6. Brief files filed** (W2). A file attached on Zadání (`POST /studies/{id}/workspace/attachments`,
`workspace.py:2323`) is also kept as one of the client's sources (once per client and SHA-256, the existing
`client_source_repository`), with this study's occurrence, and its knowledge item is filed in the study's Vstupy.
The brief keeps its attachment record. Test: an attached PDF is a client source in Vstupy, with this study named;
attaching the same bytes again files nothing twice.

**SF7. Chat files filed** (W2). A file given to the Lead, kept as a client source by `lead-orchestration#LO18a`, is
filed in the study's Vstupy at that moment. Test: a file sent in a turn is in Vstupy.

**SF8. A moved file stays moved** (W2). AIA writes a file's placement once, when it first files it (SF6, SF7, RA3,
RA4); the same bytes arriving again add an occurrence and never re-file. Test: a file moved out of Vstupy by a
person, then given to the Lead again, stays where the person put it.

**RA1. Probabilities with the answers** (W2). Read what `research_fieldwork_dataset` stores per answer
(`apps/executors/src/aia_executors/research.py:113`; the dataset is drawn by code from the model's
probabilities, `domain/ai_respondent.py`). If the probabilities are there, the chunk ticks with a test naming the
field. If not, the dataset stores them beside the drawn code (a dataset contract bump; older datasets read as
"probabilities not stored", never as zero). Test: a recorded run's dataset carries each answer's probabilities.

**RA2. The answer files** (W2). A pure renderer from the dataset: an XLSX (`openpyxl`, the `documents` extra) with
Odpovědi (one row per respondent, one column per item, the drawn code), Kódovník (each item's wording and each
code's label) and O datech (the run, its date, the model, the cost, n, and the origin in words: "modelováno: AI
respondenti z populace" or "fiktivní respondenti"), and the JSON original as stored, with its SHA-256. The origin
sentence is on every sheet. Test: the XLSX's three sheets, the origin line on each, and the JSON's SHA-256 equal to
the stored dataset's.

**RA3. Filed on finish** (W2). When a run's fieldwork has finished and its dataset is stored, both files are kept as
client sources in the study's Výstupy, once per SHA-256 (a retry that reuses the dataset files nothing new). Paid
work is never repeated for it: the files are made from the stored dataset. Test: a finished recorded run has both
files in Výstupy; a reused dataset adds none.

**RA4. Every download filed** (W2). Each study download route (the report downloads `research.py:2907-3658`, the
editor version download `report_editor.py:662`, the answer files) keeps the bytes it hands over as a client source
with this study's occurrence, in Výstupy, once per SHA-256. An approval files nothing. A download that fails to
file still downloads and says so (decided by default, planning; the download is the person's act, the filing a
record of it). Test: downloading the internal DOCX twice files one source; approving it files nothing.

**SF9. Výstupy on screen** (W2). "Stáhnout odpovědi (XLSX)" and "(JSON)" on Výsledky, beside the data's origin;
every study download's toast says "Uloženo do Výstupů" with a link to the folder. Test: a component test for both.

**SF10. Data folded into Znalosti** (W2). The client's Data tab goes (`apps/web/src/app/app/clients/[clientId]/data`, `components/aia/clients/DataArea.tsx`);
its datasets are the library's DATASET kind, shown by the kind segment; the old address opens the library on that
kind. Test: the client's tabs hold no Data; the old address lands on the datasets view.

**SF11. Sdílená data AIA on Společenská inteligence** (W2). The note that AIA's shared population data is not the
client's moves to the intelligence page. Test: the note renders there and not in the library.

**SF12. Journey** (W2). `tools/ui_workbench/client_journey.mjs` extended, at 1440 px (the narrower layouts kept as
they are): the study's folders, a brief file and a chat file in Vstupy, a file moved and left moved, a fictional
run's answers and a download in Výstupy, a folder with a subfolder deleted with its count; zero paid jobs.

## Open questions

The owner's, from the client canvas, recorded and not decided: **Q1** (does renaming a file create a new knowledge
revision?) on SF3; **Q3** (is a knowledge item retired or deleted?) for a single item, on
`client-knowledge-lifecycle#K6`. A deleted folder's files are retired by the owner's own decision of 27 Oct (SF2).

Decided by default (planning, 2026-10-27, open to Nigel's override): a person may delete a
study's folders and AIA makes them again for the next file (SF5); a download that cannot be filed still downloads
(RA4).

## Doc follow-up

- `CLAUDE.md` § 2, when SF1 lands: `client_knowledge_repository.py`'s folders are nested (a parent, a path, a
  subtree delete that retires its files); when SF4 lands: an occurrence names its study.
- `CLAUDE.md` § 2, when RA2 lands: the answer files' renderer and where it lives.
- `CLAUDE.md` § 2, when SF10 lands: the client workspace is Přehled, Výzkumy, Znalosti, Profil (Simulace hidden for the MVP; Data
  folded into Znalosti).
