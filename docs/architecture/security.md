# Security architecture and threat model

## What is at risk

| Asset | Sensitivity |
| --- | --- |
| Uploaded client research datasets | High — commercially confidential, may contain personal data |
| Generated reports and findings | High — pre-publication client deliverables |
| The calibrated population panel | Medium — licensed reference data with clearance metadata |
| AI provider credentials | High — direct financial loss if leaked |
| Project content and history | Medium — reveals client strategy |
| Cross-tenant metadata | High — even project titles disclose who a competitor's clients are |

Respondents in the synthetic population are not real people, which removes a
large class of data-subject risk. Uploaded *customer* datasets can contain real
personal data and are treated as the most sensitive class.

## Current posture, stated plainly

Two things that are easy to conflate, and must not be: **code** and **deployed
infrastructure**. Both have to be true before real client data is safe here, and
only one of them is this repository's to finish.

### Implemented in software

**Authentication.** `CognitoIdentityProvider` verifies Cognito JWTs: RS256 with an
algorithm allow-list, JWKS fetch with rotation pickup and rate-limited refresh,
issuer, `token_use`, audience, and expiry with clock skew. `IdentityProvider` is
the only identity seam; nothing else in the codebase reads identity from anywhere.

A verified token proves **identity and nothing else**. `VerifiedIdentity` carries
no role, client or study, and a test asserts those fields stay absent — because an
authorization model that trusts token claims is one misconfigured app client away
from self-service access.

`DevelopmentIdentityProvider` trusts a header so the system runs without Cognito
locally. It is refused outside `local` and `test` by two independent guards.

**Authorization.** In PostgreSQL, not in claims. `User → Organization membership →
Client grant → Study grant → Role → Permissions`, resolved per request, so
deactivation and revocation take effect on the **next request** rather than at
token expiry. See [scope-and-authorization.md](scope-and-authorization.md).

**Separation of duties.** Independent review is the default for approvals, with
self-approval available only where explicitly enabled by persisted policy, and
every decision written to an append-only ledger.

**Egress and residency.** The fail-closed boundary in
`aia_core.domain.residency`, per [ADR 0008](adr/0008-eu-data-residency.md).

### Still required operationally

Not defects in the code; work that has to exist outside it:

- **A Cognito user pool and app client**, and Google Workspace federation —
  declared in [`infra/develop/identity.tf`](../../infra/develop/identity.tf);
  the Google OAuth client and the `terraform apply` are human actions.
- **Environment configuration** — the develop host's env file is written from
  SSM Parameter Store (`deploy/develop/bin/write-env.sh`); production is still to
  be provisioned.
- **S3 bucket provisioning**, encryption and lifecycle policy for artifacts —
  declared in [`infra/develop/main.tf`](../../infra/develop/main.tf) (SSE-S3,
  versioning, TLS-only, private, lifecycle).

The API refuses to boot in production without the identity configuration, so a
missing pool is a failed health check rather than an open door. It also refuses
to boot without its build SHA and with any artifact store but S3 itself. **Until that
infrastructure exists, no deployed environment holds real client data** — but the
reason is provisioning, not an absent verifier.

## Tenant isolation

The strongest control currently in place.

`ProjectRepository` **cannot be constructed without an `organization_id`** — it
raises. There is no method that fetches a project by id alone. Every read and
every write is filtered by tenant in the same SQL statement that finds the row,
so a handler cannot leak another tenant's data by forgetting a filter, because
there is no unfiltered path to forget.

Cross-tenant access raises `ProjectNotFound`, which the API maps to **404, not
403**. A 403 would confirm the project exists, disclosing the existence of other
tenants' data. Tests assert 404 on every route, read and write.

Defence in depth still owed: PostgreSQL row-level security as a second layer, so
that a future raw query cannot bypass the repository.

## Threats and controls

