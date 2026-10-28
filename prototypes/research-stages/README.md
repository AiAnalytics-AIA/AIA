# AIA Výzkumné kroky – prototyp, 28 Oct 2026

A snapshot of the research-stages Design canvas, for use from another account. It is design reference,
not product code: nothing here is imported by `apps/web`, and every client, study, person and number is
fictional. How to read a `.dc.html` file is in [`../README.md`](../README.md) § How to read a `.dc.html`
file: the files are canvas artboards, and they do not render as designed in a plain browser.

| | |
|---|---|
| Live canvas | <https://claude.ai/artifact/U4b83GH2X5coxx51ATL1T5>, in the product owner's second account, which owns the research pages prototype since 28 Oct 2026 (private to that account) |
| Version | version 6, artifact version `1793147720-69aa` |
| Exported | 28 Oct 2026 |
| Earlier canvas | <https://claude.ai/artifact/3dkKPTDoa1yvK4GCV7PLtJ> in the first account, last exported at v95 (`1793099019-3a7d`, 27 Oct). It is no longer the source: change the second account's canvas, not this one |
| Previous versions | in git history: v95 (27 Oct) is this folder's previous export; v73 (26 Oct) was `prototypes/research-stages-v73/` |
| Build spec | <https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy>, v6. It still describes the prototype at v78 (see Open) |

## What changed since v95

The second account's canvas was rebuilt from the v95 export on 27 Oct, board for board (each render matched
`reference/` within animation). Then, on 28 Oct, the product owner made **Chat F canonical**: "we leave chat f,
the rest we dont need". Chat A–E are gone, and `ChatF.dc.html` keeps its file name under the new title "Chat
Vedoucího · bubliny na časové ose", alone in the chat row with no row title. Nothing else changed: every other
board, stylesheet and asset is byte-identical to v95. Nothing is known to be wrong in it.

## What is in this folder

- **19 boards**, listed in `canvas.json` order with their titles in the table below. `canvas.json` also
  holds each board's size and position on the canvas.
- **`assets/aia-core.css`**: core v4.3, the "Petrol" shared stylesheet (SHA-256 `bd0c156e…4a2b0e`). It is
  owned by the design-system session and is newer than `../shared/aia-core.css` (core v3), which this
  export does not touch.
- **`assets/aia-study.css`**: the research stages' own stylesheet (SHA-256 `d1a2d23b…00f689`).
- **`assets/thinking-orbs.js`**: the Lead's orb (thinking-orbs 0.3.2, MIT, Jakub Antalik).
- **`assets/<id>.png|jpg`**: the screenshots of today's AIA that the boards' "UX kritika" sections show.

The canvas keeps these files as they are here: `canvas.json`, the boards and `assets/` at the same relative
paths, so nothing is rewritten on export or rebuild. Board links (`href="Design.dc.html"`) resolve inside the
folder. `./support.js` is the canvas runtime and is not exported. "Můj Vedoucí" opens the Settings canvas, which
is exported in [`../settings/`](../settings/). (The first account's canvas also held `Hatch.dc.html` and
`LeadSettings.dc.html`, which were not boards and were never exported; the second account's canvas does not have
them.)

