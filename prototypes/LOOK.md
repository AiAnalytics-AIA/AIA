# AIA look contract

One look for Settings and the research stages, as of 26 Oct 2026. Both prototypes follow it
(Settings at the time it was written: v93, 11 pages; research stages: v63, 24 boards). It found 29
differences between them and left 3 for the product owner, all since answered (below).

Source: the coordinator's page <https://claude.ai/artifact/1iuneZ5EAYJTfr854VRHPM> (private to the
owner's account), summarised here on 26 Oct 2026. Every value comes from the product owner's words in
either prototype chat, or from the product's own tokens (`apps/web/src/design/tokens.json` on
`develop` at `bd0d1ad6`). Quotes in italics are the product owner's. The page was re-read on 26 Oct
2026 after Settings v99 and research v71 were published; it was unchanged (artifact version
`1792976899-803a`).

## How each difference was settled

The same order for every item:

| Step | Rule |
|---|---|
| 1. His words | If the product owner decided it in either chat, that decision stands. His quotes are kept where they settle something. |
| 2. The product | Otherwise the value in `tokens.json` and the real AppShell wins, because that is what ships. |
| 3. The richer prototype | Where tokens are silent, the more developed prototype's version is kept, recoloured to tokens. |
| 4. The owner | Where his words in the two chats point different ways, or nothing settles it, it is a question. |

One correction: the research session thought develop's signal was `#3557e0`. It is not. Develop
moved to Indigo `#4b48ce` (commit `1d7eae81`); `#3557e0` is now only the blue wayfinding tint. Both
prototypes already use the right signal; only the report editor's theme still had the old one.

## The three questions, answered

All three were answered with the recommended option on 26 Oct 2026 (00:41-00:42 UTC), in the page's
answer store.

