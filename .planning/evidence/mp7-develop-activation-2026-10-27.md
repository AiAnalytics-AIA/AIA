# MP7: develop's activation, read once (2026-10-27)

`mvp-master-plan#MP7`: "the operator runbook run once on develop: AI route classes, Brave sign-off,
secrets, the reach switches, with the evidence recorded". Run by the infra session on 2026-10-27,
14:30-15:00 UTC, as IAM user `aia-claude-code-2` (account `311141567391`, `eu-central-1`).

**What this run could and could not read.** The identity reads SSM `/aia/develop/*` (never the
SecureStrings it is denied), parameter history, the `/aia/develop` log group, CloudWatch, Cost
Explorer, Bedrock's profiles, agreement offers and logging configuration, and the stored output
of earlier deploy commands. It may **not** run a command on the host (`ssm:SendCommand` and
`ssm:StartSession` are denied), so nothing here was read from the database or a container's
environment. `docs.aws.amazon.com` is not reachable from the session, and the Marketplace terms'
pre-signed links fail through its proxy, so no AWS or model terms text was read either. Each row
says which source it rests on.

**Deployed build:** `f59166528478477c5f8405f116dd604ed3d924cd`, deployed 2026-10-27 13:45:45-13:47:56
UTC (SSM command `ac6c3e74-e679-43f0-a474-d118762e6425`, Success). Its smoke: every check `ok`, the AI
row `NOT_RUNNABLE` by design, schema at head `184381bbcfef`. The worker started at 13:46:41 with no
configuration refusal and has run `research_lead_turn` steps to `SUCCEEDED` since (14:32-14:35 UTC).
`develop` is at `8d9d1299`; the deploy of the newer merges had not run when this was read.

## 1. AI route classes

| Parameter | Value | Set | By |
|---|---|---|---|
| `aia_ai_runtime_enabled` | `true` | 2026-09-26 | root |
| `aia_ai_route_id` | `bedrock-eu-primary` | 2026-09-26 | root |
| `aia_ai_route_approved_for` | `CLASS_A_CLIENT_CONFIDENTIAL,CLASS_B_DERIVED_CLIENT,CLASS_C_INTERNAL` (v2; v1 was `CLASS_C_INTERNAL`) | 2026-10-21 09:23 UTC | `aia-claude-infra` |
| `aia_ai_route_retention_days` | `30` (v1) | 2026-10-21 09:23 UTC | `aia-claude-infra` |
| `aia_ai_route_eu_processing_approved` | `true` | 2026-09-26 | root |
| `aia_ai_route_excluded_from_training` | `true` | 2026-09-26 | root |
| `aia_bedrock_model_id` | `eu.anthropic.claude-sonnet-4-5-20250929-v1:0`, USD 3.30 / 16.50 per Mtok | 2026-09-26 | root |
| `aia_ai_research_lead_model_id` | `eu.anthropic.claude-sonnet-5-5`, USD 2.20 / 11.00, cache 0.11 / 2.75, `auto_tool`, `adaptive`, effort `medium`, 8,000 output, reservation USD 1.10 | 2026-10-26 | |
| `aia_ai_policy_version` | `aia-bedrock-develop-2026-09-26-lead-sonnet55-20261026` | 2026-10-26 | |

- **Invocation logging:** `get-model-invocation-logging-configuration` returns no `loggingConfig`
  (off), 2026-10-27.
- **Profiles:** both system profiles `ACTIVE`, each routing to eu-central-1, eu-north-1, eu-south-1,
  eu-south-2, eu-west-1 and eu-west-3, the same list as the tfvars' `bedrock_destination_regions`.
- **Model agreements:** Marketplace offers listed for both models (`offer-qac56zmvs7neg` for Sonnet
  4.5, `offer-5fu2rhus3byrs` for Sonnet 5.5). The Lead's turns succeed, so the Sonnet 5.5 agreement
  is in effect for the Lead; the terms text itself was not read.

**Finding MP7-1 (not passed): the retention behind `30` is not recorded.** The runbook's step 1
(`deploy/develop/README.md` § AI route classes) requires the account's Bedrock data-retention
setting and each model's terms, read and recorded with the logging state and the date in ADR 0010's
activation evidence, **before** the parameter is set; "if either piece cannot be confirmed … stop
here: the route stays Class C only". The parameter was set on 2026-10-21 by `aia-claude-infra`, and
no record of the setting, the terms reference or why the number is 30 exists in the repository
(`git grep` over `docs/` and `.planning/` on `origin/develop` @ `8d9d1299`): ADR 0010 § Retention
still says "unspecified", from 2026-09-26. Nothing is changed here: narrowing the route would be the
owner's call, and on develop `AIA_DATA_CLASS_GATES=advisory` passes class-only refusals anyway
(ADR 0008, Amendment 2026-10-21). **Who closes it:** a person with the Bedrock console reads
Settings → data retention for `eu-central-1` and the two models' terms (Sonnet 4.5 and 5.5, now both
on the route), and records them with the date in ADR 0010's activation evidence (a docs PR); if they
do not support 30, `aia_ai_route_retention_days` is corrected or the route narrowed.

