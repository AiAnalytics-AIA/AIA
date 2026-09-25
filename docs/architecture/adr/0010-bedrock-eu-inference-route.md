# ADR 0010 — Amazon Bedrock, EU geography, as the first governed inference route

**Status:** **Proposed.** Becomes *Accepted* when (a) the `ModelGateway` contract
(ADR 0005 A, PR #28) is on `main`, (b) a human has confirmed the route's terms in
§ Verification, and (c) the adapter and its recorded fixtures have landed.
(a) is met; (c) landed with the Agent Runtime Foundation (2026-09-25); **(b) is
outstanding** — the human terms review and the dated EU price entry are not recorded.
**Date:** 2026-09-23 · **Updated:** 2026-09-25 (account-side checks; adapter landed)

## Context

ADR 0008 froze EU residency as an invariant and deliberately selected no vendor.
It asks that any implementation satisfying it be recorded as its own decision,
judged against the invariant rather than allowed to modify it. ADR 0005 A fixed
the `ModelGateway` contract; nothing on `main` implements a transport.

The `develop` environment (ADR 0009) needs one real, governed inference route so
the complete runtime — capability → policy → classification → egress → budget →
transport → usage record — can be exercised against a real provider. One route,
no second provider, no fallback.

## Decision (proposed)

Declare **one** route:

```
route_id:                 bedrock-eu-primary
provider:                 aws_bedrock            (a new Provider member, lands with the adapter)
zone:                     EU
eu_processing_approved:   true                   (after § Verification, by a human)
excluded_from_training:   true                   (AWS service terms: customer content is not used to train)
retention_days:           unspecified            (see § Retention: the account setting is "inherit", not an explicit zero)
approved_for:             CLASS_C_INTERNAL only, initially
```

The route is bound to **one pinned model id** — an EU cross-region inference
profile of a current Anthropic Claude model, written in full with its version
suffix — held in `infra/develop/terraform.tfvars` and mirrored into the model
policy. The instance role is granted `bedrock:InvokeModel` and
`bedrock:InvokeModelWithResponseStream` on **that profile ARN and its EU
foundation-model ARNs only**. There is no `bedrock:*`, and there are no static
credentials: the adapter signs requests with the instance role via SigV4.

All six `ModelCapability` values initially resolve to that one model. That is a
methodology simplification made explicit in the policy document, not an
optimisation; refining it later is a versioned policy change.

### Why Bedrock

- **Residency is satisfiable in one account and one geography.** EU cross-region
  inference profiles keep requests within the EU geography, and Bedrock does not
  use customer content to train models. Both are documented AWS commitments, which
  is why § Verification exists: they are checked, not assumed.
- **No credential to store.** The instance (later the ECS task) role is the
  credential. This is the credential shape ADR 0009 selected the compute for.
- **Cost accounting is native.** Usage arrives per call with input and output
  token counts; a request id is on every response; billing is on the AWS invoice
  the develop budget alarm already watches.

### Why Class C only at first

Approval is per class (ADR 0008). Class A/B approval needs the data-processing
agreement reviewed against the client's terms by a person; that review has not
happened. The develop smoke test sends synthetic Class C material. Nothing client-
derived is admitted until a human widens `approved_for` in a reviewed change.

### What this route never does

- Fall back to Anthropic, OpenAI or any other provider, silently or otherwise.
- Change model on an error. A retired id is replaced only by a versioned policy
  change with `substituted_from` recorded (ADR 0005 A).
- Use a floating alias. `latest`-style ids are refused in the policy.
- Route Class A/B material until approved for it.

## Verification a human performs before Acceptance

Record the answer and the date beside each row; then flip the status.

Rows marked *reported* were checked on the account by the operator's Codex session on
2026-09-25 and relayed to this repository; they are recorded as reported, not re-verified
here. Acceptance still needs the two open rows.

| Check | How | Result |
|---|---|---|
| Model access enabled in `eu-central-1` for the pinned profile | Bedrock console → Model access | *Reported 2026-09-25:* `eu.anthropic.claude-sonnet-4-5-20250929-v1:0` ACTIVE; the underlying model active and authorised; Anthropic's first-use form present |
| The EU inference profile's member regions are all in the EU geography | `aws bedrock get-inference-profile --inference-profile-identifier <id>` | *Reported 2026-09-25:* routes from `eu-central-1` to six EU regions. `infra/develop` now grants exactly `var.bedrock_destination_regions` (default: eu-central-1, eu-north-1, eu-west-1, eu-west-3, eu-south-1, eu-south-2); it had also granted `eu-central-2`, which the profile does not route to. **Compare the list with the command's output before `terraform apply`** |
| The host's role may invoke the profile and model, and nothing else | IAM policy of `aia-develop-instance` | *Reported 2026-09-25:* permits the pinned profile and model |
| No model-invocation logging is configured (or it targets an EU bucket with a retention rule) | `aws bedrock get-model-invocation-logging-configuration` | *Reported 2026-09-25:* off |
| Service terms: customer content not used for training; retention as documented | AWS Service Terms §§ Machine Learning / Bedrock, current revision, link recorded | **Open** — the human terms review. Until it is recorded, `AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING` and `AIA_AI_ROUTE_EU_PROCESSING_APPROVED` stay false and the route carries nothing |
| Any Anthropic end-user licence / marketplace terms required by AWS accepted | Bedrock console prompt on first enablement | *Reported 2026-09-25:* first-use form present |
| Price per million tokens for the pinned id, for the policy's `ModelPricing` | Bedrock pricing page, region `eu-central-1`, date recorded | **Open** — no price is in the repository; `AIA_BEDROCK_INPUT_USD_PER_MTOK` / `_OUTPUT_` are required configuration with no default |
| Cost attribution | Cost Explorer / AWS Budgets | *Reported 2026-09-25:* the `Environment` cost allocation tag was activated today; the $100 develop budget may take up to 24 h to show tagged costs, and its tag filter is **not proof that Bedrock charges are included** for a system-defined inference profile (see § Cost attribution) |

### Retention

The account's Bedrock data-retention setting is `inherit`. That is not an explicit
zero-retention policy, so AIA does not declare `retention_days: 0`: the route's
retention is **unspecified** (`AIA_AI_ROUTE_RETENTION_DAYS` unset) until the terms
review records the model-specific basis — what Bedrock and the model provider retain
for this model, per the current service terms, with the link and date. ADR 0008 lets
only Class C material travel over a route with unspecified retention, which is all
this route is proposed for.

### Cost attribution

AIA's own ledger (`ai_usage_events`) prices every call from its reported usage and the
policy's price, attributed to Client → Study → run → step → attempt; that does not
depend on AWS tags. AWS-side attribution of Bedrock spend to the develop budget is not
yet shown: a system-defined inference profile carries no tag. **Proposal, not done:**
an *application inference profile* for the pinned model, tagged `Environment=develop`,
would make Bedrock spend attributable. It is one coordinated change — Terraform creates
the profile; the instance role's grant names its ARN (and keeps the foundation-model
ARNs of the destination regions); `bedrock_model_id` and `AIA_BEDROCK_MODEL_ID` become
the application profile's ARN, which changes the adapter's URL segment and the model
policy's pinned id (a new policy version) — reviewed together, never piecemeal.

