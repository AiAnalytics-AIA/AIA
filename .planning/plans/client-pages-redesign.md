---
status: planned
chunks:
  - "[ ] CPR1. The client's file count, the server: GET /clients/{id} answers the number of the client's sources beside counts.datasets, null for a caller who may not read them (W1)"
  - "[ ] CPR2. A client's status on the list, the server: ClientCard carries the client's status (active, archived), so the directory can say it (W1)"
  - "[ ] CPR3. Budget and rule changes in the profile history, the server: the profile's history reads the client budget, wallet ceiling, data posture and self-approval changes from the audit, each with who and when (W1)"
  - "[ ] CPR4. The client hero on every client tab: eyebrow, the client's name, one line, and five figures from GET /clients/{id} (the file count from CPR1); a figure the API does not give reads unknown, never 0 (W1, on prototype-build#PBA4's hero, after CPR1)"
  - "[ ] CPR5. Underline tabs, and Přidat podklady and Nový výzkum on every client tab, the same place each time (W1)"
  - "[ ] CPR6. Přehled as the canvas draws it: Čeká na vás first, no coloured tiles, the study's outputs in words (W1)"
  - "[ ] CPR7. Klienti as a table: a sort segment, honest search, the client's status (CPR2), and a similar-name warning before Nový klient makes a second one (W1, after CPR2; with input-interactions#7's inline row)"
  - "[ ] CPR8. Klienti's 'Čeká na vás dnes': the cross-client portfolio of client-knowledge-lifecycle#K9 at the top of the directory (W3, with K9)"
  - "[ ] CPR9. Výzkumy: a status segment, the Krok column in the eleven stages' words, the rejected-knowledge count per study, the table's one search matching the designs' text as project memory does, and Použít jako základ on every study (W1, after CPR10)"
  - "[ ] CPR10. One stage vocabulary: the client pages' stage names (apps/web/src/i18n/cs.ts:251-262) replaced by the eleven stages of lib/workbench-stages.ts (W1)"
  - "[ ] CPR11. Profil: fields edited in place, the data posture in words (Nesmí / Smí), the budget without a false zero, and the history with budget and rule changes (W1, after CPR3; with input-interactions#8)"
  - "[ ] CPR12. Přidat podklady: the destination folder as a tree and AI extraction as a switch showing its ceiling, 'Cena nejvýše' (W2, after study-files#SF3 and client-knowledge-lifecycle#K16)"
  - "[ ] CPR13. Přidat podklady: Vložit odkaz, one public URL kept as the client's source (W2, after client-knowledge-lifecycle#K2e)"
  - "[ ] CPR14. Remove Projektová paměť: off the global navigation (three items left), its pages redirected, its search folded into Výzkumy (CPR9); the memory search and reuse routes stay (Nigel, 27 Oct; W1)"
  - "[ ] CPR15. The library's layout: kinds as a segment, the open item in a 380 px drawer (W1)"
  - "[ ] CPR16. Label colours without green: the swatch picker offers no green, which belongs to the version in force alone; what happens to existing green labels is the owner's open Q2 (W1)"
  - "[ ] CPR17. Znalosti as a Drive (canvas v6): the folder tree on the left, a breadcrumb whose every part is a drop target, a row or tile view, every client file in one list (GET /clients/{id}/sources), a row dragged onto a folder moved at once with Vrátit for 8 s, the same actions in the ⋯ menu and on right-click, a details panel, the Interní switch on a file, Přečíst znovu; renaming a file waits on the owner's open Q1 (W2, with study-files#SF3)"
  - "[ ] CPR18. Aktivita: the client's source occurrences as a timeline (who added what, when, from where) (W2, after study-files#SF4)"
  - "[ ] CPR19. Journey: the four client tabs at 1440 px with the narrower layouts kept, the hero's figures, a client sorted and searched, a profile field edited in place and read back, a file added to a chosen folder; zero paid jobs (W2)"
  - "[ ] CPR20. Removing a contact on Profil with Vrátit: today it is removed at once, with no undo and no confirmation (ProfileArea.tsx:261-262); the removal held for Vrátit as the design draws it (a defect; W1)"
  - "[ ] CPR21. The Petrol core v4 visual base brought into apps/web/src/design/tokens.json (then npm run tokens and make web_design), a separate chunk after the redesign's screens (the design-system session's canvas v10; W3)"
---
# Client pages redesign: Klienti, the client's tabs and Přidat podklady

Written 2026-10-27 on `chore/plan-unplanned-gaps` from `origin/develop @ dbaa7720`. Anchors are `@ dbaa7720`
unless they name another ref; the canvas's own anchors are `@ a1a9a45c` (an ancestor of `dbaa7720`).

