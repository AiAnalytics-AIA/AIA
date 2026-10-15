---
status: done
chunks:
  - "[x] 1. Agent jobs get the run's event feed: GET /research/agent-jobs/{id}/events?since=; steps name their step_id"
  - "[x] 2. Step activity, pure: fold a run's events into what each running step is doing (lib/step-activity.ts)"
  - "[x] 3. The feed, read live: a cursor reader that polls only while a step runs (useStepActivity)"
  - "[x] 4. The running step gets its space: a panel that opens under it, a 64 px orb, the live feed; Progress, job panel, Deep Research, Interpretation Research"
  - "[x] 5. Model calls in the feed: a sent and an answered event per request (tokens, cost, latency), behind AIA_AI_STEP_EVENTS"
---
# A running step has its space, and says what it is doing

**Drafted:** 2026-10-12 · **Base:** `develop` @ `a7132f4` · **Owner:** the product owner: "the orbs are
subtle … make the orbs bigger … give each step where an orb is working its space, where it expands as
it's working … add streaming to the step … so we can see what is going on in the backend".
Follows [thinking-orbs.md](thinking-orbs.md) (PR #169), whose rule stays: an orb only on a step the API
reports `RUNNING`.

## What "streaming" means here

**The step's own event feed, read live**, not the model's text token by token. The worker already
writes real progress per step (`StepContext.progress` → `STEP_PROGRESS`,
`packages/aia_core/src/aia_core/infrastructure/workflow_repository.py:980 @ a7132f4`): "AI respondenti
odpověděli" with `respondents`/`of`, "AI analyzuje modul" with `module`/`turn`, every Deep Research
tool call (fingerprints, never query text: `domain/deep_research/tooling.py:150`), plus the
engine's own `ATTEMPT_CLAIMED`, `STEP_RUNNABLE`, `STEP_SUCCEEDED`, `STEP_DEFERRED`, `GATE_*`. A run's
feed is read after a cursor: `GET /research/runs/{id}/events?since=`
(`apps/api/src/aia_api/routers/research.py:626`) and Deep Research's
(`routers/deep_research.py:570`). Agent jobs have none (chunk 1).

Token streaming is deliberately out: the gateway's `invoke` is one request, one result
(`apps/executors/src/aia_executors/ai_step.py:166`), journaled and settled once; streaming its text
would reopen the call journal, the fencing and the ledger, and show a proposal before it is
validated. It is a separate decision.

**Transport: cursor polling, not SSE.** Events land in PostgreSQL as the worker writes them (ADR 0002:
no broker); an SSE endpoint would poll the same table server-side, and `EventSource` cannot send the
Cognito bearer token. The reader asks `?since=<last id>` every 1.5 s while a step runs and stops
when none does. Latency to the eye: ≤ 1.5 s after the worker's write.

## Design

- **Bigger orbs.** 64 px in the running step's panel and the job dialog (the package's tuned
  avatar size), 32 px where an orb sits in a status line. Inline 20 px goes.
- **The step's space.** A running step's row opens a panel beneath it (height and opacity
  transition, `motion-safe` only): the orb, the latest activity in words, the real counts it
  reported (`40 / 300 respondentů`, never a percentage), elapsed since the step started, the
  attempt, and the last few feed lines (`role="log"`, `aria-live="polite"`). It closes when the step
  is no longer `RUNNING`. Other rows keep their present height.
- **What a line says.** Only what an event says: its `message`, and a whitelist of payload fields
  rendered as words (counts, module, turn, tool outcome, tokens, cost, latency). Never a payload
  dump, never a guessed percentage, never an estimate.
- **Model calls (chunk 5).** `StepModelCaller` writes "Dotaz odeslán modelu" before the gateway
  call and "Model odpověděl · n → m tokenů · $x · t s" after settling, from `ModelResult`
  (`usage`, `actual_cost_usd`, `latency_ms`); no prompt or answer text. Two lease-fenced writes per
  request, so it ships behind `AIA_AI_STEP_EVENTS` (off by default, off in test), cost measured
  before it merges.

## What landed, and where it differs from the design above

- **Step ids.** A step's events name it by `step_id`, which no step response carried. Research
  steps (`ResearchStepResponse`) and Deep Research steps (`DeepResearchStep`, with `started_at` for
  the elapsed clock) now do; additive, no client removed a field. Tests:
  `test_research_api.py::test_a_run_starts_once_per_design_revision_and_is_read_by_its_study`,
  `test_research_agent_jobs_api.py::test_the_job_feed_says_what_its_step_reported_after_a_cursor_and_only_under_its_study`.
- **Model-call events reach two executors, not four.** `AIA_AI_STEP_EVENTS` is read into
  `AIRuntimeSettings.step_events` and reaches `ResearchAgentConfig` and `AnalysisConfig`
  (`StepModelCaller(announce=)`). Deep Research already journals every tool call and agent turn
  to its feed and its engine is frozen (ADR 0021); AI fieldwork reports per respondent block. Neither
  gets the switch. Tests: `test_research_agent_executor.py::test_the_feed_says_a_request_was_sent_and_what_its_answer_cost_only_when_switched_on`,
  `test_analysis_executor.py::test_the_step_events_switch_reaches_the_analysis_configuration`.
- **Tokens a provider did not report are unknown, not zero** (`ModelUsage` keeps null): the line
  says "tokeny neuvedeny" and the step's token total becomes "?" (`step-activity.test.ts`).
- **Sizes.** 64 px in the panel and the job dialog; `ActivityOrb`'s default is 32 px (was 20).

## Measured (2026-10-12)

`AIA_AI_STEP_EVENTS` on PostgreSQL 16 (local cluster), a research agent job with a recorded Bedrock
answer, 20 jobs each way, `Worker.run_once` wall time: **37.0 ms median off, 38.3 ms on** -- about
1.3 ms for the two writes, against a real model request of seconds. Burst: two event rows per model
request (an analysis run: 8 modules x up to 3 turns = at most 48 rows). Money: none; no call is
added. The browser: one `GET …/events?since=` per 1.5 s per open screen while a step runs, none
otherwise.

## Not done

- **Token streaming of the model's text**, by decision (above).
- **The UI workbench's fictional fieldwork** reports one progress line per run, so a workbench run
  shows little in the panel; a live AI run shows per-block counts.
- **No component test for the Deep Research and Interpretation panels' feed**; they share
  `StepActivityPanel`, `useStepActivity` and `deepResearchRunningStep`, each tested.

## Findings

(none)
