# AI runtime

**Status: domain rules implemented** (`aia_core.domain.providers`, verified by
`packages/aia_core/tests/test_providers_parity.py`). **Gateway and SDK adapters
not implemented** — Phase 4.

## The governing rule

> **No silent paid fallback.**

When a provider cannot serve a request, the system parks the work and asks the
user. It never quietly moves to a different provider. This is not a performance
choice; it protects two things the product sells:

- **Cost.** A silent move from the flat-rate Claude Code subscription to the
  metered Claude API spends the user's money without consent.
- **Provenance.** A research finding produced by a different model is a different
  finding. Swapping models mid-analysis silently invalidates the audit trail.

The rule is enforced in code by three mechanisms:

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

## Providers

| Internal id (persisted) | UI label | Billing |
| --- | --- | --- |
| `claude_code_subscription` | Claude Code | Subscription; no marginal API cost |
| `anthropic` | **Claude API** | Per token |
| `openai` | OpenAI API | Per token |

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

| Policy | Behaviour |
| --- | --- |
| `CLAUDE_CODE_ONLY` | Subscription only. The default |
| `CLAUDE_API_ONLY` | Claude API only |
| `OPENAI_ONLY` | OpenAI only |
| `CLAUDE_CODE_THEN_API` | Starts on the subscription; may move to the Claude API **only** on an explicit user continuation |

`CLAUDE_CODE_THEN_API` is the only policy permitting a transition, and even there
the transition is a user action, not an automatic retry path.

## Budget control

Every project has `max_api_cost_usd`, default **$10.00** (from
`PRODUCT_POLICY.json` → `ai_runtime.default_max_api_cost_usd`).

Before a paid call:

```
spent + reserved + estimate  <=  limit    →  proceed
                             >   limit    →  park in WAITING_USER and ask
```

Reservations count as spent so concurrent workers cannot each pass the check and
collectively overspend. Subscription runtimes skip the check entirely because
their marginal API cost is zero. Negative cost records are clamped so a corrupt
figure cannot manufacture headroom.

A denied check is a hard stop. The worker parks the job; it does not proceed, and
it does not choose a cheaper provider.

## Failure classification

Errors are classified before any retry decision. The taxonomy is carried over
from `ai_router.classify_provider_exception`:

| Class | Retryable | Handling |
| --- | --- | --- |
| `QUOTA` | Not a retry | Park in `WAITING_CREDITS`, reset the retry counter, schedule a one-time resume at the reset time |
| `TRANSPORT` | Yes | Backoff and retry |
| Capacity (recoverable) | Yes, later | Park in `WAITING_CAPACITY` |
| `AUTHENTICATION`, `PERMISSION`, `MISSING` | **No** | Terminal. Retrying hides a misconfiguration and burns quota |
| `SCHEMA` | Once | Structured-output contract violation; one repair attempt, then fail |
| `MODEL` | Substitute | A retired model id is replaced with a visible equivalent and recorded |
| `SDK_OUTDATED`, `MAX_TURNS`, `OTHER` | No | Terminal with a specific operator message |

Treating quota as a retry rather than a park is the single easiest way to break
this system: it would consume `max_attempts` and fail a project that was merely
waiting.

## Structured output

Domain code never imports `anthropic` or `openai`. It calls a gateway that
normalises:

- structured requests against a JSON schema, with the schema strictified where
  the provider supports strict mode
- plain text requests
- model selection by role (`research_model`, `design_model`, `respondent_model`,
  `analysis_model`, `report_polish_model`)
- token usage and cost
- cancellation
- error classification
- provenance metadata returned alongside the result

The prototype's `ai_router.py` already does all of this well, including
substituting retired model ids against what an account can actually see. Phase 4
should port it behind an interface rather than rewrite it.

## Model defaults

Defaults follow Anthropic's current lineup and are validated against the models
an account can actually see; a retired id is substituted automatically and the
substitution is recorded. Pin an id in configuration when a reproducible run is
required.

## Provenance recorded per call

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

Provider keys are stored encrypted at rest, are never returned by any API
response, and are never placed in frontend state. The logging layer redacts
secret-shaped keys and values (`sk-ant-…`, `sk-proj-…`, bearer tokens) before
anything reaches a log sink — see `aia_api.observability.redact`, and
[security.md](security.md).

The prototype documents a real operational trap worth carrying over: machine-level
`ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_PROFILE` and `ANTHROPIC_BASE_URL` variables
override an explicit API key and cause a 401 that looks like a wrong key. The
runtime deliberately ignores them and diagnostics should report their presence.
