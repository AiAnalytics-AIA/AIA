---
status: in-progress
chunks:
  - "[x] 1. Record the user's desktop regression and preserve the corrective code already written"
  - "[ ] 2. Establish a desktop journey baseline and a coherent interaction model"
  - "[ ] 3. Complete Research flow, including editable Návrh and contextual AI"
  - "[ ] 4. Complete all Settings tabs, especially Methodology"
  - "[ ] 5. Verify complete desktop journeys, release and inspect the deployed result"
---
# AIA desktop UX overhaul — handoff to Claude Code

## Product direction

Make AIA feel like one research studio, not a collection of technically correct panels. The researcher should always know **where they are, what decision they are making, what is already saved, what can be changed, what an AI action will cost, and what happens next**. Each page should present the current work before guidance, metadata or technical provenance. A reviewer must be able to understand a study's path from brief to proposal to evidence to maps to report without learning the implementation architecture.

The user explicitly said the previous UX/UI upgrade made the product feel *more broken and disconnected*, including Settings. Their desktop screenshot of Research step 1 shows a roughly 425 px page header dominated by a purple AI help card; the brief form starts below it, and a floating action dock obscures the next form section. They asked for a generally smaller header, an intuitive flow, and a **desktop-first** redesign. The screenshot is available locally at `/Users/macbookpro/Desktop/Screenshot 2026-10-13 at 13.00.56.png`; describe or crop it for private review, but do not commit the browser chrome or account details visible in it. They particularly want Methodology to make sense, and earlier asked for a much better editing experience in Research step 2, Návrh. Do not treat green component tests alone as UX acceptance again.

The previous Research/Settings UX shipped in PR #356, but the desktop composition was not inspected at the user's viewport before release. The earlier Settings UX in PR #290 is functional but remains too layered. This handoff is a new design and acceptance pass, not a mandate to preserve those layouts. The user authorized the two UX lanes and consultation with the existing [Claude Design project](https://claude.ai/design/p/a63bd61e-56c8-46f9-9e20-536b60286e61). Its exports and contracts are in `docs/design/contextual-ux/`; use them as references, and challenge them where the actual browser flow contradicts them. Preserve AIA brand foundations, content, data and the live action contracts.

## Work already done on this draft branch

The code in this PR is an **initial corrective pass, not a finished redesign**:

- `AppShell.tsx` has a smaller shared header: tighter breadcrumb/back spacing, 24 px title and less vertical padding.
- `ResearchAssistance.tsx` reduces the header's large help card to one small utility control. Opening it shows actions and a stage-specific suggested question beside the working area. A suggestion prefills a draft; it does not start a paid job. Existing agent action eligibility, draft persistence, focus restoration, saved replies, cancellation and permission checks remain.
- `ActionDock` is in document flow on desktop so it does not cover research questions while scrolling.
- Settings loses the large account card above the workspace; account information stays in a disclosure at the end. Its navigation is denser, the selected tab has one short introduction, and Methodology is the initial tab. Error details for failed runtime configuration open automatically instead of being hidden.
- Methodology starts on the current module, with an explicit **Change area** control rather than seven large chooser cards before the actual method. Its existing immutable version and editor behavior are preserved.

Five focused test files pass (75 tests), TypeScript passes, and a production webpack build passed before the final error-disclosure adjustment. Re-run all relevant checks after further edits. **No browser visual acceptance has passed and this branch is not deployed.** The attempted local production workbench failed because the sandbox refused loopback port binds (`EPERM`) and its symlinked `.venv` resolved an older `PopulationRuntime` without `record_audience_catalogue`. Fix the workbench environment or run it on a host where local ports are allowed; do not weaken browser assertions or treat that failure as a product defect.

The current branch is based on `origin/develop` at `d6c661e2`. A separate CPU incident fix is in PR #370; it addresses population catalogue classification and may merge while this UX work continues. Rebase before final validation. Never accidentally include or revert the CPU fix in the UX PR.

## Experience architecture

**One frame, one task.** The global sidebar answers “where in AIA?” The study rail answers “where in this study?” The compact page header answers “which stage, save state, and how to get back?” It must not become a content row. The main workspace begins immediately beneath the header. Avoid repeating the same title in the shell, panel and card. The first actionable field or current result should be visible without scrolling on an ordinary desktop viewport.

