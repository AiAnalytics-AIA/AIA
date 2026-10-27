# AIA Design System v3.2: export of 27 Oct 2026

The AIA Design System artifact as it stands, exported so another account can use it without access to the live
artifact. It is a design reference, not product code: nothing in `apps/web` imports it, and every client, study,
person and number in it is fictional.

| | |
|---|---|
| Live artifact (private to the owner's account) | <https://claude.ai/artifact/SEEkz1TrFgEZ1yK53Qmas4> |
| Exported version | v11, artifact version id `1793098287-902c`, 27 Oct 2026 |
| Product code it matches | draft PRs #1022 (`feature/ux-upgrade`: Petrol, the AI spark edge, the command palette, one way to save, undo, pay and fail) and #1030 (`feature/ux-shared-components`: StatusPill, Value, StaleMark, AiJobCard, ItemReview) |

## How to open it

Open [`index.html`](index.html) in a browser. It shows every component's preview on one page, grouped as in the
artifact, with a light/dark switch. It loads only files in this folder:
- `tokens.css`: generated from `tokens.json`, with the fonts' `@font-face`;
- `bundle.css`: the components' stylesheet.

| Path | What |
|---|---|
| `index.html` | Every component preview on one page |
| `components/<Name>/preview.html` | A component's preview, as the artifact shows it (a fragment: it needs `tokens.css` and `bundle.css`, as `index.html` loads them) |
| `components/<Name>/README.md` | A component's rules: anatomy, states, behaviour, what it replaces in `apps/web` with `file:line` |
| `tokens.json`, `tokens.css` | The tokens: Petrol colours in light and dark, type, spacing, radii, motion |
| `bundle.css` | The components' stylesheet: core v4.1 plus the AI layer of core v4.2 |
| `aia-core-v4.2.css` | The shared stylesheet the three prototype canvases (Klienti, Výzkumné kroky, Nastavení) load since 27 Oct |
| `docs/brand-book.md` | The artifact's README: foundations, colour and status rules, type, the Interakce catalogue's summary |
| `docs/co-nahrazuje-co.md` | Every old form in `apps/web` and what replaces it |
| `docs/otazky-k-rozhodnuti.md` | D1–D15, the questions only the owner decides, each with a recommendation |
| `docs/design-system.json` | The artifact's index (asset groups, last change) |
| `assets/Icons`, `assets/LeadMarks`, `assets/Brand` | The SVGs the artifact keeps as uploads: 93 Phosphor icons, the five Lead marks, the AIA mark and the lattice field |
| `fonts/` | IBM Plex Sans and Mono, Source Serif 4 and its Display cut (OFL) |

## The boards (48 cards)

- **Úvod:** Cover.
- **Základ:** Icon, Thinking.
- **Rám:** ActivityTray, Breadcrumb, DockRail, Hero, StageNavigator, StudyBar, StudyHeader, StudyOverview.
- **Vstupy:** FilterBar, InlineEdit, Segmented, Select, Stepper, Switch, Tabs, TextField.
- **Akce:** AiSpark, Button.
- **Stav:** Chip, StatusGlyph.
- **Zobrazení:** Card, Diff, EmptyState, KeyValue, KpiTile, Note, Table.
- **Překryvy:** CommandPalette, Dialog, SpendDialog, Toast.
- **Vedoucí:** AgentStatus, ChangeReview, LeadCard, LeadChat, LeadMark.
- **Interakce:** the nine behaviour rules:
  - I-Ukladani (saving shown one way, "Uloženo" 3 s);
  - I-VratitNeboPotvrdit (Vrátit 8 s, or a confirm only when it cannot be undone);
  - I-Penize (SpendDialog, the amount on the button, "horní mez, ne odhad");
  - I-Klavesnice (Ctrl/⌘ K, one Escape order);
  - I-AIUloha (one AI job's life);
  - I-StavyObsahu (loading, empty, error, unknown);
  - I-UpravyNaMiste (editing in place);
  - I-Vyber (selection);
  - I-Navigace (moving through a study).

## Decided

- **Palette: Petrol** (the owner's choice of three). Neutral greys; signal `#0f6577` on small marks only; "potřebuje vás" coral `#ff9050`; done in ink; green only for the version in force. 0 contrast failures in `check-design`.
- **AI has no colour of its own.** The owner disliked the lilac. AI is graphite and a cool neutral, marked by the spark edge: a 1 px conic gradient, cyan `#1c9fc4` → sky `#3a6fd8` → an ice glint (dark `#6ac5e8` / `#86aef5` / `#dff5ff`). It turns on hover and focus of an AI action and while a model works, and stays still under reduced motion (card AiSpark).
- **Each thing is said once on a screen**, and every interaction above is one shared component, not one per page (the owner: "everything has its place").
- **Phosphor icons only**, Regular weight.
- **Desktop first:** the smallest laptop in use is a 1280 px Dell XPS 13.
- **InlineEdit** works as `ui/InlineText.tsx` does: a click, Enter or F2 opens; Enter or blur saves, then "Uloženo" for 3 s; Esc restores; a refusal stays at the field. Fixed in v10; the earlier preview was static.

## Still open

- **D1–D15** in [`docs/otazky-k-rozhodnuti.md`](docs/otazky-k-rozhodnuti.md), each with a recommendation. The ones with the widest reach:
  - D2: input height 32/13 or 36/14;
  - D3: retiring the old `/studies` pages;
  - D5: the "čeká na vás" glyph as a circle;
  - D6: the budget wait in coral or slate by who can lift it.
- **Timing of the product PRs.** Whether #1022 and #1030 land now or after the client pages redesign (`client-pages-redesign#CPR21`) is on the owner's list.
- **Designed but not built in `apps/web`:** the activity tray, the study bar, Přehled studie, filter tokens, peek, and per-item accept of an agent job's proposal (the accept route takes no items; WCE8b).
- **The cover still says "v2".** The artifact's Cover card was not retitled; this folder is v3.2.