| Threat | Control | Status |
| --- | --- | --- |
| Unauthenticated access | Cognito JWT verification; production refuses to boot unconfigured | Implemented in code; pending provisioning |
| Cross-tenant data access | Repository cannot be built unscoped; 404 not 403 | Implemented, tested |
| Privilege escalation | Permissions resolved from PostgreSQL grants, never from token claims | Implemented, tested |
| Authoring and approving the same work | Independence required by default; self-approval only by persisted policy, and never a substitute for permission | Implemented, tested |
| Client data leaving the EU | Fail-closed egress boundary; per-class approved routes | Implemented, tested; routes pending provisioning |
| Scope widened by a model or tool | `StudyContext` issuable only by the authorization layer | Implemented, tested |
| SQL injection | SQLAlchemy parameter binding throughout; no string-built SQL | Implemented |
| Path traversal | No filesystem paths in the API. Project ids are regex-constrained (`^PRJ-[0-9a-f]{1,32}$`) at the route | Implemented, tested |
| Malicious upload | Type/size validation, no execution, out-of-webroot storage | Not implemented (Phase 5) |
| SSRF via a URL in a brief | Allowlist, block private ranges, resolve then re-check | Not implemented (Phase 5) |
| Secret leakage into logs | Key- and value-shape redaction before any sink | Implemented, tested |
| Secret leakage into responses | Error details redacted; unhandled exceptions return a generic message | Implemented, tested |
| Secret leakage into frontend | Credentials never serialised into any response model | Implemented |
| Prompt injection via uploaded data | Dataset content is data, not instruction; no tool access from research prompts | Design rule, Phase 4/5 |
| Information disclosure via errors | One error shape; stack traces and driver messages never returned | Implemented, tested |
| XSS | React escaping; no `dangerouslySetInnerHTML` in new code | Implemented by convention |
| CSRF | Token-header auth rather than cookie auth, so CSRF does not apply | Implemented by design |
| Denial of service | Page-size caps, request body limits, per-tenant concurrency caps | Partial — caps implemented, rate limiting absent |
| Cost exhaustion | Per-study budget ceiling with reservations, under a study-row lock, enforced before every paid call | Implemented, tested under contention |
| Double billing after a crash | `RECOVERY_REQUIRED` + `SETTLED_UNCERTAIN`; a possibly-billed call is never auto-retried | Implemented, tested |
| Dependency vulnerabilities | `pip-audit` and `npm audit` in CI | Implemented |
| Committed secrets | CI greps for provider key shapes and fails the build | Implemented |
| Client identity disclosed by legacy filenames | Repository private (D5); `tools/exposure_check.sh` blocking in CI; detail confined to the private reference repository | Guard implemented; **visibility change outstanding** |

## Repository visibility

**This repository is to be PRIVATE** — decision D5, 2026-09-22, frozen. It holds
the production codebase, architecture, client configuration and migration
metadata, none of which is intended for public distribution. Separately, the
legacy reference is client work whose *filenames alone* name real companies, and
a filename is disclosure even when the file it names is absent.

✅ **Applied 2026-09-22T20:21:38Z** and verified against the API:
`private: true`, `visibility: private`. Re-check with
`gh api repos/AiAnalytics-AIA/AIA --jq .visibility`. It was applied by a human —
an agent session cannot change repository settings in this environment.

**Private is not a control by itself, and nothing here depends on it.** Three
reasons this matters for the threat model:

1. **It is a setting, not a boundary.** It can be changed back, by accident or by
   someone who does not know why it was set.
2. **It is not need-to-know.** Every collaborator, every CI log and every future
   fork sees whatever is committed. Confidential material is kept out of the
   repository, not hidden by its visibility.
3. **It is not retroactive.** It closes future access; it does not retract what
   was already fetched or indexed while the repository was public.

So the controls stand on their own: detailed reference material lives only in
`AiAnalytics-AIA/AIA-reference` (private), and `tools/exposure_check.sh` blocks
its return regardless of visibility. History is deliberately **preserved** —
going private lowered the urgency of a rewrite enough that keeping history is the
better trade. Full reasoning, the measured public surface and the rewrite
procedure should it ever be needed:
[`../migration/public-exposure-remediation.md`](../migration/public-exposure-remediation.md).

## Secret handling

Three layers:

1. **Never stored in the repository.** `.env` is gitignored, `.env.example`
   contains only placeholders, and CI fails if a `sk-ant-…` or `sk-proj-…` shape
   appears anywhere in the tree.
