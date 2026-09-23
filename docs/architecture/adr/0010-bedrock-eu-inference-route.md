# ADR 0010 — Amazon Bedrock, EU geography, as the first governed inference route

**Status:** **Proposed.** Becomes *Accepted* when (a) the `ModelGateway` contract
(ADR 0005 A, PR #28) is on `main`, (b) a human has confirmed the route's terms in
§ Verification, and (c) the adapter and its recorded fixtures have landed.
**Date:** 2026-09-23

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
retention_days:           0                      (no model-invocation logging enabled; nothing retained by the service)
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

| Check | How | Result |
|---|---|---|
| Model access enabled in `eu-central-1` for the pinned profile | Bedrock console → Model access | |
| The EU inference profile's member regions are all in the EU geography | `aws bedrock get-inference-profile --inference-profile-identifier <id>` | |
| No model-invocation logging is configured (or it targets an EU bucket with a retention rule) | `aws bedrock get-model-invocation-logging-configuration` | |
| Service terms: customer content not used for training; retention as documented | AWS Service Terms §§ Machine Learning / Bedrock, current revision, link recorded | |
| Any Anthropic end-user licence / marketplace terms required by AWS accepted | Bedrock console prompt on first enablement | |
| Price per million tokens for the pinned id, for the policy's `ModelPricing` | Bedrock pricing page, region `eu-central-1`, date recorded | |

## Consequences

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
