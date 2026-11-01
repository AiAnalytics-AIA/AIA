---
status: in-progress
chunks:
  - "[x] 1. The code: the route model's id and request profile, the respondent's temperature, Deep Research's thinking budget, a capability's effort (feature/sonnet-5-5-readiness)"
  - "[x] 2. Nigel accepts the Bedrock Marketplace agreement for Claude Sonnet 5.5 on develop's account"
  - "[ ] 3. Terraform: bedrock_model_id swapped to eu.anthropic.claude-sonnet-5-5 (infra session)"
  - "[x] 4. SSM writes under /aia/develop/: the id, prices, limits, profile and efforts below (infra session)"
  - "[x] 5. Deploy and probe: about 20 paid fieldwork calls, about USD 0.25, measuring truncation and output tokens (infra session)"
  - "[ ] 6. The acceptance study re-run on Sonnet 5.5, within the existing USD 25 allocation"
---
# Develop's AI route from Claude Sonnet 4.5 to Claude Sonnet 5.5

**Drafted:** 2026-10-25 · **Base:** `develop` @ `f7762d72` · **Owner:** the product owner, who decided
on 2026-10-25 (audit question AUD-7) to plan the switch now, develop first. Sonnet 4.5 is LEGACY on
Bedrock, end of life 2027-04-08. The infra session (`session_01LBR1SyjXK8uYR5VdBjGAEJ`) owns every AWS
step (chunks 2-5's execution); this plan's code session owns chunk 1.

## What the infra session read (develop's Bedrock account, 2026-10-25)

- The EU profile `eu.anthropic.claude-sonnet-5-5` is ACTIVE, with no `:N` suffix, as its family's ids.
- Prices, eu-central-1, Standard geo, USD per Mtok: input 2.20, output 11.00, cache read 0.11,
  cache write 2.75.
- Limits: 1M context window, 128K maximum output.
- It refuses a forced tool, a thinking budget and a sampling temperature, and thinks adaptively.

These are configuration, never code (`apps/executors/src/aia_executors/ai_runtime.py`'s module
docstring: no default model id, price or limit). The test
`test_develop_host_configuration.py::test_the_route_models_profile_reaches_the_worker_and_unset_changes_nothing`
holds the values above against both processes' startup checks; nothing reads them from there.

## What blocked the switch, and chunk 1's answer

1. **The route model's id.** `ai_runtime.py:597-602 @ f7762d72` required a `:` in
   `AIA_BEDROCK_MODEL_ID`, so the worker refused `eu.anthropic.claude-sonnet-5-5` at start
   (reproduced at f7762d72: `AIA_BEDROCK_MODEL_ID='eu.anthropic.claude-sonnet-5-5' must be an EU
   inference profile id pinned to a version`). Now held to the Lead's rule (`_eu_profile`, formerly
   `_lead_eu_profile` at `:288`): an `eu.` profile as Bedrock lists it, an alias ending `latest` still
   refused. Test: `test_ai_runtime_route_profile.py::test_the_sonnet_5_5_profile_id_is_accepted_as_bedrock_lists_it`.
2. **The route model's request profile.** Its catalog entry declared none, so it was sent a forced
   tool, a thinking budget where asked and a temperature. Now `AIA_BEDROCK_STRUCTURED_OUTPUT`,
   `AIA_BEDROCK_THINKING` and `AIA_BEDROCK_ACCEPTS_SAMPLING`, declared together or not at all, and an
   optional `AIA_BEDROCK_EFFORT`; a wrong or missing one stops the worker by name. Unset, the bytes are
   the same: `test_without_the_keys_the_route_model_is_sent_the_same_bytes_as_before` pins a signed
   body captured at f7762d72.
