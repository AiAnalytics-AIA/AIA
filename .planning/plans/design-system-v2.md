---
status: in-progress
chunks:
  - "[ ] DS0. Owner decisions D1-D15 of the v2 design system recorded here (no code)"
  - "[ ] DS1. Tokens: hero-title, lede, eyebrow, figure, figure-xl, diff-*; num-hero 600; usage notes rewritten; eight unread colours and the two scope-bar tokens retired (tokens.json, build-tokens.mjs, check-design.mjs)"
  - "[ ] DS2. Tokens reach Tailwind: type, spacing, z-index and duration utilities from tokens-theme.css, so screens stop writing arbitrary values"
  - "[ ] DS3. Reduced motion everywhere: one global rule in globals.css; the three animate-spin spinners, FrontDoor's transitions and the `just` highlight stop"
  - "[ ] DS4. Button to the contract: 32/13 (small 28/12), a danger variant, an amount slot; AiButton's 600 weight and glow ring dropped"
  - "[ ] DS5. Inputs to the contract: TextInput, TextArea 32/13; Select as a button and a list; InlineText's dashed mark at rest; Stepper's mono value"
  - "[ ] DS6. One StatusGlyph and status pill: circles 14/16/20, the seven words; Glyph.tsx, the rehome Chip's icon glyphs, LeadCards' Pill and .statepill folded into it"
  - "[ ] DS7. Status tones: a budget wait slate for those who cannot lift it, coral for those who can, never Nezačato (run-state.ts, lead-cards.ts, lane.ts)"
  - "[ ] DS8. One Chip: RegisterChip, LabelChip, workbench .chip, ChipInput's chips and the three local 'V AIA zatím není' chips into it"
  - "[ ] DS9. One Note: plain, you, bad, sig, ai; Loaded's failed box, AiFailureCard and AnalysisFailureCard on it"
  - "[ ] DS10. One Card and EmptyState: CARD and its five copies, SampleView's Sec; Empty and workbench .empty merged; ActionDock as an action bar"
  - "[ ] DS11. Dialogs: AskDialog's confirm and prompt into ConfirmDialog; InlineConfirm's yes as Button danger; the six <dialog> frames on one class"
  - "[x] DS12. SpendDialog on every money confirmation (the withBudget call sites; confirmSpend, PR #1022)"
  - "[ ] DS13. Segmented and Tabs: single-choice ChoiceChips to look=segmented; step.tsx Segmented retired; one Tabs; the nine pill rows replaced"
  - "[ ] DS14. Switch: step.tsx and ProfileArea's switches onto ui/Switch"
  - "[ ] DS15. One Icon: one name map over PhosphorIcon; the 40 board glyphs added; 41 unicode marks and the emoji replaced; sizes 16/20 (14 in small buttons)"
  - "[ ] DS16. Table: a shared Table (header on sunken, 8x10 cells, rows 36/28, tabular numbers, roles), first on Settings' tables"
  - "[ ] DS17. Thinking: LeadPane's .typing dots onto ActivityOrb"
  - "[ ] DS18. workbench.css: its 139 unused classes removed, its .btn/.chip/.seg/.tbl copies onto the shared components"
  - "[ ] DS19. Sociomapa panel CSS on tokens: object-map-windows.css' hex and rgba, the teal pressed state to signal, the amber warning"
  - "[ ] DS20. Headers inside a study: ResearchStudy, SimulationFrame and MemoryStudy on the compact header; stage title 20/26"
  - "[ ] DS21. The old /studies pages and components/live/ retired once every function has a home under /app (D3)"
  - "[ ] DS22. The design-system/ package regenerated from v2, or removed (D1)"
  - "[x] DS23. Petrol palette, the owner's choice of three (tokens.json; check-design 0 failures; PR #1022)"
  - "[x] DS24. Ctrl/⌘ K command palette on every page and in the workbench (lib/command-palette.ts, aia/CommandPalette.tsx; PR #1022)"
  - "[x] DS25. A failure in Czech, technical detail labelled after it (lib/error-words.ts, every e.message sink; PR #1022)"
  - "[x] DS26. One interaction behaviour: SAVED_MS everywhere, ChoiceChips saves, Stepper deferred, Vrátit for a contact and a client status (PR #1022)"
  - "[x] DS27. A Czech 404 with a way back (app/not-found.tsx; PR #1022)"
  - "[x] DS28. Quiet chrome: rail and client tabs without hue, no header strip, on-client monogram, no bounce easing, Phosphor for the last glyphs, the 12 px floor (PR #1022)"
  - "[x] DS29. AI without a colour: graphite and the spark edge (spark-1..3, .ai-spark in globals.css), ai-ink retired (PR #1022)"
  - "[x] DS30. Each thing said once on a screen (Přehled, Klienti, the workbench header, Settings' search, Profil, Výzkumy) and one FaultNote (PR #1022)"
  - "[x] DS31. StatusPill: Chip, LeadCards' Pill, pillClass and .statepill as one pill drawn by Glyph's shapes (DS6's pill; the 14/16/20 sizes still open)"
  - "[x] DS32. Value and usdWords: every figure known, unknown or suppressed one way; the six money formatters one; confirmSpend required, withBudget gone"
  - "[x] DS33. StaleMark: a stale proposal and an older run's results in coral with the reopened glyph, never the fault's red"
  - "[x] DS34. AiJobCard: the Lead's job and run cards on one card with the spark edge; the .act/.kvgrid CSS removed (JobPanel still its own)"
  - "[x] DS35. ItemReview: the Lead's edits (each) and Design Research (select) on one list; an agent job's proposal stays whole until its accept takes items (WCE8b)"
