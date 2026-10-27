# AIA Klienti – prototyp (client pages), 27 Oct 2026

A snapshot of the client-pages Design canvas: the current develop screens, an anchored analysis of
each, and a redesign in the AIA design system. Design reference only: nothing here is imported by
`apps/web`, calls an AIA endpoint, a model or a paid service, and every client, study, person and
number in it is fictional.

| | |
|---|---|
| Live canvas (private to the owner's account) | <https://claude.ai/artifact/4dP7Y43dtHcJFkJLD31hFo> |
| Exported version | v20, artifact version `1793100519-580b`, 27 Oct 2026 |
| Code the analysis is anchored to | `develop` @ `a1a9a45c` (anchors re-checked @ `dbaa7720`) |
| Core stylesheet | `assets/aia-core-v4.3.css`: core v4.3 (Petrol), owned by the design-system session; SHA-256 `bd0c156ee4ef23d2dcaef0f7f10fc1a82e675a9eb3e1c9d45a3ed198d54a2b0e`. It is not `../shared/aia-core.css` (core v3) |
| Client stylesheet | `assets/aia-client.css`: scoped under `.cl`, built only on core variables, redefines no core class |

Read the `.dc.html` files as source, as `../README.md` § "How to read a `.dc.html` file" describes:
they need the canvas runtime (`./support.js`), which is not exported. In the exported files the
canvas's asset URLs (`/_blob/<id>`) are rewritten to `assets/`; the screenshots of today's
develop screens are `assets/<id>.jpg`. `canvas.json` lists the boards, titles, sizes and order.

## Boards

| # | File | What |
|---|---|---|
| 0 | `Main.dc.html` | Overview: the map of client pages, the principles, Nigel's decisions, the NO BACKEND table (11 rows) |
| 1 | `Clients.dc.html` | Klienti: the directory as a table, search, sort, Nový klient |
| 2 | `Overview.dc.html` | Přehled klienta: Čeká na vás, what AIA knows, outputs in words |
| 3 | `Studies.dc.html` | Výzkumy, with Projektová paměť merged in: one search over names and design text, "Použít jako základ nového výzkumu…" on every study |
| 4 | `Knowledge.dc.html` | Znalosti as a Drive, with Data merged in: nested folders, drag and drop with Vrátit, path, list/grid, Studie / <studie> / Vstupy and Výstupy |
| 5 | `KnowledgeItem.dc.html` | Znalosti: the review queue (Čeká na vás / Rozhodnuté) and an item with its history and diff |
| 6 | `Intake.dc.html` | Přidat podklady: the intake sheet with the destination folder chosen first |
| 7 | `Profile.dc.html` | Profil: in-place fields, contacts with Vrátit, budget without a false zero, rules |

Each board ends with its critique (a–e) and a function list (f): every function of today's page,
with `file:line`, mapped to where it is in the prototype.

## Decided (all by Nigel, 27 Oct 2026)

- **Data folded into Znalosti.** A dataset is a kind of knowledge; one folder tree; the Data tab is gone; "Sdílená data AIA" belongs to Společenská inteligence.
- **A study's folder: Vstupy and Výstupy.** A file given to the Lead is a client source in Studie / <studie> / Vstupy; every downloaded study file and the AI respondents' answers (XLSX, JSON) go to Výstupy.
- **Knowledge organised like Google Drive,** keeping the folder and label logic, with folders inside folders.
- **Compact page headers.** The hero took too much room and had no hierarchy: one line carries who, what waits on you and the actions; the figures sit on the tab row.
- **Renaming a file changes only its name:** no new knowledge revision, no approval; recorded in the audit.
- **Green leaves the label palette;** existing green labels become teal. Green stays reserved for the version in force.
- **A knowledge item is deleted** (also a brand or a competitor), permanently, after a confirmation, no undo; studies that used it keep their frozen copy; recorded in the audit.
- **Projektová paměť is removed** (plan `client-pages-redesign` CPR9, CPR14): the global navigation keeps Klienti, Společenská inteligence, Nastavení; Výzkumy's search matches the designs' text; "Použít jako základ nového výzkumu" sits on every study with the citation kept; old memory URLs redirect.

## Still open

- **NO BACKEND (11 items),** listed on board 0 with anchors. Among them: nested folders, deleting a knowledge item, dropping GREEN from the label enum with a migration, people's names instead of ids, a link as a client source, the study folders filled on their own, and the "nejvýše" price of AI proposals from a document.
- **"Použít jako základ nového výzkumu" in the study header** belongs to the research-stages canvas and is not drawn here.
- **Drag-and-drop filing and keeping Výzkumy's filter and order in the URL** are drawn here and not yet built in the product.