| Id | Question | Context | Options | Answer |
|---|---|---|---|---|
| UI-1 | Where does the big serif hero go? | Settings opens every page with a hero (40 px serif title, lede, 3-5 figures), as asked (*"now do the same"* for every page). The stages use a compact 20 px header because the Lead pane and stage navigator already take the top of the screen. | a. Top-level pages only (Settings, Můj Vedoucí, Klienti and a client's workspace get the hero; inside a study the compact stage header stays). b. Everywhere, stages too (the artifact pane loses about 140 px of height at 1440). c. Compact everywhere (a 24 px title row, as the product's Settings page has today). | **a. Top-level pages only** |
| UI-2 | Phosphor in the product too, or only in the prototypes? | The product today draws its own icons (1.5 px stroke, in `Icons.tsx` and AppShell). Phosphor Regular reads about the same weight at 16 px. | a. The product switches to Phosphor (a web chunk replaces the hand-drawn icons, except the rail's nav icons, with `@phosphor-icons/core`, MIT). b. Prototypes only (the build matches their weight, not their shapes). | **a. The product switches to Phosphor** |
| UI-3 | How soft is the Lead chat? | Research drew the chat softer: cards at 16-20 px corners, a fully rounded 24 px composer. The rule *"rounded but not complete pills"* would bring them to 10 (cards) and 12 (composer). | a. Same as the rest (chat cards 10, composer 12). b. Keep the chat softer (cards 16, composer fully rounded; the one exception to the pill rule). | **a. Same as the rest** |

## Colour

`tokens.json` values, light and dark. The dark column was corrected to `tokens.json` at `bd0d1ad6`
on 26 Oct, 01:15: the first version had 17 hand-picked dark values.

| Role | Light | Dark | Use |
|---|---|---|---|
| Surface · raised · sunken | `#eef0f4` · `#fff` · `#e5e8ee` | `#0d1015` · `#151a21` · `#0a0c10` | Page ground · cards · table headers and wells |
| Border · strong | `#dde1e8` · `#7d8490` | `#252c36` · `#6d7684` | Hairlines · control outlines |
| Ink · muted · faint | `#151a20` · `#43484f` · `#5c6167` | `#ece9e4` · `#bdbab5` · `#9e9b96` | Text levels |
| Signal (Indigo) | `#4b48ce`, hover `#3f3cad` | `#828bea` (hover `#969eed`) | Selection, links, the primary action, a running process. Never decoration. |
| Signal wash · edge · tint · on-signal | `#ededfa` · `#c0bfee` · `#f6f6fd` · `#fff` | `#1b1f2f` · `#3c416a` · `#151924` · `#0a0c10` | Selected grounds, quote rules, chosen options |
| Needs you (coral) | `#ff8270`, ink `#971c11`, wash `#fbe7e6` | `#ffaa77`, ink `#ffaa77`, wash `#45301f` | Only for something a person must act on, and only shown to people who can act. Everyone else sees slate. |
| Waiting on the world (slate) | `#576574`, wash `#e3e8ee` | `#97a7b7`, wash `#21272d` | Waiting, but not on you |
| Fault | `#c92516`, wash `#f7e3e3` | `#f5746b`, wash `#4a2323` | Failed, refused |
| In force (green) | `#1d9a6c`, wash `#e2f3ec` | `#5fd1a5`, wash `#16332a` | Only the version in force. The one green in the interface. |
| AI / Lead | `#9b8bfb`, ink `#5c28a0`, wash `#f1f0fd`, edge `#cdc5fd` | `#bab4fb`, ink `#bbb3fb`, wash `#48475d`, edge `#68678e` | The Lead's mark, the orb, paid AI starts |
| Shell | `#11151b`, ink `#e8e6e1` | the same | The graphite rail |
| Wayfinding tints | `#3557e0`, `#7a4fd6`, `#1d9a6c`, `#0f8a8a`, `#5b6472` (tokens `hue-*`) | tokens `hue-*` | Nav tiles and the R16 phase layering, at most 9 %, fading. Never a status. |

## Status, one vocabulary

| Status | Glyph |
|---|---|
| Hotovo | filled ink circle |
| Čeká na vás | filled coral |
| Běží | signal ring (2 px) |
| Čeká na rozpočet (for others) | filled slate |
| Chyba | filled fault |
| Nezačato | 1.5 px strong ring |
| V platnosti | filled in-force green |

Done is quiet ink, never green (tokens: *"there is no green in the status family"*). There is no
amber anywhere: "parked, waiting on a person" is coral; waiting on the world is slate. The one other
green is the +/- diff (*"the plus minus green red system … like code"*).

## Type

IBM Plex Sans and IBM Plex Mono; Source Serif 4 for large titles. Weights 400, 500 and 600 only.

| Role | Size / line | Weight | Where |
|---|---|---|---|
| Page hero title | serif 40/46 | 600 | Top-level pages (UI-1) |
| Stage title | sans 20/26 | 600 | The artifact header inside a study |
| Section heading | 15/20 | 600 | Both (Settings moves from 16/22) |
| Body | 14/20 | 400 | Both; tables 13 |
| Lede | 16/24 muted, max 62ch | 400 | Hero |
| Caption · label | 12/16 | 400 · 500 | Both |
| Eyebrow | 12, uppercase, .06em tracking | 600 | Signal on heroes; coral ink on a card that needs you |
| Figures | 20/26 to 44 | 600 | Hero figures and KPI tiles; research's 700 becomes 600 |
| Mono | 12 | 400 | Ids, amounts in tables, formulas |

Figures are tabular (`font-variant-numeric: tabular-nums`).

## Spacing, radii, depth, motion

The rules: *"i like rounded but not complete pills"* and *"no menu should be a row of pill buttons
ever"*.

| Radius | Applies to |
|---|---|
| 0 | Tables, the stage navigator |
| 6 | Buttons, inputs, segmented controls, chips, tags, notes, toasts, nav items |
| 8 | Cards and stage sections |
| 10 | Dialogs, menus, dropdowns, the settings flyout, Lead chat cards |
| round | Only things round by nature: avatars, the Lead mark, count badges, the switch |

Research's buttons move from 8 to 6 and its inputs from 3 to 6. Settings' chips move from full pills
(11 on 22) to 6, and its Lead-page tabs from 999 to 6.

| Aspect | Rule |
|---|---|
| Spacing | 4 · 8 · 12 · 16 · 24 · 32 · 48; 6 only inside controls |
| Depth | Flat and bordered. One shadow, the tokens' `shadow-overlay`, for dialogs, menus and the flyout only. R16's tonal layering stays (*"no hard color transitions, but a systematic way of breaking up the text and boxes"*). |
| Motion | 120 ms state changes, 180 ms panels; the rail's Dock motion as Settings built it; everything off under reduced motion, including research's spinner and shimmer. |
| Widths | 1440 only for now (*"no narrower screens right now"*). The product keeps the workbench's existing drawer and sheet layouts. |

## Icons

*"I don't want to see a single emoji used … use these icons instead."* Phosphor Regular (MIT,
`@phosphor-icons/core` 2.1.1) in both prototypes, 16 px in text and controls, 20 px in tiles.
Research replaces Lucide. The rail keeps AppShell's own nav icons. No emoji anywhere. The product
itself switches to Phosphor (UI-2).

## The frame

*"import the actual menu from the AIA software into each canvas"*; *"auto hide and auto open, like
the mac dock … keep a small menu bar, just keep the icons"*.

| Part | Rule |
|---|---|
| Left rail | The real AppShell in both prototypes: a 64 px graphite icon bar that opens to 240 px on hover or focus, with Settings' motion. Klienti, Společenská inteligence, Projektová paměť and Nastavení, then Můj Vedoucí as its own item. Nastavení opens the settings flyout. Research drops its 56 px rail and the "AIA" square. The shell is Settings' (*"leave it to the settings page"*) and research adopts it. |
| Top bar | Breadcrumb with "/" separators, 13/20 muted, the current item 500 ink: "Organizace Delta / Nastavení / Audit", "Klienti / Pivovar Zlatá Hora / Studie". Settings' 3 px accent strip goes, since no study page has one. |
| Page header | Top-level pages carry the hero (eyebrow, serif title, lede, 3-5 figures). Inside a study the study header is research's: client monogram, title, the budget meter (spent, held, total), Přehled. Then the stage navigator from #840, then the artifact header (20/26 title, saved state, next stage). Settled by UI-1. |
| Study split | Lead pane 420 px on the left, the artifact pane the rest, body up to 1000 px wide. Settings pages up to 1180 px; Můj Vedoucí 1040 px, centred (*"centre the Můj Vedoucí content"*). |

## Components

One class vocabulary for both.

| Component | The contract | From |
|---|---|---|
| Buttons | 32 high (small 28), radius 6, 13/500. Primary signal; secondary raised with a strong border; quiet; danger in fault outline for what cannot be undone; AI in the AI tint, only for paid AI starts (dark text `#120b2e`). No green "ok" button. A paid action leads with its amount (*"should focus on the 10 USD"*), e.g. "Navýšit a pokračovat · 10 USD". | both |
| Inputs, select | 32 high, radius 6, 1 px strong, 13 px. Inline edit: a 2 px signal underline on the tint. Select: a button with a caret opening a list (radius 10, overlay shadow). | Settings |
| Segmented | Square cells divided by borders, the chosen one signal-filled. Every option menu is built this way, never a row of pills. | Settings |
| Switch | 40 × 24, signal when on. Research's 32 × 18 goes: it is under the 24 px target. | Settings |
| Chips, tags | 24 high, radius 6, 12/500; status pills have the same shape with a glyph. | merged |
| Tables | Square, header 12/500 muted on sunken, cells 8 × 10, rows 36 (28 compact); needs-you rows in the coral wash for those who can act, slate wash for others. | tokens |
| Cards, sections | Raised, 1 px border, radius 8, no shadow. Stage sections keep research's numbered header (01, 02), since their order is real. | both |
| Notes | Radius 6, surface ground; variants needs-you, signal, fault. No amber or green notes. | merged |
| Dialog | 560 px, radius 10, padding 24, overlay shadow over a 10 % ink scrim. Irreversible deletes make you type the name. | Settings |
| Toast | Ink pill, radius 6, bottom centre, "Vrátit" as a text button, 8 s with undo. | both |
| Status glyph | Research's glyph circles (14/16/20 px) in the colours above; Settings' 8 px dot only in dense tables. | research |
| Thinking | The real thinking-orbs 0.3.2 in the AI ink (*"use the real orb"*), as thinking and while a Lead card streams. Research's own orb goes. | Settings |
| Lead cards | Research's CardsF: amounts first, running cards stream AIA's own words with times, never a percentage. Recoloured to tokens, radius 10. | research |
| Diffs | Line diff, added `#e6f4ea`, removed `#fdecea`, a "+n −m" summary. | Settings |

## The Lead's pages

Both prototypes drew Hatch and Můj Vedoucí. From now on there is one copy, owned by Settings.

- **Vypěstovat Vedoucího.** Settings' version (*"grow their own from a test tube … then very simply
  ask them the necessary questions"*): a single column, the test tube, traits as segmented pairs
  plus free text, then the mark. It adds the acceptance step decided on 25 Oct: the model's SOUL and
  USER are shown in full with "Přijmout" or "Zadat znovu" before anything is kept. Research's
  "líhne se" wording and its side preview go; the lead-identity plan's "Líhnutí" is renamed to match
  in the next docs batch.
- **Můj Vedoucí.** Settings' version: hero, files first and readable (*"give each file more
  space"*), centred, the chat preview behind a button, then the mark, its motion and auto-accept.
  "Otevřít chat" opens the last study the researcher talked to the Lead in (decided 25 Oct). Both
  pages move off the old 2-3 px stylesheet onto the shared one.

## Copy

Czech, sentence case, the product's own words.

| Topic | Rule |
|---|---|
| Money | Czech locale with the thousands space and the unit after: "1 250,00 USD", "0,40 USD". An unknown amount in words, never 0. The four names: Rozpočet klienta, Rozpočet studie, Peněženka, Práh potvrzení. Research switches from `toFixed` to the locale. |
| Status words | Hotovo · Čeká na vás · Běží · Čeká na rozpočet · Chyba · Zaparkováno · V platnosti · Zapnuto / Vypnuto · Jen ke čtení. "Hotovo" only when a stage really is done. |
| Casing | Sentence case for titles and buttons; uppercase only through CSS, for eyebrows and group labels. |

## One stylesheet, so they inherit from each other

- **`aia-core.css`**, owned by the Settings session: the tokens (light and dark), the type scale, the
  shell (rail, flyout, breadcrumb, hero) and every shared component above. Built from `tokens.json`,
  not hand-copied. Kept here as [`shared/aia-core.css`](shared/aia-core.css): core v3, which both
  canvases now load byte for byte (SHA-256 `bedd953f…`). It carries the Phosphor icons as `ph ph-<name>`
  classes (inline SVG masks) and scopes the serif titles to `.hero-h` (40/46) and `h1.title` (24/30).
- **`aia-study.css`**, owned by the research session, built only on core's tokens: the stage
  navigator, study header, split, Lead pane, Lead cards and stage sections. Kept as
  [`research-stages-v71/assets/aia-study.css`](research-stages-v71/assets/aia-study.css).
- Both canvases load core; the research boards add study. A change to core is made once, by its
  owner, and the other canvas copies the new version in. Page-specific CSS stays only for
  page-specific parts.

## What changes in Settings

| Change | Kind | Why |
|---|---|---|
| Build `aia-core.css` from `tokens.json` and move every page onto it, Hatch and Můj Vedoucí included | core | The Lead pages still sat on research's old stylesheet with 2-3 px radii. |
| Chips 22/11 → 24/6; Lead-page tabs and segments 999 → 6 | radii | *"rounded but not complete pills"* |
| Section heading 16/22 → 15/20; weight 700 on the Lead pages → 600 | type | |
| Metodika's "in force" from slate back to green; dark needs-you → `#ffaa77`; links `#3557e0` → signal | colour | |
| Table headers on sunken, muted; dialog padding 20 → 24 | components | |
| Remove the 3 px accent strip | frame | |
| Hatch: add the Přijmout / Zadat znovu step | owner's decision | |
| Fix the broken comment in `settings14.css` that drops `.page{display:block}` | defect | |

## What changes in the research stages

| Change | Kind | Why |
|---|---|---|
| Load `aia-core.css`; build `aia-study.css` on its tokens | core | |
| Replace the 56 px rail with the AppShell Dock rail; breadcrumb with "/" | frame | |
| Done green → ink; parked amber → coral; drop the green button, note and "Uloženo" | colour | No amber; green only for in force |
| Dark AI wash → `#48475d`; dark needs-you → `#ffaa77` | colour | |
| Buttons 8 → 6, inputs 3 → 6, chips 28/7 → 24/6, notes and toast → 6, dialog → 560/10 | radii | |
| Lead chat: cards and bubbles 16-20 → 10, composer 24 → 12 (UI-3 kept this); chat ground `#f5f6f9` → the surface token, which also fixes the light patches in dark mode | Lead pane | |
| Lucide → Phosphor; the custom orb → thinking-orbs; switch 32 × 18 → 40 × 24 | components | |
| Weight 700 → 600; money through the Czech locale | type, copy | |
| Retire its Hatch and LeadSettings copies; link to Settings' boards; keep Marks | Lead pages | |
| Report editor theme: signal `#3557e0` → `#4b48ce` | editor | |
| Reduced motion for the spinner and shimmer | defect | |

Kept as it is: R16's tonal layering, the stage navigator, the study header and budget meter, the
numbered sections, the Lead cards, the fieldwork disc. The functional questions the research session
raised (two views on Sběr dat, the editor's fonts) are in the development plan, not here.
