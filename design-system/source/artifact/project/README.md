AIA is a precision instrument for producing defensible knowledge. Its interface must never make anything look more certain, more finished or more measured than it is. Five expert researchers live in it eight hours a day; clients only ever see the report. Every rule below follows from that.

The system has two registers on one token set:

- **Studio** — the working surface. Dense, tabular, keyboard-driven; `light` (Paper) and `dark` (Graphite) are equal themes.
- **Deliverable** — the report. Serif, generous, print-first. It is always paper: inside `.aia-doc` the Studio tokens are re-scoped to `doc-paper`, `doc-ink`, `doc-muted` and `doc-rule`, so a report looks the same in a dark Studio as on a printed page.

## Content fundamentals

- Write the UI in Czech. Copy lives in `src/i18n/cs.ts` (`AIA.cs` in the bundle); components never hardcode text.
- Use sentence case everywhere. Never use all caps for labels: caps squash Czech diacritics (Ř, Č, Ů).
- Address the researcher as *vy*. Say what is needed, from whom and since when: "Čeká na vás 2 d 4 h. Schválit výdaj 4 900 USD." — never "Pozor!" and never an exclamation mark.
- Name the thing and its state, not the feeling: "Selhalo · neplatná struktura výstupu", not "Něco se pokazilo".
- Say what you do not know. "Odhad zatím backend neposkytuje" beats a plausible number. A modelled claim says *modelováno* in the sentence, not only in a footnote.
- The AI is an assistant that picks tools and writes prose. Label its suggestions "Návrh asistenta · <model role> · neschváleno". It never computes figures, and no copy may suggest it does.
- No emoji, no sparkles, no wands, no "magic". The words AI, chytrý and inteligentní are never used as adjectives for a result.
- Numbers use Czech formatting with a unit every time: `12 480,50 USD`, `41,7 %`, `n = 1 204`. A bare number whose unit you must guess is a defect.

## Visual foundations

**Colour comes in four families that never mix.**

| Family | Tokens | Only for |
|---|---|---|
| Semantic UI | `surface`, `surface-raised`, `surface-sunken`, `surface-overlay`, `border`, `border-strong`, `ink`, `ink-muted`, `ink-faint`, `signal`, `signal-wash` | Structure, text, selection, focus |
| Status | `status-running`, `status-you`, `status-world`, `status-fault`, `status-recovery`, `status-done`, `status-inert` (+ `-wash`, `on-`, `-ink`) | The state of a stage, run, step or reservation |
| Data viz | `viz-cat-1…6`, `viz-seq-1…7`, `viz-div-1…7`, `viz-grid`, `viz-axis` | Inside a plot area and nowhere else |
| Client accent | `client-1…6`, `on-client` | The scope band and the client monogram, and nothing else |

- Set text in `ink` on `surface`, `surface-raised` or `surface-sunken` (≥ 7:1 in both themes). Secondary text uses `ink-muted`, tertiary `ink-faint` (both ≥ 4.5:1). Nothing is set below 12px.
- Use `signal` sparingly: selection, links, the primary action, focus and the live edge of a running process. It is never decoration and never a warning.
- `status-you` (amber) is **reserved** for "parked, waiting on a person". Nothing else in the product may be amber: no warnings, no highlights, no chart series. That reservation is what makes it readable across a room.
- The status family has no green. Done is plain `ink` with a check. Success is quiet on purpose.
- Evidence grades, null states and the budget meter's hatches are achromatic (`evidence-mark`, `null-mark`, `suppressed-fill`). They must survive greyscale print, so they are carried by form.

**Type.** IBM Plex Sans for the UI, IBM Plex Mono for identifiers, Source Serif 4 (and Source Serif 4 Display for covers) for the Deliverable. All ship as real woff2 files, cover Latin Extended-A, and are under the SIL Open Font License 1.1.

- Plex Sans figures are tabular by default (every digit is 600 units), so columns align without a feature flag. Keep `font-variant-numeric: tabular-nums` anyway, so a fallback face aligns too.
- Set compared numbers in `num`, the headline figure in `num-hero`, and fingerprints and run ids in `mono` with the slashed zero on.
- Report prose is `doc-body` (15/24, prints at 10.5pt), chapters `doc-h1`, captions `doc-caption`. Every caption names n and the evidence grade.

