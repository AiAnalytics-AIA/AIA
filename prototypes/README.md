# Prototypes

Design references for AIA's interface. None of this is product code: nothing here is imported by
`apps/web`, calls an AIA endpoint, a model or a paid service, and every client, study, person and
number in it is fictional.

## The canonical design reference (from 26 Oct 2026)

From 26 Oct 2026 the canonical design reference is these two Design-canvas prototypes, by the product
owner's decision: *"i am super happy with the design of the research steps, we need to aim to build
out this exact UX design."*

| Folder | What | Live canvas (private to the owner's account) | Exported version |
|---|---|---|---|
| [`settings-v99/`](settings-v99/) | "AIA Nastavení – prototyp": 11 pages: Metodika, Systémové prompty, Deep Research, AI běh, Přístup a schvalování, Studie a rozpočty, Audit, Stav systému, Správa dat, Vypěstovat Vedoucího, Můj Vedoucí | <https://claude.ai/artifact/8W9LR8Ju9BWnR5JACmiWv7> | v99 (artifact version `1792978087-0038`) |
| [`research-stages-v73/`](research-stages-v73/) | "AIA Výzkumné kroky – prototyp": 22 boards: the eleven stages (Zadání … Zpráva), the respondent disc, the overview, the Lead's cards, six chat variants, the Lead's mark | <https://claude.ai/artifact/3dkKPTDoa1yvK4GCV7PLtJ> | v73 (artifact version `1792979634-5793`) |
| [`research-stages-v73/spec/`](research-stages-v73/spec/) | The research build spec: the prototype mapped onto `develop` at `bd0d1ad6`, stage by stage, with build chunks, backend gaps and owner questions | <https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy> | spec v4 (artifact version `1792979639-7523`; written against prototype v73, with the owner's decisions of 26 Oct) |
| [`LOOK.md`](LOOK.md) | The look contract both prototypes follow: colour, status, type, radii, icons, frame, components, copy; the three questions it raised and their answers | <https://claude.ai/artifact/1iuneZ5EAYJTfr854VRHPM> | artifact version `1792976899-803a` |
| [`shared/aia-core.css`](shared/aia-core.css) | Core v3, the one shared stylesheet: tokens from `tokens.json` @ `bd0d1ad6`, the shell, the shared components and the Phosphor icons. Owned by the Settings canvas | Settings asset `c4e14f481d7c21ea1bf1a75f25894eea`; research's copy `32eed12bf6d8fbe65a8c1b56d49b11e9` | SHA-256 `bedd953f6e8d77433f0bd69be873eb9da6c2afede59b6922a29a31333f2e6b70`; the two canvases' copies are byte-identical |

The older references stay as history: [`research-lead-v2/`](research-lead-v2/) (the workbench
prototype, canonical from 2026-10-20 until now) and [`research-lead-v3/`](research-lead-v3/) (its
artifact boards as text). Where they disagree with the two above, the two above win.

The canvases are the source of truth and keep moving; these folders are snapshots. Re-export into a
new `-v<N>` folder rather than editing a snapshot by hand.

## How to read a `.dc.html` file

Each `.dc.html` is one **Design-canvas artboard**, not a web page. It loads `./support.js` (the canvas
runtime) and its scripts, and uses the canvas's own markup (`<x-dc>`, `<helmet>`, `<sc-if>`,
`<sc-for>`, `{{…}}` bindings and a `DCLogic` component class in a `text/x-dc` script). That runtime
exists only inside the canvas, so opened in a browser the file does not render as designed. Read it
as source: the markup, the copy, the class names and the component logic are the design.
`canvas.json` in each folder lists the boards, their titles, sizes and positions, and their order.

Links between boards (`href="Design.dc.html"`) are relative and resolve inside the folder. Links to
`https://claude.ai/artifact/…` point at the live canvases: the research boards' "Můj Vedoucí" button
opens the Settings canvas, and Sociomapa's "Otevřít živou dílnu" opens the Sociomap workshop
(`QWDidu8ztrcuiBNL5Sa4Vy`, not exported).

Icons are Phosphor Regular (`@phosphor-icons/core` 2.1.1, MIT licence, Copyright (c) 2023 Phosphor
Icons; the licence text is in [`shared/PHOSPHOR-LICENSE`](shared/PHOSPHOR-LICENSE), copied from the 2.1.1 package), written as `<i class="ph ph-<name>">`. Their 93 glyphs are inline SVG masks inside
`shared/aia-core.css`, so no icon font or CDN is involved. Fonts load from Google Fonts in the boards
themselves (IBM Plex Sans, IBM Plex Mono, Source Serif 4).

## What was exported, and what was not

Every `/_blob/<id>` URL whose file was exported has been rewritten to a relative path.

**Settings (`settings-v99/`)**

| File | From | Used by |
|---|---|---|
| `canvas.json`, 11 `*.dc.html` | `project/` | |
| `../shared/aia-core.css` | asset `c4e14f481d7c21ea1bf1a75f25894eea` | every page |
| `assets/aia-settings.css` | asset `299c2616168d3335f9bc59cbb708478c` | every page but Hatch and LeadSettings |
| `assets/889c3d28bc209704c3ef7887107cb48d.webp` | asset of that id | Main (Metodika): the Sociomap sample image |

**Research stages (`research-stages-v73/`)**

| File | From | Used by |
|---|---|---|
| `canvas.json`, 22 `*.dc.html` | `project/` | |
| `../shared/aia-core.css` | asset `32eed12bf6d8fbe65a8c1b56d49b11e9` (byte-identical to Settings') | every board |
| `assets/aia-study.css` | asset `49420235f65095ba317683657e5dddbb` (SHA-256 `d1a2d23b…`) | every board: the study layer on top of core (stage navigator, study header, split, Lead pane and cards, stage sections) |
| `assets/<id>.jpg` (12) | assets of those ids | "Dnes v AIA" screenshots of today's workbench at 1440 px, one per stage board (Fieldwork has two) |
| `assets/<id>.png` (12) | assets of those ids | Sociomap: the approved 3D map (`03a69632…`, 0.9 MB); Report: the report editor's toolbar in ONLYOFFICE's default and AIA's theme, the 232-icon grid and the editor states |

The research canvas still publishes its own `Hatch.dc.html` and `LeadSettings.dc.html`, but they are
not on its canvas and no board links them: the look contract retired them in favour of Settings'
copies. They and the old stylesheet only they used were not exported.

**Not exported** (left as they are in the HTML):

| Asset | What | Where | Why |
|---|---|---|---|
| `/_blob/1aa4f92cccca03849efce6807a4b7c3c` (28,761 bytes) | thinking-orbs 0.3.2 engine (MIT, Jakub Antalik), JavaScript | all 22 research boards | a script, not a font, icon or image; the product already ships the package (`ActivityOrb`) |
| `/_blob/6659cc2592302e4ff9bbdaaa4c953b68` (29,791 bytes) | the same engine wrapped as a `<thinking-orb>` element, JavaScript | Settings: LeadSettings, System | as above |
| `./support.js` | the canvas runtime | every board | part of the Design canvas, not of the prototype |
| `https://fonts.googleapis.com/css2?…` | IBM Plex Sans, IBM Plex Mono, Source Serif 4 | every board | loaded from Google Fonts, kept as a link |

The canvases' asset stores also hold earlier versions of these stylesheets, scripts and screenshots
that no current board references; they were not exported.
