---
status: in-progress
chunks:
  - "[x] 1. Tokens, sparkle, AiButton; the shell: sidebar, header, client tabs, stage rail, AI pomoc bar, job panel badge"
  - "[x] 2. Shared step pieces: StepSection, ActionDock, RadioCard, Switch, ChipInput, InlineConfirm, Segmented"
  - "[x] 3. Step 1 · Zadání"
  - "[x] 4. Step 2 · Návrh"
  - "[x] 5. Step 3 · Dotazník"
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

## Chunk 4 — Návrh

- Jump chips (Rozsah, Porozumění, Sady, Otázky AI a/b, Komentáře) with a status dot each.
- The variants as radio cards (`applyVariant`, as before); the understanding with
  its two lists and the "Princip objektů" note folded in.
- Each set edited on its card: the name in place (`renameSet` on leaving the field),
  the items as a chip input (`addObject` / `removeObject`, the 15-item refusal
  toasted as before), a count against 4–15 (the questionnaire's `SET_SIZE`), a
  "Respondent uvidí například" preview, and removal confirmed on the card instead of
  `confirm()`. "Přidat sadu" takes the name inline and calls `addSet` with no items.
- "AI se doptává": one input per follow-up question. The answers reach
  `answerFollowUps` as one text, each answered question followed by its answer
  (the classic textarea took whatever the person typed); empty still refuses with
  "Napište odpovědi.".
- Comments: the floating "Přidat komentář" puts a row with the quote in Komentáře;
  the comment is typed there and kept with `addComment` once it has text.
- The dock: back to Zadání, the way on as before (always enabled), and a note:
  a set outside 4–15, else the comments waiting, else ready.

**Not built, needs a decision:** v3 also edits the understanding (objectives,
hypotheses), a set's "Porovnáváme mezi sebou", its question(s) and scale ends, and
allows several questions per set. None of these has a write path today
(`plan.ts` has no setter; a set has one `object_question`), so each would be new
logic, not a redraw. They are shown read-only.

## Chunk 5 — Dotazník

- The three path tiles (icon, description, when to use); once a path is chosen, a
  "Způsob" segmented control (`setQuestionnairePath`) replaces "změnit způsob".
- Upload as two numbered steps, the file as a drop zone (`importQuestionnaire`).
- The editor in two columns: a sticky outline (B/Q/S rows, empty or invalid in
  amber, click to scroll; "Rychle přidat" keeps the classic guided prompts and
  `addGuidedQuestion`; "Nový blok", "Sledovaná sada" with its prompts and 4–15 rule)
  and the main column with "Upravit / Náhled respondenta".
- Blocks as panels with the name and purpose edited in place and removal confirmed
  on the panel; questions with type pills (`changeQType`), the text, options as rows
  applied when the list is left (`setQuestionOptions`, Enter adds a row), a drawn
  scale with its ends and range (`setScaleLabel`, `setScaleEnd`).
- Sets with the violet top edge, inline name, a 4–15 count, the purpose field, the
  question with "+ {object}" and a warning when it is missing, objects as chips
  (`updateObjects`, its under-four note shown on the card), the knowledge check as
  a switch, price bands for a concept test.
- The optimisation and Deep Research as AI actions; the dock's way on is enabled
  when a regular question exists or the editor is open, as the two classic
  buttons together were.

**Not built:** reordering questions (↑ ↓; no move function exists) and
"Nejdřív aktualizovat research" (not wired in the current screen).

## Chunks 6–10

Each step follows its v3 prototype file against its existing hooks, one chunk per
PR, with the step's existing tests kept green and no API diff.