## Context

The client pages prototype, canvas <https://claude.ai/artifact/4dP7Y43dtHcJFkJLD31hFo> ("AIA Klienti – prototyp",
nine boards: 0 Přehled prototypu, 1 Klienti, 2 Přehled klienta, 3 Výzkumy, 4 Projektová paměť (removed by CPR14), 5 Znalosti jako Disk
(Data sloučena), 6 Znalosti: schvalování a položka, 7 Přidat podklady, 8 Profil), redraws every client page. At v5 it
listed 184 functions kept and 11 things the API does not do. The client inventory of 27 Oct 2026 (35 items, about
24 in no plan) found no plan for most of it. The canvas has since moved to **v7** (Nigel's chat, relayed by the PM
coordinator):

- **v6: Znalosti drawn as a Google Drive.** A nested folder tree on the left; a breadcrumb path where each part is a
  drop target; a row or tile view. A row dragged onto a folder moves at once, with Vrátit for 8 s; the ⋯ menu and
  right-click offer the same actions. A "Přesunout do…" dialog for keyboard users, and a details panel. A new
  subfolder opens with its name already selected. Backend: nested folders (flat today,
  `packages/aia_core/src/aia_core/infrastructure/tables.py:1336-1355`, `domain/knowledge.py:479-488`;
  `study-files#SF1`); a file dragged onto a folder uses the existing `PUT …/knowledge/placement`
  (`apps/api/src/aia_api/routers/workspace.py:1853`). CPR17 and `study-files#SF3`.
- **v7: four tabs on every client board**, Přehled / Výzkumy / Znalosti / Profil. The Data tab is removed (folded
  into Znalosti) and "Sdílená data AIA" moves to Společenská inteligence (`study-files#SF10`, `#SF11`). Znalosti
  gains a Studie / <studie> / Vstupy, Výstupy tree: respondents' answers (XLSX and JSON) and every download go in
  Výstupy, a Lead-produced file in Vstupy (`study-files#SF5` to `#RA4`). The merged board is "5 · Znalosti jako Disk
  (Data sloučena)", with 34 function rows.
- **A defect the design fixes:** removing a contact on Profil happens at once, with no undo and no confirmation
  (`apps/web/src/components/aia/clients/ProfileArea.tsx:261-262`); the design gives it Vrátit (CPR20).

This plan owns the pages. It does not own:

