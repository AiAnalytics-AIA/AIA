---
status: in-progress
chunks:
  - "[ ] 1. Terraform: an application inference profile, tagged Environment=develop, for every live model the acceptance run uses (main, the Lead's, the light model)"
  - "[ ] 2. IAM and the model policy follow the profiles; the cost-allocation tag is activated (a billing action)"
  - "[ ] 3. A reconciliation: AIA's usage ledger against the AWS cost record for the tag over a window"
  - "[ ] 4. The runbook states the check, its lag and its tolerance"
  - "[x] 5a. The worker accepts what the plan creates (W0): a tagged profile ARN or an `eu.` id, decided as a model identity versus an invocation target; and the statement "no Environment tag" corrected"
  - "[ ] 5b. The reconciliation's lines (W3): model usage, tool and search spend, open reservations and uncertain calls, each separate, after `deep-research` 4; billing lag recorded, never zero"
  - "[ ] 6. An organization's monthly spend, read-only for OWNER and ADMIN in Settings: model, Brave and other tool spend across clients, from the content-free rows MVPQ-07 keeps (D-47)"
---
# Spend proven twice: AIA's ledger and an AWS cost record

Track A of the MVP roadmap (`overview.md` § MVP roadmap, #493). Written 2026-10-19 from MVP-30 and
`mvp-cohesion.md` F7 (#496). **Owner: a chat session for chunks 1 and 3; chunk 2's tag
activation is the account owner's.**

## Decisions this plan carries

MVP-30: spend is proven by AIA's ledger **and** an AWS application inference profile tagged
`Environment=develop` (AR-3; one Terraform + IAM + model-policy change). `MVP-ACCEPT-2` AC-15:
spend reconciles to AIA's usage ledger within USD 0.01 and agrees with the develop-tagged AWS
cost record.

## What exists

- Terraform grants the instance role invoke on two inference profiles by id, the main model and the
  Lead's own (`infra/develop/main.tf:34, 39 @ 085abe0`, `var.bedrock_lead_model_id`,
  `var.bedrock_model_id`); the operator procedure is in `infra/develop/README.md:65-66` and
  `deploy/develop/README.md:502` (`aws bedrock get-inference-profile`).
- ~~The only tags in `infra/develop/main.tf` are `Name` and `Snapshot` on compute and volumes: no
  `Environment` tag, so no AWS cost can be filtered to develop today (grep, `main.tf:443-527`).~~
  **Corrected (5a, 2026-10-21):** every resource the provider creates carries `Environment =
  "develop"` through its `default_tags` (`infra/develop/versions.tf:33-42 @ 9bbc5019`), and the
  monthly budget already filters on it (`TagKeyValue` `user:Environment$develop`,
  `infra/develop/main.tf:600-610 @ 9bbc5019`). What is missing is a *Bedrock* resource the tag can
  sit on: model calls through a system inference profile carry no resource tag, which chunk 1's
  application inference profiles supply. Whether the tag is activated for cost allocation is
  chunk 2's billing action and is not visible in Terraform.
- AIA's append-only usage ledger (`infrastructure/ai_usage_repository.py`) records every call's
  cost as priced from the model catalogue, not as AWS billed it.

## Chunks

1. **Profiles.** Application inference profiles over the system EU profiles for **every live
   model the acceptance run can call**, each tagged `Environment=develop`: the main model, the
   Lead's model and, when live Deep Research enables it, the light model that serves
   `RESEARCH_TRIAGE` through its own profile (`LightModelSettings`,
   `apps/executors/src/aia_executors/ai_runtime.py:187 @ 085abe0`, marked *Proposed* there). A
   model left untagged still enters AIA's ledger but not the tagged AWS cost, so chunk 3's
   reconciliation would disagree by design. Their ARNs replace the ids in the settings the worker
   reads (`AIA_BEDROCK_*`, `AIA_AI_RESEARCH_LEAD_MODEL_ID`, the light model's). One Terraform
   change. List the models in use from the registry, not from memory.
2. **IAM and policy.** The role's invoke grants point at every application profile above; the model
   policy's profile ids follow (`ModelRegistry` fails closed on an unknown id, so a mismatch
   refuses before a call). The `Environment` cost-allocation tag is activated in billing: a human
   action, named in the runbook, not Terraform.
3. **Reconciliation.** A read-only command (under `tools/` or `aia_executors/smoke.py`) that sums
   the ledger over a window and reads the tagged AWS cost for the same window, printing both and
   the difference. Test the arithmetic on recorded figures; the live read is an operator's.
4. **Runbook.** In `deploy/develop/README.md` (docs PR): how to run the check and what it proves.

## Risks stated, not assumed

- **Hypothesis: "within USD 0.01" may be unreachable.** AWS cost data lags (a day, by AWS's own
  documentation, unverified here) and rounds its own way, and the ledger prices from AIA's
  catalogue. If the live check differs by more than a cent for reasons of rounding or lag, chunk 3
  reports the difference and the owner sets the tolerance. Do not loosen the criterion to pass it.
- Changing the profiles changes the model route; the licence determination names
  `bedrock-eu-primary` (OI-61). Confirm the application profile is the same route in the
  determination's terms before chunk 1 merges.

## Depends on / feeds

Independent of the other tracks until tier B. Feeds AC-15 and the budget table in
`mvp-acceptance-harness` chunk 1.

## Doc follow-up

`deploy/develop/README.md` (runbook), `infra/develop/README.md` (the tag and the profiles).

## Added by the master plan (2026-10-19)

**5a.** The worker refuses a model id that is not an `eu.` profile id (`ai_runtime.py:254, 516`), so the
ARNs chunk 1 creates would stop the worker at start; and the plan's "no Environment tag" is wrong
(`infra/develop/versions.tf:34-40`, `main.tf:597-607` set one). Tool spend (Brave, Athena) is not in the
usage ledger, so AC-15 as written reconciles model spend only: `deep-research` 4 ("tool usage in the
ledger") is the chunk that closes that and is scheduled with this plan (**5b** is the reconciliation
that reads it). Gap G9.


## Execution prerequisite (2026-10-20)

Chunk 5a's semantic-model-id versus invocation-target contract is W0, before chunks 1-2
configure profiles. Implement compatibility before passing an application-profile ARN to a
validator requiring `eu.` ids; do not loosen arbitrary model identity. Reuse the same contract in
production PE7 before PE1's live model configuration. Chunks 5b, 3 and 4 are final reconciliation (5b W3, 3-4 W5):
model usage to its ledger within AC-15's USD 0.01, tool/search separately, tagged AWS billing in
its stated window with lag and a stated billing tolerance. Unknown billing is never zero.

## Migration (lane M9, only if needed)

If 5a finds the model fields cannot carry the application inference profile, the lane's **M9**
(`ai_usage_events.inference_profile_arn`) is added under 5a, **W0**, after lane M3 and before 1-2 configure profiles; if they can, M9 is
removed from the lane in the same PR. Gap G43.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

**New chunk.** 6 (W3), D-47 in. **5b** gains the infrastructure-charges line.

## 5a delivered (2026-10-21, E03)

**Decision: a model's identity and its invocation target are two values** (`domain/model_invocation.py`).
The identity is the `eu.` profile id each `…MODEL_ID` key carries today: the catalogue prices it, the
policy binds a capability to it, the request profile is declared for it, the licence determination's
route carries it and every usage-ledger row records it. Its validation is unchanged and not loosened
(an ARN given as `AIA_BEDROCK_MODEL_ID` is still refused, `test_a_wrong_target_stops_the_worker_by_name`).
The invocation target is what the Converse URL names: unset, the identity itself (today's
behaviour, byte for byte); set, an application inference profile ARN
(`arn:aws:bedrock:<region>:<account>:application-inference-profile/<id>`) in the route's own EU region.
Keys: `AIA_BEDROCK_INVOCATION_TARGET` (the route model), `AIA_AI_RESEARCH_LEAD_INVOCATION_TARGET`
(the Lead's own model), and `LightModelSettings.invocation_target` (the light model, which has no
keys yet). Each is checked at worker start by name; two models may not share one target; the
adapter (`BedrockConverseAdapter(invocation_target=)`) puts it in the URL as one percent-encoded
segment, which is exactly the URL botocore serialises for the same ARN
(`test_the_url_is_the_one_botocore_serialises_for_the_same_arn`, offline). Compose passes both keys to
the worker alone, empty by default; `env.example` names them.

Why this shape: chunk 1's ARNs carry no model name, so an ARN as the identity would break pricing,
the policy and the ledger at once; a second value leaves all of them on the id they already use. The
pair is asserted by configuration: whether a profile really copies the identity's system profile is a
fact in AWS (`aws bedrock get-inference-profile`), which the operator checks when setting it (chunk
2's runbook); the worker makes no AWS call to find out. A kill switch is the unset key.

**Lane M9 is not needed** (`ai_usage_events.inference_profile_arn`): the model fields carry the
identity, which is what a row is priced by, and chunk 3's reconciliation compares the ledger's total
with the AWS cost record filtered by the `Environment` tag over the same window, so it needs no
per-row ARN. The target in force is configuration, which the worker's composition record
(`lead-orchestration` LO12b, the digest on each run in LO12c) is the place to record. If chunk 3 finds
it must attribute per profile, M9 comes back with that evidence.

Tests: `packages/aia_core/tests/test_model_invocation.py`,
`apps/executors/tests/test_ai_runtime_invocation_target.py`,
`test_an_invocation_target_reaches_the_worker_alone_and_unset_changes_nothing`
(`test_develop_host_configuration.py`). Production PE7 reuses the same contract before PE1.

### Doc follow-up (5a)

- `mvp-development-plan.md` lane table: remove row M9 (5a found the model fields carry the
  identity; no `inference_profile_arn` column), or mark it "not needed, 5a".
- `CLAUDE.md` map, `ai_runtime.py`: "each `…MODEL_ID` is the model's identity; the optional
  `AIA_BEDROCK_INVOCATION_TARGET` / `AIA_AI_RESEARCH_LEAD_INVOCATION_TARGET` is the application
  inference profile ARN its calls go through (`domain/model_invocation.py`)"; and the domain list:
  "`model_invocation.py` A model's identity versus its invocation target (5a)".
- `deploy/develop/README.md` § The Research Lead's own model and the AI runtime section: the two
  optional keys, set in SSM once chunk 1's profiles exist.