## Consequences

**Landed (Agent Runtime Foundation, 2026-09-25):** `Provider.AWS_BEDROCK`;
`BedrockConverseAdapter` bound to one region and one model id (refuses any other before
signing); `InstanceRoleSigner` (botocore SigV4, instance or container role only; the
named `layer_check` exemption); `Urllib3Transport` (no retries, delivery stated);
20 recorded fixtures (`fixtures/model_adapters/bedrock/`, hand-authored from the
service model); `aia_executors.ai_runtime` (the route, catalog and policy from
`AIA_AI_*` / `AIA_BEDROCK_*`, off by default, fail closed). Only
`ModelCapability.SIMULATION` is bound: the other capabilities wait for their agents.
No live call has been made.

- A `Provider.BEDROCK = "aws_bedrock"` member, a `BedrockConverseAdapter`
  implementing PR #28's `ProviderAdapter` over a SigV4 `HttpTransport`, recorded
  fixtures for success / throttling / access-denied / validation / unreadable-200,
  and the pricing entry — one PR, after #28 merges.
- `tools/layer_check.sh` gains a named exemption for the adapter's `botocore`
  import (signing only), in the same PR.
- Every call's `AIUsageEvent` carries route id, resolved model and profile,
  policy version, prompt version, runtime version (git SHA), input fingerprint,
  Bedrock request id, token counts, cost basis and latency — the provenance the
  brief lists, most of it already fields on PR #28's event.

## Revisit when

- A second route is needed for benchmarking, sensitivity analysis or explicit
  researcher switching — each is its own route and its own approval.
- AWS changes the geography membership of the EU inference profiles, or the
  service terms on training and retention.
- Class A/B approval is sought: a reviewed change to `approved_for`, with the DPA
  reference recorded here.