**One primary next step.** Each research stage should have a clear sequence: orient → do the work → review readiness or implications → continue. Put the primary action at the end of the relevant work, near the decision it advances. Secondary tools, AI, history, raw references and advanced controls remain discoverable but do not compete with it. The right rail should reinforce the current task, not interrupt it; a readiness panel should align with the first form section and explain exactly what is missing, with links/focus actions to fix it.

**Honest states.** Separate saved draft, unsaved edits, submitted revision, running agent job, stored suggestion, accepted proposal, active methodology version and published report. Never call configuration “connected” without a health check. Never imply an AI response changes a study automatically. State paid action cost and study budget at the moment of submission, using the existing server gates. Make errors local to the action with a clear retry or recovery path. Preserve Czech product language and use human-readable labels before IDs or code paths.

**Calm visual system.** Use the existing AIA design tokens, type and spacing. Do not introduce raw colors or a second brand system. The purple AI semantic accent may identify a paid AI action or its open workspace; it must not fill the main page header or dominate the form. Establish a consistent hierarchy for title, section title, field label, explanation, system status and technical detail. Reduce nested bordered boxes and avoid mixing eight different card shapes on one page. Keep readable line lengths and substantial content width for document editing. Dense information can be progressive, but critical status or errors cannot hide in closed disclosures.

## Research journeys to build

1. **Brief (Zadání):** start with the question the researcher is answering. Group objective, project context and problem type in a simple vertical flow. Show “readiness” as actionable guidance, not a score with no next step. The stage header must remain compact with AI as a utility. The desktop action bar must never overlap an input, choice or validation message.
2. **Proposal (Návrh):** make the proposal an editable research document, not a loose stack of widgets. The current `PlanStep.tsx` has variants, understanding, sets, measurement questions and comments. Give it an overview or outline that shows these in research order, a focused editing canvas, explicit draft/save state, and a review area where AI critique and client context can be compared with the researcher's own edits. Make it obvious which AI text is a suggestion, which content is accepted and which is still an unsaved draft. Preserve current API contracts and draft-loss protection; do not fabricate auto-acceptance or rewrite evidence provenance.
3. **Later steps:** carry the same hierarchy through questionnaire, audience, dimensions, run and results. Results should connect numeric findings, sociomaps, their interpretation, limitations and the report. The earlier user request for map screenshots and well-written branded reports remains relevant: navigation should make those outputs findable and attributable to a run, without changing map math or report content in this UX-only PR.
4. **Contextual AI:** use one consistent entry point per stage, with a side workspace on desktop. Show what the model will see, what it will not see, the source boundary, explicit submit and budget signal. Preserve the native `critique_design`, `design_copilot`, `answer_memory` stage eligibility and job recovery. The user must be able to close help and continue editing without losing either draft.

## Settings journeys to build

Organize all eight current tabs around questions a person asks, with a predictable **read → edit/inspect → validate → save/propose → activate/approve** sequence. The current tabs are Methodology, System Prompts, Deep Research, AI runtime, Access, Study budgets, Audit and Reference. Keep tab URL hashes, keyboard navigation and unsaved drafts when switching. The left navigation should be scannable at desktop size; use short labels there, and one contextual explanation in the selected panel. Account and technical provenance are utilities, not competing opening cards.

**Methodology is the flagship:** Start by naming the current area and *in-force* version. Let the researcher switch modules without losing a draft. Clearly separate (a) the method actually used by new runs, (b) a code preset being inspected, (c) a draft replacement, and (d) a saved version not yet activated. Lay out a readable method overview before formula details. Group steps in computational order, with plain-language purpose, source of each value, limits and evidence; keep formulas and raw paths one click away for experts. The administrator's flow should be explicit: choose a starting version → edit one logical section → see original and changed values → check on server → compare on fictional panels → save immutable version → deliberately activate with a reason. A failed check must point to the field and keep the draft. Leaving or switching modules with changes must offer a real keep/discard decision. Do not relax server validation or change sociomapping formulas as a side effect of UI work.

**Other tabs:** Prompts should show slot purpose, current active version, draft, test/review and activation separately. Deep Research should expose policy scope, current approved values, proposal and approval, with sandbox-only test permissions visibly distinct from organization-wide policy. AI runtime should distinguish configured from verified, and present capability states with an actionable reason. Access and budgets should show scope and current authority before editing. Audit should answer who changed what and when without raw JSON dominating. Reference should retain all code/deployment/invariant controls as searchable, read-only material, with clear ownership of each value. Never invent an edit button for a deployment or code setting.

