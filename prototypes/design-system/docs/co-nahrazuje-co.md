# Co nahrazuje co

Every visual element of the product at develop `a1a9a45c`, classed against the approved look. A form is retired; its function always keeps a home, named in the last column. Counts are importers (non-test files) / JSX call sites, measured with a script; anchors are `path:line @ a1a9a45c` under `apps/web/src/`.

**Totals over 107 component and variant rows: keep 57 · change 20 · merge 22 · retire 8.** 17 clusters of duplicates.

## Retire (the form goes; the function moves)

| Element | Anchor | Use | Why | Its function's new home |
|---|---|---|---|---|
| `live/` LiveShell, Panel, Button, Status, ErrorNote, Loading | `components/live/LiveShell.tsx:16`, `live/ui.tsx:9,21,67,76,98` | 3 pages (`/studies`) | raw zinc/amber/emerald/red, no tokens, no rail | AppShell + DockRail; Card; Button; StatusGlyph pill; Note `bad`/`you`; Loaded (see D3) |
| WellItem | `rehome/ui.tsx:94` | 0 | unused | none needed (no caller) |
| `.typing` dots | `workbench.css:528`, `LeadPane.tsx:505` | 1 | LOOK: the real orb | Thinking (ActivityOrb) |
| unused `workbench.css` classes | `workbench.css` | 139 of 352 classes | leftovers of the research-lead-v2 prototype | none (no caller) |
| colour tokens with no reader | `signal-wash-strong`, `on-status-recovery`, `status-recovery-hatch`, `null-mark`, `suppressed-fill`, `budget-uncertain`, `scope-above`, `selection` | 0 in web and report | unused | — (`selection` → `signal-wash`) |
| scope-bar tokens | `z-scope`, `stroke-scope` | 0 | the scope bar is gone | — |
| unicode and emoji as icons | 41 places (ⓘ ▸ ▾ ⚠ ✎ ▶ ◐ ✓ ▪ ✕ ↗ ← →), 👤︎ `ResearcherSpendCard.tsx:118` | 41 | "not a single emoji" | Icon (Phosphor) or StatusGlyph |
| `design-system/` package | repo root | reference only | 17 colours stale (old blue `#006b9f`, warm paper, amber you), radii 2/4, status map with squares and amber; its header claims parity, which is false | this system (see D1) |

## Merge (two forms doing one job)

| Cluster | Members | Into |
|---|---|---|
| Buttons | `rehome/ui.tsx:34` Button (49 / 204), `:57` AiButton (10 / 14), workbench `.btn--*` (27 lines), hand-made danger ×3, 171 hand-rolled `<button>` in 45 files | Button (`primary`, secondary, `quiet`, `danger`, `ai` with amount, `sm`) |
| Status marks | `workbench/Glyph.tsx:14` (4 / 29), rehome Chip's icon glyphs, `LeadCards.tsx:30` Pill, workbench `.statepill`, `StageTrack.tsx:31-51`, `live` Status, `StudiesPanel.tsx:39` unicode, `run-state.ts` tones | StatusGlyph + status pill |
| Chips | workbench `.chip` (r11), `MethodologyRegister.tsx:13` RegisterChip, `KnowledgeLibrary.tsx:70` LabelChip, ChipInput chips, 3 local "V AIA zatím není" | Chip |
| Notes | 244 hand-rolled boxes, `states.tsx:29` failed box, `useAiStep.tsx:156` AiFailureCard, `useAnalysis.tsx:118` AnalysisFailureCard, workbench `.notice` | Note |
| Cards | `states.tsx:13` CARD + 5 private copies, SampleView `Sec`, 65 hand-rolled | Card / StageSection |
| Confirmations | AskDialog confirm and prompt (`rehome/ui.tsx:155,173`), InlineConfirm (`step.tsx:342`), ConfirmDialog, 6 `<dialog>` frames | Dialog (ConfirmDialog with an optional field) |
| Money | `withBudget` + AskDialog text (≥ 10 call sites, e.g. `ExecutionSteps.tsx:767,1177,1250`), unused `ui/SpendDialog.tsx:60` | SpendDialog |
| Toasts | `rehome/ui.tsx:286` Toast, `ui/UndoToast.tsx` | Toast (UndoToast without undo) |
| Option menus | ChoiceChips default look for single choice, `step.tsx:217` Segmented, workbench `.seg`, 9 pill rows | Segmented |
| Tabs | three looks | Tabs |
| Switches | `ui/Switch.tsx`, `step.tsx:194`, `ProfileArea.tsx:306` | Switch |
| Empty states | `states.tsx:44` Empty (15 / 23), workbench `.empty`, 24 hand-rolled | EmptyState |
| Eyebrows | `states.tsx:14` EYEBROW, `AudienceStep.tsx:94`, `AppShell.tsx:183`, 2 more | the `eyebrow` style |
| Icon wrappers | `rehome/icons.tsx`, `workbench/Icons.tsx:34`, `components/icons/PhosphorIcon.tsx` | Icon (one name map) |
| Focus ring | the same string declared 11 times; `ui/parts.tsx:44` FOCUS | FOCUS everywhere; 3 deviations (`workbench.css:636`, `object-map-windows.css:123`, the split handle) to it |