3. **The respondent's temperature.** `domain/ai_respondent.py:682 @ f7762d72` sent `temperature=0.0`,
   which `bedrock.py:269` refuses unsent for a profile without sampling: every fieldwork request would
   have failed. Fieldwork now reads the resolved model's profile at the preflight and sends no
   temperature to a model that refuses sampling (`build_request(sampling=)`). The respondent system's
   `model_binding` names a non-default profile (`RequestProfile.tag`: `…#auto_tool,adaptive,no_sampling[,effort=…]`),
   so its fingerprint, a validation's required binding and the fieldwork journal's replay key all
   move with the sampling choice and the effort; a default profile adds nothing, so every binding
   recorded before is unchanged. Test:
   `test_ai_fieldwork_answer_plans.py::test_a_model_that_takes_no_sampling_is_sent_no_temperature_and_named_with_its_profile`.
   Metodika's `response/request` step (`domain/methodology/response.py`) said "teplota 0" for every
   model; it now says "(přijímá-li ji model)" and explains the no-sampling case, its pin moved with
   `build_request` and the web fixture is regenerated (`tools/methodology_fixture.py`).
4. **Deep Research's thinking budget.** SSM sets `aia_deep_research_thinking_budget_tokens=2048`
   (`deep_research/runtime.py:121`), which `bedrock.py:264` refuses for an adaptive model. The
   composition (`deep_research_runtime.py`, not the frozen engine) drops it when the route thinks
   adaptively, after checking it as before; the API's ceiling does the same from `AIA_BEDROCK_THINKING`
   so the quote and the worker agree. Tests:
   `test_deep_research_journey.py::test_an_adaptive_route_model_is_sent_no_thinking_budget`,
   `test_deep_research_quote_api.py::test_an_adaptive_route_model_is_priced_without_the_thinking_budget`.
5. **Adaptive thinking and max_tokens.** Adaptive thinking counts against `maxTokens`. A policy may
   now set one capability's effort on an adaptive model (`ModelPolicy.efforts`, refused at load for a
   budgeted one): `AIA_AI_FIELDWORK_EFFORT` (`SIMULATION`) and `AIA_AI_RESEARCH_EFFORT`
   (`RESEARCH_REASONING`, `CRITIC` and `RESEARCH_LEAD`: the design jobs, analysis and Deep Research's
   agents). The caps are not changed here;
   chunk 5 measures them (below).

## Chunk 4: the SSM values (proposed; the infra session writes them)

