---
status: in-progress
chunks:
  - "[x] 1. Progress page prints why a step waits, and names the step that is parked"
  - "[ ] 2. Results page names the module or step that holds the report back"
---
# A waiting run says why

**Drafted:** 2026-10-02 · **Base:** `develop` @ `3677b0a` · **Owner:** the researcher who asked for
the research workflow to "run properly and output a report".

## Why this first

Ordered by mutual dependency across the open work (ranking recorded here so it is not re-litigated):

| Item | Depends on | Blocks |
|---|---|---|
| This plan (a waiting run says why) | nothing | gate 5b's spend gate; diagnosing any live acceptance |
| `two-roles-human-ai-gates` chunk 3 (resolver drops grants) | nothing | its chunk 4, and chunk 6 after one deploy |
| `two-roles-human-ai-gates` chunk 5b (gates) | this plan; the spend threshold, a number the owner must choose | nothing |
| Live acceptance (`internal-report-composition` 4, `ai-workflow-completion` 3 and 6, `ai-research-activation` 4) | this plan for diagnosis; credentials, an approved route and a cap | the goal |
| Docs-only PR (`CLAUDE.md` Client Knowledge sentences, `open-items.md`) | every PR above merged | nothing |

This plan has no dependency and unblocks two items, and the report workflow is exactly where a run
can stall with no visible reason. Chunk 3 is independent and also valuable, but nothing bites with
one user and it loosens client isolation irreversibly, so it gets its own deliberate PR.

## Finding

**A step parked by a gate shows a status chip and no reason.** The API already returns the reason as
`error_message` and the machine reason as `waiting_reason`
(`apps/api/src/aia_api/routers/research.py:_step`), but `ProgressStep` prints a step's message only
for a `FAILED` step (`apps/web/src/components/rehome/research/ExecutionSteps.tsx:302 @ 3677b0a`).
A licence or residency refusal parks fieldwork as `WAITING_PROVIDER` / `ai_runtime_unavailable` with
`error.message = "AI respondenti nejsou pro tento výzkum povoleni: <gate reason>…"`
(`apps/executors/src/aia_executors/ai_fieldwork.py:182`), so the banner's own advice, "Zkontrolujte
důvod u kroku sběru dat" (`apps/web/src/i18n/cs.ts:897`), points at a reason that is not on the page.

Three defects, reproduced with a throwaway Vitest render of `ProgressStep` on 2026-10-02:

1. The gate's message is not shown for a waiting step.
2. `parkedForRuntime` (`lib/research-execution.ts:61`) matches any step parked as
   `ai_runtime_unavailable`, but the banner text is fixed to fieldwork ("Běh čeká u sběru dat").
   Analysis steps park the same way (`apps/executors/src/aia_executors/analysis.py:366`).
3. Budget (`budget_exceeded`, `model_gateway.py:434`), quota (`provider_quota_exhausted`) and
   approval (`approval_required`, `gate:*`) waits show only the chip. **Hypothesis, not reproduced:**
   whether raising the study budget resumes an `AWAITING_BUDGET` run; no route to decide a workflow
   gate for a research run was found in `routers/research.py` or `routers/runs.py`.

## Chunk 1 — Progress page

Web only; no API or contract change.

- A waiting step (`WAITING_*`, `AWAITING_*`, `RECOVERY_REQUIRED`) prints its `error_message` under its
  row, and, where it has none, a one-line Czech explanation chosen by `waiting_reason`.
- The banner names the parked step; fieldwork keeps its existing wording, other steps get their own.
- A `FAILED` step is unchanged (still the one alert above the list), so nothing prints twice.
- Words for `budget_exceeded`, `provider_quota_exhausted`, `approval_required` / `gate:*` say only what
  is known: that the step waits and why. They promise no action the page cannot take (chunk 5b of
  `two-roles-human-ai-gates` adds the action).

Tests: the existing parked-run test keeps passing; new tests render a fieldwork park carrying a
licence message, an analysis park, and a budget wait and a quota wait.

## Chunk 2 — Results page

The report and analysis cards say "waiting" or "refused" without naming the module. Name the blocked
or waiting analysis module on the report card and link to Progress. Not started.

## Not done here

- An action for a budget or approval wait (chunk 5b of `two-roles-human-ai-gates`).
- Anything on `ai-workflow-completion`, which Codex owns.

## Doc follow-up

`docs/migration/interface-screens.json` is untouched. `CLAUDE.md` / `open-items.md` need no change
from chunk 1; the docs PR should record the finding above as an OI if this plan is abandoned.
