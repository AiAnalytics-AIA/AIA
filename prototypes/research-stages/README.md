# AIA Výzkumné kroky – prototyp, 30 Oct 2026

A snapshot of the research-stages Design canvas, for use from another account. It is design reference,
not product code: nothing here is imported by `apps/web`, and every client, study, person and number is
fictional. How to read a `.dc.html` file is in [`../README.md`](../README.md) § How to read a `.dc.html`
file: the files are canvas artboards, and they do not render as designed in a plain browser.

| | |
|---|---|
| Live canvas | <https://claude.ai/artifact/U4b83GH2X5coxx51ATL1T5>, in the product owner's second account, which owns the research pages prototype since 28 Oct 2026 (private to that account) |
| Version | version 20, artifact version `1793348891-11ce` |
| Exported | 30 Oct 2026 |
| Earlier canvas | <https://claude.ai/artifact/3dkKPTDoa1yvK4GCV7PLtJ> in the first account, last exported at v95 (`1793099019-3a7d`, 27 Oct). It is no longer the source: change the second account's canvas, not this one |
| Previous versions | in git history: version 14 (29 Oct, the Zadání proposal's first export); version 9 (28 Oct, the core v4.3 heroes); v95 (27 Oct) is this folder's previous export; v73 (26 Oct) was `prototypes/research-stages-v73/` |
| Build spec | <https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy>, v6. It still describes the prototype at v78 (see Open) |

## What changed in version 20 (30 Oct)

**The stage navigator on the Zadání boards** (the product owner, 30 Oct, relayed by the PM coordinator). Only
`Z0`–`Z7` changed; every other board, stylesheet and asset is byte-identical to version 14.

- **Zadání is the first phase of its own on both bars**, in a fixed 180 px column, so it stays in the same place
  whatever the path.
- **The Výzkum bar** reads Zadání | Návrh výzkumu: Návrh, Dotazník | Vymezení vzorku | Sběr | Evidence |
  Interpretace | Předání.
- **`Z3Decision` and `Z7Ready` show their bar as `Z4`/`Z5` do** and say which path the example follows. On `Z7`
  the bar, the study and the hand-off follow its path switch.
- **`Z6Both` has a Studie switch** between the two linked studies (Model · sklad / Výzkum · zákazníci), each
  with its own header and bar.
- **`Z0Flow` notes** that the regrouping is proposed for the app's navigator too (research-lead-workbench 35)
  and waits on D1–D7.

The `Z0Flow` and `Z6Both` frames grew to 1500 and 1720 px. `canvas.json` also carries the move of
`CardsF.dc.html` made on the canvas (now at x 3080, y −2600). Every render has no new script error.

## What changed in version 14 (29 Oct)

**A proposal: Zadání with two paths** (the product owner, 29 Oct: "I want to upgrade the zadani step to allow
for this dual path … Suggest upgrades based on the best research design practices", and "i want to see
something visual"). Ten new boards in a row of their own, "Zadání se dvěma cestami · návrh 29. 10.", walk
one intake that routes a study to Výzkum, Model (the coming scenario cost model) or both:

- `Z0Flow` is the walk-through: the five moves and every board in order.
- `Z1Start` starts from one box, "Co potřebujete rozhodnout?", and Přidat podklady (empty and typed).
- `Z2Triage` shows the Lead's path proposal with its reason, the drafted sections as one proposal with
  checkboxes, and three questions ranked by how much each answer changes the design.
- `Z3Decision` holds the decision block: decision, owner, date, options with "nic neměnit", the action
  standard per path, a grey zone and the certainty needed; states "chybí práh" and the vague word with its
  measurable rewrite.
- `Z4Research` (Pivovar Zlatá Hora, +3 Kč) runs from information needs to research questions with their type,
  whom the decision concerns, the measures the rule reads, what is known with its certainty, and what each
  becomes on Návrh.
- `Z5Model` (a fictional e-shop, a 2 000 m² warehouse or a 3PL) has the target quantity, horizon, boundary in and
  out, the data inventory (file → number, one missing), assumptions with value or range, source and owner,
  and what could flip the answer.
- `Z6Both` shows one Zadání creating two linked studies: what each inherits, and the research result
  offered to the model as an assumption.
- `Z7Ready` puts rubric R1–R7 in the chip row and its drawer, then the hand-off blocked, ready and done, into
  Návrh or into Data.
- `Z8aPhone` and `Z8bPhone` are the start and the triage at 390 px.

The existing boards are unchanged; `Brief.dc.html` stays the approved Zadání until the product owner picks.
The new boards keep the decisions below: no data classes on screen, no stage showing what another owns
(the population, comparison objects and measures are asked in words and handed on as proposals), the
readiness chip row, paid AI only through a card, the compact stage header. Every render has no new script
error; Report's and ReportEditor's `{{shot}}` placeholders are as before. Known gaps: the model study's own
stages (Data, Předpoklady, Model, Výsledky) are not drawn yet; its navigator links nowhere.

## What changed since v95

The second account's canvas was rebuilt from the v95 export on 27 Oct, board for board (each render matched
`reference/` within animation). Then, on 28 Oct, the product owner made **Chat F canonical**: "we leave chat f,
the rest we dont need". Chat A–E are gone, and `ChatF.dc.html` keeps its file name under the new title "Chat
Vedoucího · bubliny na časové ose", alone in the chat row with no row title. Nothing else changed: every other
board, stylesheet and asset is byte-identical to v95. Nothing is known to be wrong in it.

## What is in this folder

- **29 boards**, listed in `canvas.json` order with their titles in the table below. `canvas.json` also
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
| `Z0Flow.dc.html` | Z0 · Zadání se dvěma cestami: průchod |
| `Z1Start.dc.html` | Z1 · Zadání: začátek |
| `Z2Triage.dc.html` | Z2 · Zadání: triáž |
| `Z3Decision.dc.html` | Z3 · Zadání: rozhodnutí a pravidlo |
| `Z8aPhone.dc.html`, `Z8bPhone.dc.html` | Z8a, Z8b · Telefon: začátek, triáž |
| `Z4Research.dc.html` | Z4 · Zadání: cesta Výzkum |
| `Z5Model.dc.html` | Z5 · Zadání: cesta Model |
| `Z6Both.dc.html` | Z6 · Zadání: obojí |
| `Z7Ready.dc.html` | Z7 · Zadání: připravenost a předání |

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
