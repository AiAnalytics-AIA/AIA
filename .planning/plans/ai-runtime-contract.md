# AI runtime contract (Phase 4, first slice)

**Status:** in progress · **Owner:** ai-runtime · **Started:** 2026-09-22 ·
**Branch:** `claude/eager-mendel-3bom5p`

## Problem

Nothing in AIA can call a model. The rules a call must obey exist and are tested
(`aia_core.domain.providers`, `aia_core.domain.residency`, `decide_recovery` in
`aia_core.domain.workflow`), but no code joins them into one boundary. Every
later agent (research-engine first) would otherwise invent its own call path,
and the reference behaviours that matter more than provider convenience would
be re-implemented per call site, or not at all:

- no silent fallback (reference `ai_router` `allow_fallback=False`; R11);
- the ten-way error taxonomy, with quota and capacity kept apart;
- provider request ids retained, so a possibly-billed call can be reconciled;
- structured output checked by a deterministic validator, not by the model;
- budget preflight and residency egress checked *before* anything leaves;
- a model, a tool argument or a request body never supplying client/study scope.

## Approach

AIA owns the contract (ADR 0005 decision A, *Accepted*). Providers sit under it
as adapters. LiteLLM is not used (decision B is still *Proposed*); if it is
adopted later it becomes one more `ProviderAdapter`, not the interface.

Layered as the rest of the codebase:

| Layer | Module | Holds |
|---|---|---|
| Domain | `domain/ai_models.py` | `ModelCapability`, `ModelDescriptor`, `ModelPricing`, `ModelBinding`, `ModelPolicy`, `ModelRegistry` (pure resolution, fail closed), config parsing that fails closed |
| Domain | `domain/ai_contracts.py` | `ProviderErrorKind` (the ten + OTHER), `ProviderError`, `Delivery`, `FallbackPolicy`, structured-output validation and strictification, `AgentDefinition`, `ModelRequest`, `ModelResult`, `ModelUsage`, `CallProvenance`, `AIUsageEvent`, `ModelCallFailed` |
| Domain | `domain/ai_execution.py` | **The StepExecutor contract**: `ExecutionContext`, `CallJournal`, `ReservationView`, `ModelGateway` protocol, `recovery_inputs()` |
| Domain | `domain/ai_tools.py` | `ToolDefinition`, `ToolRegistry`, scope-key refusal |
| Application | `application/model_gateway.py` | `GovernedModelGateway` — the one implementation of the semantics |
| Infrastructure | `infrastructure/model_adapters/` | `ProviderAdapter` implementations: Anthropic Messages, OpenAI Chat Completions, Claude Code CLI result; `RecordedTransport` replaying recorded exchanges |
| Infrastructure | `infrastructure/ai_usage_repository.py` + table + migration | Append-only `ai_usage_events` ledger, with compensating entries for uncertain-call resolution |
| Infrastructure | `infrastructure/ai_call_journal.py` | `CallJournal` over `WorkflowRepository`'s *public* methods — no edit to platform-runtime code |

Order inside `GovernedModelGateway.invoke`, each step a way the rule is broken in
practice if skipped:

1. scope is an issued `StudyContext` (never a model argument);
2. cancellation checked;
3. registry resolves capability → `(provider, model, route)` under a named policy
   version; unknown capability, unknown pin or unpermitted provider **fails closed**;
4. egress authorised by `EgressPolicy` for the request's data class and the
   binding's route; route provider must equal binding provider;
5. budget preflight against the **reservation** the durable layer took
   (`ReservationView` from the context, not the request); paid route with no
   reservation is refused;
6. journal records the dispatch **before** the adapter sends;
7. adapter sends; its `ProviderError` carries kind, request id, retry-after and
   whether the provider responded (`Delivery`);
8. structured output validated by Pydantic in strict mode; one same-model repair
   attempt on `SCHEMA`, recorded as its own call;
9. an `AIUsageEvent` per call, success or failure, with request id and provenance;
10. explicitly authorised fallback only: named alternates, named authoriser, only
    after a failure whose billing outcome is known, each alternate re-checked
    through 3–5.

## Decisions taken here

- **Model substitution only from the versioned policy.** The reference swapped a
  retired id for a visible equivalent after listing the account's models. Here a
  retirement is declared in `ModelPolicy.retirements` and the resolution records
  `substituted_from`. A live model listing never changes what runs.
- **No in-call capacity retry.** The reference retried Anthropic capacity
  5 s → 15 s → 45 s inside the call. ADR 0005 condition 1 forbids unrecorded
  retries, so capacity raises `PROVIDER_CAPACITY` and the step parks in
  `WAITING_CAPACITY`; the backoff is the scheduler's (platform-runtime).
- **`WAITING_CREDITS` is `WAITING_PROVIDER`.** The reference name
  (`test_1788_ui_maps_waiting_credits_as_paused`) maps to the frozen v2.1
  vocabulary; no new state is added. `ARCHITECTURE.md §10` is corrected.
