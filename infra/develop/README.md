# `infra/develop` — the develop environment's AWS resources

One Terraform root, no modules ([ADR 0009](../../docs/architecture/adr/0009-single-host-develop-environment.md)).
What it creates, and why each piece exists:

| Resource | Purpose |
|---|---|
| EC2 `t3a.medium`, Ubuntu 24.04, 80 GB gp3 encrypted, IMDSv2 only, no key pair | The one host. Management is SSM Session Manager, so no port 22 |
| Elastic IP (+ optional Route 53 `A` record) | The stable address behind `dev.<domain>` |
| Security group: 80/tcp, 443/tcp, 443/udp in; all out | Caddy's two ports; nothing else is reachable |
| Instance role | The host's only credential: S3 (artifacts, ops), ECR pull, SSM parameters under `/aia/develop/`, `bedrock:InvokeModel` on **one** pinned EU model, SSM agent, CloudWatch agent |
| S3 `aia-develop-artifacts-<account>` | The `ArtifactStore`. Versioned, SSE-S3, private, TLS-only |
| S3 `aia-develop-ops-<account>` | `backups/` (pg_dump, expire after 30 days) and `deploy/` (bundles, 90 days) |
| ECR `aia-api`, `aia-worker`, `aia-web` | Images by git SHA; 30 kept; scan on push |
| SSM parameters `/aia/develop/*` | Configuration for the host's env file; the PostgreSQL password is a generated `SecureString` |
| Cognito user pool + Google IdP + hosted domain + public app client | Authentication only ([ADR 0003](../../docs/architecture/adr/0003-cognito-identity-boundary.md)); PKCE; no self sign-up |
| GitHub OIDC provider + `aia-develop-github-deploy` role | Lets the `develop` GitHub environment push images, upload one bundle and run one SSM command. No stored keys |
| DLM daily snapshot (7 kept), CloudWatch log group, 3 alarms, SNS email, AWS Budget | Observability and cost control at the size that matters here |

Not created: a KMS customer-managed key (SSE-S3 covers encryption at rest for
synthetic data; set `AIA_STORAGE_KMS_KEY_ID` when one exists), an ALB, RDS,
a NAT gateway, autoscaling. The compose file and the runbook are in
[`deploy/develop/`](../../deploy/develop/README.md).

## Apply

```bash
cd infra/develop
cp terraform.tfvars.example terraform.tfvars    # fill in; gitignored
terraform init
terraform plan
terraform apply
terraform output                                # values for GitHub and DNS below
```

`terraform validate` and `plan` need provider downloads and an AWS account,
so they run on an operator's machine, not in CI. `terraform fmt -check` is
the only check the repository runs on these files.

## Human actions

These need account control an agent does not have. In order.

### Before `terraform apply`

1. **AWS account and region.** Confirm the account this environment bills to,
   and that `eu-central-1` is the region (ADR 0008 requires an EU region;
   Frankfurt hosts the EU Bedrock inference profiles). Set `aws_region` if not.
2. **Hostname.** Choose `dev.<domain>` and set `public_hostname`. Decide whether
   the zone is in Route 53 (`route53_zone_id`) or elsewhere.
3. **Google OAuth client** (Google Cloud console → APIs & Services → Credentials
   → *Create credentials* → *OAuth client ID*, type *Web application*):
   - Authorised JavaScript origins: none needed.
   - Authorised redirect URI: `https://<cognito_domain_prefix>.auth.<region>.amazoncognito.com/oauth2/idpresponse`
     (Terraform's `google_redirect_uri` output prints the exact value; the
     prefix defaults to `aia-develop`).
   - OAuth consent screen: *Internal* (Workspace users only).
   - Copy the client id and secret into `google_client_id` / `google_client_secret`,
     and the Workspace domain into `google_hosted_domain`.
4. **Bedrock model access** (Bedrock console, region `eu-central-1` → *Model
   access*): enable the Anthropic model you will pin; accept the end-user
   licence if prompted. Then complete the verification table in
   [ADR 0010](../../docs/architecture/adr/0010-bedrock-eu-inference-route.md)
   and write the full, versioned EU inference-profile id into `bedrock_model_id`.
5. **Budget.** Approve `monthly_budget_usd` (default 100) and set `alert_email`.
6. **Terraform state.** Decide where state lives (an S3 bucket in the same
   account is the simple answer; `versions.tf` has the block to uncomment).

### After `terraform apply`

7. **DNS**, if not Route 53: create `A dev.<domain> → <public_ip>`. Caddy will
   not obtain a certificate until the name resolves to the host.
8. **SNS subscription**: confirm the email AWS sends to `alert_email`.
9. **GitHub environment `develop`** (repository → Settings → Environments →
   *New environment*):
   - Variables (not secrets; none of these is sensitive):

     | Variable | From |
     |---|---|
     | `AWS_REGION` | `aws_region` |
     | `AIA_DEPLOY_ROLE_ARN` | output `github_deploy_role_arn` |
     | `AIA_ECR_REGISTRY` | output `ecr_registry` |
     | `AIA_OPS_BUCKET` | output `ops_bucket` |
     | `AIA_DEVELOP_INSTANCE_ID` | output `instance_id` |
     | `AIA_PUBLIC_HOSTNAME` | `public_hostname` |
   - Protection: *Deployment branches and tags* → selected branches → `develop`
     only. Optional: required reviewers, once more than one person deploys.
10. **Branch `develop`**: create it from `main` if the deploy PR did not. Then
    protect it (Settings → Branches, or a ruleset): require a pull request,
    require the `CI` checks (`Backend`, `API contract`, `Frontend`, `Application
    starts`, `Parity status`), block force pushes and deletion, restrict direct
    pushes to administrators.
11. **Branch `main`**: stricter — the same, plus require review, and merge only
    release PRs from `develop`. **Then release once before the first deploy:**
    GitHub registers `workflow_run` and `workflow_dispatch` only from the default
    branch, so `.github/workflows/deploy-develop.yml` deploys nothing — and
    offers no *Run workflow* — until it is on `main`. A release PR `develop →
    main` (or a chore PR carrying only that file) is the step; after it, every
    CI-green head of `develop` deploys, and every later change to the workflow
    itself is likewise inert until released (OI-37).
12. **Cognito users.** Provisioning is administrator-only. Add each person in
    the Cognito console (*Users* → *Create user*; email as username; any
    temporary password is unused because sign-in is Google), or leave it to
    the first Google sign-in: with the Google IdP linked, Cognito creates the
    federated user on first sign-in, and **AIA still grants nothing** until the
    develop seed or an organization owner adds them (403 `not_provisioned`).
13. **First deploy and seed** — [`deploy/develop/README.md` § First deployment](../../deploy/develop/README.md#first-deployment-bootstrap).

## Resize, destroy

`deploy/develop/README.md` § Resize and § Destroy. `terraform destroy` removes
everything here including both buckets (`force_destroy`, synthetic data) and
the user pool (deletion protection off).