2. **Never logged.** `aia_api.observability.redact` scrubs by key name
   (`api_key`, `secret`, `token`, `password`, `authorization`, `cookie`, …) at any
   nesting depth, and by value shape for provider key formats and bearer tokens.
   Both the log formatter and the error serialiser run it.
3. **Never returned.** No response model contains a credential field. Provider
   keys will be stored encrypted at rest and referenced by id.

A note on the value-shape patterns: they must allow interior hyphens. Current
keys are `sk-ant-api03-…` and `sk-proj-…`, and a character class without `-`
stops matching at the first separator and leaks the remainder of the key. This
was a real bug caught by a test, and the test remains.

## Request correlation

Every request carries a `request_id`, returned in `X-Request-ID` and included in
every error body and log line. An inbound id is honoured so traces survive across
services, but it is stripped to `[A-Za-z0-9._-]` and capped at 64 characters — an
unsanitised value would let a client inject forged lines into the log stream.

## Production configuration guards

`Settings.validate_for_production()` runs at startup and refuses to boot on:

- a missing `DATABASE_URL`
- a SQLite `DATABASE_URL` (no concurrency, no shared state)
- `AIA_DEBUG` enabled
- a wildcard CORS origin

It reports every problem at once, and it fails at startup rather than on first
request, so a bad deploy fails its health check instead of serving traffic in an
unsafe state. Interactive API docs are disabled in production; the OpenAPI
document is still published as a CI artifact.

## Audit trail

`project_events` and `project_provider_events` are append-only, carry `actor_id`
and `request_id`, and are never updated or deleted. Provider switches, settings
changes, revisions, trash and restore are all recorded. This is a security
control as much as a product feature: it answers who changed what, and whether a
provider switch was genuinely user-authorised.

## Known gaps

Ordered by how much they should worry you:

1. **Identity infrastructure declared, not yet applied.** The verifier exists and
   `infra/develop` declares the pool, client and Google federation; a human must
   create the Google OAuth client and run `terraform apply`. Until then no
   deployment exists at all, and the develop deployment holds synthetic data only.
2. **No approved egress routes configured.** The boundary is enforceable and
   currently permits nothing, which is the right failure mode but means no client
   inference can run until routes are declared and justified against
   [ADR 0008](adr/0008-eu-data-residency.md).
3. **No rate limiting.** An authenticated member can exhaust the API.
4. **No encryption-at-rest configuration** documented for the database or bucket.
5. **No RLS** as a second isolation layer, so a future raw query could bypass the
   repository.
6. **No OpenTelemetry instrumentation.** Structured logging, request correlation
   and secret redaction exist; distributed tracing does not. See
   *Observability* below.
7. **Client-identifying legacy filenames remain** in `reference-manifest.json`
   pending D4. Not a code defect, but open exposure — now to everyone with
   repository access rather than to everyone. The ~7 months of public
   availability before 2026-09-22T20:21:38Z cannot be retracted.
8. **Upload, SSRF and export controls** are not built because those features are
   not built.

## Observability

**OpenTelemetry is the instrumentation standard.** It is a decision, not a
description: what exists today is structured JSON logging, a `request_id` on every
request, response, log line and error body, and secret redaction before any sink.
There are no spans, no trace propagation and no metrics, and no document should
imply otherwise.

The backend OTel exports to is **replaceable and unchosen**. Instrumenting against
the vendor-neutral API is what keeps it that way; no observability vendor is part
of the architecture.

## Settled, and not open questions

These have been asked before and are answered. They are recorded here so they are
not reopened by inference from an older document:

- **Identity provider.** Cognito, federated to Google Workspace, with
  authorization in AIA rather than in claims.
  [ADR 0003](adr/0003-cognito-identity-boundary.md).
- **Tenancy model.** `Organization → Client → Study`, with Client and Study as hard
  isolation boundaries. [ADR 0004](adr/0004-client-study-isolation.md).
- **Data residency.** EU residency is a frozen invariant with a fail-closed egress
  boundary, independent of which vendor eventually satisfies it.
  [ADR 0008](adr/0008-eu-data-residency.md).
