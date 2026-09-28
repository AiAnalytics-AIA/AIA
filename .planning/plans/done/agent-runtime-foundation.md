---
status: done
chunks:
  - "[x] 0. This plan"
  - "[x] 1. Bedrock provider and adapter (2e8beb5)"
  - "[x] 2. The gateway can preflight (125a8be)"
  - "[x] 3. Deterministic respondent layer (b2cc9ff)"
  - "[x] 4. The respondent agent (9b7fa9b)"
  - "[x] 5. The bridge and the producer (dec2fd1)"
  - "[x] 6. Composition and deployable configuration (dec2fd1, 2840d34)"
  - "[x] 7. Proof: end-to-end worker run on recorded exchanges"
  - "[x] 8. Documents and records; merged PR #56, deployed at 0310091"
---
# Agent Runtime Foundation — AI respondent fieldwork, the first end-to-end Research integration

**Status:** done — chunks 0–8 merged in PR #56 @ `0310091` (2026-09-26) and deployed; ADR 0010 accepted for fictional Class C on develop (AR-2). Follow-ups are carried in PROGRESS *Next* (OI-64, OI-65). Archived 2026-09-27.
**Follows:** [research-execution.md](research-execution.md) (PR C, ADR 0016) — its *Deferred* list names this PR.
**Governing records:** ADR 0005 (A: the gateway contract), ADR 0006 (AIA owns the workflow), ADR 0008
(residency), ADR 0010 (Bedrock, EU — *Proposed*, stays Proposed here), ADR 0016 (the fieldwork boundary,
the licence gate), `docs/architecture/ai-step-executor-contract.md`.

## Problem

`develop` @ `b3bd42f`: a research run parks at fieldwork because nothing produces an `ai_runtime` dataset —
`FieldworkExecutor.execute` returns `RUNTIME_UNAVAILABLE` for that source unconditionally
(`apps/executors/src/aia_executors/research.py:278`), and the constructor refuses an AI producer outright
(`research.py:264`). Behind that, four things are missing:

1. **No agent.** No respondent `AgentDefinition`, no output contract, no prompt with an identity.
2. **No bridge.** `GovernedModelGateway.invoke` is async and checks one `ExecutionContext.reservation`
   (`application/model_gateway.py:317`); the worker's `StepContext` is sync and meters per call
   (`apps/worker/src/aia_worker/executor.py:244`). PROGRESS D11 is the open question between them. The
   durable journal (`WorkflowCallJournal`) needs a session and a worker id the executor never sees.
3. **No provider.** `Provider` has no Bedrock member (`domain/providers.py:31`); no adapter, no live
   transport, no signer. ADR 0010's route exists only as prose and as an IAM grant
   (`infra/develop/main.tf:329`).
