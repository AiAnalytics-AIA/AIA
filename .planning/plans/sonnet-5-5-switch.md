---
status: in-progress
chunks:
  - "[x] 1. The code: the route model's id and request profile, the respondent's temperature, Deep Research's thinking budget, a capability's effort (feature/sonnet-5-5-readiness)"
  - "[ ] 2. Nigel accepts the Bedrock Marketplace agreement for Claude Sonnet 5.5 on develop's account"
  - "[ ] 3. Terraform: bedrock_model_id swapped to eu.anthropic.claude-sonnet-5-5 (infra session)"
  - "[ ] 4. SSM writes under /aia/develop/: the id, prices, limits, profile and efforts below (infra session)"
  - "[ ] 5. Deploy and probe: about 20 paid fieldwork calls, about USD 0.25, measuring truncation and output tokens (infra session)"
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

## Doc follow-up (for the docs PR)

See the PR description: CLAUDE.md § 2's `ai_runtime.py` entry, ADR 0010's route model row, and an
`AGENTS.md` note on adaptive thinking against `maxTokens`.