- the folder model, the study folders and the filing (`study-files`); CPR12 and CPR17 draw on it;
- knowledge review (reject with a reason, Rozhodnuté, people's names) and the ceiling of AI proposals from a
  document (`client-knowledge-lifecycle#K14` to `#K17`);
- the cross-client portfolio's read (`client-knowledge-lifecycle#K9`); CPR8 is its place on Klienti;
- the shared input primitives (`input-interactions`), which these screens use.

**The visual base: Petrol core v4.** Nigel, 27 Oct 2026, first: "build it, the design system upgrade will take place
once that's finished". Later that night he ordered the design-system upgrade, and the design-system session's canvas
v10 makes the visual base "Petrol" core v4. So the redesign builds on that upgrade's look, and bringing the system
into `apps/web/src/design/tokens.json` is a separate later chunk (CPR21): no screen chunk here waits on the token
change, and no token change rides inside a screen PR.

## The owner's decisions (Nigel, 27 Oct 2026, ~01:10-01:40 UTC, in the PM coordinator's chat)

- The client pages redesign is in the MVP, from canvas v5 plus that night's decisions (since redrawn to v7): "build
  it, the design system upgrade will take place once that's finished"; the visual base is Petrol core v4 (above).
- Data is folded into Znalosti (a dataset a kind of knowledge item; `study-files#SF10`), so the client has four tabs:
  Přehled, Výzkumy, Znalosti, Profil (canvas v7; Simulace stays hidden for the MVP, `client-knowledge-lifecycle#K12`).
- Cross-client "needs me today" on Klienti is in the MVP (CPR8, over `client-knowledge-lifecycle#K9`).
- A price before approval on every paid card, the ceiling "horní mez, ne odhad", per the D-01 money words (CPR12's
  AI switch).

## Prerequisites

- `prototype-build#PBA4`'s hero component (built) for CPR4; `input-interactions#7` and `#8` for CPR7 and CPR11.
- CPR1, CPR2 and CPR3 (the server) before the screens that read them.
- `study-files#SF1` to `#SF4` before CPR12, CPR17 and CPR18; `client-knowledge-lifecycle#K16` before CPR12's
  ceiling, `#K2e` before CPR13, `#K9` before CPR8.

## Chunks

**CPR1. The file count** (W1, server). `ClientCounts` (`apps/api/src/aia_api/routers/workspace.py:204-216`) has
`datasets` but no file count; the sources route exists (`apps/api/src/aia_api/routers/client_sources.py:295`). Add
`sources: int | None`, null without `VIEW_CLIENT_KNOWLEDGE` as the knowledge counts are. Test: a client with three
sources answers 3; a caller without the permission reads null.

**CPR2. Status on the list** (W1, server). `ClientCard` (`workspace.py:189-201`) carries no status. Add it. Test:
an archived client's card says so.

**CPR3. Budget and rule changes in the history** (W1, server). The profile history returns profile and contact
actions only (`apps/web/src/components/aia/clients/ProfileArea.tsx:324-346`). Read the client budget, wallet
ceiling, data posture and self-approval changes from the audit too, each with the person's name
(`client-knowledge-lifecycle#K15`) and never an e-mail. Test: a budget change reads in the history with who and
when.

**CPR4. The client hero** (W1). Five figures (the canvas: studies, knowledge, waiting, files, budget), each from the
API, unknown in words. Test: a figure the API leaves null reads "neznámé".

**CPR5. Tabs and actions** (W1). Underline tabs; Přidat podklady (secondary) and Nový výzkum (primary) in the hero
on every tab. Test: every tab shows both, in the same place.

**CPR6. Přehled** (W1). Čeká na vás first; no coloured tiles; outputs in words. Test: `ClientOverview` renders no
tile and lists what waits first.

**CPR7. Klienti as a table** (W1). A table, not cards; a sort segment; search that says what it matched; the
client's status; a similar-name warning ("Klient s podobným názvem už existuje") before a second client of nearly
the same name is made (accent-folded, the rule `domain/project_memory.py` uses). Test: "Pivovar Lázně" warns
beside "Pivovar Lazne".

**CPR8. Čeká na vás dnes** (W3, with `client-knowledge-lifecycle#K9`). Every study waiting for the signed-in
researcher, across clients, at the top of Klienti. Test: two clients' waiting studies listed, each opening its
stage.

**CPR9. Výzkumy** (W1). The status segment; Krok in the eleven stages' words (CPR10); the rejected-knowledge count
per study. **One search** over the table that matches the designs' text the way project memory does today (every
word, accent-folded, a four-letter stem: `domain/project_memory.py`, served by `GET /clients/{id}/memory/search`),
not only the studies' names, so "find the study where we asked about X" still works; the matched words are said
beside each row. **Použít jako základ nového výzkumu** on every study, in the row's ⋯ menu and in the study header,
calling the existing `POST /clients/{id}/memory/reuse` (`application/design_reuse.py`), its citation kept
(`DesignSourceNote` on every stage of the new study). No separate memory section (Nigel, 27 Oct: CPR14). Simulace stays hidden as
`client-knowledge-lifecycle#K12` left it. Test: `StudyList` shows the stage word, never a stage code.

**CPR10. One stage vocabulary** (W1). `cs.ts:251-262` names ten stages of the classic flow (Audience, Kontrola a
spuštění, Ověření, Další krok). The client pages read the eleven stages of `lib/workbench-stages.ts` instead. Test:
a guard test that the client pages import no stage word but the workbench's.

**CPR11. Profil** (W1). Fields edited in place (`input-interactions#8`); the data posture in words: "Nesmí" /
"Smí" for what Deep Research may send (`clients.data_posture`, `deep-research-web-search#53`); the budget unset
said in words, never 0; the history with CPR3's rows. Test: a field saved in place reads back after a reload.

**CPR12. Přidat podklady: the folder tree and the AI switch** (W2). The destination folder chosen from SF3's tree;
"Navrhnout znalosti" as a switch that shows its ceiling ("Cena nejvýše … · horní mez, ne odhad") before it is
turned on, asked again if the ceiling grows (`client-knowledge-lifecycle#K16`); neutral file-type icons; one
close. Test: the switch shows the ceiling the API quotes; an unknown ceiling turns nothing on.

**CPR13. Vložit odkaz** (W2). The intake's link field becomes live (`IntakeSheet.tsx:307-308`, today "V AIA zatím
není") over `client-knowledge-lifecycle#K2e`'s capture. Test: a public URL is kept as the client's source.

**CPR14. Remove Projektová paměť** (W1). Nigel, 27 Oct 2026, in the PM coordinator's chat: "yes lets remove
projektova pamet", after agreeing that even a memory section inside Výzkumy is redundant. Each of its jobs now
lives where the study already is:

- searching past studies: the Výzkumy table's one search over the designs' text (CPR9);
- reading a past study: opening the study itself, read-only where it can no longer change;
- Použít tento design: Použít jako základ nového výzkumu on every study (CPR9).

