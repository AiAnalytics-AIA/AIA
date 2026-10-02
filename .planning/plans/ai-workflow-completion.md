---
status: in-progress
chunks:
  - "[x] 1. Resume a pre-dispatch research proposal after runtime activation"
  - "[ ] 2. Make material review usable without host configuration edits"
  - "[ ] 3. Verify respondents and admitted analysis in a recorded full Study run"
  - "[ ] 4. Compose an internal branded report from admitted analysis"
  - "[ ] 5. Store and retrieve the report through the Study with explicit review state"
  - "[ ] 6. Deploy and complete bounded live acceptance"
---
# Complete the AIA research workflow

Owner: Codex. User direction 2026-10-01: own development of the working research
flow and branded output rather than hand it to Claude Code. The prior fictional
acceptance and the public Starbucks proposal proved one design action, not the
whole Study journey. Work in reviewable slices against `develop`; preserve the
unfinished role-workflow checkout separately.

## Findings at `2e6d219`

1. A design job is idempotent by Design Revision and context hash
   (`packages/aia_core/src/aia_core/application/research.py:286 @ 2e6d219`). A
   runtime-unavailable park never resumes on the worker's timer
   (`packages/aia_core/src/aia_core/domain/workflow.py:734 @ 2e6d219`). Clicking
   the same AI button after activation therefore returns the old parked job. An
   explicit retry may reoffer it only when no paid call was dispatched.
2. Analysis is a deployed but off-by-default capability
   (`deploy/develop/env.example:104 @ 2e6d219`). Activation requires exact
   material classification, budget, route, and a complete Study test; the design
   proposal alone is no evidence of analysis working.
3. Results explicitly say that the client report has no AIA counterpart
   (`apps/web/src/components/rehome/research/ExecutionSteps.tsx:431 @ 2e6d219`).
   The renderer and templates exist, while composition from admitted results,
   durable storage, retrieval and review remain.
4. A questionnaire build reruns `analyze_brief` even after its proposal was
   accepted (`apps/web/src/components/rehome/research/QuestionnaireStep.tsx:100`
   and `useAnalysis.tsx:50 @ 3c2ddda`). Native acceptance stores the model's
   analysis without the brief signature used by `reusableAnalysis`
   (`useResearchAgents.tsx:75 @ 3c2ddda`). On develop, that repeat created a new
   fictional design revision and the following questionnaire job parked on an
   exact-material classification mismatch. Sign the accepted analysis and reuse
   it only while the brief fingerprint matches; explicit Brief-stage reanalysis
   remains an intentional fresh request.

## Acceptance

- A repeated proposal click after runtime activation continues the same frozen,
  unbilled job without editing a brief or creating another run. A billed or
  uncertain attempt cannot use that route; Study scope and permissions hold.
- A complete recorded Study uses one Design Revision through proposal,
  questionnaire, fieldwork, aggregation and admission-checked analysis. Synthetic
  answers remain internal and plainly labelled.
- The AIA-branded DOCX is built only from reconstructed admitted results. A
  client-facing report refuses synthetic or internal claims. A researcher can
  retrieve the internal draft through a Study-scoped route; the review state is
  visible and delivery cannot be inferred from generation.
- The live run uses an approved material route and explicit cap, records actual
  cost, and stops on a missing classification or uncertain paid delivery.

## Chunk 1 verification (2026-10-01)

The same Study-scoped job is reoffered after a researcher repeats the AI action;
the repository refuses a paid/uncertain attempt and logs the explicit resume.
Focused core/API/browser tests pass, including same-study rights and cross-study
404. Strict mypy (228 source files), layer (70), exposure (7), lint, formatting
and TypeScript checks pass. The unsandboxed full Python run passed core 3,182
(102 reference/PostgreSQL skips), API 263, worker 50 (6 PostgreSQL skips) and
executors 134. The full web run passed 482 of 484 under bundled Node 24; the two
download tests fail on the base checkout too because their `Blob.text()` fixture
is unavailable in this local jsdom runtime. The changed web hook's 9 tests pass.
CI on its supported runtime remains required before merge.

## Doc follow-up

After each feature slice merges, update the shared architecture and migration
status documents through a separate docs-only PR. Record the runtime-resume
operation, report composition and retrieval contracts, the accepted-brief
fingerprint reuse in the questionnaire path, and the verified live acceptance
at their final SHAs.
