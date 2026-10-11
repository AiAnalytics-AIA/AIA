---
status: in-progress
chunks:
  - "[x] 1. Repair prompt naming, navigation and draft replacement; redesign the prompt workspace"
  - "[x] 2. Expose saved proposals and add direct narrative and measurement editing in step 2"
  - "[x] 3. Verify persistence, failures, responsive layouts and downstream design through real local APIs"
  - "[ ] 4. Integrate, deploy and verify the live pages"
---
# Prompt settings and research proposal UX

User request: repair the broken system prompt settings page and substantially improve editing in research step 2 (Návrh).

Baseline: `SystemPromptsPanel.tsx` has missing names for five registered Deep Research slots, an unbounded catalogue and a dense version table. Loading an old version silently replaces a dirty editor. `PlanStep.tsx` displays no proposal when analysis is null, despite saved project.research_plan objectives/questions; its narrative and set measurement wording are read-only.

Design: searchable bounded prompt catalogue, readable active/editor status, prominent save/activation flow, responsive version cards, protected draft replacement and recoverable test reads. Preserve API declarations, organization scope and code-owned prompt restrictions. Step 2 renders the saved plan, offers direct editing of summary/questions/objectives/hypotheses and set purposes/items/questions/scale anchors, and sends identical edited content to the existing workspace and design boundaries. Existing questionnaires are not overwritten by proposal edits; show that distinction. AI regeneration retains the human review gate.

Validation: meaningful UI tests plus a real browser journey over local fictional studies. Test save/reload, rejected saves, prompt switches/version replacement, field validation, set edits, desktop/tablet/phone, and design submission. Live checks read the actual pages without modifying organization prompts or spending research budget.

Doc follow-up: add the new proposal editor and its browser acceptance command to CLAUDE.md; record any non-obvious draft/async lifecycle defect with test anchors. Shared documentation changes belong to a separate docs PR.

## Verification and review

Local fictional browser journey: all eight flows pass through real workspace, design-revision and prompt APIs, with 20 responsive layout assertions at 1440/1024/768/390 px, zero page errors and zero paid AI jobs. Narrative and measurement edits survive reloads, the downstream design contains exactly the edited proposal, rail navigation protects unfinished edits, failed saves retry, saved native proposals appear without legacy analysis, and prompt save/activation/reload/reset works. Screenshots visually reviewed for desktop and phone.

Frontend: full 47-file suite / 694 tests passed; final four affected suites / 70 tests passed after the additional native-set preservation regression. TypeScript, ESLint, production webpack build and all design-token/210 contrast checks passed. Layer/exposure checks, Python types and formatting passed. Local core: 5576 passed / 104 environment skips / one unchanged macOS floating-point fixture mismatch. API: 362 passed. Worker: 54 passed / 8 PostgreSQL skips. Executors: 417 passed / 2 PostgreSQL skips / three unchanged macOS `mv -T` failures in population carry-over. These platform failures remain intact; Linux/PostgreSQL CI must pass before deployment.

Review map:
- Settings presentation: translated catalogue names/search/filter, editor and version cards, draft replacement guards, retryable result reads and async lifecycle; covered by SystemPromptsPanel tests and local prompt acceptance.
- Settings navigation/auth: preserve Next history state and follow hash changes; return from sign-in to the selected section. ControlPanel tests cover navigation.
- Research presentation/store boundary: ProposalEditor, PlanStep, plan-edit helpers synchronize native project and legacy analysis while preserving questionnaire, extra fields and provenance. Store edits invalidate the existing check as before; no readiness authority added.
- Shared step primitives: disabled object chips and wrapping section headers/chips for phone layouts; full frontend suite and responsive acceptance.
- Local verification tool: new proposal_prompt_journey.mjs is guarded to localhost and fictional identity, uses existing APIs, and asserts no paid jobs.
- Backend APIs, database schema, runtime policy, approval gates and frozen outputs are unchanged.

Integrated develop @ 999be17d: 51 frontend files / 938 tests pass, lint and production webpack build pass. The nine-flow Playwright journey also passes against that production build at all four widths. Repeated executions select the exact newly created prompt version from its API text instead of racing a previously saved card. Session-expiry acceptance confirms sign-in's next=/app/settings#prompts. The new methodology tab remains present.
