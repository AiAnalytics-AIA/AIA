---
status: planned
chunks:
  - "[ ] 1. Terraform: application inference profiles for the main and the Lead's models, tagged Environment=develop"
  - "[ ] 2. IAM and the model policy follow the profiles; the cost-allocation tag is activated (a billing action)"
  - "[ ] 3. A reconciliation: AIA's usage ledger against the AWS cost record for the tag over a window"
  - "[ ] 4. The runbook states the check, its lag and its tolerance"
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

1. **Profiles.** Application inference profiles over the system EU profiles for the main and the
   Lead's model, each tagged `Environment=develop`; their ARNs replace the ids in the settings the
   worker reads (`AIA_BEDROCK_*`, `AIA_AI_RESEARCH_LEAD_MODEL_ID`). One Terraform change.
2. **IAM and policy.** The role's invoke grants point at the application profiles; the model
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