4. **The ledger does not record lineage** (PR C chunk 3's *Not done*). Still not done here: the dataset
   artifact records the lineage its calls declared; a ledger column is follow-up 6 below.

## What the reference does (18.6.6, `legacy/npc-panel-18.6.6/app/`), and what AIA keeps

| Reference | Anchor | AIA |
|---|---|---|
| The model returns, per respondent and question, a **probability vector** over the options (`vyber`) or scale points (+ DK last) (`skala`); a direct answer for `multi` (indices) and `otevrena` (≤ 600 chars). Forced tool, `additionalProperties: false` | `dotaznik.py:136-176` | Same shapes, one strict per-block contract (below) |
| Prompt rules: answer as this person, only profile facts, never population estimates; probabilities are *this respondent's* uncertainty | `dotaznik.py:106-133`, `:209-222` | Carried into prompt `aia.respondent.system` v1 (Czech), versioned |
| Blocks of 2–8 questions per call; open and filtered questions outside blocks; previous answers shown as history | `dotaznik.py:237-293` | Blocks ≤ 8 closed items; each open question alone; history of drawn answers. Filtered questions are already a readiness FAIL (`research_design.py`) |
| Code normalises (clip ≥ 0, divide by sum; zero mass or wrong length ⇒ parse error), applies the response-process layer, then draws with an external seeded RNG | `dotaznik.py:319-356`, `behavior.py:46-126` | Ported: `adjust_probabilities` pure Python, fixtures captured from the unit's own function. Draw from `random.Random(seed)` (OI-62's stdlib rule), seed derived from the run fingerprint, persona and item |
| Response styles: z-scores `souhlasny_sklon`, `vyhranenost`, `ochota_priznat_nevim`, `satisficing`, `social_desirability_sensitivity`; stable hash noise per respondent | `styly.py:30-100` | Fictional personas get the hash-noise part only (no panel to z-score against); stdlib `NormalDist.inv_cdf` for `norm.ppf` |
| Dispersion temperature scaling before behaviour | `dotaznik.py:345` | Temperature 1.0 (identity) — no calibration exists in AIA; recorded as a deviation, not ported |
| Facts already in the panel are answered by code, never the model; unsupported individual facts fail closed | `factual_layer.py:56-201`, `dotaznik.py:1082-1095` | Ported: `classify_question`, `_choice_index`, `deterministic_answer`; parity-tested by importing the unit's own module (stdlib only) |
| A parse error leaves the answer blank and counts a call error | `dotaznik.py:1269-1275` | **Deviation:** AIA never leaves a silent hole. The gateway allows one schema repair (its own ledgered call); a semantic violation after that fails the attempt `SCHEMA_VIOLATION` |

