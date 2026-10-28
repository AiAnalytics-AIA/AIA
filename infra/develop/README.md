# `infra/develop` — the develop environment's AWS resources

One Terraform root, no modules ([ADR 0009](../../docs/architecture/adr/0009-single-host-develop-environment.md)).
What it creates, and why each piece exists:

| Resource | Purpose |
|---|---|
| EC2 `t3a.medium`, Ubuntu 24.04, 80 GB gp3 encrypted, IMDSv2 only, no key pair | The one host. Management is SSM Session Manager, so no port 22 |
| Elastic IP (+ optional Route 53 `A` record) | The stable address behind `dev.<domain>` |
| Security group: 80/tcp, 443/tcp, 443/udp in; all out | Caddy's two ports; nothing else is reachable |
| Instance role | The host's only credential: S3 (artifacts, ops), ECR pull, SSM parameters under `/aia/develop/`, `bedrock:InvokeModel` on the route's pinned EU model (and the Lead's, when `bedrock_lead_model_id` is set) and the two application profiles, SSM agent, CloudWatch agent |
| S3 `aia-develop-artifacts-<account>` | The `ArtifactStore`. Versioned, SSE-S3, private, TLS-only |
| S3 `aia-develop-ops-<account>` | `backups/` (pg_dump, expire after 30 days) and `deploy/` (bundles, 90 days) |
| ECR `aia-api`, `aia-worker`, `aia-web`, `aia-legacy-panel` | Images by git SHA; 30 kept; scan on push. The list (`local.images`) is also the deploy role's push grant: an image a workflow pushes without it here is refused with 403 (OI-41). `aia-legacy-panel` is pushed only by the hand-dispatched *Reference unit* workflow (`deploy/reference`, ADR 0018 decision 5); the product's deploy builds the other three |
| Bedrock application inference profiles `aia-develop-route`, `aia-develop-lead` | Each copies one model's EU system profile under the `Environment` tag, so Bedrock spend lands in the tagged cost record (AC-15). A changed model id fails the plan until `terraform apply -replace='aws_bedrock_inference_profile.route'` (or `.lead[0]`) |
| SSM parameters `/aia/develop/*` | Configuration for the host's env file; the PostgreSQL password is a generated `SecureString` |
| Cognito user pool + Google IdP + hosted domain + public app client | Authentication only ([ADR 0003](../../docs/architecture/adr/0003-cognito-identity-boundary.md)); PKCE; no self sign-up |
| GitHub OIDC provider + `aia-develop-github-deploy` role | Lets the `develop` GitHub environment push images, upload one bundle and run one SSM command. No stored keys |
| `aia-develop-github-plan` role | Lets CI's *Terraform plan (develop)* job, in the `terraform-plan` GitHub environment only, read develop's state, its tfvars in SSM and the settings of what it refreshes. No write, no bucket object ([§ Terraform in CI](#terraform-in-ci)) |
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

The tfvars an apply reads live in SSM `/aia/terraform/develop/tfvars` (a SecureString), not only on
one operator's disk: fetch them with `aws ssm get-parameter --name /aia/terraform/develop/tfvars
--with-decryption --query Parameter.Value --output text > terraform.tfvars`, never print them, and
store any change back with `put-parameter --overwrite` under the same type and tier. CI's plan job
reads the same parameter.

**From AWS CloudShell**, set `export TF_DATA_DIR=/tmp/tf-develop` before `terraform init`: the
providers do not fit in CloudShell's 1 GB home, and `init` fails there for want of space
(2026-10-28, the plan role's apply).

## Terraform in CI

`.github/workflows/ci.yml` checks this root (production-environment PE3):

- **Terraform (format, validate)**, on every pull request that touches `infra/**` or `ci.yml` and on
  every push to `main` and `develop`: `terraform fmt -check -recursive infra`, then `init
  -backend=false` and `validate` in every `infra/*/` root, Terraform 1.10.5 and the committed
  `.terraform.lock.hcl`. No credentials, no state.
- **Terraform plan (develop)**, on a pull request that touches `infra/**` or `ci.yml`, once the
  repository variable `TERRAFORM_PLAN_ENABLED` is `true`: `terraform plan -lock=false` against
  develop's state, its text in the job summary. It runs in the `terraform-plan` GitHub environment,
  which a person approves for every run, because the state it reads holds the PostgreSQL password and
  the Google and Cognito client secrets, and a pull request runs its own branch's copy of the
  workflow. Read the workflow change in the pull request before approving the job.
  - Its role, `aia-develop-github-plan` (`github.tf`), trusts only that environment's subject:
    `github_plan_oidc_subject`, the tfvars' `github_oidc_subject` with `:environment:develop` replaced
    by `:environment:terraform-plan` (this organization issues immutable subjects). It reads the state
    key, bucket settings (never an object), the resource types this root refreshes and SSM
    `/aia/develop/*` and `/aia/terraform/develop/tfvars`; it writes nothing.
  - The environment's variable `AWS_PLAN_ROLE_ARN` is `terraform output -raw github_plan_role_arn`.
    GitHub holds no copy of the tfvars.
  - The environment's "Allow administrators to bypass" lets an administrator run the job without the
    approval; with one administrator that is the reviewer, but turn it off when there is a second.
  - An `AccessDenied` naming an action in the plan's refresh is a read missing from
    `data.aws_iam_policy_document.github_plan`; add it there and apply.

## Human actions

These need account control an agent does not have. In order.

### Before `terraform apply`

1. **AWS account and region.** Confirm the account this environment bills to,
   and that `eu-central-1` is the region (ADR 0008 requires an EU region;
   Frankfurt hosts the EU Bedrock inference profiles). Set `aws_region` if not.
2. **Hostname.** Choose `dev.<domain>` and set `public_hostname`. Decide whether
   the zone is in Route 53 (`route53_zone_id`) or elsewhere. Chosen:
   `aia-develop.art-chain.io`.
3. **Google OAuth client** (Google Cloud console → APIs & Services → Credentials
   → *Create credentials* → *OAuth client ID*, type *Web application*):
   - Authorised JavaScript origins: none needed.
   - Authorised redirect URI: `https://<cognito_domain_prefix>.auth.<region>.amazoncognito.com/oauth2/idpresponse`
     (Terraform's `google_redirect_uri` output prints the exact value; the
     prefix defaults to `aia-develop`).
   - OAuth consent screen: *Internal* (Workspace users only). **This is the
     Workspace restriction**; nothing in Terraform restricts the domain.
     Cognito keeps its own fixed Google endpoints and drops an `hd` hint, so
     an account outside the Workspace is stopped here or not at all. Whoever
     passes is created in Cognito on first sign-in, and AIA grants them
     nothing until provisioned (403 `not_provisioned`, step 12).
   - Copy the client id and secret into `google_client_id` / `google_client_secret`.
4. **Bedrock model access** (Bedrock console, region `eu-central-1` → *Model
   access*): enable the Anthropic model you will pin; accept the end-user
   licence if prompted. Then complete the verification table in
   [ADR 0010](../../docs/architecture/adr/0010-bedrock-eu-inference-route.md)
   and write the full, versioned EU inference-profile id into `bedrock_model_id`.
   Then run `aws bedrock get-inference-profile --inference-profile-identifier <id>`
   and set `bedrock_destination_regions` to exactly the destination regions it lists
   (the default is the six reported for `eu.anthropic.claude-sonnet-4-5-20250929-v1:0`
   on 2026-09-25); the role is granted the foundation model there and nowhere else.
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
   - If the organization uses immutable OIDC subjects, set
     `github_oidc_subject` in `terraform.tfvars` to the exact subject from
     GitHub's OIDC customization settings. The role trusts that single subject,
     including the immutable organization and repository IDs and `develop`
     environment. The classic repository-name subject is the default otherwise.
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
    itself is likewise inert until released (OI-37). **Done 2026-09-23:** PR #32
    registered the file on `main` at `7f8cb2a`; CI has dispatched it since.
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
