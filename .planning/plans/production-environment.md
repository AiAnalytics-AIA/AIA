---
status: in-progress
chunks:
  - "[x] PE0. The production environment ADR (supersedes "undecided" in ADR 0009)"
  - "[ ] PE1a. `infra/account`: the GitHub OIDC provider (moved out of develop by import) and CloudTrail, under prevent_destroy; the roots test"
  - "[ ] PE1b. `infra/production` foundation: state, tags, its own VPC, KMS, the three buckets (prevent_destroy, other environments denied), ECR"
  - "[ ] PE1c. RDS PostgreSQL 16 in private subnets: KMS, deletion protection, 14-day PITR, final snapshot, the database URL in SSM"
  - "[ ] PE1d. The host: t3a.large, encrypted EBS, EIP, DLM, an instance role conditioned on the Environment tag under a permission boundary"
  - "[ ] PE1e. Identity and DNS: the ai-analytics.ai zone and app record, the Cognito pool, Google and callbacks for app.ai-analytics.ai"
  - "[ ] PE1f. Alarms (develop's three, RDS, oldest QUEUED step), the tagged Budget, the production deploy role, tagged Bedrock profiles"
  - "[ ] PE2. `deploy-production.yml`: a manual release, an RDS snapshot first, the rollback"
  - "[x] PE3. Terraform validation in CI: format, validate and plan on a pull request that touches `infra/`"
  - "[ ] PE4. The egress allow-list: a forward proxy for search hosts, reconciled with fetch from any public host"
  - "[ ] PE5. Production route classes and retention evidence; `AIA_AI_ROUTE_ID` must equal `bedrock-eu-primary` for panel lineage; ADR 0022 approvals per organization"
  - "[ ] PE6. Population provisioning in production: asset root, import, establish, `record-dictionary`, `record-catalogue`, the store"
  - "[ ] PE7. Tagged Bedrock profiles: the worker accepts the profile ARN (or the plan uses `eu.` ids); cost reconciliation includes tool spend"
  - "[ ] PE8. A freeze of auto-deploys during a tier B run"
  - "[ ] PE9a. Restore and the delete path exercised once on develop (W4): a restore after a deletion does not resurrect it (`study-data-lifecycle#SDL6`)"
  - "[ ] PE9b. The rest of the release checklist evidenced (W5): rollback, alarms, the activation profile `READY` on the production host"
  - "[ ] PE10. An audited operator command that creates the first organization and its owner; production starts empty (D-22)"
  - "[ ] PE11. An external security review of the production hostname before the first client (D-23)"
  - "[ ] PE12. The browser holds no token: the API authenticates by AIA's HttpOnly session cookie with a CSRF token, before the first production sign-in (OI-35)"
---
# The production environment

The environment the MVP is released into. Written 2026-10-19 from `mvp-target-architecture.md` §6 and `.planning/evidence/mvp-master-traces/trace-5-deepresearch-data-infra.md`.

**Owner: S3.** Takes the gap rows G2, G6, G7, G9 and interface I18 of `mvp-master-plan.md` §6.1 and serves AC-14, AC-15 and gate I-5 (production released).
Every chunk below is **open**; a chunk is built from this file, not from the master plan.

## Decisions this plan carries (settled by the owner; not re-asked)

- **PE0 is done by ADR 0031** (`docs/architecture/adr/0031-production-environment.md`), accepted by the owner
  on 2026-10-20 ("accept 0028-0033, 0035, 0038-0040"). It supersedes ADR 0009's "production compute remains
  undecided"; ADR 0009, the ADR index, CLAUDE.md §2 and ARCHITECTURE.md §9 still say "undecided" (a docs
  PR's follow-up). Ticked 2026-10-27.