**The model may generate:** per-item probability vectors, `multi` selections and open text, for one fictional
or cleared persona. **It may not generate:** facts about the respondent (answered by code or refused), a
respondent id, weight or donor (code's), and any aggregate (Aggregate reads only the dataset).

## Decisions taken here (engineering; each reversible by a reviewed change)

| # | Decision | Why |
|---|---|---|
| AR1 | **D11 resolved: one reservation per logical request.** For each `invoke` the executor reserves through `StepContext.reserve`, passes that reservation as the `ExecutionContext.reservation`, and settles it once, with the sum of the request's terminal ledger costs, when `invoke` returns or fails with a known outcome. An uncertain outcome is left dispatched, so `fail_attempt` chooses `RECOVERY_REQUIRED` | Keeps both halves unchanged: the gateway still checks every call (primary and repair) against the reservation; the worker still commits reserve → dispatching → settled. Settling per *call* would no-op the repair's cost (`settle_paid_call` is idempotent per reservation) |
| AR2 | **The outcome ledger row is written unfenced**, through a new `StepContext.record_usage(event)`: append-only, scope-checked by `AIUsageRepository`, committed before any fenced write | The contract's rule: a lease lost mid-call must still leave the provider's answer on the ledger (`test_outcome_is_ledgered_even_when_the_lease_is_lost_mid_call`). `StepContext.transaction()` is fenced and would lose it |
| AR3 | **The first live path is fictional Class C material only.** A respondent request is `CLASS_C_INTERNAL` only when *both* its parts are non-client: the personas are the fictional roster (lineage `aia_synthetic_fixture`) **and** the Study's client is one the operator has declared fictional (`AIA_AI_FICTIONAL_CLIENT_IDS`, a deployment setting read into the composition, never from a request or the browser). Every other request is `CLASS_A_CLIENT_CONFIDENTIAL` — its questionnaire is a client's study design (ADR 0008) — and ADR 0010's route, approved for Class C at most, refuses it | User direction 2026-09-25 ("only approved fictional Class C material for the first live path"). Classification is a property of the material decided by the code that holds it; the only trustworthy statement that a design is not client material is the operator's that the client itself is invented (the develop seed's *(fiktivní)* clients). Unknown ⇒ Class A ⇒ refused: never score unknown as good |
| AR4 | **A gate refusal or a missing route parks, it does not fail.** Before reserving, the executor runs `GovernedModelGateway.preflight` (resolution + both gates + adapter binding, no journal, no send); a refusal becomes `RUNTIME_UNAVAILABLE` with the gate's reason. The gateway still refuses on its own if reached | "Preserve the honest park when the runtime or an approved route is unavailable." A licence or residency decision changes policy data; a failed run would need re-creating |
| AR5 | **Personas are fictional in this PR.** `FictionalPersonaRoster` builds invented respondents (lineage `aia_synthetic_fixture`, donors `FIC-D…`); the dataset's origin is a new `DataOrigin.SYNTHETIC_AI_FICTIONAL`, refused client-facing by the evidence gate and labelled by the web client like the fixture. The panel persona source is not built: OI-61 blocks it and it would enter only through `PopulationRuntime` | D3 / OI-61. A model's answers for invented people are not fieldwork |
| AR6 | **Fail-closed configuration.** `AIA_AI_RUNTIME_ENABLED` unset/false ⇒ no AI producer ⇒ the run parks (today's behaviour). Enabled with any key missing or invalid ⇒ the worker refuses to start. No default model id, price, route approval or persona source | ADR 0010; CLAUDE.md §8 "never stamp a guess" |
| AR7 | **Transport: stdlib-free-of-SDKs.** `urllib3` (botocore's own dependency) with `retries=False` in a thread, and botocore's `SigV4Auth` for signing only; credentials must come from an instance or container role (`iam-role` / `container-role`), anything else refused | ADR 0010; ADR 0005 A (no SDK call path). One named `layer_check` exemption |

## Shape

```
worker (claims research_fieldwork, heartbeat thread keeps the lease)
  FieldworkExecutor(source=ai_runtime)
    ai_runtime is None ────────────────────────────────▶ park RUNTIME_UNAVAILABLE (today)
    AIFieldwork.produce(spec, step, context)
      personas  ← FictionalPersonaRoster(spec.n, seed)         (lineage: aia_synthetic_fixture)
      plan      ← plan_items(spec, persona)  facts by code │ blocks ≤ 8 │ open alone
      preflight ← gateway.preflight(first request)  refused ─▶ park (gate named)
      per request:
        StepModelCaller.invoke(request)
          paid  = context.reserve(amount, AWS_BEDROCK)       (BudgetExceeded ─▶ AWAITING_BUDGET)
          ExecutionContext(scope=context.scope, reservation=paid, journal=StepCallJournal)
          asyncio.run(gateway.invoke(...))
            record_dispatch → context.dispatching(paid) [checkpoint + fence] → record_usage(DISPATCHED)
            adapter.send  (BedrockConverseAdapter → SigV4 → urllib3, no retry)
            record_outcome → record_usage(terminal)           [unfenced, committed]
          context.settled(paid, Σ terminal cost)  | uncertain: left dispatched → RECOVERY_REQUIRED
        interpret_block(...)  validate → adjust_probabilities → seeded draw
      FieldworkDataset(source=ai_runtime, origin=SYNTHETIC_AI_FICTIONAL)  → validate_dataset
  Aggregate, Sociomap: unchanged
```

## The contract, point by point

**Integration point.** `FieldworkExecutor.execute`'s `AI_RUNTIME` branch
(`apps/executors/src/aia_executors/research.py:278` @ `b3bd42f`) and its constructor refusal (`:264`).
`research_registry(..., ai_runtime=AIFieldwork | None)`; `None` keeps today's park byte for byte. The run's
recorded source (`fieldwork_source`, fixed at start by `ResearchRuns.start`) is still what selects the
producer; the workbench's `SYNTHETIC_FIXTURE` producer is never consulted for an `ai_runtime` run. Nothing
downstream changes: the step stores the same `research_fieldwork_dataset` artifact that Aggregate and
Sociomap already read. No HTTP route, no second engine, no `AgentRun` table: the step attempt *is* the
agent run (ADR 0006), and its provenance lives on the artifact and the ledger (run / step / attempt ids).

**Respondent agent.** `aia.research.respondent` v1, capability `SIMULATION`, prompt `aia.respondent.block`
v1 (Czech, from `dotaznik.py:209-222`'s rules; the prompt text's SHA-256 is recorded). One call per
respondent per block (≤ 8 closed items; an open question alone), temperature 0.0, forced tool, one schema
repair allowed by the gateway. Output contract, built per block by a versioned builder
(`aia-respondent-contract-1`), `extra="forbid"` at every level, one required property per asked item
(keyed by the item id): `{"probabilities": [k numbers ≥ 0]}` for `vyber` / `skala` / battery ratings
(k = options, or scale points + DK when allowed), `{"selected": [option numbers]}` for `multi`,
`{"text": "≤ 600 chars"}` for `otevrena`. An unasked item, a missing item or a wrong-length vector is a
schema violation the gateway sees (and may repair once).

**Deterministic handling** (`domain/ai_respondent.py`, pure). Facts first: an item the factual layer
classifies DIRECT is answered from the persona's own attributes, never asked (it appears to the model
only as history, as the unit shows prior answers); UNSUPPORTED fails the step before any call. After the
call: finite, non-negative, non-zero mass and in-range selections (duplicates collapsed, as the unit
does), else the attempt fails `SCHEMA_VIOLATION` (no silent hole, no retry). Normalise → `adjust_probabilities` (ported
`behavior.py`) with the persona's style → draw with `random.Random(seed)` where `seed` derives from the
spec fingerprint, the persona and the item. The model never sets an answer, a weight, a donor, an id or a
fact.

**Artifact provenance.** The dataset (`source = ai_runtime`, `origin = SYNTHETIC_AI_FICTIONAL`,
`generator = aia-ai-respondent-1`, `seed`) and the artifact's payload carry: agent id/version, prompt
id/version and SHA-256, contract builder version, behaviour version, fact layer version, persona roster
version, the declared data class and lineage, and per call its `call_id`, provider request id, route,
resolved model, policy version, cost and cost basis. The ledger has the same calls, attributed to the
Study from the issued scope.

**Heartbeat and recovery.** The worker's heartbeat thread keeps the lease across a blocking `invoke`
(`aia_worker/heartbeat.py`); cancellation is checked at every `dispatching` (before money) and between
respondents. Per request: reserve → dispatching (fenced, committed) → send → ledger outcome (unfenced,
committed) → settled (fenced). Lease lost mid-call ⇒ the outcome is still on the ledger and the attempt is
recovered `RECOVERY_REQUIRED`; an uncertain outcome ⇒ left dispatched ⇒ `RECOVERY_REQUIRED`, never a
retry; quota / capacity ⇒ park (`WAITING_PROVIDER` / `WAITING_CAPACITY`); budget ⇒ `AWAITING_BUDGET`;
schema / permission / auth ⇒ `FAILED`. No fallback policy is ever built: the request carries none.

**Route through the gateway.** `StepModelCaller` is the only caller; it builds `ExecutionContext` from
`StepContext` (issued Study scope, run / step / attempt ids, the reservation, `is_cancelled`, the build
SHA) and awaits `GovernedModelGateway.invoke`. Residency and licence are checked there before any adapter,
and first by `preflight`, which parks the run with the refusing gate's reason.

## Reconciled with the supplied documents (2026-09-25 export, `aia_commit` `b3bd42f`)

| Document says | Code says | Followed |
|---|---|---|
| Respondent prompt at `pipeline.py:790-822,916-1060` (workflow map) | The questionnaire engine's respondent is `dotaznik.py:106-356` (forced tool, probabilities, seeded draw); `pipeline.py:822` is the older one-question `{"volba"}` path | `dotaznik.py` |
| "Add Bedrock ... only after ADR 0010's route verification" (map, step 3) | The task asks for the adapter as code | Adapter and configuration land; the route's `eu_processing_approved` and `approved_for` come only from operator configuration and default to nothing, so nothing is sent until a person records the verification. ADR 0010 stays Proposed |
| PR C "draft" (PROGRESS extract) | PR #52 merged at `b3bd42f` | Historical wording; PROGRESS updated |
| "Study → AgentRun → Orchestrator" (PROGRESS *Next*) | ADR 0006: the workflow engine is the record; an attempt is the unit | No `AgentRun` table; the attempt and artifact provenance carry it |
| First live route "Class C fictional/internal" (README) | ADR 0010 `approved_for: CLASS_C_INTERNAL only`; residency refuses anything else | AR3 |

## Chunks

| # | Chunk | State |
|---|---|---|
| 0 | This plan; PROGRESS *In progress* row | done (in `2e8beb5`) |
| 1 | **Bedrock provider and adapter.** `Provider.AWS_BEDROCK` (paid); `BedrockConverseAdapter` (route-bound to one model id; Converse, forced tool; usage, `x-amzn-requestid`; error taxonomy); `SigV4Signer` protocol + botocore instance-role signer; `Urllib3Transport` (no retries, delivery from the exception); `HttpRequest.raw_body`; optional `temperature` on request/adapter request; recorded fixtures for success, throttling, access-denied, validation, not-ready, service-unavailable, unreadable-200, read-timeout; layer exemption || done `2e8beb5`: 20 fixtures, `test_bedrock_adapter.py` (signer against botocore, live transport against a local stub: sent once, read timeout UNKNOWN and not re-sent, refused connection NOT_SENT) |
| 2 | **The gateway can preflight.** `GovernedModelGateway.preflight(request, context)`: resolution, residency, licence, adapter binding and output limit — the same `_lane` the call uses; nothing journaled, reserved or sent || done `125a8be`: `test_model_gateway.py` preflight tests (each gate refuses with no journal entry; an unreserved context passes preflight and is still refused by invoke) |
| 3 | **Deterministic respondent layer (domain).** `respondent_behavior.py` (port of `behavior.adjust_probabilities` + stable style noise) with fixtures captured from the unit; `respondent_facts.py` (port of the factual layer) with parity against the unit's module || done `b2cc9ff`: 66 behaviour cases 1e-12 and 40 style rows 1e-9 against the unit's own functions (`tools/respondent_capture.py`); 39 classifications and 12 choice mappings against the unit module itself |
| 4 | **The respondent agent (domain).** Persona, fictional roster, item plan, per-block strict contract, prompt v1 and its identity, `ModelRequest` builder, response interpretation (validate, adjust, draw), dataset assembly; `DataOrigin.SYNTHETIC_AI_FICTIONAL`; evidence gate; web label || done `9b7fa9b`: `test_ai_respondent.py` (19); evidence gate refuses the new origin; web label + Vitest |
| 5 | **The bridge and the producer.** `StepContext.record_usage`; `StepCallJournal` + `StepModelCaller` (AR1, AR2, cancellation, heartbeat); `AIFieldwork` producer; `FieldworkExecutor(ai_runtime=…)`; park on preflight refusal (AR4) || done `dec2fd1`: `test_ai_fieldwork.py` (26 then 27) |
| 6 | **Composition and deployable configuration.** `AIRuntimeSettings.from_env` (AR6); production registry builds the producer only when enabled; compose + env example + runbook keys (SSM → env) || done in `dec2fd1` (settings) and `2840d34` (Compose, env example, Terraform regions narrowed to the profile's six, two layer rules) |
| 7 | **Proof.** End-to-end worker run: compile → preflight → AI fieldwork (recorded Bedrock exchanges, fictional personas, a test route approved for Class A) → aggregate → sociomap; production registry parks with no configuration; refusals before network; budget, ledger, lease, cancellation, provider errors, no fallback || done: the acceptance run and every failure path in `test_ai_fieldwork.py`, recorded exchanges; no live call |
| 8 | **Documents and records.** ARCHITECTURE, CLAUDE.md, AGENTS.md, contract doc (D11 resolved), ADR 0010 consequences (still Proposed), PROGRESS, open items; `make verify`; PR with the AWS handoff || done: this change. `make verify` exit 0; PostgreSQL 16 core 2410 / API 199 / worker 49 / executors 56 |

## Review outcomes

| Finding | Resolution |
|---|---|
| `live_transport.py` classified every `urllib3.exceptions.SSLError` as `NOT_SENT`, but urllib3 2.x raises it from the handshake *and* from reading the response; a post-send TLS failure was ledgered as a free, retryable failure and the request re-sent (three attempts against the old code) | `4d99e6a`: only a refused server certificate (`ssl.SSLCertVerificationError`, handshake-only) stays `NOT_SENT`; every other SSL error is `UNKNOWN` → `RECOVERY_REQUIRED`, `SETTLED_UNCERTAIN`, no retry. Local TLS server tests in `test_bedrock_adapter.py` and `test_ai_fieldwork.py`, each failing under the opposite mutation |

## AWS handoff (account side), as of 2026-09-25

**Reported done by the operator's Codex session (not re-verified here):** profile
`eu.anthropic.claude-sonnet-4-5-20250929-v1:0` ACTIVE, routing from `eu-central-1` to six EU
regions; the underlying model active and authorised; Anthropic's first-use form present; the
running host's role `aia-develop-instance` permits the pinned profile and model; model
invocation logging off; the `Environment` cost allocation tag activated (up to 24 h to show;
the budget's tag filter is **not** proof Bedrock charges are included for a system-defined
profile); Bedrock data retention `inherit` (not an explicit zero). No live call made.

**Still owed before any call** (none is engineering's to supply):

1. ADR 0010's human terms review — training exclusion and the model-specific retention basis,
   with the service-terms link and date — then `aia_ai_route_excluded_from_training` and
   `aia_ai_route_eu_processing_approved` may be set `true`.
2. The dated `eu-central-1` price per million input and output tokens (and cache rates, if
   used) for the pinned id → `aia_bedrock_input_usd_per_mtok`, `aia_bedrock_output_usd_per_mtok`.
3. `aws bedrock get-inference-profile --inference-profile-identifier eu.anthropic.claude-sonnet-4-5-20250929-v1:0`
   → its destination regions must equal `bedrock_destination_regions` (default: eu-central-1,
   eu-north-1, eu-west-1, eu-west-3, eu-south-1, eu-south-2). Then `terraform plan` shows the
   grant losing `eu-central-2`'s foundation-model ARN; apply only as a reviewed change.
4. The model's output ceiling and context window from its model card →
   `aia_bedrock_max_output_tokens`, `aia_bedrock_context_window_tokens`.
5. The seed's fictional client ids → `aia_ai_fictional_client_ids` (OI-63's default).
6. A human flips ADR 0010 to Accepted; then `aia_ai_runtime_enabled=true` and the remaining
   keys (`deploy/develop/README.md` § AI), and a first authorised Class C run.
7. Optional (AR-3): an application inference profile for AWS-side cost attribution — a
   coordinated Terraform + IAM + model-policy change, never piecemeal.

## Not in this PR (follow-up chunks, in order)

1. **Account-side AWS** (Codex, after sign-in) and ADR 0010's verification table, then a human flips it to
   Accepted; a person widens `approved_for` for Class A after the DPA review — only then can a develop
   study's AI fieldwork leave the park.
2. **Checkpointed fieldwork** — resume a long fieldwork attempt per respondent instead of re-asking every
   respondent after a retry (artifact per respondent block, reuse by fingerprint).
3. **Panel-grounded personas** through `PopulationRuntime.load_for_run` — blocked on OI-61 and on the
   population import (PROGRESS *Next* a–c).
4. OI-58, OI-59 (unit store, grants), Donor QC → battery gates → segments (ADR 0016 D2's order), the
   eight analysis modules, interpretation and report generation.
5. Dispersion calibration and declared response-process metadata (social desirability, acquiescence) on
   AIA questions.
6. `ai_usage_events.data_lineage` (a column + migration), so the ledger alone shows what each call
   declared at the licence gate.
7. A smoke-module Class C call on develop (PROGRESS *Next* 5c's second half), once ADR 0010 is verified.