- **Structured output contract = a Pydantic model.** Its JSON Schema is what the
  provider sees; `model_validate_json(strict=True)` is the deterministic
  validator. No new dependency. Schema fingerprint recorded in provenance.
- **Strict tier skipped, never forced.** A schema that is not strict-compatible
  is sent non-strict rather than rewritten (reference `ai_router` docstring at
  line 143: mutating the contract silently changes the returned shape).

## Trade-off accepted

The runtime is built and tested against recorded exchanges only: no adapter has
made a live call, so provider-side drift from the recorded shapes will be found
by the first live run rather than by CI.

## Chunks

- [x] 1. Domain: model catalog, policy, registry — `domain/ai_models.py` + `tests/test_ai_models.py` (46)
- [x] 2. Domain: call contracts, taxonomy, structured output — `domain/ai_contracts.py` + `tests/test_ai_contracts.py` (70)
- [x] 3. Domain: StepExecutor contract + ToolRegistry — `domain/ai_execution.py`, `domain/ai_tools.py` + `tests/test_ai_tools.py` (36)
- [x] 4. Application: `GovernedModelGateway` — `application/model_gateway.py` + `tests/test_model_gateway.py` (40)
- [x] 5. Infrastructure: three adapters over transport protocols + 42 recorded exchanges — `infrastructure/model_adapters/` + `tests/test_model_adapters.py` (74)
- [x] 6. Infrastructure: `ai_usage_events` (migration `1cd2a5acd29f`), `AIUsageRepository`, `WorkflowCallJournal` + `tests/test_ai_usage_ledger.py` (17)
- [x] 7. Enforcement + docs: `layer_check` provider-SDK rules (12 → 14), `ai-runtime.md`,
      `ai-step-executor-contract.md`, ADR 0005 implementation note, ARCHITECTURE /
      CLAUDE / AGENTS, data-model, domain-map, parity matrix, OI-32 (filed as OI-6, renumbered on merge with main), PROGRESS

All seven landed on PR #28.

## Status

### Contract / API introduced

| Name | Module | Role |
| --- | --- | --- |
| `ModelCapability` | `domain/ai_models.py` | What domain code asks for instead of a model |
| `ModelDescriptor`, `ModelPricing`, `ModelBinding` | `domain/ai_models.py` | Catalog entry, prices, `(provider, model, route)` |
| `ModelPolicy`, `ModelRegistry`, `parse_model_config` | `domain/ai_models.py` | Versioned capability → binding; fails closed at load and at resolution |
| `AgentDefinition` | `domain/ai_contracts.py` | Capability, prompt id/version, closed output contract, allowed tools, ≤1 repair |
| `ModelRequest`, `ModelResult`, `ModelUsage`, `CallProvenance`, `FallbackPolicy` | `domain/ai_contracts.py` | ADR 0005's shapes; no scope field on the request |
| `ProviderErrorKind`, `Delivery`, `ProviderError`, `ModelCallFailed` | `domain/ai_contracts.py` | Ten-way taxonomy + OTHER; whether the provider answered |
| `AIUsageEvent`, `UsageOutcome`, `CostBasis` | `domain/ai_contracts.py` | Append-only ledger record |
| `ModelGateway`, `ExecutionContext`, `CallJournal`, `ReservationView`, `recovery_inputs` | `domain/ai_execution.py` | The step-executor seam |
| `ToolRegistry`, `ToolDefinition`, `ToolInvocation` | `domain/ai_tools.py` | Registered deterministic tools; scope refused in arguments |
| `GovernedModelGateway` | `application/model_gateway.py` | The one implementation of the semantics |
| `ProviderAdapter` impls, `HttpTransport`, `CliRunner`, `CredentialSource`, recorded doubles | `infrastructure/model_adapters/` | Transport, classification only |
| `AIUsageRepository`, `WorkflowCallJournal`, `InMemoryCallJournal` | `infrastructure/` | Ledger persistence and the durable journal |

### Provider semantics covered

