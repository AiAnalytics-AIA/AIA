---
status: in-progress
chunks:
  - "[x] 1. Audit the complete research journey with Playwright at desktop and narrow widths"
  - "[x] 2. Improve study navigation and organize results, maps, literature and report actions"
  - "[x] 3. Add repeatable browser regressions and verify the complete local journey"
  - "[ ] 4. Validate, integrate and verify the deployed sandbox journey"
---
# Research UX and browser verification

Requested 2026-10-11: test AIA end to end with Playwright and substantially improve clarity and organization.

## Scope

Walk client directory → study design → run → progress → results → maps → literature → branded report. Audit other global areas for navigation and readable empty states. Preserve existing study content, frozen artifacts, approval boundaries and the sandbox's hard USD 20 budget. Local test runs use explicitly fictional workbench fieldwork and no paid model calls; live acceptance reuses the completed sandbox run and literature review.

Implement changes in small chunks, with evidence before/after and regression coverage. Keep original AIA design tokens and identity. Clear navigation must not imply that visited stages have passed validation or received human approval.

## Findings

Initial code hypotheses (to reproduce in browser): the fixed 240px global menu plus 256px study rail leaves little content room at narrow widths; results jump links lead through one long sequence of data, maps, analysis and report; stage position is drawn as completed checkmarks even though it reflects navigation only.

## Verification

Local: `ux_journey.mjs` passes 84 layout assertions (17 real routes × 1440/1024/768/390, plus four result sections × those widths), client search, keyboard focus, hash/reload, mobile menu and canonical 3D rotation/state preservation. `research_journey.mjs` passes real API → worker → results; `sociomapping_journey.mjs` passes all seven steps, drag/button rotation, zoom, top view, object/fit/limitations and Word download; no page/console/unexpected HTTP errors. No live research started or budget changed.

Frontend suite: 46 files / 681 passing, including cancellation/settings regressions. Production webpack build, types, lint, 101 layer rules, 7 exposure rules, Python format and design-token/210 contrast checks pass. The full suite exposed Settings examples inheriting another example's URL hash; reset the URL in beforeEach rather than querying hidden roles. Local backend: 5547 core pass, 104 environment/reference skips and one unchanged fixture exact-serialization failure; API 361 pass; worker 54 pass/8 PostgreSQL-dependent skips; executors 400 pass/2 environment skips. Mac fixture mismatch affects floating-point last digits; `packages/aia_core`, its fixture and builder are unchanged from base abe2d711. Keep the failing test intact and require all blocking Linux/PostgreSQL CI gates before release.

Runtime and deployed sandbox acceptance pending.

## Doc follow-up

In CLAUDE.md §3, next to "See every screen", document `node tools/ui_workbench/ux_journey.mjs` after `make ui-fixtures` + `make ui-research`: 17 AIA routes at 1440/1024/768/390, result sections, keyboard/hash navigation, client search and preserved 3D camera; outputs `tmp/ui-workbench/ux-journey/`. In §2's web map, add ResultsWorkspace.tsx as presentation over one frozen research run (views, not additional runs). Add the Next-generated apps/web/AGENTS.md and apps/web/CLAUDE.md in the separate docs PR; their instruction block is emitted by the installed Next dev runtime. Shared architecture documents remain unchanged in this feature PR.

## Reproduced findings and fixes

- Fixed navigation leaves a 64px main area at a 390px viewport and 881px page width. Reproduced with Playwright over the signed-in sandbox results at the deployed baseline; responsive shell/rail fixes this. `ux_journey.mjs` asserts viewport containment and minimum content width on every route.
- Results renders a ~9908px desktop / ~63198px phone page at baseline. Result tabs expose one panel while preserving map cameras and selected literature. `ResultsWorkspace.test.tsx` covers panel accessibility, keyboard focus, old anchors, query preservation and history.
- Stage checkmarks reflect URL position, not validated completion (`ResearchRail.tsx` at base abe2d711). Remove implied completion and retain current-stage position only.
- Failed initial Results/Progress reads can remain a loading message (`useRun`/`ResultsStep` at base abe2d711). Surface the error and retry; `explains a failed run load and retries instead of leaving Results loading forever` reproduces the regression.
- Analysis runtime activity has no readable title/text/off translation; Settings overflow reproduced by the browser audit at 390px. Add the missing translations and wrap configuration identifiers; `names analysis activity and its disabled state in human-readable language` and the Settings browser viewport assertions guard this.
- Interpretation review cancellation had no confirmation (`InterpretationResearch.tsx` at base abe2d711); keep the paid-job boundary visible in an explicit confirmation before dispatch, covered by `requires confirmation before cancelling an active interpretation review`.

## Review map

- Presentation shell/client: AppShell + ClientDirectory (ClientFirst tests); Settings ControlPanel + cs.ts (ControlPanel tests).
- Study presentation: ResearchRail; ResultsWorkspace (new component + tests); ExecutionSteps (existing tests updated to open the selected view + failure retry regression); InterpretationResearch (same scoped API/download contracts + cancellation regression); DeepResearchPanel corrects obsolete Wikipedia-only copy.
- Local verification tooling: updated research/sociomapping journeys for result sections and module compatibility; new ux_journey over real APIs; README command.
- Domain, application, database, paid-call routing, approval policy, report content and frozen map geometry unchanged.
