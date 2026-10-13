---
status: in-progress
chunks:
  - "[x] 1. Obtain and inspect Research variants and reusable exports from Claude Design"
  - "[x] 2. Implement contextual Research assistance with preserved drafts and truthful job states"
  - "[ ] 3. Obtain and implement Settings variants, prioritizing methodology parent/variable hierarchy"
  - "[ ] 4. Verify both lanes with real local APIs, responsive/keyboard checks and measured interaction latency"
  - "[ ] 5. Pass release checks, deploy, verify live behavior and reconcile shared documentation"
---
# Contextual Research assistance and understandable Settings

The user explicitly approved both UX lanes and sending interface layout,
component/token names and UI action contracts to the existing Claude Design
project “AIA design system access”. Client study data and credentials are excluded.
Claude Design must produce new variants and reusable exported assets before
frontend implementation; the core AIA design foundation stays unchanged.

## Research first

At baseline `33959ec3022b`, `ResearchScreen.tsx` renders the three native AI
actions below the stage. Move assistance beside its relevant workspace, using
compact context-aware choices and a desktop side panel/mobile accessible dialog.
Keep the actual action contract: critique_design stages 2–6, design_copilot 2–5,
answer_memory all stages. Preserve typed questions, design drafts, stored
responses, permission/budget gates, refusals and explicit cancellation/retry.
Do not imply client-knowledge questions receive sociomap numerical artifacts.
Results distinguish knowledge, literature interpretation and read-only map help;
preserve provenance, pinned methodology, uncertainty and suppression.

## Settings next

Audit all existing tabs. Methodology gets a clear module → logic block → child
variable hierarchy, original/current/draft values, readable formulas, optional
expert detail and focused editing. Preserve validation, comparisons, immutable
save, separate reasoned activation and unsaved-draft protection. Only controls
the actual API permits are editable; multiple modules are already editable.

## Acceptance

Import real Claude exports with a change manifest and evidence that baseline
tokens/fonts/brand files were preserved. Integrate modular presentation code.
Playwright covers desktop/tablet/phone, light/dark, 44px primary targets, focus,
Escape/return-focus, real save/reload and refused-save retry using fictional local
fixtures and zero paid jobs. Measure critical local feedback and navigation
under 400ms; slower server/model work has immediate truthful pending feedback.
Measure cold and warm paths separately. Do not weaken checks to obtain green.
Run frontend lint/types/build, token verification, relevant component/API suites
and full required CI before integration. Record live verification separately.

## Current evidence

The actual Research R1 and Settings S1 exports are recorded in
`docs/design/contextual-ux/manifest.json`, with contracts and component layouts.
The authorized requests were sent to the existing Claude Design project. The
first reusable Research preview incorrectly used purple accent values; Claude
corrected it to the original stylesheet before this import. Hash comparison of
118 baseline/core files found no changes. The prototype's simulated API rules
and persistence are design examples, not authority for production behavior.

The unchanged baseline builds successfully with Next.js 16.3.6 production
webpack and TypeScript. Isolated production-mode local services run at port
8870 over fictional fixtures and the real local API/worker. They use no model
credential. This is baseline evidence, not acceptance of the new UX.

Baseline components: 51 tests across ResearchScreen, useResearchAgents,
MethodologyPanel and MethodologyVersions pass. Existing Settings Playwright
passes seven workflow checks, 52 layouts and 15 local writes, with no page errors
and zero paid jobs. Fictional Research Run → Progress → Results passes through
aggregate tables and internal Sociomap without requests to legacy-unit paths.
Untracked evidence: tmp/ui-workbench/baseline-settings/ and baseline-research/.

Real local catalogue confirms editable sociomap/support/aggregation/response;
weighting/reference/experimental sociomapping are read-only. The Settings brief
records this API mapping. No final sub-400ms performance claim is made yet.

Research implementation: contextual heading assistance, nonmodal desktop/native
mobile panel, prefill without submission, retained study-session questions,
saved responses, explicit follow/resume of existing jobs, truthful pending and
unknown costs. Knowledge, literature and map guidance stay distinct. Scope,
revision checks and paid-call boundaries are unchanged. Heavy stage views load
on demand; working content starts directly after scope/relationship checks.
Next dynamic options must be inline object literals (production compiler).

Research component checks: 97 tests across six files pass, including existing
wrong-client/not-found scope checks. Frontend lint, production webpack build,
TypeScript and token/design checks pass. First local cold-load performance
attempts at 418.8ms and 404.5ms failed the strict 400ms target; these are recorded
findings and motivated eliminating heavy initial modules and loading waterfalls.
Final acceptance remains pending until the revised browser test completes.

Research browser acceptance after a production build passed through the real
fictional local API, including desktop/tablet/phone, dark/reduced-motion,
44px contextual targets, modal focus/Escape, draft survival, one explicit job,
refused runtime and refresh without resubmission. `tmp/ui-workbench/contextual-research/checks.json`
records 207.6ms cold document-to-usable-editor/help with no browser cache,
65.2ms first navigation to usable questionnaire controls, 49.8ms prefill,
32.2ms phone open and 31.9ms pending feedback after a deliberately delayed
actual API response. The earlier 404.5ms miss was addressed by starting the
content read immediately after study scope checks. A viewport listener race in
the acceptance script was repaired by waiting for the desktop panel before
arming its timing observer, without changing the 400ms threshold.