**Space and shape.** Use a 4px base (`space-1` to `space-12`). Radii are `radius-0` for tables, rails and figures, `radius-sm` (2px) for controls and chips, and `radius-md` (4px) for panels and dialogs. Nothing is rounder. Separate things with `border`; the only shadow is `shadow-overlay`, on dialogs.

**Density.** Compact (`row-compact` 28px, `control-compact` 24px) for the respondent explorer, the usage ledger and the run log. Comfortable (`row-comfortable` 36px) for Portfolio, Admin and prose. Never go below the 24px target size.

**Motion.** `duration-confirm` (120ms) confirms a transition that has already happened; `duration-panel` (180ms) opens panels. Motion never anticipates. There are no spinners, shimmers or percentage bars: a running process shows real elapsed time, a heartbeat, the current step and real counts. Under `prefers-reduced-motion` everything uses `duration-instant`.

**Focus.** A 2px solid `focus-ring` outline with a 2px `surface` gap, on every interactive element in both themes. The gap means the ring always sits on a known ground, so it keeps 3:1 even on an amber fill.

## The signature systems

1. **Status.** Every status has a shape, a label and a tone. Machine states are circles; parked states are squares with pause bars (solid = on you, hollow = on the world); recovery is a diamond; inert states are dashed. `StatusChip` maps every domain enum in full. A value it does not know renders as "Neznámý stav: X" in the fault tone, never as a neutral default.
2. **Evidence grade.** ■ measured, ▣ calibrated core, □ modelled (plus a dotted underline), ⬚ holdout pending (plus the "neval." tag), and a bold **?** for an unknown role. It is one grammar for a number, a cell, a series, a map node and a sentence. See *Evidence and null states*.
3. **Null is not zero.** Value, zero, *chybí* (not available), *potlačeno* (suppressed) and loading look different. *Chybí* is drawn in full ink with a hatch, so it is never softer than a bad value.
4. **Scope chrome.** `ScopeBar` sits above every screen: a 4px client-accent band, the client monogram, client / study, study status, revision and your role. Screens that span clients get a hatched ink band and read "Napříč klienty". Delivered and archived studies carry a "Pouze ke čtení" plate.
5. **Consequences before commits.** `ImpactPreview` shows which stages survive and which reopen, how many artifacts are kept, and the cost and time estimates. When the server gives no estimate, it says *chybí*.
6. **Money.** `BudgetMeter` shows spent, uncertain (`SETTLED_UNCERTAIN`), reserved and remaining separately. `ParkAndAsk` has no cheerful default. The ledger is immutable and attributable.

## Iconography

- Use one set: 24-unit grid, 1.5 stroke, square caps, mitred joins, drawn for this system (`assets/Icons/`, `AIA.Icon`). In the bundle icons inherit `currentColor`; the SVG files are single-ink `#151a20` (`ink`, light theme).
- There are icons for the AIA concepts: `stage`, `revision`, `fingerprint` (a hash sign — it *is* a hash), `artifact`, `gate`, `reservation`, `evidence`, `parked`, `waiting`, `recovery`, `ledger`, `budget`, `provider`, `population`.
- Status glyphs (`StatusGlyph`) are a separate 16-unit set. Never use a status glyph as decoration, and never use an icon to mean a status.
- No emoji anywhere, including in copy, commit messages and exported reports.

## Identity

