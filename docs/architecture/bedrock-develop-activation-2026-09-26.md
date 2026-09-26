# Bedrock develop activation — 2026-09-26

## Authorised scope

The AIA operator explicitly approved this scope in the Codex conversation on 2026-09-26, after being asked to confirm authority to approve the terms: EU Sonnet 4.5, fictional internal Class C text material only, retention recorded as unspecified, one isolated Research test capped at $2. The operator also approved publishing the ADR approval/results and reconciling PR #55. This is operational evidence; PROGRESS remains the tracker.

## Sources reviewed

- [Anthropic terms for AWS Bedrock](https://aws.amazon.com/legal/bedrock/third-party-models/) — AWS page version 18 August 2025, Customer Content excluded from training.
- [AWS Service Terms](https://aws.amazon.com/service-terms/) — Bedrock and third-party models.
- [Abuse detection](https://docs.aws.amazon.com/bedrock/latest/userguide/abuse-detection.html) and [retention](https://docs.aws.amazon.com/bedrock/latest/userguide/data-retention.html) — account `inherit` remains unspecified in AIA; no explicit zero-retention claim.
- [Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) — verified 2026-09-26, Anthropic → Geo and In-region Cross-region Inference → Europe (Frankfurt), Sonnet 4.5: input $3.30 / output $16.50 per million tokens.
- [Model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-4-5.html) — context 200K, output 64K. Conservative configured model output ceiling 64,000; respondent cap 1,024.

## Verified preparation

PR #56 merged and deployed at `03100912ebcf012296c0e53e07b85e43ebd31dd6`. [CI](https://github.com/AiAnalytics-AIA/AIA/actions/runs/36234914562) and [deployment](https://github.com/AiAnalytics-AIA/AIA/actions/runs/36235378083) succeeded; running worker SHA verified. API, web, Caddy, PostgreSQL and legacy panel healthy, worker running.

Account `311141567391`; source eu-central-1; pinned profile `eu.anthropic.claude-sonnet-4-5-20250929-v1:0`. Six destinations verified: eu-central-1, eu-north-1, eu-west-1, eu-west-3, eu-south-1, eu-south-2. Audited Terraform apply changed only the instance IAM policy, removing the unused eu-central-2 model grant; 0 added, 1 changed, 0 destroyed. Readback confirmed the exact profile plus six destination model ARNs. Invocation logging off; account retention `inherit`.

Only synthetic client `CLI-905099f4020045` is approved for the fictional allowlist. No nonterminal runs existed under it at the final pre-activation check. Existing studies/budgets remain intact. New test: 20 fictional respondents, one block of five fictional library-service ratings, $2 study cap. Largest primary input bound 4,323 tokens; conservative primary ceiling $0.0311619. Reservation $0.15 per logical request; any repair ceiling is checked again before dispatch. No caching/fallback. Calls use the host instance role, never the operator root credentials.

## Activation result

Pending configuration, study creation and the first live request. No successful live call or cost claimed yet. OI-61, D6, general fictional-client authority (OI-63), checkpointing (OI-64), persistent lineage (OI-65) and AWS application-profile attribution remain separate work.