**Finding MP7-2: panel personas were switched on before the catalogue was verified.** §4 has
`aia_ai_population_personas_enabled` set "after `audience-catalogue-cpu` 4"; it was set `true` on
2026-10-14 14:08 UTC. No harm followed: the corrected catalogue had been kept since 2026-10-13 11:45
UTC (`audience-catalogue-cpu` § Chunk 4 verified, closed by this run).

## 2. Brave sign-off

- **SSM:** `aia_deep_research_enabled=true`, `aia_deep_research_web_search=brave` (v3; v1 `brave`
  2026-10-12, v2 `wikipedia`, v3 `brave` 2026-10-14 14:08), `aia_deep_research_brave_usd_per_1000=5.00`,
  `aia_deep_research_brave_prices_as_of=2026-10-14`, `aia_deep_research_wikipedia_enabled=false`,
  `aia_deep_research_public_fetch_contact` set.
- **ADR 0022 approvals (Nastavení → Deep Research):** the API's request log shows 26
  `POST /api/v1/deep-research/settings/{key}/approval` answered 200 on 2026-10-14 between 14:17 and
  14:40 UTC, among them `provider.search.plan`, `provider.search.price_per_1000`,
  `provider.search.terms_url`, `provider.search.terms_date`,
  `provider.search.storage_and_ai_use_granted`, `provider.search.query_log_retention`,
  `provider.search.failed_requests_billed`, `sign_off.design_and_boundaries` and
  `sign_off.adr_0017_amendment`. Who approved is in the audit log, which this run cannot read. On
  2026-10-27 13:31-13:32 UTC two new versions of `provider.search.price_per_1000` were proposed and
  both withdrawn (versions 2 and 3); the approved version is unchanged.
- **Not seen:** whether a run since has reached Brave. The last Deep Research start in the log is an
  Interpretation run on 2026-10-15; the tool events and the worker's recorded reach (Settings → Deep
  Research → Dosah) are in the database.

## 3. Secrets

Present as `SecureString` under `/aia/develop/` (names and types only; this identity is denied the
values of the unmanaged ones): `postgres_password`, `aia_deep_research_brave_api_key`,
`aia_onlyoffice_jwt_secret`, `aia_glitchtip_api_token`, `glitchtip_secret_key`,
`glitchtip_db_password`, `glitchtip_email_user`, `glitchtip_email_password`. No API key, token or
password is a `String`; the two error-tracking DSNs are, as a DSN's key is public by design. The worker signs Bedrock with the instance role (`Found credentials from IAM
Role: aia-develop-instance`, worker log 2026-10-27 13:47:43).

## 4. The reach switches

| Switch | Value | Set |
|---|---|---|
| `aia_deep_research_agent_directed` | `true` | 2026-10-14 |
| `aia_deep_research_lead` | `true` | 2026-10-14 |
| `aia_deep_research_connectors` | `datastat,nkod,eurostat,openalex,ares,crossref,wayback` | 2026-10-14 |
| `aia_deep_research_fan_out` / `_model_concurrency` | `true` / `4` | 2026-10-14 |
| `aia_deep_research_thinking_budget_tokens` | `2048` (dropped by the composition for an adaptive route model, #907) | 2026-10-14 |
| `aia_deep_research_common_crawl` and its keys | **absent** | |

**Finding MP7-3: Common Crawl is not configured.** Under §9 "a W0 smoke may omit the archive; I-R
is then BLOCKED, not passed". Its AWS side (workgroup, results bucket, `ccindex`, role grants) is an
operator's with IAM, which agents here are denied.

## 5. The other §4 switches, as read

`aia_ai_research_agents_enabled=true` (4,096 tokens, USD 2.00), `aia_ai_analysis_enabled=true`
(8,192, USD 1.00), `aia_ai_client_source_proposals_enabled=true` (4,096, USD 0.50),
`aia_ai_population_personas_enabled=true`, `aia_ai_fieldwork_checkpoint=true`,
`aia_ai_step_events=true`, `aia_sociomapping_experimental_enabled=true`, `aia_onlyoffice_enabled=true`
(`https://docs.aia-develop.art-chain.io`), `aia_errors_enabled=true`. Not set:
`aia_bedrock_invocation_target`, `aia_ai_research_lead_invocation_target` (develop-spend-attribution
2), `aia_study_wallet_enabled`, the fieldwork heartbeat and quota fill, `aia_ai_scale_labels_in_prompt`.
The route model is still Sonnet 4.5 (`sonnet-5-5-switch` 3-5 open).

## 6. Cost attribution, as read

The `Environment` cost-allocation tag is `Active` (since 2026-09-25). For 2026-10-01 to 2026-10-27
the `Environment=develop` cost holds no Bedrock line; `Claude Sonnet 4.5 (Amazon Bedrock Edition)`
holds USD 33.15 untagged. Two tagged application inference profiles exist since this run
(`develop-spend-attribution` § Chunk 1 delivered); calls go through them only after chunk 2.

## What MP7 still needs

MP7 stays open on MP7-1 alone, which needs the Bedrock console and a person; MP7-3 is a known
blocked gate, recorded, not a defect of the run. Neither is fixed by repeating this read.
