---
status: in-progress
chunks:
  - "[x] 1. This plan: per-kind request limits, derived reservations, measured before code"
  - "[x] 2. Domain: the request-limit table, role to kind, kind budgets derived from the model's prices"
  - "[ ] 3. Executors: every request carries its kind's output limit, window and reservation"
  - "[ ] 4. API: the ceiling priced from the same keys, per kind"
  - "[ ] 5. Measurements, findings and doc follow-up"
---
# Deep Research — per-kind request limits and reservations (chunk 23, first part)

**Status:** in-progress · **Parent:** [deep-research-web-search.md](deep-research-web-search.md)
chunk 23 ("per-kind reservations first") · **Base:** `develop` @ `d2e038a` (PR #167 merged)

## Why

Every Deep Research model request reserves the same amount: the research agents'
`AIA_AI_RESEARCH_RESERVATION_USD`, which the worker requires to cover two calls at the whole
context window and the whole research output limit (`aia_executors/ai_runtime.py:342-361 @
d2e038a`). A verifier batch and an investigator turn are priced like a synthesizer that may read
the window, so a run's ceiling (`domain/run_cost.py`, chunk 22) prices every one of hundreds of
requests at that worst case.

Measured before code (develop-like settings: $3 / $15 per MTok, 8,192 output tokens, a 200,000
token window, 12 web and 2 internal tracks; `call_bounds` over each preset and mode):

| Preset, mode | model calls | ceiling today | input envelopes only | output term alone |
|---|---|---|---|---|
| Standard, planned | 78 | $113 | $75 | $19 |
| Standard, agent-directed | 211 | $305 | $210 | $52 |
| Standard, lead | 152 | $220 | $150 | $37 |
| Deep, lead | 410 | $593 | $410 | $101 |
| Exhaustive, lead | 883 | $1,277 | $869 | $217 |

Input envelopes alone remove about 30 %; every call priced at the full output limit, twice for
its repair, is a floor they cannot touch. The owner chose envelopes **and** per-kind output
limits (2026-10-06).

## Approach

**One table, in the domain** (`domain/deep_research/request_limits.py`, pure). Per model kind of
`budgets.CallKind` (triage excepted: its own model, wired with its route later in chunk 23):

- `window_tokens`: the window a request of this kind must fit, in the same terms the executor's
  size check already uses (request bytes + 5 × output limit + 2048, `_shared.py:91-106`). `None`
  is the model's whole context window.
- `answer_tokens`: the output limit of this kind's answer. `None` is the research output limit.
  With thinking on, thinking is added on top (thinking is part of the output limit), never above
  the research output limit.

Proposed values (`REQUEST_LIMITS_VERSION`, for chunk 1's sign-off with the presets):

| Kind | window | answer | why |
|---|---|---|---|
| planner, lead, synthesizer | model's | research limit | one to a few calls per run; inputs scale with the run (every track, every finding) |
| investigator (planned round, agent-directed turn) | 144,000 | 6,144 | a heavy turn: 18,000 chars read, 40 results, 60 links, the track's sources and findings ≈ 103 KB; up to 12 evidence items per answer |
| internal investigator | model's | 6,144 | up to 12 knowledge items of 12,000 chars; once per internal track |
| verifier (planned, independent) | 112,000 | 4,096 | 12 items with excerpt, measures and up to 5 related claims ≈ 72 KB; 12 verdicts of ≤ 500 chars |

**Derived, never configured.** A kind's output limit is
`min(research_limit, answer + thinking)`; its window is `min(context_window, window)`; its
reservation is the worker's existing rule with its own window and limit:
`2 × (window × max(input, cache write, cache read) + output limit × output price) / 1e6`. The same
invariant as today holds per kind: the primary's ceiling fits, and the repair (the original, the
answer, the instruction) fits what the primary left.

**Enforced where requests already pass.** `_Step._request` sets the kind's output limit;
`_Step._send` checks the kind's window (an oversize request is refused by the existing
`CONTEXT_WINDOW` gate, nothing reserved, nothing sent, the track recorded incomplete, as today
for the whole window) and reserves the kind's amount (`StepModelCaller.invoke(...,
reservation_usd=)`). The gateway's own per-call check is unchanged.

**One rule for the worker and the API.** The worker derives the budgets from its model settings
at composition; the API derives the same from the same keys (the model's prices, window, research
output limit, thinking budget) and prices the ceiling per kind. Any missing key is an unknown
ceiling, never a zero. `AIA_AI_RESEARCH_RESERVATION_USD` stays the design jobs' reservation and
stops pricing Deep Research.

**Deliberately unchanged:** fingerprints and recorded versions (the output limit was never in
them; changing it does not invalidate a stored track), the engine's payloads, the presets and
call counts, the gateway's input bound.

## Trade-off

A request larger than its kind's window is refused where today it would have been sent. The
windows are sized above a heavy turn and batch; a refusal is visible (the gate, the size) and
costs nothing. An answer longer than its kind's limit is cut, fails its schema and takes its one
repair, as any off-contract answer does today.

## Findings

(Recorded as they are found.)

## Doc follow-up

(Written when the code lands.)