---
# Design system v2: from the approved look to apps/web

**Source:** the AIA Design System v2 artifact, <https://claude.ai/artifact/SEEkz1TrFgEZ1yK53Qmas4> (built 27 Oct 2026 from
the Settings canvas v99, the research canvas v77, `prototypes/shared/aia-core.css` (core v3, sha256 `bedd953f`) and
`prototypes/LOOK.md`), and its inventory of `develop` at `a1a9a45c`. The artifact's *Co nahrazuje co* lists every
element, kept, changed, merged or retired, with its anchor; *Otázky k rozhodnutí* lists D1-D15.

**What this plan is.** The code half of the design system: tokens first, then components, then screens. It follows
`prototype-build.md` lane A (PBA1, 2, 4, 5, 6, 7 landed: the Dock rail, the hero, Phosphor, the primitives' radii, the
Lead chat's radii) and does not redo it. Screen redesigns stay with their stage and Settings plans; this plan gives them
one set of parts.

**Rules for every chunk.** A form retires only when its function has a home, named in the PR. No test is loosened: a
test that pins an old size or tone changes in the same commit, with the reason. Each chunk is one PR into `develop`.

## The chunks, with their tests

| Chunk | Proves it with |
|---|---|
| DS0 | the owner's answers, quoted here |
| DS1 | `make web_design` (token drift, contrast for the new type and diff pairs in both themes); `make test-web` |
| DS2 | `make web_design`; `make typecheck`; a grep count of `text-[`, `rounded-full` and off-grid spacing that only falls |
| DS3 | a Vitest of the global rule; `ux_journey.mjs` with reduced motion on |
| DS4 | Button tests (sizes, danger, amount slot); `make web_unused` |
| DS5 | TextInput, Select, InlineText and Stepper tests; `workspace_journey.mjs`, `settings_journey.mjs` |
| DS6 | a StatusGlyph test per word; `workbench_journey.mjs` (the navigator) |
| DS7 | `run-state.test.ts`, `lead-cards.test.ts`, `lane.test.ts` with a budget wait read by a person who can and one who cannot lift |
| DS8-DS10 | component tests; `client_journey.mjs`, `settings_journey.mjs`; `make web_unused` |
| DS11-DS12 | ConfirmDialog and SpendDialog tests; `research_journey.mjs`, `lead_stale_journey.mjs` (the threshold) |
| DS13-DS14 | ChoiceChips, Tabs and Switch tests; `workspace_journey.mjs`, `settings_journey.mjs` |
| DS15 | `PhosphorIcon.test.tsx` (every registered glyph drawn, none unused); a test that no source file holds an emoji or the listed unicode marks |
| DS16 | a Table test (roles, header, suppressed value named); `settings_journey.mjs` |
| DS17 | `LeadPane.test.tsx`; `lead_journey.mjs` |
| DS18 | `make web_unused`; `workbench_journey.mjs` at 1440/1100/768/390 |
| DS19 | `sociomap_journey.mjs`; `make web_design` § 4 |
| DS20 | `ResearchStudy.stages.test.tsx`; `ux_journey.mjs` |
| DS21 | the function check written in the PR; `make test-web` |
| DS22 | the package's pages read against the artifact |

Every chunk also passes `make verify`.

## Findings

- `design-system/tokens/tokens.json` and `tokens.css` claim to agree with `apps/web/src/design/tokens.json`; 17 colours
  differ (signal `#006b9f`, the warm paper surfaces, an amber needs-you), radii 2/4 against 6/8.
  Repro: compare `design-system/tokens/tokens.json` with `apps/web/src/design/tokens.json` @ a1a9a45c. Fix: DS22.
- `ui/SpendDialog.tsx:60` @ a1a9a45c has no product importer; money confirmations go through AskDialog text via
  `withBudget` (`ExecutionSteps.tsx:767,1177,1250` @ a1a9a45c). Fix: DS12.
- `lib/run-state.ts:31` @ a1a9a45c maps every WAITING run to the coral tone, while `lib/lead-cards.ts:41` maps budget waits
  to slate; `research/lane.ts:160` reads a budget wait as idle (Nezačato). Fix: DS7.
- Reduced motion is honoured only under the workbench (`workbench.css:37`); `globals.css` has no rule. Fix: DS3.
- CLAUDE.md's map names `AiaMark` and `AiaMark.test.tsx`; neither exists. The mark is `Mark` in
  `components/workbench/Icons.tsx:39` @ a1a9a45c.

## Doc follow-up

For the docs PR after the chunks land, not this plan's PRs:

- `CLAUDE.md` § 2, `src/components/brand/`: drop "AiaMark (… held to … by AiaMark.test.tsx)"; name `Mark` where it lives
  (or its new home after DS15).
- `CLAUDE.md` § 2, `src/components/ui/`: add Table, Tabs, Note, EmptyState and StatusGlyph as they land; Button's danger
  variant and amount slot.
- `CLAUDE.md` § 2: remove `components/live/` with DS21; `design-system/` per DS22.
- `CLAUDE.md` § 3: the design system's artifact link beside `make web_design`.
- `ARCHITECTURE.md`: if it describes the UI layer's primitives, name the v2 set.
- `prototypes/LOOK.md` (owned by the PM coordinator): D5, D6, D7, D8, D12 and D13 once answered.