- A separate production on the one-host pattern with RDS PostgreSQL 16, in the **same AWS account** as develop with separate resources, tags and the mitigations of the target architecture §6.2 (Q24).
- About ten users; no permanent staging; develop is staging and tier B runs there (target architecture).
- Production release is a **blocker for the MVP release even when tier B passes on develop** (the owner's I-5 reads "production released").

## Chunks

**PE0. The production environment ADR (supersedes "undecided" in ADR 0009)**  
Records the same-account decision and its mitigations: shared Bedrock quota, tag-conditioned IAM with a permission boundary, separate OIDC roles, destroy guards.

**PE1. `infra/production`, split into PE1a-PE1f (2026-10-28, the owner's go-ahead in the PE3 session)**  
ADR 0031 decides the shape; each sub-chunk is one PR, and every apply is a person's, its steps in the
PR and the root's README. The OIDC provider and destroy hazards (`infra/develop/github.tf:8-31`,
`main.tf:106-117` @ 854c209) are handled so one root cannot destroy the other's resources.

Decided by the owner on 2026-10-28 (this session, answering the split):
- **Network: production's own VPC**, two public subnets for the host and two private ones for RDS, no
  NAT and no internet route from the private ones; develop stays in the default VPC.
- **Images: production's own ECR repositories** (`aia-production-api`, `-worker`, `-web`); the release
  (PE2) copies the exact SHA develop ran into them, so a develop push never changes what production
  runs.
- **The content security policy** (scope freeze, PE1) lives in production's Caddyfile, which PE2
  creates; it is built with PE2.

- **PE1a.** `infra/account/` owns what the account holds once: the GitHub OIDC provider, imported from
  develop (whose `removed` block drops it from its state without destroying it), and CloudTrail with
  its bucket, all under `prevent_destroy`. `test_terraform_roots.py`: only `infra/account` declares the
  provider, its three resources keep `prevent_destroy`, and `infra/production` declares no
  `force_destroy = true`. Ticked once the owner's apply ran (`infra/account/README.md` § First apply).
- **PE1b-PE1f** as listed above, each with its own plan check and apply steps.

**PE2. `deploy-production.yml`: a manual release, an RDS snapshot first, the rollback**  


**PE3. Terraform validation in CI: format, validate and plan on a pull request that touches `infra/`**  
No Terraform step exists in `ci.yml` though two documents assume one. A separate PR, because `ci.yml` is outside the docs-only path list.

**PE4. The egress allow-list: a forward proxy for search hosts, reconciled with fetch from any public host**  
The proxy contradicts "any public host" (`deep_research_live.py:161-198`); the decision is which hosts the production worker may reach and how.

**PE5. Production route classes and retention evidence; `AIA_AI_ROUTE_ID` must equal `bedrock-eu-primary` for panel lineage; ADR 0022 approvals per organization**  
`licence_determinations.py:44`. ADR 0010's amendment is develop-only today.

**PE6. Population provisioning in production: asset root, import, establish, `record-dictionary`, `record-catalogue`, the store**  
Interfaces I18; shared with `run-qc-and-checkpoint#RQC10`.

**PE7. Tagged Bedrock profiles: the worker accepts the profile ARN (or the plan uses `eu.` ids); cost reconciliation includes tool spend**  
`ai_runtime.py:254, 516` require an `eu.` id, so the ARNs of `develop-spend-attribution` 1 would be refused at start; Brave and Athena spend is not in the usage ledger.

**PE8. A freeze of auto-deploys during a tier B run**  


**PE9a. Restore and the delete path exercised once on develop (W4), consuming `study-data-lifecycle#SDL6`**  
**PE9b. Rollback, alarms and the activation profile `READY` on the production host (W5)**  
A production release stays a blocker on I-5 whatever tier B showed on develop.

**PE12. The browser holds no token: the API authenticates by AIA's HttpOnly session cookie with a CSRF token (OI-35)**  
The owner, 2026-10-25 (OI-35 (a), the audit page): "HttpOnly cookie session before production." Half of it exists.
`POST /session` already sets an HttpOnly, SameSite=Lax cookie, `__Host-aia_session` when deployed (`apps/api/src/aia_api/routers/session.py:69-73,120-122 @ 399b8057`, #831). But it serves only the `/app` gate, and its value is the Cognito id token itself (`session.py:20-22`).
Every `/api/v1` call still sends `Authorization: Bearer` (`apps/web/src/lib/api.ts:38`, `apps/api/src/aia_api/dependencies.py:410-416`). The browser keeps the id and refresh tokens in `sessionStorage` (`apps/web/src/lib/auth.ts:18,96-119`), within reach of any XSS.
Done when:
- the API accepts the session cookie on every `/api/v1` route, through the same verification and `ScopeResolver` path as a bearer token;
- every unsafe method requires a CSRF token minted with the session (double-submit or header-bound) and refuses without it by name;
- the session's lifetime no longer rides the id token's: the refresh happens server-side, so no refresh token reaches the browser;
- `sessionStorage` holds no token after sign-in;
- the bearer path is refused outside `AIA_ENV` local and test, or kept only for named non-browser callers. Which one is decided in this chunk's PR.

Its tests: a cookie-only call succeeds; an unsafe call without the CSRF token is refused; a bearer call is refused in a deployed environment; and a journey shows no token in the browser's storage after sign-in. W1, beside PE10: settled before anyone signs in on production. The `IdentityProvider` seam is unchanged (OI-35's smallest fix).

## Open: owner clarifications

- The production hostname, RDS sizing and Bedrock quota (owner and operator).


## Execution prerequisites (2026-10-20)

PE0/PE3 precede PE1's apply and PE2's release workflow. Resolve the model-identity/invocation-target
contract (develop-spend-attribution 5a) before configuring the PE7 tagged target, not after a failing
production startup. PE4 must preserve the decided public-host retrieval scope and existing URL/
private-address safeguards; a proxy cannot silently reduce the product to a fixed publisher list.
PE5/PE6 and the effective activation profile are evidenced before live production work. PE8 freezes
the tested candidate during tier B; PE9a consumes SDL6 and PE9b closes the checklist; both are prerequisites to final manual release.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

**New chunks.** PE10 (W1), PE11 (W4). PE12 (W1) was added 2026-10-25 from the owner's OI-35 answer, not the scope freeze.

**Existing chunks, changed by the owner's answers.**

- **PE0-PE3 (D-20).** The proposed sizes are accepted (`t3a.large`, `db.t4g.medium`, measured on
  develop first). Production's hostname is **`app.ai-analytics.ai`** (page Q15: (a)): its Cognito and Google
  callbacks and the certificate are for that name.
- **PE1.** A content security policy.
- **PE4 (D-19).** The proxy blocks private and metadata ranges only; the application's per-hop checks
  are the boundary.
- **PE7 (D-21).** Tagged application inference profiles in production.
- **PE9a (D-25).** RPO 24 h and RTO 4 h, the database and S3 restored together, proved once.
- **PE9b (D-26, Q7).** GlitchTip already runs for errors (the owner, "i have glitchtip
  implemented"). Production adds a GlitchTip uptime monitor on its `/health`, alerting Nigel Blount
  by e-mail (its threshold set and stated in the chunk's PR); no other service.
- **The release checklist (D-28).** Terms, a privacy notice, a client DPA and the data owner's
  confirmation that the panel licence covers paid deliverables, all before the first client; the
  first-sign-in notice is the only screen.

## PE3: what landed, and what a person still does (2026-10-28)

**Landed** (`.github/workflows/ci.yml`, jobs `terraform` and `terraform-plan`):

- `Terraform (format, validate)`: `terraform fmt -check -recursive infra`, then `init -backend=false`
  and `validate` in every `infra/*/` root with a `versions.tf`, under Terraform 1.10.5 (the minimum
  `versions.tf` accepts). No credentials and no state. It runs on a pull request that changes
  `infra/**` or `ci.yml` (the `changes` job's new `infra` output) and on every push to `main` and
  `develop`. `dispatch-develop` does not wait on it.
- Checked before the push, with Terraform 1.10.5: `infra/develop` on `origin/develop` @ 7107c1f0 and
  #1046's head (the two `aws_bedrock_inference_profile` resources, `model_source` in
  `ignore_changes`, the `postcondition`) both pass `fmt`, `init -backend=false` and `validate` (AWS
  provider 5.100.0). A root with an unsupported argument fails the step (exit 1). The `changes`
  filter, run outside CI: a plan-only change is `infra=false`, an `apps/` change is `infra=false`,
  `infra/develop/main.tf` and `ci.yml` are `infra=true`, a push is `infra=true`.
- `Terraform plan (develop)`: written, **off**. It runs only with the repository variable
  `TERRAFORM_PLAN_ENABLED=true`. Until then the validate job's summary says so.

**Why the plan is gated by a person.** The plan reads develop's state, which holds the PostgreSQL
password, the Google client secret and the Cognito client secret. A job on a pull request runs the
branch's own copy of the workflow, so anyone who can push a branch could print whatever the plan's
role can read. Read-only rights do not change that. So the role may be assumed only from the
`terraform-plan` environment, and that environment requires a person's approval before the job
starts. The plan runs with `-lock=false`, so it writes nothing, not even the state's lock file.

**PE3 done (2026-10-28).** The role was applied by the owner (plan: 2 to add, 0 to change, 0 to
destroy), the `terraform-plan` environment and `TERRAFORM_PLAN_ENABLED` set, and the plan ran once on
#1076 behind his approval: job 122931673979, every resource refreshed with no access refused,
"No changes. Your infrastructure matches the configuration." (16:04 UTC).

### The person's steps (no agent may do these: IAM, an apply, GitHub settings)

Updated 2026-10-28 after #1065 merged: the role is now Terraform in `infra/develop/github.tf`
(`aws_iam_role.github_plan`, merged by the follow-up PR), and the plan job reads its tfvars from SSM
`/aia/terraform/develop/tfvars`, the parameter an operator's apply reads, so GitHub keeps no copy of
them and no secret is set.

1. **The subject.** Add `github_plan_oidc_subject` to the tfvars in SSM `/aia/terraform/develop/tfvars`:
   the value of its `github_oidc_subject` with `:environment:develop` replaced by
   `:environment:terraform-plan`. The organization issues immutable subjects (develop-deployment, run
   35863981545); unset, the role trusts a subject its tokens never carry.
2. **The apply**, from CloudShell on a clean checkout of `develop` (after the follow-up PR merges), with
   that tfvars: `terraform plan` must read **2 to add, 0 to change, 0 to destroy** (`aws_iam_role.github_plan`,
   `aws_iam_role_policy.github_plan`) and one new output, `github_plan_role_arn`. Anything else, in
   particular a change to `aws_bedrock_inference_profile.route` / `.lead` or to
   `aws_iam_role_policy.instance`, means the tfvars or the state is not what develop's code expects:
   stop, apply nothing. Then `terraform apply` that plan.
3. **The environment.** GitHub → Settings → Environments → New environment `terraform-plan`; required
   reviewer Nigel Blount; Prevent self-review off (a single reviewer).
4. **Its variable.** In that environment, the variable `AWS_PLAN_ROLE_ARN` =
   `terraform output -raw github_plan_role_arn`. Then the repository variable
   `TERRAFORM_PLAN_ENABLED` = `true`, **last**, so the job never starts before its reviewer exists.
5. **One run.** A pull request that touches `infra/develop` (the docs of this role in
   `infra/develop/README.md`); approve the job and read the plan in its summary. An `AccessDenied` that
   names an action is a read to add to `data.aws_iam_policy_document.github_plan`. PE3 is ticked in that
   pull request once the plan has run.
6. Optional: `Terraform (format, validate)` a required check on `develop`.

Correction (2026-10-28): `infra/develop/.terraform.lock.hcl` **is** committed (since #525, AWS provider
5.100.0). #1065 said otherwise from a directory listing that hid dotfiles. CI's `init -backend=false`
honours it, so CI and the operator's apply already use the same provider.
