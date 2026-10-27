# AIA Výzkumné kroky – prototyp, 27 Oct 2026

A snapshot of the research-stages Design canvas, for use from another account. It is design reference,
not product code: nothing here is imported by `apps/web`, and every client, study, person and number is
fictional. How to read a `.dc.html` file is in [`../README.md`](../README.md) § How to read a `.dc.html`
file: the files are canvas artboards, and they do not render as designed in a plain browser.

| | |
|---|---|
| Live canvas | <https://claude.ai/artifact/3dkKPTDoa1yvK4GCV7PLtJ> (private to the owner's account) |
| Version | v93, artifact version `1793095498-cbb2` |
| Exported | 27 Oct 2026 |
| Previous snapshot | [`../research-stages-v73/`](../research-stages-v73/) (v73, 26 Oct) |
| Build spec | <https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy>, v6. It still describes the prototype at v78 (see Open) |

## What is in this folder

- **24 boards**, listed in `canvas.json` order with their titles in the table below. `canvas.json` also
  holds each board's size and position on the canvas.
- **`assets/aia-core.css`**: core v4.2, the "Petrol" shared stylesheet (SHA-256 `b6bb5edf…6e103d`). It is
  owned by the design-system session and is newer than `../shared/aia-core.css` (core v3), which this
  export does not touch.
- **`assets/aia-study.css`**: the research stages' own stylesheet (SHA-256 `d1a2d23b…00f689`).
- **`assets/thinking-orbs.js`**: the Lead's orb (thinking-orbs 0.3.2, MIT, Jakub Antalik).
- **`assets/<id>.png|jpg`**: the screenshots of today's AIA that the boards' "UX kritika" sections show.

Every `/_blob/<id>` reference was rewritten to its file under `assets/`. Board links (`href="Design.dc.html"`)
resolve inside the folder. `./support.js` is the canvas runtime and is not exported.

Two files on the canvas are not exported:
- `Hatch.dc.html` and `LeadSettings.dc.html` are not boards of this canvas, and no board links to them.
- "Můj Vedoucí" opens the Settings canvas, which is exported in [`../settings-v99/`](../settings-v99/).

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
| `ChatA.dc.html` … `ChatF.dc.html` | Six variants of the Lead's chat |
| `Marks.dc.html` | Značka Vedoucího · 5 variant |

## What is decided (the product owner, 26–27 Oct 2026)

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
- **The look is core v4.2:** the Petrol palette, AI shown in graphite with a spark edge, the ⌘K palette,
  the activity tray and the study bar. All of it is from the design-system session.

## What is still open

- **Reuse in the study bar.** The coordinator asked for "Použít jako základ…" in the study bar as well
  as the header. It is not there, because the bar sits directly below the header and the action would
  show twice. This waits on the product owner.
- **The left rail's hover.** Item text turns white on hover and cannot be read. Core v4.2 owns this, and
  the design-system session will fix it; nothing in this canvas overrides it.
- **`ph-dots-three` in core.** Core v4.2 has no ⋯ icon. The boards define it locally (Phosphor's path),
  and it should move into core.
- **The build spec.** Spec v6 describes the prototype at v78. It does not yet carry:
  - Sběr dat from v82;
  - the de-duplication of v92;
  - reuse and the removal of Projektová paměť from v93.
- **Backend gaps that the folder decision needs.** Both are recorded in spec v6 `lead.md` § 3.4 as B17
  and B18:
  - client-knowledge folders are flat today;
  - a download stores nothing.
- **Counts per age group while collecting** need quota reporting from the run. It is switched off on
  develop, so "Podle věku" is drawn from the planned quota shares.