The work:

- the global navigation loses Projektová paměť and keeps three items: Klienti, Společenská inteligence,
  Nastavení (`components/aia/AppShell`, `lib/app-routes.ts`);
- `/app/memory` redirects to `/app/clients`, and `/app/clients/<client>/memory/<study>` to the study itself;
- `MemorySearch.tsx`'s own section and `MemoryStudy.tsx` go once nothing renders them, with their tests;
- the routes stay: `GET /clients/{id}/memory/search` serves the Výzkumy search and can serve the Lead's "najdi
  podobný výzkum" later, and `POST /clients/{id}/memory/reuse` serves Použít jako základ.

Tests:
- the navigation renders three items;
- both old URLs redirect;
- Výzkumy finds a study by a word that appears only in its design;
- Použít jako základ creates a study whose stages show the citation.

Doc follow-up: CLAUDE.md's map (the four global items; `MemorySearch`, `MemoryStudy`, `clients/<client>/memory/<study>`) and
ADR 0015's navigation.

**CPR15. The library's layout** (W1). Kinds as a segment (not pills); the open item in a 380 px drawer; the review
views as `client-knowledge-lifecycle#K14` names them. Test: the drawer opens on `?item=` at 380 px.

**CPR16. Labels without green** (W1). `LabelColour.GREEN` stays in the API
(`packages/aia_core/src/aia_core/domain/knowledge.py:353`); the picker stops offering it. **Open (the owner's Q2):**
what happens to the existing green labels; not decided here, and until it is they render as stored. Test: the picker
has no green.

**CPR17. Znalosti as a Drive** (W2; canvas v6, with `study-files#SF3`'s tree and moves). The folder tree on the left;
a breadcrumb whose every part is a drop target; a row or tile view; every client file in one list from the sources
route the web does not read yet (`client_sources.py:295`); a row dragged onto a folder moves at once with Vrátit for
8 s (`components/ui` UndoToast), the same actions in the ⋯ menu and on right-click; a details panel; the "Interní
dokument" switch on a file (`PUT …/sources/{id}/internal`); Přečíst znovu (`POST …/sources/{id}/reading`). SF3 owns
the tree, the "Přesunout do…" dialog and a new subfolder opening with its name selected. **Open (the owner's Q1):**
does renaming a file create a new knowledge revision? No file rename is built here until it is answered. Test: the
file list matches the sources route; a drag onto a breadcrumb part moves the file and Vrátit puts it back; Přečíst
znovu shows the new reading.

**CPR18. Aktivita** (W2). Each source occurrence (`domain/client_sources.py:314-324`; with SF4, its study) as a
row: who, when, the file, from where. Test: an occurrence added from a study names it.

**CPR19. Journey** (W2). `tools/ui_workbench/client_journey.mjs` rewritten for the four tabs at 1440 px, the
narrower layouts kept as they are (Nigel, 26 Oct 2026: "no narrower screens right now").

**CPR20. A contact removed with Vrátit** (W1; a defect). `ProfileArea.tsx:261-262` calls `workspace.removeContact` on
the click: no undo, no confirmation. The design gives it Vrátit: the row leaves at once and the removal is sent when
the Vrátit window closes, or, if the server removes at once, Vrátit re-creates the contact with its fields (the PR
says which and why). Test: remove, Vrátit, the contact is back after a reload; remove and wait, it is gone.

**CPR21. Petrol core v4 into tokens.json** (W3; a separate chunk after the screens). The design-system session's
canvas v10 is the source; `apps/web/src/design/tokens.json` is the design system's one source (CLAUDE.md § 2), so the
change is made there, then `npm run tokens`, and `make web_design` holds (contrast, palette and accent evidence).
Test: `make web_design`; the client journey (CPR19) passes on the new tokens.

## Open questions for the owner (from the canvas, board 0, §03; recorded, not decided)

- **Q1. Does renaming a file create a new knowledge revision?** The file's name is the knowledge item's name; a file
  browser renames without one. Open, on CPR17 and `study-files#SF3`.
- **Q2. What happens to the existing green labels?** The picker loses green (the owner's "label colours without
  green"); the stored green labels are open, on CPR16.
- **Q3. Is a knowledge item retired or deleted?** Open for a single item, on `client-knowledge-lifecycle#K6` and
  CPR17's details panel. A deleted folder's files are retired by the owner's own decision of 27 Oct
  (`study-files#SF2`), which this question does not reopen.

## Doc follow-up

- `CLAUDE.md` § 2, when CPR4 lands: the client workspace's hero and its five figures; when CPR10 lands: the client
  pages read the eleven stages of `lib/workbench-stages.ts`.
