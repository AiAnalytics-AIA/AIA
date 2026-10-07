---
status: done
chunks:
  - "[x] 1. This plan: per-kind request limits, derived reservations, measured before code"
  - "[x] 2. Domain: the request-limit table, role to kind, kind budgets derived from the model's prices"
  - "[x] 3. Executors: every request carries its kind's output limit, window and reservation"
  - "[x] 4. API: the ceiling priced from the same keys, per kind"
  - "[x] 5. Measurements, findings and doc follow-up"
---
# Deep Research — per-kind request limits and reservations (chunk 23, first part)

**Status:** done (on its pull request) · **Parent:** [deep-research-web-search.md](deep-research-web-search.md)
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

**A method change, so a new harness** (the owner's review, 2026-10-07). A shorter answer limit
or a refused oversize request can change a track, a verification, a stop and so the bundle.
`HARNESS_VERSION` moves to `aia-deep-research-harness-2`; it is already in every reuse key
that crosses runs (the track, verification, independent-verification, synthesis and brief
fingerprints) and in `runtime.versions()`, which also records `REQUEST_LIMITS_VERSION`. New
requests are frozen for harness 2. A harness-1 request stays readable (the request literal
accepts both, so its fingerprint and its sealed bundle keep verifying) and is never executed:
the plan step refuses it (`harness_changed`, start a new run). A test pins the limit table to
the harness, so the table cannot move again without it.

**Deliberately unchanged:** the engine's payloads, the presets and call counts, the gateway's
input bound.

## Trade-off

A request larger than its kind's window is refused where today it would have been sent. The
windows are sized above a heavy turn and batch; a refusal is visible (the gate, the size) and
costs nothing. An answer longer than its kind's limit is cut, fails its schema and takes its one
repair, as any off-contract answer does today.

## Measurements

Ceilings at the same settings as § Why, 12 web and 2 internal tracks, before and after
(`call_bounds` priced by `kind_budgets`, on `e8a23e3`):

| Preset, mode | model calls | one flat reservation | per kind | lower by |
|---|---|---|---|---|
| Standard, planned | 78 | $113 | $77 | 32 % |
| Standard, agent-directed | 211 | $305 | $216 | 29 % |
| Standard, lead | 152 | $220 | $155 | 29 % |
| Deep, planned | 102 | $147 | $102 | 31 % |
| Deep, agent-directed | 391 | $565 | $405 | 28 % |
| Deep, lead | 410 | $593 | $422 | 29 % |
| Exhaustive, planned | 162 | $234 | $162 | 31 % |
| Exhaustive, agent-directed | 523 | $756 | $541 | 29 % |
| Exhaustive, lead | 883 | $1,277 | $891 | 30 % |

Per request: planner, lead, synthesizer $1.446 (unchanged); investigator $1.048; internal
investigator $1.384; verifier $0.795. The spend API's one-track EXHAUSTIVE planned run: $15.76
against $21.69 (`test_deep_research_spend_api.py`).

## Findings

- **The engine method moves for a cost-governance finding (ADR 0021 decision 7's exception).**
  Every request reserved the whole window and output limit
  (`aia_executors/ai_runtime.py:342-361 @ d2e038a`), so a run's ceiling was priced at a worst
  case most requests cannot reach, and a study's spend limit was checked against it. Per-kind
  limits are the fix; because they change what a request can return, the harness moves with
  them. Tests: `test_the_request_limits_move_only_with_the_harness`,
  `test_an_identical_run_under_the_new_limits_reuses_nothing_made_under_the_old`,
  `test_a_request_frozen_under_harness_one_is_never_executed_under_harness_two`.

- **The ceiling stays an order of magnitude above § 9's estimates, and the input bound is why.**
  An investigator's reservation is $1.048: $0.864 of it is its 144,000-token window priced at
  the input rate, twice (`request_limits.reservation_usd`), because the gateway bounds input
  tokens by UTF-8 bytes (`application/model_gateway.py:107-124 @ d2e038a`), several times the
  real count for Czech text, and the repair must fit what the primary may have spent. The
  answer limits take the output term from $0.246 to $0.184. A ceiling is a bound, so this is
  correct, not a defect; the next lever is a sound, tighter input bound (a provider token
  count before dispatch) or showing an expected cost beside the ceiling. Test that would
  measure it: `test_deep_research_ceiling_journey.py`'s per-kind holds, against the ledger's
  `input_tokens`. Not done here.
- **The windows and answer limits are judgment, not measurement.** No live run's request sizes
  exist yet (develop has Deep Research off); the sizes in § Approach are from the code's caps
  and plausible content. Chunk 25/26's runs measure them; until then the values are proposed
  with the presets (chunk 1).

## Doc follow-up

- ADR 0021 decision 7 (the frozen engine): add "Moved once, to harness 2, for per-kind
  request limits (`deep-research-request-limits.md`, a cost-governance finding); harness-1
  requests stay readable and are never executed."

- `CLAUDE.md` § 2, `aia_core/domain/deep_research/`: add "`request_limits.py` each model
  kind's window and output limit (proposed) and its reservation, derived from the route's
  prices; the worker and the API derive the same".
- `CLAUDE.md` § 2, `deep_research_runtime.py`: "each kind of request reserves its own amount
  (`request_limits`); `AIA_AI_RESEARCH_RESERVATION_USD` is the design jobs' only".
- `docs/architecture/deep-research.md` (cost section) and `docs/architecture/research-agents.md`
  line 81: the research reservation no longer prices Deep Research; the API reads
  `AIA_BEDROCK_*_USD_PER_MTOK`, `AIA_BEDROCK_CONTEXT_WINDOW_TOKENS`,
  `AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS`, `AIA_DEEP_RESEARCH_THINKING_BUDGET_TOKENS` for a run's
  ceiling.
- `.planning/plans/deep-research-web-search.md` chunk 23 and § 13: "per-kind reservations done
  (`deep-research-request-limits.md`); switches, routes and dated prices remain"; § 13 gets
  the measurements above.
- `.planning/open-items.md`: the first finding above, as a new OI.
