# `infra/account` — what the AWS account holds once

Develop and production share one AWS account (ADR 0031). What exists once per account and every
environment relies on lives here, in a root of its own, so that no environment's `terraform destroy`
can reach it:

| Resource | Why it is here |
|---|---|
| GitHub OIDC provider (`token.actions.githubusercontent.com`) | Every deploy and plan role trusts it. While `infra/develop` created it, destroying develop would have removed production's deploy trust (ADR 0031 §2). Develop and production look it up |
| CloudTrail `aia-account` and its bucket `aia-account-cloudtrail-<account>` | The account's audit trail (ADR 0031 §3): every region's management events, log file validation, a private versioned bucket, TLS only, logs kept `cloudtrail_retention_days` (365) |

Everything above carries `prevent_destroy`, and `packages/aia_core/tests/test_terraform_roots.py`
fails if it is dropped or if another root declares the OIDC provider. State: the develop state
bucket, key `account/terraform.tfstate`, its own lock.

## First apply: taking the provider over from develop

The provider exists already; develop created it. It is imported here, never destroyed and
recreated, because every deploy role's trust names its ARN.

1. Before anything, check what the account has (read only):
   ```bash
   aws iam list-open-id-connect-providers
   aws cloudtrail describe-trails --region eu-central-1 \
     --query 'trailList[].[Name,IsMultiRegionTrail,S3BucketName]'
   ```
   If a multi-region trail already exists, stop: import it instead of creating a second (each copy of
   management events after the first is billed), and say so in the plan file.
2. Import the provider and plan:
   ```bash
   cd infra/account
   export TF_DATA_DIR=/tmp/tf-account   # in CloudShell: the providers do not fit in its 1 GB home
   terraform init
   terraform import aws_iam_openid_connect_provider.github \
     arn:aws:iam::<account>:oidc-provider/token.actions.githubusercontent.com
   terraform plan
   ```
   The plan must read **7 to add, 1 to change, 0 to destroy**: the trail, its bucket and the bucket's
   public access block, versioning, encryption, lifecycle and policy are added; the one change is the
   provider's tags, `Environment` from `develop` to `account` (its URL, client ids and thumbprints are
   develop's, unchanged). Anything else, above all a replacement of the provider: stop, apply nothing.
3. `terraform apply` that plan.
4. Then `infra/develop`: its `removed` block takes the provider out of develop's state without
   destroying it. Its plan must show the provider as **"will no longer be managed by Terraform"** and
   **0 to destroy**; apply. If develop's tfvars still set `create_github_oidc_provider`, Terraform warns
   about an undeclared variable; delete the line from SSM `/aia/terraform/develop/tfvars`.

Steps 3 and 4 are safe in either order: `removed { lifecycle { destroy = false } }` never deletes the
provider, so between them it simply belongs to no state.

`terraform validate` and `fmt -check` run in CI on every pull request that touches `infra/`
(`infra/develop/README.md` § Terraform in CI). CI plans develop only; this root is planned by hand.
