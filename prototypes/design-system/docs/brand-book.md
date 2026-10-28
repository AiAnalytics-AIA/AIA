# AIA Design System v3 (Petrol)

**What changed in v3 (27 Oct 2026).** The product owner chose the **Petrol** palette over the indigo of v2:
- true neutral greys;
- a deep petrol-teal `signal` (#0f6577 light, #4fb2c3 dark) used only for selection, links, focus and the one primary action;
- AI has no colour of its own: graphite and the spark edge (`spark-1..3`, the identity's cyan, sky and an ice glint), turning on hover, focus and while a model works (v3.1, 27 Oct 2026; the iris violet is gone);
- warm orange `status-you` (#ff9050) reserved for what waits on a person;
- green only for "v platnosti".

Every pair is re-measured by `check-design.mjs`: 222 contrast checks, 0 failures; needs-you is held apart from fault and orange.

The rail now follows the theme. Core v4.1 adds:
- the command palette (Ctrl/⌘ K) and the activity tray in every top bar;
- the study bar under the stage navigator;
- a new home for a study, **Přehled studie**.

The new group **Interakce** is the catalogue of how things behave: saving, undo or confirm, money, keyboard, an AI job's life, loading, empty and error states, editing in place, selection and moving through a study. It was read from the code of every page and checked against what the page-owning sessions report. Each rule names the places that break it today, with file:line.

All three prototype canvases (Klienti, Výzkumné kroky, Nastavení) load core v4.1.

AIA is a dense, professional research studio in Czech: a researcher designs a study, an AI Lead (Ada) works beside every artifact, money is confirmed before it is spent, and evidence states are never rounded into good news. v2 was the look the product owner approved on 26 Oct 2026: the Settings prototype (v99) and the research-stage prototype (v77), both built on one shared stylesheet, core v3, and the look contract `prototypes/LOOK.md`. Where `tokens.json` in the product, core v3 and LOOK.md disagree, the section *Otázky k rozhodnutí* lists it with a recommendation; *Co nahrazuje co* lists every old form and its replacement.

## Principles

- **Flat and bordered.** Surfaces are told apart by `surface`, `surface-raised` and `surface-sunken` and a 1 px `border`, never by shadow. One shadow, `shadow-overlay`, only for dialogs, menus and the settings flyout.
- **Colour means something or it is not there.** `signal` is selection, links, the primary action and a running process; never decoration. Status colours are reserved (below). Wayfinding tints (`hue-*`) at most 9 % and fading, never a status.
- **Rounded, not pills.** "I like rounded but not complete pills"; "no menu should be a row of pill buttons ever".
- **Unknown is never good.** An unknown amount, count or status reads in words ("neznámá", "nezaznamenáno", "?") and is never drawn as 0 or as done.
- **No emoji.** "I don't want to see a single emoji used." Phosphor icons only.

## Content

- Czech, sentence case, the product's own words. Uppercase only through CSS, for eyebrows and group labels.
- A control says exactly what happens: "Uložit jako v3", "Smazat natrvalo", "Spustit úlohu · 0,40 USD". The toast then says what happened: "Role změněna. Vrátit".
- Money in the Czech locale, the thousands space and the unit after: "1 250,00 USD", "0,40 USD". The four money names, written once: **Rozpočet klienta, Rozpočet studie, Peněženka, Práh potvrzení**. A ceiling is "horní mez, ne odhad".
- Status words: **Hotovo · Čeká na vás · Běží · Čeká na rozpočet · Chyba · Zaparkováno · V platnosti · Zapnuto / Vypnuto · Jen ke čtení.** "Hotovo" only when a stage really is done.
- A failure says what failed, why and the way out. A refusal names who can change it ("Mění jen vlastník nebo správce.").
- The Lead is "Vedoucí výzkumu"; the default Lead in examples is "Ada". What the Lead or a model wrote is labelled as such and is never evidence.

## Colour

Set every colour from a token; light and dark are both designed (themes Světlý, Tmavý).

- Ground: `surface` for the page, `surface-raised` for cards, sections and table bodies, `surface-sunken` for table headers, wells and meter tracks, `surface-overlay` for dialogs and menus.
- Text: `ink` for text and every figure a conclusion rests on, `ink-muted` for labels and secondary text, `ink-faint` for captions, hints and timestamps. All three hold 4.5:1 on all four surfaces in both themes.
- Lines: `border` for hairlines (decorative), `border-strong` for control outlines (3:1).
- `signal` for the primary action, selection, links and focus; `signal-wash` for a selected row or stage, `signal-tint` for an informational ground, `signal-edge` for its edge.
- `ai`, `ai-strong`, `on-ai` (graphite), `ai-wash`, `ai-edge` (a cool neutral) and `spark-1..3`: only the Lead's mark, the thinking orb, a paid AI start and what an AI wrote that waits for a person. `ai-ink` is gone: AI text is ink beside the sparkle. Component **AiSpark**.
- The shell: `shell` follows the theme (light #f1f3f4, dark #0a0d0f) with `shell-ink`; rail tiles are neutral, the active place is `signal-wash` with a `signal` mark.

### Status, one vocabulary

| Word | Glyph | Tokens |
|---|---|---|
| Hotovo | filled ink circle | `status-done` |
| Čeká na vás | filled coral | `status-you`, `status-you-ink`, `status-you-wash`; only to people who can act |
| Běží | 2 px signal ring | `status-running` |
| Čeká na rozpočet (for others), waiting on the world | filled slate | `status-world`, `status-world-wash` |
| Chyba | filled fault | `status-fault`, `status-fault-wash` |
| Nezačato | 1.5 px strong ring | `border-strong` |
| V platnosti | filled green | `in-force`, `in-force-wash` |

Done is quiet ink, never green. There is no amber anywhere. The only other green is the diff's + (`diff-add*`).

## Type

IBM Plex Sans for the interface, IBM Plex Mono for ids, amounts in tables and formulas, Source Serif 4 for the hero title only. Weights 400, 500 and 600; never 700. Figures are tabular.

- `hero-title` serif 40/46 on top-level pages only (UI-1); `studio-title` 20/26 for the stage title inside a study; `studio-heading` 15/20 for sections; `studio-body` 14/20; `studio-body-compact` 13/18 in tables; `lede` 16/24 muted under a hero, 62ch at most; `studio-caption` 12/16 and `studio-label` 12/16 500; `eyebrow` 12, 600, .06em, uppercase by CSS; `figure` 20/26 to `figure-xl` 44/50, 600; `mono-sm` 12.
- 12 px is the floor.

## Space, radius, depth, motion

- Spacing 4 · 8 · 12 · 16 · 24 · 32 · 48 (`space-1` … `space-12`); 6 only inside controls.
- Radius 0 for tables and the stage navigator; 6 (`radius-control`) for buttons, inputs, segmented controls, chips, tags, notes, toasts and nav items; 8 (`radius-card`) for cards and stage sections; 10 (`radius-panel`) for dialogs, menus, dropdowns, the settings flyout and the Lead's chat cards; 12 (`radius-composer`) for the Lead's composer; round only for things round by nature (avatars, the Lead mark, count badges, the switch).
- Controls 32 px high (small 28); table rows 36 (compact 28); touch targets at least 24 px, 44 on a phone.
- Motion: `duration-confirm` 120 ms for a state change, `duration-panel` 180 ms for panels; the rail's Dock motion as Settings built it. Everything stops under `prefers-reduced-motion`, spinners and orbs included.
- Focus: a 2 px `focus-ring` outline with a 2 px offset, on everything focusable.

## The frame

- **Rail** (DockRail): 64 px graphite icons, 240 px on hover or focus; Klienti, Společenská inteligence, Projektová paměť, Nastavení, then Můj Vedoucí with the researcher's Lead mark.
- **Top bar**: the breadcrumb with "/".
- **Page header**: top-level pages carry the Hero; inside a study the StudyHeader, the StageNavigator, then the artifact header.
- **Study split**: the Lead pane 420 px on the left, the artifact the rest, body up to 1000 px; Settings pages up to 1180 px; Můj Vedoucí 1040 px, centred. Below 1100 px the Lead is a drawer, below 768 a sheet.

## Iconography

Phosphor Regular (`@phosphor-icons/core` 2.1.1, MIT), single ink, `currentColor`: 16 px in text and controls, 14 in small buttons, 20 in tiles. The 93 glyphs of core v3 are in Assets → Icons. The rail keeps its own navigation icons. An icon never stands for a status. Identity: the AIA mark (Assets → Brand) on graphite; each researcher's Lead has its own mark (Assets → LeadMarks), chosen on Můj Vedoucí.

## Where the rest is

- *Co nahrazuje co*: every element of today's product, kept, changed, merged or retired, and what replaces it.
- *Otázky k rozhodnutí*: where the sources disagree, with a recommendation.
- *Návrhy*: proposals from the UX research, marked as proposals. (Added in phase 2.)

## Interakce (v3), in one screen

1. **Ukládání**: Ukládám… → Uloženo (3 s) → Neuloženo – Zkusit znovu. The same everywhere.
2. **Vrátit, nebo potvrdit**: reversible actions act at once with Vrátit (8 s). Irreversible or external ones get ConfirmDialog. Money gets SpendDialog. Unsaved work gets InlineConfirm, where Esc keeps the work.
3. **Peníze**: one SpendDialog with the ceiling, "horní mez, ne odhad", the remainder, and unknown never zero. The amount sits on the button.
4. **Klávesnice**: Ctrl/⌘ K, `?`, G+K/P/N, F2, Enter, Esc from the inside out. In a group, arrows move; Enter or Space chooses when the choice saves.
5. **AI úloha**: připraveno → běží (Zastavit) → čeká na rozpočet → hotovo, návrh čeká → přijato / zahozeno / zastaralé. One card, the same words in the tray, the palette and the bar.
6. **Stavy obsahu**: skeleton, one-sentence empty, "neznámé", a Czech error with Zkusit znovu. Never raw codes, ids or English.
7. **Úpravy na místě**: InlineText and InlineCreateRow. A select never acts. Every ordered list reorders by drag or Alt+↑↓.
8. **Výběr**: checkbox rows, a bulk bar, and a toast with Vrátit after every bulk action.
9. **Pohyb studií**: the forward action focuses the next stage. Opening a stage never writes. The study bar and Přehled studie say what waits.