## Change (keep the element, fix the form)

| Element | Anchor | Change |
|---|---|---|
| Button sizes | `rehome/ui.tsx:38` | 36/14 → 32/13 (small 28/12) |
| TextInput, TextArea, Select | `rehome/ui.tsx:134,139,143` | 32/13; Select becomes a button + list |
| InlineText | `ui/InlineText.tsx:21` | an always-visible dashed mark at rest |
| Stepper value | `ui/Stepper.tsx:17` | mono 12, 72 px |
| ActionDock | `rehome/step.tsx:120` | an action bar on `surface`, not a card |
| Loaded failed state | `states.tsx:29` | → Note `bad` |
| PageError actions | `errors/PageError.tsx:12` | retry as Button `primary`, home as `quiet` |
| Hero sizes | `aia/Hero.tsx:63-75` | read the new type tokens |
| Headers inside a study | `ResearchStudy.tsx:26`, `SimulationFrame.tsx:25`, `MemoryStudy.tsx:46` | the compact header, not 28/36 |
| Stage title | `workbench.css:289` (16/20), `AppShell.tsx:184` (22/28) | 20/26 |
| Run state tones | `lib/run-state.ts:31`, `lib/lead-cards.ts:220`, `research/lane.ts:160` | budget waits slate for those who can't lift, coral only for those who can; a budget wait never reads Nezačato |
| Reduced motion | `globals.css` | a global rule; `animate-spin` ×3, FrontDoor's transitions, the `just` highlight stop |
| Sociomapa panel CSS | `object-map-windows.css` (31 hex, 27 rgba, `#ffd27a` warning, teal pressed state) | tokens; pressed = `signal`; the quality warning not amber |
| Icon sizes | ~100 uses at 12 or 14 px | 16 / 20 (14 only in small buttons) |
| Tailwind arbitrary values | 223 `text-[Npx]`, 446 off-grid spacings, 69 `rounded-full`, 22 bare `rounded` | expose the type, spacing and z-index tokens to Tailwind, then sweep |
| Green outside "in force" | `AppShell.tsx:38`, `DockRail.tsx:31` (wayfinding), `LiveShell.tsx:46` (badge) | wayfinding kept at ≤ 9 % (D4); the badge retires with `live/` |

## Kept as built

AppShell, DockRail, Hero (sizes aside), StepSection, UndoToast, ConfirmDialog, MenuButton, ChoiceChips `look="segmented"`, Switch, ActivityOrb, Split, Lead cards, InlineCreateRow, SwatchPicker, the stage navigator, `lib/` rules behind the inputs (`number-input.ts`, `name-input.ts`, `roving.ts`, `spend.ts`).

## Functions not yet placed

- **The respondent disc** (research board 7b, Sběr dat): its form is a board-specific canvas, not a shared component; it lives on its stage. Its "Na rozpočtu" colour is amber `#f0b429` on the board (`--pfill`), against the contract (see D6).
- **The Sociomap stage** (`viz-*`, `viz-stage*`, `viz-terrace-*`): a plot area with its own approved palette; out of this system's components, kept as tokens.
- **The report's print register** (`doc-*`, `print`): read by the DOCX renderer; kept as tokens, not UI.
- **Tooltip**: 90 native `title=` tooltips; neither prototype defines a tooltip component. Proposed in Návrhy.