- The motif is the synthetic population: discrete points that resolve into structure from a distance. The mark is a 5 × 5 lattice where ten points form an A and one — the apex — is `signal`: the calibrated measurement. The wordmark builds the I from a column of five individuals and the A crossbars from three points.
- Use `aia-mark` at 20px and up. Below 20px use `favicon-16`, the six-point pyramid with no faint field.
- Keep clear space of one lattice pitch (a sixth of the mark's width) on all sides. The wordmark's minimum height is 16px; the lockup's is 24px.
- On graphite use the `-on-graphite` files. For one-colour print use the `-mono` files. Never recolour the apex dot to anything but `signal` or the mono ink.
- Never use Czech national iconography (flags, lions, skylines), gradients, glows or northern-lights effects.

## Keyboard

`⌘K` opens the command palette and `?` lists shortcuts. `g p` goes to Portfolio and `g s` to the study. `[` and `]` step between stages, `j` / `k` move between rows, `Enter` opens a row, and `e` edits (it always opens the impact preview first). `a` approves, and exists only for someone who holds the permission. `Esc` closes. Focus order: skip link → scope bar → stage rail → main → side panel. Skip targets are "Přeskočit na obsah" and "Přeskočit na fáze".


---

## Consuming this system (generated — do not edit)

Every path named below is under `project/` in this design system: read `project/api/tokens.md`, not `api/tokens.md`.

If the text above differs on what to load or read, follow this section.

`components/bundle.js` defines `window.AIA` (30 components); `components/bundle.css` is its stylesheet; `tokens.css` is every token as a CSS variable plus `@font-face` for the fonts. `components/bundle.css` reads its variables from `tokens.css`. The bundle needs react 18 (not packed in this system: bring your own copy) (`window.React`), react-dom 18 (not packed in this system: bring your own copy) (`window.ReactDOM`), loaded before it. Build any UI by mounting these components; never hand-build a control or draw an icon the system provides.

- **Standalone page:** inline `tokens.css` and `components/bundle.css` in a `<style>`, then the library files and `components/bundle.js` as classic scripts (a file containing `</style`, `</script` or `<!--` breaks an inline element: write the sequence `<\/style`, `<\/script` or `\x3C!--` in your copy, or load that file by URL).
- **Design canvas:** bring `components/bundle.css`, `components/bundle.js` and `components/index.d.ts` (for the editor’s props panel) onto the canvas in full, as the canvas type’s design-system components reference says (a server-side copy first where it offers one); load the stylesheet before the script; skip the library files (the artboard supplies React); mount with `<x-import component-from-global-scope="AIA.<Comp>" …>`.
- **Slides deck, or any surface that cannot run the bundle:** tokens only — the values are on `api/tokens.md`; the deck takes `tokens.json` by file path for its colour pickers.

Fonts: one file per family is enough (below: the upright face nearest regular weight; bold and italic synthesize). Fetch it as the fetch column says (Artifact tool `read`, that id or path as `path`) and upload it as an asset where you use it (`publish`, `file_path`, `asset:true`) — HTML/CSS: an `@font-face { font-family: "<family>"; src: url(<uploaded>) }` rule; a Slides deck: write `fonts/<id>` = `{"family":"<family>","src":"<the url the upload returned>"}`.

| family | file | fetch | CSS | Slides `fonts/<id>` |
| --- | --- | --- | --- | --- |
| IBM Plex Sans | `fonts/IBMPlexSans-Regular.woff2` (weight 400) | `read` the file with `project/` in front | `var(--font-sans)` | `ibm-plex-sans` |
| IBM Plex Mono | `fonts/IBMPlexMono-Regular.woff2` (weight 400) | `read` the file with `project/` in front | `var(--font-mono)` | `ibm-plex-mono` |
| Source Serif 4 | `fonts/SourceSerif4-Regular.woff2` (weight 400) | `read` the file with `project/` in front | `var(--font-serif)` | `source-serif-4` |
| Source Serif 4 Display | `fonts/SourceSerif4Display-Semibold.woff2` (weight 600) | `read` the file with `project/` in front | `var(--font-display)` | `source-serif-4-display` |

**Read, per thing:** a component’s props, parts and examples: `api/components/<Comp>.md`; token values: `api/tokens.md`; stored assets and their paths: `api/assets/<Group>.md`. After this README, fetch the cards and fonts you need in ONE message as parallel calls — none depends on another.

**Two rules.** Before you use a thing — a component, a token group, an icon, an asset — read its card from the index below; a value you did not read from a card is a guess. `tokens.json`, `manifest.json`, `components/index.d.ts` and `design-system.json` are sources for tools: hand them over. `components/<Comp>/README.md` and `assets/<Group>/README.md` are the long-form second read a card links to; `SKILL.md` and `artifact-type/` beside them are authoring guidance, not needed to consume the system.

## Index (generated — do not edit)

**Tokens**

- `api/tokens.md` — Every token: surface, text, fill, border, palette, type, spacing, radius, shadow, stroke, density, duration, z-index. (19.1k)

**Icons and assets**

- `api/assets/Logos.md` — 9 files, by asset id. (2.2k)
- `api/assets/Icons.md` — 32 files, by asset id. (3.7k)
- `api/assets/Motif.md` — 4 files, by asset id. (1.4k)
- `api/assets/Favicons.md` — 6 files, by asset id. (1.5k)
- `api/assets/Accessibility.md` — 5 files, by asset id. (1.5k)

**Components** (`api/components/<Comp>.md`, 42; 12 of them showcase pages)

- **Status**: `StatusChip` — Renders any domain status as a glyph plus a label in its tone · `StatusGlyph` — The 16-unit status glyph set: shape carries the state
- **Evidence**: `EvidenceMark` — The epistemic grade mark: ■ measured, ▣ calibrated, □ modelled, ⬚ holdout pending, ? unknown · `Value` — The one way a figure is rendered: value, zero, chybí, potlačeno or loading, with an optional evidence grade · `EvidenceLegend` — The persistent legend for the five evidence grades
- **Money**: `Money` — A monetary amount with its currency, in Czech formatting · `BudgetMeter` — A study budget: spent, uncertain (SETTLED_UNCERTAIN), reserved and remaining, each with an exact amount · `ParkAndAsk` — The spending-authorisation dialog when work parks on budget · `ProviderChoice` — An explicit choice when a provider cannot serve: wait (free) or switch (paid, changes provenance) · `RecoveryDecision` — RECOVERY_REQUIRED: a metered call may have been billed with an unknown outcome · `UsageLedger` — The immutable AI usage ledger: dense, sortable, attributable
- **Actions**: `Button` — Action buttons: primary (signal), secondary (bordered), quiet, danger; comfortable or compact · `Kbd` — A keyboard shortcut hint
- **Identity**: `Icon` — The AIA icon set: 24 grid, 1.5 stroke, square caps · `Mark` — The AIA mark: a 5 × 5 population lattice resolving into A, the apex in signal · `Wordmark` — The AIA wordmark: the I is a column of five individuals · `Lattice` — The motif as a deterministic dot field, for empty states and dividers
- **Scope**: `ScopeBar` — Persistent scope chrome: client accent band, monogram, client / study, study status, revision and role · `ClientMonogram` — A client's two-letter monogram on its accent
- **Lifecycle**: `StageRail` — The thirteen-stage lifecycle rail and a project's primary navigation · `RunTimeline` — Honest progress: real elapsed time, heartbeat, real counts, the current step and what it waits on · `ImpactPreview` — Shows an edit's consequences before it is committed: kept vs reopened stages, artifacts kept, cost and time · `RevisionBanner` — Marks that you are looking at a superseded revision · `RevisionHistory` — Immutable revision list with what each change reopened
- **Review**: `ApprovalPanel` — Gate approval and sign-off, including the separation-of-duties refusal
- **Results**: `HeadlineAnswer` — The single sentence a client pays for, with its grade, n and interval, and the findings one level down · `GradedBars` — A bar chart whose bars carry their evidence grade, with direct labels · `Sociomap` — Respondent and object maps over immutable originals; view overrides and what-if are visible layers
- **Deliverable**: `ReportCover` — The Deliverable cover · `ReportPage` — A Deliverable page: chapter, headline paragraph, holdout statement, evidence margin, figure, table and footnotes
- **Screens**: `Admin` (showcase page) — Admin · `CostBudget` (showcase page) — CostBudget · `DataLibrary` (showcase page) — DataLibrary · `DirectionB` (showcase page) — DirectionB · `Portfolio` (showcase page) — Portfolio · `ReportDelivery` (showcase page) — ReportDelivery · `ResearchStage` (showcase page) — ResearchStage · `Results` (showcase page) — Results · `SimulationStudio` (showcase page) — SimulationStudio · `SociomapaPage` (showcase page) — SociomapaPage · `StateGallery` (showcase page) — StateGallery · `StudyOverview` (showcase page) — StudyOverview
