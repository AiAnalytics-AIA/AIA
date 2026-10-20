---
status: planned
chunks:
  - "[ ] PE0. The production environment ADR (supersedes "undecided" in ADR 0009)"
  - "[ ] PE1. `infra/production`: the host, RDS, buckets, SSM, Cognito pool and Google callbacks for the production hostname, ECR, tagged IAM"
  - "[ ] PE2. `deploy-production.yml`: a manual release, an RDS snapshot first, the rollback"
  - "[ ] PE3. Terraform validation in CI: format, validate and plan on a pull request that touches `infra/`"
  - "[ ] PE4. The egress allow-list: a forward proxy for search hosts, reconciled with fetch from any public host"
  - "[ ] PE5. Production route classes and retention evidence; `AIA_AI_ROUTE_ID` must equal `bedrock-eu-primary` for panel lineage; ADR 0022 approvals per organization"
  - "[ ] PE6. Population provisioning in production: asset root, import, establish, `record-dictionary`, `record-catalogue`, the store"
  - "[ ] PE7. Tagged Bedrock profiles: the worker accepts the profile ARN (or the plan uses `eu.` ids); cost reconciliation includes tool spend"
  - "[ ] PE8. A freeze of auto-deploys during a tier B run"
  - "[ ] PE9a. Restore and the delete path exercised once on develop (W4): a restore after a deletion does not resurrect it (`study-data-lifecycle#SDL6`)"
  - "[ ] PE9b. The rest of the release checklist evidenced (W5): rollback, alarms, the activation profile `READY` on the production host"
  - "[ ] PE10. An audited operator command that creates the first organization and its owner; production starts empty (D-22)"
  - "[ ] PE11. An external security review of the production hostname before the first client (D-23)"
---
# The production environment

The environment the MVP is released into. Written 2026-10-19 from `mvp-target-architecture.md` §6 and `.planning/evidence/mvp-master-traces/trace-5-deepresearch-data-infra.md`.

**Owner: S3.** Takes the gap rows G2, G6, G7, G9 and interface I18 of `mvp-master-plan.md` §6.1 and serves AC-14, AC-15 and gate I-5 (production released).
Every chunk below is **open**; a chunk is built from this file, not from the master plan.

## Decisions this plan carries (settled by the owner; not re-asked)

- A separate production on the one-host pattern with RDS PostgreSQL 16, in the **same AWS account** as develop with separate resources, tags and the mitigations of the target architecture §6.2 (Q24).
- About ten users; no permanent staging; develop is staging and tier B runs there (target architecture).
- Production release is a **blocker for the MVP release even when tier B passes on develop** (the owner's I-5 reads "production released").

## Chunks

**PE0. The production environment ADR (supersedes "undecided" in ADR 0009)**  
Records the same-account decision and its mitigations: shared Bedrock quota, tag-conditioned IAM with a permission boundary, separate OIDC roles, destroy guards.

**PE1. `infra/production`: the host, RDS, buckets, SSM, Cognito pool and Google callbacks for the production hostname, ECR, tagged IAM**  
The OIDC provider and destroy hazards in `infra/develop/github.tf:19-31` and `main.tf:106-117` are handled so one root cannot destroy the other's resources.

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

**New chunks.** PE10 (W1), PE11 (W4).

**Existing chunks, changed by the owner's answers.**

- **PE0-PE3 (D-20).** The proposed sizes are accepted (`t3a.large`, `db.t4g.medium`, measured on
  develop first). Production moves to a **new domain**, not yet named: open in the baseline.
- **PE1.** A content security policy.
- **PE4 (D-19).** The proxy blocks private and metadata ranges only; the application's per-hop checks
  are the boundary.
- **PE7 (D-21).** Tagged application inference profiles in production.
- **PE9a (D-25).** RPO 24 h and RTO 4 h, the database and S3 restored together, proved once.
- **PE9b (D-26).** GlitchTip already runs for errors (the owner, "i have glitchtip implemented");
  an uptime probe and a named on-call recipient are open (baseline Q7).
- **The release checklist (D-28).** Terms, a privacy notice, a client DPA and the data owner's
  confirmation that the panel licence covers paid deliverables, all before the first client; the
  first-sign-in notice is the only screen.
