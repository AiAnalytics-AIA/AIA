# AI runtime

**Status: Bedrock respondent fieldwork is implemented and was activated for
fictional Class C on develop on 2026-09-26. Native design proposal jobs merged in
PR #63 (`85fa951`) with a separate switch, off by default; they are in every develop
build since deploy run 31, and no live design call is recorded. Analysis/report
execution and owned web retrieval remain required for the complete workflow
([research-journey.md](research-journey.md)).**

The dated [activation evidence](bedrock-develop-activation-2026-09-26.md) records
20 successful requests, $0.2303301, settled reservations and the exact authorised
scope. This is a historical acceptance result, not approval for another live run.
[Native Research jobs](research-agents.md) describe the new proposal path.

| Piece | State |
| --- | --- |
| Provider policy, budget rules, failure taxonomy (`aia_core.domain.providers`, `workflow`) | Implemented, parity-verified |
| Budget reservations and enforcement (`workflow_repository`) | Implemented, tested under contention |
| EU residency and the fail-closed egress boundary (`aia_core.domain.residency`) | Implemented, tested |
| Capabilities, catalog, `ModelPolicy`, `ModelRegistry` (`domain/ai_models.py`) | **Implemented** — fail-closed resolution and config parsing |
| Call contract: `AgentDefinition`, `ModelRequest`, `ModelResult`, `AIUsageEvent`, the ten-way `ProviderErrorKind`, structured-output validation (`domain/ai_contracts.py`) | **Implemented** |
| `ModelGateway` contract and the step-executor seam (`domain/ai_execution.py`) | **Implemented** — see [ai-step-executor-contract.md](ai-step-executor-contract.md) |
| `ToolRegistry` (`domain/ai_tools.py`) | **Implemented** — scope never from arguments |
| `GovernedModelGateway` (`application/model_gateway.py`) | **Implemented** — the one implementation of the semantics |
| Adapters (`infrastructure/model_adapters/`) | Bedrock Converse is the deployed model path. Anthropic, OpenAI and Claude Code adapters remain recorded-exchange compatibility code; they are not connected product settings |
| AI usage ledger `ai_usage_events` + `AIUsageRepository` + `WorkflowCallJournal` | **Implemented** — append-only, compensating entries |
| Live transport and credentials | Bedrock HTTP transport with SigV4 and the develop instance role is implemented. No direct Anthropic key or Claude Code login is required |
| Approved route | `bedrock-eu-primary`, accepted for fictional Class C on develop only ([ADR 0010](adr/0010-bedrock-eu-inference-route.md)). Pinned EU profile, six destinations; retention unspecified. No approval for confidential Class A/B follows from it |
| Generalized metered-cost ledger for non-model tools | **Not built.** See *Cost accounting* |
| Research prompts and agents | Respondent fieldwork is deployed and was activated; eight native design/advice contracts, prompts and proposal jobs are merged (PR #63) and off by default. Interpretation/report and Deep Research integration remain incomplete |

The gateway, adapter, ledger and real worker are checked against recorded
exchanges and delivery failures. The isolated fictional fieldwork acceptance also
exercised the deployed Bedrock path. Native proposal jobs have recorded-adapter
tests; they have not been activated or tested with a live model.

## The call path

```
domain code ──ModelRequest──▶ GovernedModelGateway.invoke(request, ExecutionContext)
                                 1 resolve   ModelRegistry: capability → (provider, model, route)
                                 2 egress    EgressPolicy.authorise(issued scope, data class, route)
                                 3 budget    ceiling + committed ≤ reservation   (metered only)
                                 4 journal   DISPATCHED entry, committed         (before sending)
                                 5 send      the ProviderAdapter bound to that route → transport
                                 6 validate  Pydantic strict JSON; ≤1 same-model repair
                                 7 ledger    terminal entry: SUCCEEDED / FAILED / UNCERTAIN
                                 8 fallback  only if explicitly authorised, outcome known
```

Adapters are bound **per route**, not per provider: the same provider over two
routes (region, account, credential, transport) is two residency answers, and a
call authorised for one route cannot leave over the other's adapter.

Each step is a refusal point, and none offers an alternative: there is no
`suggested_model`, `suggested_route` or `suggested_provider` anywhere in the
failure types. The tests that pin each refusal are in
`packages/aia_core/tests/test_model_gateway.py`.

## The governing rule

> **No silent paid fallback.**

When a provider cannot serve a request, the system parks the work and asks the
user. It never quietly moves to a different provider. This is not a performance
choice; it protects two things the product sells:

- **Cost.** Any unapproved model switch or repeat request can spend the user's
  money. Bedrock calls reserve their worst-case exposure before dispatch.
- **Provenance.** A research finding produced by a different model is a different
  finding. Swapping models mid-analysis silently invalidates the audit trail.

The rule is enforced by the governed gateway and reservation journal. Historical
provider-policy contracts remain tested for persisted state:

1. `provider_for_stage()` resolves a provider from explicit policy only. A paid
   API continuation requires `explicit_api_continue=True`, which may be set **only
   from a deliberate user action** — never from a retry or an error handler.
2. `check_budget()` returns a `BudgetDecision` that carries no
   `suggested_provider` or `fallback_provider` field. There is deliberately no
   affordance for "try something cheaper". A test asserts those attributes stay
   absent.
3. Every switch is written to `project_provider_events` with
   `explicit_user_action`. A switch with that flag false and a cost attached is a
   queryable bug.
4. `GovernedModelGateway` falls back only under a `FallbackPolicy` that names its
   alternates, the failure kinds it covers and **who authorised it**; it cannot
   cover authentication, permission, missing-configuration or schema failures;
   it never runs while a failed call's billing is uncertain; and every alternate
   must be a binding the model policy already permits. The default policy is no
   fallback. `test_model_gateway.py::test_no_fallback_without_an_explicit_policy`.
5. The Claude Code adapter strips `ANTHROPIC_API_KEY` and the other credential
   overrides from the CLI's environment, because with a key present the CLI bills
   the metered API instead of the subscription.

## Providers

The deployed composition binds AWS Bedrock only. Other identifiers below are
retained for persisted provenance and reference parity; they are not connection
choices in the rebuilt product. Legacy policies in the following section do not
authorize the native executor, which resolves explicit capability bindings.


| Internal id (persisted) | UI label | Use (`NATIVE_PROVIDERS`) | Billing, as its records read |
| --- | --- | --- | --- |
| `aws_bedrock` | Amazon Bedrock | **Native**: the one provider the worker calls | Per token over the pinned route |
| `claude_code_subscription` | Claude Code | Historical: the prototype's subscription runtime | Subscription; no marginal API cost |
| `anthropic` | **Claude API** | Historical | Per token |
| `openai` | OpenAI API | Historical | Per token |

The internal id is written into artifact provenance and must never change. The UI
label is separate: `anthropic` displays as "Claude API" to distinguish it from
the Claude Code subscription runtime, and the parity suite asserts this mapping
against the prototype.

Several historical spellings (`claude_api`, `api`, `anthropic_api`, `claude_code`,
`subscription`, `openai_api`) are still accepted on input because persisted rows
contain them. Normalisation accepts them all; anything unrecognised resolves to
the default **and** must emit a `CONFIG_NORMALIZED` warning, because silently
retargeting a provider breaks provenance.

## Policies

Every policy is historical: the prototype's per-project rule, kept so persisted
projects read as they did. No native run consults one; the worker's `ModelPolicy`
binds each capability to its model.

| Policy | Behaviour |
| --- | --- |
| `CLAUDE_CODE_ONLY` | Subscription only. The generic project model's default (`DEFAULT_POLICY`) |
| `CLAUDE_API_ONLY` | Claude API only |
| `OPENAI_ONLY` | OpenAI only |
| `CLAUDE_CODE_THEN_API` | Starts on the subscription; may move to the Claude API **only** on an explicit user continuation |

`CLAUDE_CODE_THEN_API` is the only policy permitting a transition, and even there
the transition is a user action, not an automatic retry path.

## Budget control

A native run is held to its **Study's budget**: every paid request reserves its
ceiling against the Study row before dispatch (`WorkflowRepository.reserve_budget`),
and the gateway checks each call against that reservation. The prototype's
per-project ceiling, `max_api_cost_usd` (default **$10.00**, from
`PRODUCT_POLICY.json` → `ai_runtime.default_max_api_cost_usd`), is still stored on
generic projects and read by no native path.

Before a paid call:

```
spent + reserved + estimate  <=  limit    →  proceed
                             >   limit    →  park in AWAITING_BUDGET and ask
```

Reservations count as spent so concurrent workers cannot each pass the check and
collectively overspend — and the check takes a blocking lock on the study row,
because without it four workers reserving $40 against a $100 budget all succeed.
That was a real defect, found only by a genuinely concurrent test. Subscription
runtimes skip the check entirely because their marginal API cost is zero. Negative
cost records are clamped so a corrupt figure cannot manufacture headroom.

A denied check is a hard stop. The worker parks the job; it does not proceed, and
it does not choose a cheaper provider.

## Cost accounting

**What exists:** per-study budget ceilings, transactional reservations, settlement
including the `SETTLED_UNCERTAIN` path, and `Study.spent_usd`. That is genuine
spend *control*, and it is enforced before every paid call.

**What does not exist, and should not be described as if it did:** a generalized
metered-cost ledger. The final authoritative ledger has to meter AI and model
calls, research APIs, search APIs, retrieval APIs, paid datasets and any other
metered tool, and attribute each to

```
Client → Study → Revision → WorkflowRun → Step → Agent/Tool/Call
```

with corrections written as **compensating entries** rather than by mutating
history — an accounting record that can be edited after the fact cannot be
reconciled against an invoice.

**Model calls now have that ledger.** `ai_usage_events` is append-only, carries
`Client → Study → Run → Step → Attempt → Agent → Call` attribution, and corrects
by compensating entry (`resolve_uncertain`). The database refuses a negative
cost that is not a compensation. It is authoritative for model-call cost, per
ADR 0006.

Still outstanding: the same for **non-model** metered tools (research, search,
retrieval, paid datasets). `ToolRegistry` refuses to register a tool with an
external paid effect until that exists, rather than letting one run uncounted.
Also outstanding: reconciling a resolved uncertain call back into
`Study.spent_usd`, which still carries the `SETTLED_UNCERTAIN` reservation
amount (OI-36), and the reference's per-run hard cap (`budget_guard.py`, R10).

## Residency and egress

Every outbound call carries a data classification and resolves to an approved
route before it is made, per [ADR 0008](adr/0008-eu-data-residency.md). The
boundary fails closed: unclassified material does not leave, an unknown route is a
refusal rather than a substitution, and a denial has no fallback affordance — the
same rule as budget, for the same reason.

A capability with no approved route for a study's data class cannot run, and that
is discoverable before the study starts rather than mid-pipeline.

## Failure classification

Errors are classified before any retry decision. The taxonomy is carried over
from `ai_router.classify_provider_exception`:

| Class | Retryable | Handling |
| --- | --- | --- |
| `QUOTA` | Not a retry | Park in `WAITING_PROVIDER` (the reference's `WAITING_CREDITS`), reset the retry counter, schedule a one-time resume at the reset time when the provider gave a plausible one |
| `TRANSPORT` | Yes | Backoff and retry |
| `PROVIDER_CAPACITY` | Yes, later | Park in `WAITING_CAPACITY` — a **separate** state from the quota park, because it clears by itself with no reset instant. The reference retried 5 s → 15 s → 45 s inside the call; that is **not** ported (ADR 0005 condition 1 forbids unrecorded retries) and the backoff is the scheduler's |
| `AUTHENTICATION`, `PERMISSION`, `MISSING` | **No** | Terminal. Retrying hides a misconfiguration and burns quota |
| `SCHEMA` | Once | Structured-output contract violation; one repair attempt, then fail |
| `MODEL` | No | Terminal. Retirement substitution happens at resolution, from the versioned policy — see *Model defaults* |
| `SDK_OUTDATED`, `MAX_TURNS`, `OTHER` | No | Terminal with a specific operator message |

Treating quota as a retry rather than a park is the single easiest way to break
this system: it would consume `max_attempts` and fail a project that was merely
waiting.

The adapters' mappings are tabulated in each adapter's module docstring and
pinned by one recorded exchange per row in
`packages/aia_core/tests/fixtures/model_adapters/`. Two mappings are judgement
calls worth knowing: an out-of-credit response (Anthropic's "credit balance is
too low", OpenAI's `insufficient_quota`) is `QUOTA` with **no** reset instant,
because somebody has to add credit; and a `200` whose body cannot be read is
`OTHER` with delivery `UNKNOWN`, because the provider processed something and may
have billed it.

### Delivery, and the uncertain call

Every adapter failure states a `Delivery`: `NOT_SENT`, `RESPONDED` or `UNKNOWN`.
Only `UNKNOWN` leaves a billing question open, and for a metered call it becomes
an `UNCERTAIN` ledger entry carried at the call's ceiling, an attempt left
`paid_call_dispatched` and not `paid_call_outcome_known`, and therefore
`RECOVERY_REQUIRED` with the reservation `SETTLED_UNCERTAIN`. An authorised
fallback does **not** run after an uncertain failure: the first call may already
have done the work.

If the worker dies instead, the committed `DISPATCHED` entry is what remains.
`AIUsageRepository.uncertain_calls()` lists both kinds; a person holding
`MANAGE_STUDY_BUDGET` closes one with `resolve_uncertain`, which appends a
`COMPENSATION` entry of `actual − recorded exposure`. The provider-side handle is
the provider request id where a response carried one, and AIA's `call_id` —
sent as `X-Client-Request-Id` where the provider accepts a client id.

## Structured output

**Implemented.** An agent's output contract is a Pydantic model that must forbid
undeclared fields at every level. Its JSON Schema is what the provider sees;
Pydantic in strict JSON mode is what accepts or rejects the answer. A violation
gets one repair call on the same model (versioned `schema-repair-v1`, recorded as
its own ledger entry and budget-checked like any call), then `SCHEMA_VIOLATION`.
Truncated structured output is a violation. Strict mode is used only when the
contract is strict-compatible unchanged; otherwise the schema is sent non-strict
rather than rewritten, as the reference router did.

JSON extraction from text is deliberately narrow: a bare object, or one fenced
block holding one. Prose around JSON is a violation, not something to dig out.

Domain code never imports a provider SDK (`make layer_check` enforces it). It
calls a gateway that normalises:

- structured requests against a JSON schema, with the schema strictified where
  the provider supports strict mode
- plain text requests
- model selection by role (`research_model`, `design_model`, `respondent_model`,
  `analysis_model`, `report_polish_model`)
- token usage and cost
- cancellation
- error classification
- provenance metadata returned alongside the result

Model selection is by `ModelCapability` (ADR 0005), not by the legacy
`ModelRole` slots, which remain for the project settings that still name them.

## Model defaults

There are none in code. The catalog, prices and policies are a configuration
document parsed by `parse_model_config`, which fails closed: an unknown provider
spelling, a numeric string, an empty allow-list or a metered model without
pricing is an error, never a default. (The reference's edition loader reverted a
malformed file to "all providers on".)

**Retirement is declared, not discovered.** The reference replaced a retired id
with a visible equivalent after listing the account's models. Here a policy
declares `retired → replacement` per provider; a pinned retired id resolves to
its replacement and the resolution, the result's provenance and every ledger
entry record `substituted_from`. A live listing never changes what runs.

## Provenance recorded per call

Every call writes `AIUsageEvent`s (`ai_usage_events`) carrying the fields below
plus agent id/version, policy version, route, data class, residency zone,
schema fingerprint, `input_fingerprint` (a hash of exactly what that call sent, so a
primary call and its repair are distinguishable), `served_model` (what the provider says ran),
`substituted_from`, and `fallback_from` / `fallback_authorised_by`.

| Field | Why |
| --- | --- |
| `provider`, `model` | Which system produced the output |
| `prompt_version` | Prompt changes change results |
| `runtime_version` | Build identity |
| `input_tokens`, `output_tokens` | Usage, where the provider reports it |
| `estimated_cost_usd`, `actual_cost_usd` | Budget accounting and dashboards |
| `input_fingerprint` | Ties the output to the exact inputs |
| `produced_by_job_id` | Ties it to the job and its event log |

Claude Code subscription calls have an API cost of **$0**, and token counts appear
only when the CLI returns them. The UI must not imply a cost that was not
incurred, nor a token count it does not have.

## Credentials

The deployed Bedrock signer obtains temporary credentials from the host's
instance role. The product exposes no Claude Code login or direct Anthropic API
key setting. No static model key is placed in browser state, and no provider
credential store is claimed to exist for this native path. The logging layer redacts
secret-shaped keys and values (`sk-ant-…`, `sk-proj-…`, bearer tokens) before
anything reaches a log sink — see `aia_api.observability.redact`, and
[security.md](security.md).

The prototype documents a real operational trap worth carrying over: machine-level
`ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_PROFILE` and `ANTHROPIC_BASE_URL` variables
override an explicit API key and cause a 401 that looks like a wrong key. The
historical CLI adapter strips those overrides. The native Bedrock path does not
invoke that adapter or read those credentials.

## What Settings shows

`/app/settings` has one AI section from two sources, and neither is a connection:

| Source | What | Where |
| --- | --- | --- |
| Code | The native providers, the worker's role credential, the switch it reads first, each native activity (`respondent_fieldwork`, `design_agents`) with its step kind, capabilities, harness/agent/prompt versions, switches and actions, and the capabilities no native step asks for | `GET /api/v1/settings` → `ai_runtime`, any organization member |
| Deployment | Each switch by variable name (the worker's vocabulary; `null` is a value it refuses), the source region, the model's inference profile, the approved data classes | `/config` → `aiRuntime`, public and nonsecret |

An activity reads *on in configuration* when every switch it needs is on; *off*,
naming the first switch that is not; *invalid* when a switch holds a value the
worker refuses -- the worker then refuses to start, so every activity is invalid;
and *unknown* when the page cannot read a switch. It never reads *connected*,
*healthy* or *verified*: nothing on the page calls a model, and whether the worker
accepted the rest of its configuration shows only in its runs.
`apps/executors/tests/test_settings_presentation.py` holds the description to the
worker's composition, and `apps/web/src/lib/ai-runtime.ts` states the one worker
rule it mirrors. The prototype's providers, policies and project fields are listed
under a collapsed history, for reading older records.
