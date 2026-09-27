# AIA design system: reference package

This is the AIA Design System (the Claude.ai artifact
<https://claude.ai/artifact/LB7SgQGTiynynHZNEXgqBy>) as plain files that any
tool can read from the repository. Nothing here needs a build step, a
framework or JavaScript. Every page under `reference/` opens directly in a
browser and links only `tokens/tokens.css` and `fonts/fonts.css`.

**This is a reference package, not the implementation.** `apps/web` does not
import it. The web client's token source is `apps/web/src/design/tokens.json`,
which `apps/web/scripts/build-tokens.mjs` turns into its CSS. That file was
ported from this same artifact. Every token both files name has the same
value; the web file adds five (`doc-wash`, `signal-hover`, `signal-edge`,
`signal-tint`, `signal-wash-strong`) and its own type groups, as checked at
`043b0dd`. If the two ever disagree, the web file is what ships and this
package is stale. Update this package from the artifact; never hand-edit
the generated files.

The artifact also rendered twelve screens of the application (Portfolio,
Study overview, Results and others). **Those screens are wrong and are not
part of this package.** Only the system is here: tokens, type, identity,
components and their states, and the rules. See `source/README.md` for what
was left out.

Vocabulary follows `docs/product/README.md`: Organization → Client → Study
(research or simulation, `Study.kind`) → Project → Revision → Stage. The UI is
Czech: *studie*, *projekt*, *revize*, *fáze*.

## Files

| Path | What it is for |
|---|---|
| `README.md` | This index, the brand direction and the colour rules |
| [`status-map.md`](status-map.md) | Every backend status enum value → Czech and English label → mark → colour tokens, derived from `packages/aia_core/src/aia_core/domain/*.py` at `043b0dd`, with the drift since the artifact was built |
| [`tokens/tokens.css`](tokens/tokens.css) | Every token as a CSS custom property: `:root` (light, Paper) and `[data-theme="dark"]` (Graphite); `[data-density="compact"]`; reduced motion; the `.aia-doc` re-scope for the Deliverable. One comment per token states its purpose |
| [`tokens/tokens.json`](tokens/tokens.json) | The same tokens, flat: `name → { light, dark, purpose }`, plus `category`, `alias` (the token a colour follows) and `compact` (density-mode tokens) |
| [`fonts/fonts.css`](fonts/fonts.css) | `@font-face` rules for the ten faces |
| `fonts/*.woff2` | IBM Plex Sans (400, 400 italic, 500, 600), IBM Plex Mono (400, 500), Source Serif 4 (400, 400 italic, 600), Source Serif 4 Display (600). Czech is fully covered |
| [`fonts/LICENSES.md`](fonts/LICENSES.md) | SIL OFL 1.1, provenance and the fontTools coverage check. The three `LICENSE-*` files are the full licence texts |
| `assets/logos/aia-mark.svg` | The mark: a 5 × 5 population lattice where ten points form an A, the apex in `signal`. 20px and up |
| `assets/logos/aia-mark-on-graphite.svg` | The mark on the graphite tile (dark-theme ink and signal) |
| `assets/logos/aia-mark-mono-black.svg`, `aia-mark-mono-white.svg` | The monochrome mark, for one-colour print and embossing |
| `assets/logos/aia-wordmark.svg` | The wordmark: the I is a column of five individuals, the A crossbars are three points. 16px minimum height |
| `assets/logos/aia-wordmark-on-graphite.svg`, `aia-wordmark-mono.svg` | The wordmark on graphite, and monochrome |
| `assets/logos/aia-lockup.svg`, `aia-lockup-mono.svg` | The wordmark + "Agentic AI Analytics" (Plex Sans Medium, outlined), and monochrome. 24px minimum height |
| `assets/favicons/favicon-16.svg`, `favicon-16.png` | 16px: the six-point pyramid with no faint field (the full mark does not survive 16px) |
| `assets/favicons/favicon-32.svg`, `favicon-32.png` | 32px |
| `assets/favicons/apple-touch-icon-180.svg`, `apple-touch-icon-180.png` | 180px (Apple touch icon) |
| `assets/favicons/icon-512.svg`, `icon-512.png` | 512px (PWA / store icon) |
| `assets/favicons/app-icon.svg` | The app icon as drawn in the artifact (the full lattice on graphite). The 32/180/512 SVGs are this drawing at that pixel size; the PNGs are the artifact's own renders |
| `assets/motif/lattice-field.svg`, `lattice-field-on-graphite.svg` | The point-lattice motif: discrete points that resolve into structure. For empty states and section heads, behind copy and never behind data |
| `assets/motif/section-divider.svg` | The lattice as a divider between report sections |
| `assets/motif/report-cover-field.svg` | The report cover field on `doc-paper` |
| `assets/icons/*.svg` | The 32 icons (24-unit grid, 1.5 stroke, square caps, mitred joins), single ink `ink` (light). They are exported from the path data in the artifact's bundle, which is the data its own icon files use |
| [`reference/state-gallery.html`](reference/state-gallery.html) | Every `StageStatus`, `WorkflowRunStatus`, `StepRunStatus`, `ReservationStatus`, `StudyStatus`, `ClientStatus` and `FailureClass` (and `AttemptStatus`, `ProjectStatus`); every evidence role; value, zero, not available, suppressed and loading; the waiting, recovery, denied, empty and loading states, in both themes |
| [`reference/components.html`](reference/components.html) | Every component in every state: button, kbd, input, chip and status glyph, evidence mark and value, table, scope chrome, client accents, stage rail, run timeline, budget meter, impact preview, park-and-ask dialog, provider choice and recovery decision, usage ledger, approval object, revision banner and history, headline answer and graded bars, identity and icons, the report page. Both themes |
| [`reference/type-and-color.html`](reference/type-and-color.html) | The type scale with Czech samples, every colour swatch with its contrast ratio, every text/ground pairing the system relies on (WCAG ratios, both themes), and the data-viz palette in colour and greyscale |
| [`source/README.md`](source/README.md) | What `source/artifact/` holds and what was deliberately left out |
| `source/artifact/project/` | The artifact's content, byte for byte except one word the exposure check refuses (`source/README.md`): brand book, nine guideline chapters, `tokens.json`, the React 18 component bundle (`bundle.js`, `bundle.css`, `index.d.ts`), 30 component READMEs and previews, the asset groups. Reference only |

### Using the reference markup

The class structure in `reference/*.html` is the canonical structure for each
component: it is the markup the artifact's React bundle renders, with its
inline styles turned into token-only classes. Each page carries that
stylesheet in one `<style>` block; the part headed "the reference pages' own
layout" is page chrome, not the system. The classes `is-hover` and `is-focus`
only show those states without a pointer; real markup uses `:hover` and
`:focus-visible`. There are no hex values in the pages. Every colour is a
`var(--…)` from `tokens/tokens.css`.

Themes: set `data-theme="dark"` on any element (usually `<html>`) to switch its
subtree; light is the default. Density: set `data-density="compact"` for the
respondent explorer, usage ledger and run log.

## Brand direction

AIA is a precision instrument for producing defensible knowledge. Its interface
must never make anything look more certain, more finished or more measured
than it is. Five expert researchers work in it eight hours a day; clients only
ever see the report.

The direction is **A: Instrument**. The base is graphite and paper, with one
cold, calibrated accent: `signal`, a blue with a cyan lean. One warm
counterpart, `status-you` (amber), is reserved for *waiting on a person*. The
system has two registers on one token set:

- **Studio**, the working surface. Dense, tabular and keyboard-driven.
  `light` (Paper) and `dark` (Graphite) are equal themes.
- **Deliverable**, the report. Serif, generous and print-first. It is always
  paper: inside `.aia-doc` the Studio tokens are re-scoped to `doc-paper`,
  `doc-ink`, `doc-muted` and `doc-rule`, so a report looks the same in a dark
  Studio as on a printed page.

Type is IBM Plex Sans for the UI, IBM Plex Mono for identifiers (with a
slashed zero) and Source Serif 4 for the Deliverable (Source Serif 4 Display
for covers). Space uses a 4px base. The radii are 0 for tables, rails and
figures, 2px for controls and chips, and 4px for panels and dialogs, and
nothing is rounder. There is one shadow, `shadow-overlay`, used only on
dialogs. Motion only confirms a change that has already happened: there are
no spinners, shimmer, skeletons or percentage bars.

### Rationale

- **It gives the refusals a vocabulary.** An instrument panel already has a
  grammar for "live", "held", "fault" and "needs an operator". AIA's parked
  states map onto it directly. A dashboard grammar would turn them all into a
  "pending" grey and lose the difference.
- **It keeps colour available for meaning.** On a near-achromatic base, every
  remaining hue carries information: signal, amber, fault red and the data
  palette. Each decorative hue added would make amber less loud.
- **It holds density.** Plex Sans has tabular figures by default, a large
  x-height, and unambiguous 1/l/I and 0/O at 13px, including with Czech
  diacritics.
- **It is honest about the product.** A lattice of points is literally what
  the synthetic population is. It needs no metaphor, no "AI" imagery and no
  national symbolism.

Direction B (Editorial: warm paper, serif headings) was stronger for the
report and weaker for dense tables, where serif figures lose their rhythm and
warm paper narrows the gap between amber and the ground. So B's typography is
the Deliverable register. Direction C (the lattice as texture everywhere) was
not pursued, because a field of dots behind a table is noise on the pixels a
conclusion rests on.

**The accepted cost.** The system optimises for five experts over eight-hour
days, and for epistemic honesty over visual reassurance. It looks denser and
more sober than a product built to impress a first-time visitor. Some states
are deliberately loud: a row parked on you is solid amber, *chybí* is drawn
heavier than a number, and the holdout statement is a boxed paragraph, not a
footnote. The full argument is in
`source/artifact/project/guidelines/01-direction.md`.

## The four colour families

Colour comes in four families that **never mix**. A token from one family is
never used for another family's job.

| Family | Tokens | Only for |
|---|---|---|
| **Semantic UI** | `surface`, `surface-raised`, `surface-sunken`, `surface-overlay`, `surface-inverse`, `border`, `border-strong`, `ink`, `ink-muted`, `ink-faint`, `ink-inverse`, `signal`, `signal-wash`, `on-signal`, `focus-ring`, `selection` | Structure, text, selection, focus |
| **Status** | `status-running`, `status-you`, `status-world`, `status-fault`, `status-recovery`, `status-done`, `status-inert`, with their `-wash`, `-ink`, `-hatch` and `on-status-*` companions | The state of a stage, run, step or reservation. Nothing else |
| **Data viz** | `viz-cat-1…6`, `viz-seq-1…7`, `viz-div-1…7`, `viz-grid`, `viz-axis` | Inside a plot area, and nowhere else |
| **Client accent** | `client-1…6`, `on-client` (and `scope-above` for surfaces that span clients) | The scope band and the client monogram, and nothing else |

**Semantic UI**

- Set text in `ink` on `surface`, `surface-raised` or `surface-sunken`
  (≥ 7:1 in both themes). Secondary text uses `ink-muted` and tertiary
  `ink-faint`, both ≥ 4.5:1. Nothing is set below 12px.
- Use `signal` sparingly: selection, links, the primary action, focus, and
  the live edge of a running process. It is never decoration and never a
  warning.
- `border` is a decorative hairline. A control's edge is `border-strong`
  (≥ 3:1).
- Focus is a 2px `focus-ring` outline with a 2px `surface` gap on every
  interactive element, so the ring always sits on a known ground.

**Status** (the full mapping is in [`status-map.md`](status-map.md))

- Shape carries the state and colour only reinforces it. Machine states are
  circles. Parked states are squares: solid means it is on you, hollow means
  it is on the world. Recovery is a diamond, and inert states are dashed.
- `status-you` (amber) is **reserved** for "parked, waiting on a person":
  `AWAITING_*`, `WAITING_USER`, `WAITING_CREDITS`. Nothing else in the product
  may be amber: no warnings, no highlights, no chart series. That reservation
  is what makes it readable across a room.
- `status-world` (slate) is for a system owing capacity: `WAITING_PROVIDER`,
  `WAITING_CAPACITY`, a quota or a missing runtime. It has the same parked
  shape as `you`, but hollow and dashed.
- The status family has no green. Done is plain `ink` with a check, quiet on
  purpose.
- An unknown value renders as "Neznámý stav: X" in the fault tone, never as a
  neutral default.
- Evidence grades, null states and the budget meter's hatches are
  achromatic (`evidence-mark`, `null-mark`, `suppressed-fill`, `budget-*`).
  They must survive greyscale print, so form carries them, not hue.

**Data viz**

- Categorical slots have a fixed order and are never cycled. A seventh series
  folds into "Ostatní" or small multiples.
- Several light-theme categorical colours are below 3:1 on the ground
  (`viz-cat-2`, `-3`, `-6`). Every chart therefore carries direct labels or a
  table view (the relief rule), and text stays in text tokens, never in the
  series colour.
- `viz-seq-*` is a one-hue ramp, and dark flips its anchor so step 1 recedes.
  `viz-div-*` has a neutral grey midpoint, never a hue.
- Series identity never rests on hue alone. `reference/type-and-color.html`
  shows the palettes in greyscale.

**Client accent**

- Six low-chroma accents are spread in hue and lightness. They avoid the amber
  band (55–100°) and the signal/slate band (228–262°), and keep ≥ 7.6 ΔE (OKLab
  × 100) from every status, UI and categorical token. These are the artifact's
  own measurements (`guidelines/04-scope-and-money.md`); this package did not
  re-measure them.
- They are used only in the 4px scope band and the two-letter monogram, with
  `on-client` letters (≥ 4.5:1 on all six in both themes). They never appear
  in a plot and never in a status.
- The accent is a **second channel**. The client name and monogram are always
  present and are the primary identification. Assign a persisted slot,
  least-used first, when the client is created, and never change it. A hash
  of the client id collides at five clients. The hash is only a fallback.
- Surfaces that span clients (Portfolio, Admin) use a hatched `scope-above`
  ink band instead: you are above the client boundary.

## Known gaps

- **`FailureClass.RUNTIME_UNAVAILABLE`** is newer than the artifact. This
  package maps it to the `world` tone ("Chybí běhové prostředí"). That is a
  choice for the design owner to confirm (`status-map.md`, *Drift since the
  artifact*).
- **Inputs** have token rules in the artifact but no component in its
  bundle. `reference/components.html` builds them from those rules
  (`surface-sunken`, `border-strong`, `control-*`), and the page says so.
- **Evidence roles** are an open set. The domain does not publish the enum
  yet, so any unknown role renders as "?".
- **Provider vocabulary.** The artifact's provider choice and copy name the
  `Provider` values in `domain/providers.py`: `claude_code_subscription`,
  `anthropic` and `openai`. The develop runtime now routes through Bedrock, and
  removing the old Claude Code/direct-API controls is in progress
  (`.planning/PROGRESS.md`). Treat the provider names in the reference as
  placeholders.
- `ImpactPreview` has no cost or time estimate from the domain yet, so both
  read *chybí* (`packages/aia_core/src/aia_core/domain/pipeline.py:423` @ `043b0dd`).
