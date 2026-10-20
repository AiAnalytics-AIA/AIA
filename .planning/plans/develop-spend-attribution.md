---
status: planned
chunks:
  - "[ ] 1. Terraform: an application inference profile, tagged Environment=develop, for every live model the acceptance run uses (main, the Lead's, the light model)"
  - "[ ] 2. IAM and the model policy follow the profiles; the cost-allocation tag is activated (a billing action)"
  - "[ ] 3. A reconciliation: AIA's usage ledger against the AWS cost record for the tag over a window"
  - "[ ] 4. The runbook states the check, its lag and its tolerance"
  - "[ ] 5. The worker accepts what the plan creates: a tagged profile ARN or an `eu.` id, decided; and the statement "no Environment tag" corrected"
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
- The only tags in `infra/develop/main.tf` are `Name` and `Snapshot` on compute and volumes: no
  `Environment` tag, so no AWS cost can be filtered to develop today (grep, `main.tf:443-527`).
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

**5.** The worker refuses a model id that is not an `eu.` profile id (`ai_runtime.py:254, 516`), so the
ARNs chunk 1 creates would stop the worker at start; and the plan's "no Environment tag" is wrong
(`infra/develop/versions.tf:34-40`, `main.tf:597-607` set one). Tool spend (Brave, Athena) is not in the
usage ledger, so AC-15 as written reconciles model spend only: `deep-research` 4 ("tool usage in the
ledger") is the chunk that closes that and is scheduled with this plan. Gap G9.


## Execution prerequisite (2026-10-20)

Chunk 5's semantic-model-id versus invocation-target contract is W0, before chunks 1-2
configure profiles. Implement compatibility before passing an application-profile ARN to a
validator requiring `eu.` ids; do not loosen arbitrary model identity. Reuse the same contract in
production PE7 before PE1's live model configuration. Chunks 3-4 are final W5 reconciliation:
model usage to its ledger within AC-15's USD 0.01, tool/search separately, tagged AWS billing in
its stated window with lag and a stated billing tolerance. Unknown billing is never zero.