| Behaviour | Test |
| --- | --- |
| No silent provider fallback; explicit fallback only with named alternates, kinds and authoriser | `test_model_gateway.py::test_no_fallback_without_an_explicit_policy`, `::test_explicit_fallback_runs_and_is_recorded` |
| No fallback while a failed call's billing is uncertain | `::test_no_fallback_while_the_failed_call_may_have_been_billed` |
| 10-way classification, one vocabulary with `classify_failure` | `test_ai_contracts.py::test_taxonomy_and_workflow_tag_map_are_one_vocabulary`; every kind produced by a recorded exchange: `test_model_adapters.py::test_fixtures_cover_every_error_kind_an_adapter_can_emit` |
| Provider/model provenance, `served_model`, `substituted_from`, schema fingerprint | `test_model_gateway.py::test_structured_call_on_a_metered_route`, `::test_retired_pin_is_recorded_on_every_entry` |
| Structured output, deterministic schema validation, one repair | `test_ai_contracts.py` (validation block), `test_model_gateway.py::test_one_same_model_repair_is_made_and_recorded` |
| Budget preflight before paid calls, including repairs | `::test_budget_preflight_refuses_a_call_the_reservation_cannot_cover`, `::test_repair_is_budget_checked_like_any_call` |
| Egress/residency before sending | `::test_egress_is_refused_before_dispatch`, `::test_route_approved_for_another_provider_is_refused` |
| `WAITING_CREDITS` (→ `WAITING_PROVIDER`) / `WAITING_CAPACITY` | `::test_quota_parks_in_waiting_provider_with_its_reset_and_request_id`, `::test_capacity_parks_in_waiting_capacity`; out-of-credit fixtures `anthropic/error_credit_balance`, `openai/error_insufficient_quota` |
| Provider request id retained on success and failure | the recorded-exchange suite; `test_model_gateway.py::test_explicit_fallback_runs_and_is_recorded` |
| Paid-call uncertainty recoverable | `test_ai_usage_ledger.py::test_worker_killed_mid_call_parks_for_a_person_and_the_ledger_can_find_it`, `::test_uncertain_outcome_leaves_the_attempt_unknown_and_resolves_to_zero` |
| No client/study scope from model arguments | `test_ai_tools.py::test_model_supplied_scope_is_refused_before_validation`, `::test_execution_context_refuses_anything_but_an_issued_scope`, `test_ai_contracts.py::test_model_request_has_no_scope_field` |
| Subscription runtime cannot silently become metered | `test_model_adapters.py::test_claude_code_invocation_scrubs_every_credential_override` |

### Reference parity coverage

- **Behavioural, against the reference's documented contract**
  (`AIA-reference` @ `678e298`: `ai-prompt-inventory.md`,
  `configuration-contract.md`, `high-risk-behaviors.md` R10/R11): the ten tags,
  `allow_fallback=False` as the production contract, skip-don't-mutate strict
  tier, forced-tool structured output, fail-closed configuration (the
  `config.edition` defect not repeated).
- **Not run against reference code.** The reference archive is withheld
  (`REF-WITHHELD-REFERENCE-ARCHIVE`) and `AIA_LEGACY_REFERENCE` is not available,
  so `ai_router.classify_provider_exception` itself was never executed. The
  recorded fixtures are **hand-authored from provider API references, not live
  captures**, and each file says so.
- **Deliberate deviations:** retirement substitution from the versioned policy
  rather than a live model listing; no in-call capacity retry (5/15/45 s);
  `MODEL` is terminal rather than "substitute".

### Decisions still needed

D6 route approval per data class · D7 live transport · D8 credential storage ·
D9 catalog/prices/policy ownership · D10 capacity backoff and per-run cap
(platform-runtime). All in `PROGRESS.md` *Decisions needed*. Plus OI-32
(uncertain resolution → study spend), owned by platform-runtime.

### Dependency for research-engine

Available now, and enough to build and test agents offline:

- Define `AgentDefinition`s (capability, prompt id/version, closed Pydantic
  output contract, allowed tools) and `ToolDefinition`s.
- Call `ModelGateway.invoke` with a `ModelRequest` naming a capability and a
  `DataClass`; test with `GovernedModelGateway` over a scripted adapter and
  `InMemoryCallJournal`, as `test_model_gateway.py` does.
- Promote prompt-stated constraints (the analysis metric set, simulation factor
  bounds) into output contracts, which the gateway now enforces.

Not available, and blocking a real run: a worker (PROGRESS #2), D6-D9. Also not
provided here and research-engine's to decide: **where versioned prompt assets
live** — `AgentDefinition` carries `prompt_id`/`prompt_version`, the gateway
records them, but there is no prompt store (reference rebuild requirement 1).

## Review outcome

Codex review on #28 (four findings, all verified and fixed): adapters are now bound
per route, not per provider (P1); OpenAI usage with `cached_tokens > prompt_tokens`
is carried as unreported and `ModelUsage` refuses negatives inside `send` (P2);
`resolve_uncertain` refuses non-finite costs (P2); every ledger entry and the
result provenance carry an `input_fingerprint` (P2). 

Merge of `main` @ a15be65 (worker, lease-fenced `WorkflowRepository`): the journal
now passes `worker_id`, fences dispatch before writing the ledger row, commits
an outcome's ledger row before its fenced attempt write, and reports each call's
own cost because `mark_paid_call_outcome_known` now adds rather than sets --
passing the running total would have double-charged every multi-call attempt
(`test_several_calls_in_one_attempt_are_charged_once_each`,
`test_a_failed_attempt_is_charged_for_every_billed_call`, both shown to fail
against the old journal). OI-6 renumbered OI-32; the ledger migration re-parented
onto `85637e58c7dd`. Remaining fields filled in when archived.
