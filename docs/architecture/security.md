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

**Authentication is not implemented.** `aia_api.dependencies.get_principal` is a
development seam that trusts `X-AIA-User` and `X-AIA-Org` headers. It **refuses
every request in production**, and a middleware gate rejects authenticated routes
before any dependency resolves.

This is deliberate: the AIA repository has no identity provider wired up, and the
alternative — shipping a placeholder that *looks* like auth — is worse than an
explicit refusal. The system fails closed.

Replacing that single function with a token verifier that derives `user_id` and
`organization_id` from verified claims is the whole of the integration. Nothing
else in the codebase reads identity from anywhere else.

Until then, no environment holding real client data may run this API.

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
| Unauthenticated access | Auth gate; production fails closed | Partial — gate present, verifier absent |
| Cross-tenant data access | Repository cannot be built unscoped; 404 not 403 | Implemented, tested |
| Privilege escalation | `Principal.roles`; per-tenant roles | Not implemented |
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
| CSRF | Token-header auth rather than cookie auth, so CSRF does not apply | Pending the auth decision |
| Denial of service | Page-size caps, request body limits, per-tenant concurrency caps | Partial — caps implemented, rate limiting absent |
| Cost exhaustion | Per-project budget ceiling enforced before every paid call | Implemented |
| Dependency vulnerabilities | `pip-audit` and `npm audit` in CI | Implemented |
| Committed secrets | CI greps for provider key shapes and fails the build | Implemented |

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

1. **No authentication.** Blocks any deployment with real data. Needs a decision
   on the identity provider.
2. **No authorization model.** `Principal.roles` exists but nothing consumes it.
   Roles, and who may approve a gate or export a report, are undefined.
3. **No rate limiting.** An authenticated tenant can exhaust the API.
4. **No encryption-at-rest configuration** documented for the database or bucket.
5. **No RLS** as a second isolation layer.
6. **Upload, SSRF and export controls** are not built because those features are
   not built.

## Decisions needed from the team

- **Identity provider.** Is there an existing AIA SSO, or should this be
  OIDC-based? The commit history mentions AWS Amplify but no identity
  configuration is present in the repository.
- **Tenancy model.** `apps/web` routes are already `/org/[orgSlug]/…`, implying
  organizations. Is a user in exactly one organization, or several?
- **Data residency.** Client research data for Czech clients may carry an EU
  residency requirement that constrains region and provider routing.