| parameter | value | note |
|---|---|---|
| `aia_bedrock_model_id` | `eu.anthropic.claude-sonnet-5-5` | with chunk 3's Terraform grant |
| `aia_bedrock_input_usd_per_mtok` / `_output_` | `2.20` / `11.00` | read 2026-10-25 |
| `aia_bedrock_cache_read_usd_per_mtok` / `_cache_write_` | `0.11` / `2.75` | **set the write price**: unset, writes are charged at the input rate, below Bedrock's (see Findings) |
| `aia_bedrock_max_output_tokens` | `128000` | the model's ceiling |
| `aia_bedrock_context_window_tokens` | `200000` | the product owner's decision, 2026-10-25; see below |
| `aia_bedrock_structured_output` / `_thinking` / `_accepts_sampling` | `auto_tool` / `adaptive` / `false` | |
| `aia_bedrock_effort` | unset (the model's default, `high`) | |
| `aia_ai_fieldwork_effort` | `low` | to be measured in chunk 5 |
| `aia_ai_policy_version` | a new version | a model change changes results |

**The window decides the research reservation.** The worker refuses to start unless
`AIA_AI_RESEARCH_RESERVATION_USD` covers two calls at the window and the research cap (`from_env`).
Computed by the code's own `reservation_usd` at the prices above and a 4,096 research cap: 1.1901 USD
at a 200,000 window, 5.5901 USD at 1,000,000 (Sonnet 4.5 today: 1.3229 at 200,000). The Lead's
default 1.02 covers its 0.6893 minimum. Configuring 200,000 keeps every reservation at today's
scale, as the 2026-09-26 activation configured a conservative output ceiling
(`docs/architecture/bedrock-develop-activation-2026-09-26.md:13`). **Decided:** the product owner chose 200,000 on 2026-10-25, and the infra session was told. Raising it is a later decision.

## Chunk 5: what the probe measures (no number here is a guess)

About 20 fieldwork calls, about USD 0.25, on a fictional study, with `aia_ai_fieldwork_effort=low`
and today's caps (fieldwork 1,024; Lead 1,500; research 4,096; analysis 8,192). For each call: the
`stopReason` (any `max_tokens` is a truncation), output tokens, latency and cost from the usage
ledger. A cap is raised only on a measured truncation, to a value the measurement supports, with the
fieldwork reservation re-checked against the new ceiling. Then one design job, one analysis module
and one Lead turn at the route's default effort, the same readings, before chunk 6. Deep Research
needs its own reading: with the budget dropped, each agent kind's answer limit
(`request_limits.REQUEST_LIMITS`) no longer carries the 2,048 tokens of thinking headroom it had, while
adaptive thinking still counts inside it, so its truncation is measured before Deep Research is
switched on for Sonnet 5.5 (and `AIA_AI_RESEARCH_EFFORT` is the lever, not the frozen engine).

## Chunk 6: waits for tier B (decided 2026-10-28)

**The product owner's decision,** relayed by the PM coordinator at about 20:48 UTC: "Wait for tier B". Chunk 6 stays open until `mvp-acceptance-harness` chunk 7 (the tier B runbook and record) exists, and it runs then as tier B.

**Why chunk 6 could not run as written.** The acceptance study (`docs/migration/mvp-acceptance.md` § 1) has never run live, so there was nothing to re-run, and the full tier B was not runnable that night. It also needs:
- Deep Research measured on 5.5 (allocation lines A06-A08);
- the report-writer and map-interpreter workers (A05, LO9b);
- the client-source extraction (A10);
- a second person's approvals;
- the runbook itself.

**Prepared for the tier B runbook** (nothing run). The study's core path is brief, design jobs, the n = 300 panel run, analysis and the internal report, on `tests/acceptance/inputs/brief.json` and `concepts.json`, in a study named so that queries can find it.

- **Ceiling as a start shows it:** n × blocks × 0.15 (fieldwork) + 24.00 (analysis: 8 modules × 3 calls × 1.00). The probe confirms the rule: 78 × 0.15 + 24 = 35.70.
  - n = 300 at 2 blocks (`MAX_BLOCK_ITEMS` 8) gives USD 114.00; at 1 block, 69.00.
  - It is above the study's limit, so the start asks for the person's confirmation.
- **Expected spend at the 5.5 rates measured in chunk 5:**

  | Allocation line | Calls | Expected | Ceiling |
  |---|---|---|---|
  | A01 fieldwork | 600 at about USD 0.013 (the probe's 0.0100, plus a panel persona's profile and 8-item blocks) | ≈ USD 7.8 | 8.00, **tight** |
  | A02 analysis and repairs | 8 modules + repairs | ≈ USD 0.5-1.0 | 1.80 |
  | A04 design workers | two jobs at about 0.11-0.15 | ≈ USD 0.3 | 1.50 |
  | A03 Lead turns | about 10 at 0.043 | ≈ USD 0.4 | 2.60 |
  | **Core path total** | | **≈ USD 9-10.5** | |

  The allocation (`tests/acceptance/allocation.json`) was priced on Sonnet 4.5. Tier B re-prices A01-A04 from these rates before it runs.
- **Read-out:** five read-only queries filter the usage ledger, steps and attempts by the study's name: calls by capability with `finish_reason`, the calls that did not complete, the study's steps, failed attempts with their error, and spend by `agent_id` mapped onto A01-A04. CloudTrail is read for the instance's own session, to show every call's `modelId` is the tagged profile.

## Chunk 5: done (2026-10-28)

The probe ran on Nigel's ok, at 19:49 UTC, on a fictional study ("Sonnet 5.5 probe", the fictional Fio banka Sandbox client). It ran after develop's deploy, which rewrote `.env` from the switched SSM.

- **The run.** n = 78: a fictional roster at n = 20 drew only 6 donors, and the panel could not draw 20.
  - Ceiling USD 35.70. Started 20:16:12 and ended 20:22:10 UTC: fieldwork took 3 min 48 s; analysis and the report 2 min 8 s.
  - All 16 steps SUCCEEDED on their first attempt. The run cost USD 1.10.
- **The usage ledger, under policy `aia-bedrock-develop-2026-10-28-route-sonnet55`.** Total USD 1.35, the 19:45 smoke turn included.

  | capability | calls | outcome / finish | output tokens (avg / max) | latency ms (avg / max) | USD |
  |---|---|---|---|---|---|
  | SIMULATION (fieldwork, cap 1,024, effort low) | 78 | SUCCEEDED / COMPLETED | 314 / 322 | 2,845 / 34,065 | 0.7830 |
  | RESEARCH_REASONING | 9 | SUCCEEDED / COMPLETED | 1,608 / 2,807 | 10,904 / 15,836 | 0.3039 |
  | RESEARCH_REASONING | 2 | FAILED / COMPLETED (schema refused, then repaired) | 1,844 / 2,141 | 13,601 / 15,776 | 0.0698 |
  | RESEARCH_REASONING | 1 | FAILED / TRUNCATED | 4,096 | 28,121 | 0.0622 |
  | STUDY_LEAD (cap 8,000, effort medium) | 3 | SUCCEEDED / COMPLETED | 575 / 692 | 5,960 / 7,330 | 0.1284 |

- **CloudTrail**, read for the instance's own session alone, 19:42-20:29 UTC: 93 `Converse` calls, every one to `application-inference-profile/hnpij62nm89g`, none with an error. The calls by `maxTokens`:
  - 78 at 1,024 (fieldwork);
  - 10 at 8,192 (analysis: 8 modules and 2 repairs);
  - 2 at 4,096 (the design job: its truncated primary and its repair);
  - 3 at 8,000 (the Lead).
- **One truncation: the design job's primary** (`aia.research.build_questionnaire`, 20:23:57 UTC). It used all 4,096 output tokens of `AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS` at research effort `high`. Adaptive thinking counts inside that cap, which Sonnet 4.5, with no thinking, never spent. Its repair answered, and the proposal arrived complete; the cost was one wasted call (USD 0.0622, 28 s).
  - Raising the cap is the product owner's decision. Proposed: 8,192, the analysis cap, where no analysis call came near it (max 2,807).
  - **Raised to 8,192 on the product owner's decision.** He said "lets raise it" at about 20:35 UTC, relayed by the PM coordinator.
    - SSM `aia_ai_research_max_output_tokens` went from 4096 to 8192 (version 3).
    - `aia_ai_research_reservation_usd` stays 2.00, above the 1.2802 that two calls at 200,000 and 8,192 need.
    - `bin/write-env.sh` and the restart of the API and worker finished at 2026-10-28T20:38:27Z, on image `92041d11`. The worker started at 20:38:20 with no `AIRuntimeConfigError`, reading `AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS=8192`.
  - **Side effect:** the same key bounds Deep Research's per-kind output (`domain/deep_research/request_limits.py:172-205`), so its ceilings rise a little. An investigator call's reservation goes from 0.882 to 0.927, a planner, lead or synthesizer call's from 1.190 to 1.280.
  - **Rollback:** the same write with 4096 and the same restart.
  - Whether 8,192 holds shows in the next design job's `finish_reason`, which chunk 6 measures.
- **Analysis.** 2 of its 10 calls failed their schema at first and were repaired: a 5.5 reading for the schema-enforced-output work. Segmenty and Hypotézy stated nothing (not enough data).
- **The Lead** answered "Shrň mi, co běh zjistil" without the run's values, which are not in its context. That's the known gap until LO8's ResultsContext.
- **Deep Research** was not run on 5.5. It is measured on its own before anyone relies on it.

## Chunk 4: done (2026-10-28)

Nigel ran it from prompts the infra session prepared, relayed by the PM coordinator. Nothing was applied by an agent. The route now runs on `eu.anthropic.claude-sonnet-5-5` through the tagged profile `application-inference-profile/hnpij62nm89g`, so spend keeps the `Environment=develop` tag.

- **Chunk 3 (Terraform) did not gate this.** The tagged 5.5 profile and its IAM grant already existed (`aia-develop-lead`, develop-spend-attribution 1 and 2), and Terraform owns none of these SSM values (`infra/develop/main.tf:286-316`). Chunk 3 becomes a cleanup: one profile per model, keeping hnpij by a `moved` block, then the 4.5 profile `xz0r7v8bizok` and its grants removed after chunk 6.
- **SSM, set 19:26-19:30 UTC.**
  - The route's values are as § Chunk 4 lists them.
  - `aia_bedrock_effort=medium` and `aia_ai_research_effort=high`. The product owner chose to keep the Lead at medium: on the route binding, `STUDY_LEAD` takes the route's effort, since no capability key covers it (`ai_runtime.py:515-521`).
  - `aia_ai_fieldwork_effort=low`.
  - `aia_bedrock_invocation_target` points at hnpij.
  - `aia_ai_policy_version=aia-bedrock-develop-2026-10-28-route-sonnet55`.
  - The Lead's 11 own-model keys were deleted, because the worker refuses a Lead model equal to the route's (`ai_runtime.py:821-825`). `aia_ai_research_lead_max_output_tokens` (8000) and `_reservation_usd` (1.10) stay.
  - The values before are saved in CloudShell as `~/aia-s55-rollback-20261028T192600Z.json`: 23 values, route `eu.anthropic.claude-sonnet-4-5-20250929-v1:0` at 3.30 / 16.50 through `xz0r7v8bizok`, and policy `aia-bedrock-develop-2026-09-26-lead-sonnet55-20261026`.
- **Start-time checks**, computed beforehand with the code's `reservation_usd`. Each holds with the reservations unchanged:
  - research: 1.1901 needed, 2.00 set;
  - Lead: 1.0259 needed (window 154,519), 1.10 set;
  - client source: 0.3573 needed, 0.50 set.
- **The switch.** At 2026-10-28T19:42:33Z, `bin/write-env.sh` then `docker compose up -d api web worker`, image `1f633e5b` unchanged.
  - The worker logged "worker started" at 19:42:27 with no `AIRuntimeConfigError`.
  - Its environment shows every value above, and the deleted keys empty.
- **The smoke.** One Lead turn on a fictional study at 19:45:44 UTC:
  - the ledger row reads `STUDY_LEAD`, `eu.anthropic.claude-sonnet-5-5`, `SUCCEEDED`, `COMPLETED`;
  - 23,918 input and 570 output tokens, 6,212 ms, USD 0.0588896 (exactly 2.20 / 11.00 per Mtok);
  - under the new policy version.

  CloudTrail, read for the instance role's session alone: one `Converse` at 19:45:44 UTC, `modelId` `arn:aws:bedrock:eu-central-1:311141567391:application-inference-profile/hnpij62nm89g`, `maxTokens` 8000, no error.
- **Before the switch, nothing could resume on 5.5 by itself.**
  - Every `WAITING_PROVIDER` step was `ai_runtime_unavailable`: unpaid, no `runnable_after`, never timer-resumed (`domain/workflow.py:797-798`).
  - The 2 `AWAITING_BUDGET` steps wait for a person.
  - The 6 RUNNABLE sociomapping steps sit in FAILED runs (§ Findings).

## Chunk 2: done (2026-10-27)

- **The agreement.** Accepted by Nigel on 27 Oct from the Bedrock console. `get-foundation-model-availability`
  for `anthropic.claude-sonnet-5-5` answered agreement `AVAILABLE`, authorization `AUTHORIZED` at 13:22 UTC,
  read-only, by the second account's PM coordinator.
- **The first Lead turns on develop.** Nigel sent the Lead "Shrň mi zadání" on a fictional study at 14:35 UTC,
  and it answered. CloudTrail then showed eight `Converse` calls from the role `aia-develop-instance` to
  `eu.anthropic.claude-sonnet-5-5`, 14:32-14:38 UTC, none with an error.
- **What stays open.** That is the Lead's own model (`AIA_AI_RESEARCH_LEAD_MODEL_ID`). Chunks 3-6 move the
  *route* model, which is still `eu.anthropic.claude-sonnet-4-5-20250929-v1:0` in SSM.

## Findings

- **An unset cache-write price charges writes below their price.** `ModelPricing.cost_usd`
  (`domain/ai_models.py:174-206 @ f7762d72`) charges cache writes at the input rate when
  `cache_write_usd_per_mtok` is `None`, which the docstring calls an overstatement; for Sonnet 5.5 a
  write costs 2.75 against 2.20 input, so an unset price under-states it. Reproduction:
  `ModelPricing(input_usd_per_mtok=2.2, output_usd_per_mtok=11).cost_usd(input_tokens=0,
  output_tokens=0, cache_write_input_tokens=1_000_000)` is 2.2, the real cost 2.75. Consequence today:
  none measured, since AIA sends no cache point and Bedrock reports no writes; the ceiling already
  takes the larger of the two. Smallest fix: set the price (chunk 4); a code fix would refuse an
  unknown write price once writes are possible. Test that would catch it:
  `test_ai_runtime_route_profile.py::test_a_cache_write_is_charged_at_its_own_price`, with the price
  unset.
- **A run that fails leaves its other ready steps RUNNABLE for good.** A run's status is FAILED as
  soon as any step has failed. FAILED outranks RUNNABLE (`domain/workflow.py:852-861 @ e53fddbd`,
  `derive_run_status` at `:864`), and `claim_next` takes no step whose run is FAILED
  (`infrastructure/workflow_repository.py:1013-1031 @ e53fddbd`). So a step that was already
  RUNNABLE, on a branch the failure does not depend on, stays RUNNABLE: nothing claims it, cancels
  it or skips it.
  - **Seen on develop**, read 2026-10-28 13:20 UTC, before the route switch: 6 `research_sociomapping`
    steps (`domain/workflow_templates.py:245 @ e53fddbd`, depending only on `run`) were RUNNABLE in
    FAILED runs, with no cancel flag and no `runnable_after`.
  - **Reproduction:** a run of two independent steps, both RUNNABLE. Fail one terminally;
    `claim_next` then returns nothing, and the other stays RUNNABLE.
  - **Consequence:** no cost, since the experimental Sociomapping calls no model. A failed run's step
    list shows a step as waiting in the queue that will never run. A sweep for "RUNNABLE work" (such as
    the precondition before this switch) counts it as live and has to be explained away.
  - **Smallest fix:** when a run's derived status becomes FAILED, move its RUNNABLE and BLOCKED steps
    to SKIPPED with the reason `run_failed`, in the same transaction.
  - **Test that would catch it:**
    `test_workflow_repository.py::test_a_failed_run_leaves_no_step_runnable`.
  - This is a hypothesis about intent until the workflow plan's owner says whether a FAILED run's
    siblings are meant to stay offered.
- **`ssm delete-parameters` takes at most 10 names.** The chunk 4 prompt deleted the Lead's 11
  own-model keys in one call, and it stopped there at 19:26 UTC on 2026-10-28 with a
  `ValidationException` ("Member must have length less than or equal to 10"). By then all 15 writes
  had landed, so SSM was half-written: the route model and the Lead's own model both read
  `eu.anthropic.claude-sonnet-5-5`, a pair the worker refuses at start (`ai_runtime.py:821-825`).
  - **Consequence:** no running process changed, because only `bin/write-env.sh` (run by a deploy or
    by prompt C) reads SSM. A deploy in that window would have stopped the worker, so merges into
    develop were held until the deletes and the restart were done.
  - **Fix for any later prompt:** split the deletes into calls of at most 10 names (here 10, then
    `invocation_target`).
  - **No order of single writes is safe to start between.** Deleting first leaves the Lead on the
    4.5 route, where its 1.10 reservation is below that model's 1.2838 minimum for an 8,000-token
    turn (`ai_runtime.py:1023-1029`), and the worker refuses that state too. So the guard is that
    nothing reads SSM until every write and delete is done: hold deploys, and restart only from
    prompt C, after the "after" list matches.

## Doc follow-up (for the docs PR)

See the PR description: CLAUDE.md § 2's `ai_runtime.py` entry, ADR 0010's route model row, and an
`AGENTS.md` note on adaptive thinking against `maxTokens`.
