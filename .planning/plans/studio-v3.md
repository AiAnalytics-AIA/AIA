---
status: in-progress
chunks:
  - "[x] 1. Tokens, sparkle, AiButton; the shell: sidebar, header, client tabs, stage rail, AI pomoc bar, job panel badge"
  - "[x] 2. Shared step pieces: StepSection, ActionDock, RadioCard, Switch, ChipInput, InlineConfirm, Segmented"
  - "[x] 3. Step 1 · Zadání"
  - "[ ] 4. Step 2 · Návrh"
  - "[ ] 5. Step 3 · Dotazník"
  - "[ ] 6. Step 4 · Audience"
  - "[ ] 7. Step 5 · Dimenze"
  - "[ ] 8. Step 6 · Kontrola & spuštění"
  - "[ ] 9. Step 7 · Výsledky: jump chips and interval bars"
  - "[ ] 10. Znalosti: remove the \"Odkud znalosti pocházejí\" strip"
---
# Studio v3 — the shell redesign and the research flow's UX

**Status:** in progress · **Owner:** web · **Started:** 2026-10-05
**Source:** the Claude Design handoff `design_handoff_research_flow_v3` (README and
prototype `AIA Studio v3.dc.html` plus one file per step). The rule it sets: **no
functional or logic change**. Layout, input controls and visual treatment change;
every API call, permission, state transition, AI job, validation rule and copy stays.

## Chunk 1 — the shell (this PR)

- **Tokens** (`src/design/tokens.json`, then `npm run tokens`): the v3 surface and
  signal palette in both themes; the AI family `ai`, `ai-strong`, `ai-wash`, `ai-edge`,
  `ai-ink`, `on-ai` (for controls that start an AI worker job, nothing else); the
  sidebar's `shell-*`; the wayfinding tints `hue-*` / `shell-hue-*`; radii
  `radius-control` 6, `radius-card` 8, `radius-panel` 10, `radius-pill` 999.
  Where a v3 value failed the system's own contrast floors it was moved the least
  that passes, and `check-design.mjs` now measures the new pairs:
  `border-strong` light #8b93a0 → #7d8490 (3:1 control border on surface-sunken),
  `signal-wash-strong` light #d6e0fb → #d8e2fb (signal text 4.5:1),
  `shell-faint` #6c7079 → #7a7e87 (4.5:1 on the sidebar). `ai-wash` and `ai-edge`
  are v3's translucent values made opaque on surface-raised (the token test wants
  opaque hex).
- **AppShell:** graphite sidebar (mark on graphite, "Research Studio", the client card
  with "Změnit klienta ›", "Pracovní prostor", tinted nav tiles, account footer with
  sign-out); sticky header with a 3 px accent (the client's accent in a client,
  ink-muted on Nastavení, signal elsewhere), optional "← Zpět na klienta", nowrap
  crumbs, the eyebrow as a pill, a 28/36 title, client tabs with tinted icon tiles.
  The client's accent is one of the six `client-*` accents, picked from its id
  (`clientAccent`), since a client record carries no colour.
- **ResearchRail:** "Krok n ze 7" and its bar, three phases (Návrh výzkumu 1–3,
  Vzorek 4–5, Běh a výsledky 6–7), done / current / upcoming markers.
- **AI pomoc bar:** `aiHelpFor(step)` — "AI zkontroluje návrh" on 2–6, "Zeptat se na
  návrh" on 2–5, "Zeptat se na klientské znalosti" everywhere; Průběh counts as 6.
  Same handlers, same dialog. `AiButton` gives every one the sparkle, `data-ai-action`
  and the title "Spustí AI úlohu na pozadí · platí se z rozpočtu studie".
- **JobPanel:** the "✦ AI úloha" badge above the title.

Not taken from the prototype: the overview KPI tiles (no endpoint gives "Rozpočet
zbývá" per client) and the tab count badges (ClientWorkspace carries no counts).

## Chunks 2–3 — the shared step pieces and Zadání

- `components/rehome/step.tsx`: `StepSection` (numbered card, body indented to the
  title), `ActionDock` (sticky: back, the readiness note, the primary action),
  `RadioCard`, `Switch`, `Segmented`, `ChipInput`, `InlineConfirm`; tested in
  `step.test.tsx`. Only `StepSection` and `ActionDock` are used yet.
- `BriefStep`: the goal (sentence starters, a character count, "Navrhnout z cíle",
  which derives a title in the browser and writes the same field as typing), the
  problem types as pills, Podklady (a drop zone that uploads like the picker, the
  link field, kind badges), the context fields opened one at a time (× empties the
  field), the "Připravenost zadání" panel, and the analysis as the primary AI action
  in the dock.
- The dock's action keeps the classic condition, `canAnalyse` (a goal, or a
  description of what is studied). The handoff wrote "a goal or a problem type";
  the code wins. The duplicate analysis button inside the form is gone, so an
  empty brief is no longer refused with "Nejdřív popište zadání výzkumu." after a
  click: the action is disabled and the dock says what is missing.

## Chunks 4–10

Each step follows its v3 prototype file against its existing hooks, one chunk per
PR, with the step's existing tests kept green and no API diff.