| Board | Title |
|---|---|
| `Main.dc.html` | Přehled, kritika a předání |
| `Overview.dc.html` | Přehled studie (nový, UX v4) |
| `Cards.dc.html` | Karty Vedoucího |
| `CardsF.dc.html` | Karty Vedoucího v chatu (nové) |
| `Brief.dc.html` | 1 · Zadání |
| `Design.dc.html` | 2 · Návrh |
| `Questionnaire.dc.html` | 3 · Dotazník |
| `Audience.dc.html` | 4 · Cílová skupina |
| `Dimensions.dc.html` | 5 · Dimenze |
| `Sample.dc.html` | 6 · Vzorek |
| `Fieldwork.dc.html` | 7 · Sběr dat |
| `FieldworkDisc.dc.html` | 7b · Respondenti při sběru dat |
| `Results.dc.html` | 8 · Výsledky |
| `Sociomap.dc.html` | 9 · Sociomapa (schválená dílna) |
| `Analysis.dc.html` | 10 · Analýza |
| `Report.dc.html` | 11 · Zpráva |
| `ReportEditor.dc.html` | 11b · Editor zprávy: vzhled a ověření |
| `ChatF.dc.html` | Chat Vedoucího · bubliny na časové ose (the Lead's chat; canonical since 28 Oct) |
| `Marks.dc.html` | Značka Vedoucího · 5 variant |

## What is decided (the product owner, 26–28 Oct 2026)

- **The Lead's chat is Chat F**, bubbles on a timeline (28 Oct). The other five variants are dropped.
- **Zpráva: the document editor is the page.** The header carries:
  - the state;
  - two chips, "Zjištění 3/4" and "1 ruční úprava", each with its detail in a popover;
  - Interní / Pro klienta;
  - one "Stáhnout" menu (DOCX for editing in Word, PDF for sending);
  - "Schválit".

  "Osnova a zdroje" is an optional side panel, and "Než schválíte" moved into the approval dialog. The
  earlier three sections duplicated each other. Board 11b compares the editor's look with ONLYOFFICE's
  default.
- **A file given to the Lead in chat is kept as one of the client's sources:**
  - Each study gets its own folder among the client's sources, holding a **Vstupy** and a **Výstupy** folder.
  - A person can move a file to another folder.
  - **Výstupy** holds what was downloaded, not what was approved.
- **Data-class gates stay out of the MVP.** No board shows "třída A/B".
- **Sběr dat · Průběh:**
  - The respondent disc (7b) is the page's centre: each dot is one AI respondent, and "Podle věku" splits the disc into the sample's age groups, whose sum is always the answered total.
  - The 16 run steps are gone. The page shows collection only, then three linked rows, "Po sběru dat", one each for Výsledky a Sociomapa, Analýza and Zpráva.
  - Sběr dat and 7b say what happened in plain words, with no model blocks or journal.
  - A budget lift sits where the waiting step is: on Sběr dat during collection, on Analýza during analysis.
- **No stage shows what another stage owns:**

  | What | Shown only on |
  |---|---|
  | Pre-launch checks, "Kdo odpovídá", the population | Sběr dat · Kontrola a spuštění |
  | Research-question coverage | Návrh before the run, Analýza after it |
  | The comparison set | Návrh owns the objects; Dotazník owns the scale and statements |
  | "Použít ve zprávě" | Zpráva |

  The run's ceiling is 14,60 USD at N 400 everywhere. Internal codes, ids, SHA, provider names and
  web-call counts are off the screens. "Not in AIA yet" notes stay where a person meets the gap.
- **Přehled studie stays as it is**, including what it repeats from the stages: an overview is allowed to.
- **Projektová paměť is removed** (#1024, `client-pages-redesign#CPR14`). The left rail and ⌘K have three
  items: Klienti, Společenská inteligence, Nastavení.
- **"Použít jako základ nového výzkumu…"** is in every stage header's ⋯ menu and in ⌘K (`CPR9`). It is the
  same dialog as the Klienti canvas:
  - a revision, with what its design says;
  - a new named study, or the client's empty study;
  - the design only, with no respondent data, results, reports or costs;
  - the citation "Design převzat z …, revize N" on every stage of the new study.
- **The look is core v4.3:** the Petrol palette, AI shown in graphite with a spark edge, the ⌘K palette,
  the activity tray and the study bar. All of it is from the design-system session.

## What is still open

- **Reuse in the study bar.** The coordinator asked for "Použít jako základ…" in the study bar as well
  as the header. It is not there, because the bar sits directly below the header and the action would
  show twice. This waits on the product owner.
- **The build spec.** Spec v6 describes the prototype at v78. It does not yet carry:
  - Sběr dat from v82;
  - the de-duplication of v92;
  - reuse and the removal of Projektová paměť from v93;
  - 7b in plain words from v95.
- **Backend gaps that the folder decision needs.** Both are recorded in spec v6 `lead.md` § 3.4 as B17
  and B18:
  - client-knowledge folders are flat today;
  - a download stores nothing.
- **Counts per age group while collecting** need quota reporting from the run. It is switched off on
  develop, so "Podle věku" is drawn from the planned quota shares.