## Execution plan and release gates

1. **Audit the live desktop experience first.** Capture the current Research brief, proposal, results and all eight Settings tabs at 1440×900, approximately 1710×1000 (the user's screenshot scale) and 1920×1080. Record header height, first actionable element position, content width, scroll/overlap, focus order, number of repeated headings and page errors. Ask Claude Design for a cohesive desktop flow if its existing exports do not resolve these concrete problems. Keep a before/after visual record in the PR, redacted of identities.
2. **Build a small shared composition system** for compact headers, task introductions, working sections, context rails, disclosures, status, errors and action rows. Refactor Research and Settings onto it incrementally rather than styling each screen independently. Preserve all API boundaries, routes, permissions and state machines.
3. **Finish Research first**, with Brief and Proposal as the acceptance anchors; then extend through Results. Test unsaved form fields, AI drafts, job states, proposal acceptance and history across stage navigation. No paid live AI calls in UI acceptance.
4. **Finish Settings**, especially the Methodology editor and activation distinction. Exercise every tab with the real local API and fictional data. Keep editable state while moving between tabs; verify permission refusals and exact scope. Do not change organization policies during live acceptance.
5. **Verify the whole story, not just components.** Update the existing Playwright journeys in `tools/ui_workbench/` to the new interface, retaining their functional assertions. Add a desktop regression that fails if a helper/card makes the research header tall again, if the first form field falls below the initial viewport, if a dock covers input content, or if Settings hides an actionable error. Test 1440/1710/1920 widths, normal and long names, keyboard navigation, focus return, zoom at 125%, loading/error/empty/editing states, no horizontal overflow, and browser → API → persisted state → reload. Run frontend types/lint/tests/build and required CI at the exact commit. Inspect screenshot diffs manually. Basic smaller-screen checks prevent regressions, but the design target is desktop.
6. **Release only the complete, reviewed work.** Merge after full CI and review; then verify the deployed exact SHA, live read-only journeys and screenshots at the target desktop viewport. Do not claim success from a passing unit suite or a local design preview. Keep the existing live research runs and settings untouched during acceptance.

The outcome to seek is not merely fewer pixels. A researcher should be able to finish a brief, refine a proposal, understand the method behind a map, and locate the resulting report without wondering whether they are editing a draft, reading a generated suggestion or looking at an active rule.

## Decisions with the product owner (2026-10-13)

Asked and answered in the session that took over this handoff; they bind the remaining chunks.

- **Review loop:** each screen is mocked on the Claude Design canvas first, built from the app's
  current look (`apps/web/src/design/tokens.json`, Studio v3 shell and components), then implemented
  and tested. Canvas: <https://claude.ai/artifact/AxP51RbkDroRQpDx4uqFzb>.
- **Ship order:** small PRs. This PR lands the compact stage header and Zadání; Návrh and Metodika
  follow as their own PRs. Settings: Metodika first, the other seven tabs later on the same pattern.
- **Contextual AI:** one AI entry per stage, beside the stage's main work, plus the nonmodal side
  panel on desktop (history, cost, what AI sees). Not a trigger beside every number. What a job sees
  is unchanged: approved client knowledge, the saved design and the typed question; result and map
  values are sent only when the researcher types them.
- **Peak-end:** the moment that must feel finished is the downloaded report: which run, which
  method, the file ready, where to find it again.
- **Metodika:** used by one or two methodologists; it opens on the editor. Safety stays draft →
  check → compare → save → activate, shown as one sequence with each result kept and activation a
  separate confirmed action with a reason. Formula first, with the named parameters and the formula
  editor combined into one clear editor (today's hierarchy is the problem).
- **Measured in Playwright:** visible feedback to every interaction within 400 ms (pressed state,
  panel open, "Ukládám…"); server work may take longer and says so honestly. Must-pass viewports:
  1440 × 900, 1710 × 1000, 1920 × 1080.
- **Remove across the app:** disclosure arrows that hide text, boxes inside boxes, small grey
  explanatory text everywhere, technical ids and hashes shown to researchers, inconsistent buttons.

## Chunk 3, first slice: the stage header and Zadání (this PR)

- One-row stage header (`AppShell` `compact`): breadcrumbs, save state, AI help; the title opens the
  work. The duplicate "Zpět na klienta" link and the step pill are gone (the breadcrumb and the rail
  carry them). Tests: `ResearchScreen.test.tsx` "draws the step in the shell…", "says in the
  breadcrumbs…".
- Zadání is one surface: required (goal, problem type) first, then "Volitelné · zpřesní návrh"
  (files, context). Readiness counts what is done, names the next gap, and a row puts the caret in
  its field. At ≥ 1280 px the start action and its cost sit beside the checklist; below, the dock
  closes the form. AI next to the goal opens the help panel and sends nothing. Tests:
  `BriefStep.test.tsx` "draws the classic blocks…", "on a wide desktop the start action…", "asks AI
  about the client's knowledge…".

## Chunk 4, first slice: the Metodika editor (stacked on the Zadání PR)

Mocked first on the canvas (artboard "Nastavení · Metodika · editor"), then built over the same
API calls, guards and server checks; nothing about what a version may be moved.

- An administrator opens on the editor (from the stored version in force, else the code's first
  preset, as before). A one-row sequence shows where the change stands: upravit → zkontrolovat →
  porovnat → uložit verzi → aktivovat, each with its result. Tests:
  `MethodologyVersions.test.tsx` "opens on the editor, with no extra click", "shows the change's
  place in the safe sequence…".
- The step `<select>` and arrows are replaced by an outline of the calculation in order (group,
  then its steps; a dot marks a changed step, "problém" a refused one). A step shows its formula
  first, each formula slot's expression with "Vrátit původní", its variables and the conditions the
  server checks, then its parameters with the value in force; no disclosure hides any of it.
- What the draft changes is listed in words (old → new); check, compare, note and save sit beside
  the step from 1536 px and under the sequence below that. A saved version offers its activation at
  once (reason required); activating another version waits only on unsaved changes. Test: "offers to
  put a just-saved version in force…".
- Switching areas asks only when the open editor holds changes (was: whenever it was open). Test:
  "switches areas at once from an untouched editor, and asks first when it holds changes".
- Measured: re-typesetting every step's MathML on each keystroke made the guided-editing test
  3.7 s → 5.4 s; typesetting is now cached by its LaTeX (`formulaMathML`), `Formula` is memoised and
  a hidden step renders only its inputs: 3.4 s. In the browser (`settings_journey.mjs`, local
  workbench, Chromium): a step opens in 118–123 ms and a typed value reaches the draft list in
  111–215 ms; the sequence is above the fold at 1440 × 900, 1710 × 1000 and 1920 × 1080.

### Findings

- Hypothesis, not reproduced as a defect: with the code's preset in force the editor starts from the
  first preset (`aia-sociomap-4`), not the one in force (`aia-sociomap-3`)
  (`MethodologyVersions.tsx` `editStart`). Kept as it was; whether an edit should start from what is
  in force is the product owner's call.

## Chunk 4, second slice: the other Settings tabs (plan, 2026-10-13)

The research lane belongs to `research-lane-redesign.md` (PR #382, the owner's decision); this plan
keeps Settings. Problems seen in the running app (settings journey screenshots, 1440 px): every tab
opens with a run-on sentence, a "Rozsah a správa změn" disclosure and an inner card repeating the
title; technical detail (env names, codes, client ids, catalogue ids, raw audit actions) is behind
dozens of disclosure arrows or shown to researchers outright; Reference is a column of closed
disclosures.

- [x] S1. One tab header: title, one sentence, a "platí pro / mění" line without a disclosure; no
      inner card repeating the title.
- [x] S2. One "Technické údaje" switch per page (off by default, kept for the session) instead of
      every technical disclosure: env names, codes, ids, catalogue and implementation references.
- [x] S3. AI běh as one table: capability, state, the reason in words, what happens meanwhile.
- [x] S4. Přístup: members, clients and self-approval as tables with an "Upravit" action per row;
      roles in words.
- [x] S5. Studie a rozpočty as a table with "Upravit" per row; audit events named in Czech (the
      audit stays a list of entries: each has a reason line a table cell would truncate).
- [x] S6. Reference: headed groups with a jump list, searchable, nothing collapsed.
- [x] S7. Deep Research and Systémové prompty on the same pattern, built from the canvas
      artboards "Nastavení · Deep Research" and "Nastavení · Systémové prompty" (owner, 2026-10-13).

Landed (S1-S6), measured with `tools/ui_workbench/settings_journey.mjs` on the local workbench
(next dev, fictional data): three consecutive PASS runs; no `details`/`summary` in AI běh, Přístup,
Studie, Audit or Reference; no page overflow at 1440x900, 1710x1000, 1920x1080 (and 1024/768/390).
The technical switch first took 514 ms to show its details, because the toggle re-rendered every
tab and Metodika re-typeset its formulas; memoising the three tabs that read their own routes
brought it to 284-365 ms (< 400 ms) under dev-mode React. A filtered-out study's open edit row is
hidden, never unmounted, so a typed budget survives the search (test: "filters studies without
unmounting their budget drafts").

Fixed here (from #379): after a Metodika save, its confirmation and the version list both offered
"Uvést … v platnost" for the same version. The owner chose to drop the list's: while the
confirmation offers a version, the list does not (test: "offers to put a just-saved version in
force"). The list keeps the button for every other version, which is how an older one is put back.

S7 landed (Deep Research, Systémové prompty), measured on the local workbench (next dev, fictional
data): `settings_journey.mjs` and `proposal_prompt_journey.mjs` PASS; no horizontal overflow at
1440x900, 1710x1000, 1920x1080.

- Deep Research: the groups on the left say how many rules each still needs approved; the chosen
  group's rules are a table (value, origin, flags in words; catalogue keys only with technical
  details); "Upravit" opens the rule beneath its row with the order Navrhnout → Schválit → Platí
  pro nové běhy. Live readiness is one line whose button shows exactly those rules (the closed
  list of names is gone). Every group stays mounted and hidden, so a draft survives a change of
  group (test: "opens on one group and switches groups without losing an unsaved proposal").
- Systémové prompty: the instruction is the page, in a reading font; the code frame is one plain
  line, its text only with technical details; Upravit → Uložit verzi → Vyzkoušet (nepovinné) →
  Zapnout; the diff against the starting text shows while typing. Beside it (2xl) or below it:
  what runs, the next step after a save, versions, the data-class declarations and the history,
  none of them behind a disclosure. API labels "e3" read "verze 3".
- One button per action: after a save the next-step card offers "Zapnout verzi N" and the
  version's row does not (the Metodika rule).

Finding (this slice, fixed): the next-step card was first derived from the save message, so
"Vrátit neuložené změny" after a save cleared it and the row's button came back. The offer is now
its own state (test: "walks the change in order", the revert step). Caught by
`proposal_prompt_journey.mjs`, not by the unit tests.

Finding (not this slice, hypothesis-grade until reproduced on develop):
`ResearchScreen.test.tsx` "keeps one study session while each step's page mounts afresh" failed
once in the full web suite (`Unable to find role="list" and name "Kontrola připravenosti"`, the
file took 17 s) and passed twice alone. Likely a default 1 s `findBy` under load; the research
lane is `research-lane-redesign.md`'s, so it is left there.

Metodika: an edit starts from what is in force (owner, 2026-10-13). It already did: a stored version
in force is the editor's start, and with the code's aia-sociomap-3 in force the start is
aia-sociomap-4, which computes the same byte for byte and declares the constants -3 keeps in code
(f588045c), so an edit can move them. What was wrong was the label: "Úprava metodiky (výchozí:
aia-sociomap-4)" read as a different starting point. The editor now says "Úprava metodiky v
platnosti (…)", one line says why it saves over -4, and the base picker reads "Začít od metodiky
z kódu" with "Metodika v platnosti" selected (tests: "opens on the editor, with no extra click",
"opens the next edit on the stored version in force, with its values").

Metodika: the object map grouped by the stages of the computation, with each step's place in it
(owner, 2026-10-14, from the canvas artboard "Nastavení · Metodika"). The F1-F16 groups were the
audit's numbering; a methodologist reads the computation in order. The Sociomap module's groups
are now Metoda, Vstupní hodnocení, Vztahy mezi objekty, Rozložení na mapě, Věrohodnost mapy, Skóre
a výška objektů, Terén, Respondenti a podpora mapy, then the points AIA does not compute (F5, F14,
F15, F16) with their notes kept (test: `test_the_groups_follow_the_computation_by_its_stages`).
Each step declares what it is for (`role_cs`), the steps it reads (`inputs`) or, for a first step,
its source in words (`source_cs`), and its audit point (`audit`, kept as a small tag). Which steps
read a step is derived (`feeds_of`), never declared twice; `module_problems` refuses an input that
names no step, the step itself, or a step twice
(`test_a_steps_inputs_name_other_steps_of_its_module_once`). The editor and the read-only
catalogue show "K čemu / Bere z / Předává do" with links that move to the step (in the catalogue,
opening a closed stage). Measured on the local workbench (next dev): moving along a link 64-173 ms
at 1440/1710/1920, no overflow; `settings_journey.mjs` PASS.

Finding (this slice, fixed): the context links were first buttons, and the catalogue draws every
card; two editor tests went from 1.7 s to 5-7 s (over Vitest's 5 s), because Testing Library's
`getByRole("button")` checks every button's visibility. They are links now (they move within the
page), rendered in the editor only for the visible step: 1.9 and 2.0 s.

Finding (this slice, fixed; raised by the owner's outside review, 2026-10-14): the editor showed a
step's whole formula and, under it, "Vzorec · <slot>" with an expression covering only part of it.
F1's refusal of an off-scale rating, F2's exclusion of a respondent with no spread and F3's
respondent-count branch are all code, untouched by the slot (`engine_v2._scaled`,
`relations.person_minmax`, `pairs.derive_pair_relations`), but nothing said so: a reader took
the expression for the whole step. The numbers were never wrong. Every Sociomap formula now
declares what the engine keeps around it (`BuiltinFormula.kept_cs`, served as `kept_cs`); the
editor labels the box "Upravitelný výraz" and lists "Co výraz nepokrývá (drží kód)". Tests:
`test_every_formula_says_what_the_engine_keeps_around_it` and, with each slot replaced,
`test_a_replaced_scale_still_refuses_a_rating_off_its_scale`,
`test_a_replaced_person_scale_never_sees_a_row_without_spread`,
`test_a_replaced_kish_n_is_only_the_kish_branch`.

Doc follow-up: ARCHITECTURE/CLAUDE map, `domain/methodology/catalogue.py`: "MethodStep carries
role_cs, inputs, source_cs and audit; feeds_of derives the steps that read a step"; `sociomap.py`:
"the object map in the order of its computation (stages S1-S7), each step citing its audit point
F1-F16" (replacing "in the audit's order F1-F16").

Metodika, Agregace: the same "what stays code" lists (owner, 2026-10-14, after #400). The five
estimators (`agg.kish`, `agg.share`, `agg.mean`, `agg.variance`, `agg.top_box`) each declare what
`research_aggregate` keeps around them: weights cleaned to the median before any estimator runs,
the effective n capped by the donors, the bootstrap and its quantiles, the rounding, and that the
mean also computes the top box's share and the multi-choice intervals. Tests, with the slot
replaced: `test_a_replaced_kish_n_sees_cleaned_weights_and_stays_capped_by_the_donors`,
`test_a_replaced_variance_never_sees_fewer_than_two_answers`; the existing
`test_a_replaced_estimator_is_what_the_aggregate_computes` already proves the mean drives the top
box.

Metodika editor outline, hierarchy (owner, 2026-10-15: "better visual hierarchy and text sizing to
have more readable labels in the formula selector menu"). The code had drifted from the canvas
(stage headings 12 px faint, unnumbered). Now, as the canvas draws it and a step larger:
- each stage is a heading: 14 px semibold ink with its number (mono, faint), a rule between stages;
  "Metoda" carries no number; "Zatím v AIA není" reads as the last heading;
- its steps 14 px, indented under the heading, the audit tag 12 px mono;
- the column 13 rem -> 19 rem; five long titles still take two lines at 1440 and 1710;
- rows 32 px. The Settings workspace forces every button to 44 px; the outline's buttons opt out
  with `data-dense` (ControlPanel's selector `[&_button:not([data-dense])]`), 32 px being above
  WCAG 2.5.8's 24 px. The rest of Settings keeps 44 px.
Measured on the workbench (next dev): a step opens in 48-90 ms at 1440/1710, no overflow;
`settings_journey.mjs` and `methodology_journey.mjs` PASS; web 1484 tests pass.
