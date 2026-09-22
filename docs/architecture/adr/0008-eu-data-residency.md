# ADR 0008 — EU data residency; Bedrock in `eu-central-1` is the only inference path

**Status:** Accepted.
**Date:** 2026-09-22

## Context

Signed client agreements for Czech client research require that client data is
processed and stored in the EU. This was recorded as an open question in three
places and is now closed:

- `docs/architecture/security.md` — "Client research data for Czech clients **may**
  carry an EU residency requirement that constrains region and provider routing."
- `docs/migration/migration-plan.md` — listed under open questions.
- [ADR 0005](0005-llm-gateway.md) — "would transit a third party, and residency is
  unresolved".

The requirement is not a preference and not limited to inference. It covers every
place client data comes to rest or is processed: database, object storage,
backups, application logs and AI traces.

One provider fact decides the inference path. The first-party Anthropic API pins
inference geography with a parameter that accepts `us` and `global` **only** —
there is no EU value. It therefore cannot satisfy an EU-only processing clause for
client-scoped data, regardless of contractual terms with the provider.

## Decision

**All processing and storage of client data occurs in the EU. Model inference for
client-scoped data runs on Amazon Bedrock in `eu-central-1`. The first-party
Anthropic API is not an approved provider for client data.**

Concretely:

| Concern | Decision |
| --- | --- |
| Model inference | Amazon Bedrock, `eu-central-1` |
| Compute | AWS App Runner, `eu-central-1` (see [ADR 0002](0002-postgresql-authoritative-store.md)) |
| Database | RDS PostgreSQL, `eu-central-1` |
| Object storage | S3, `eu-central-1`, with EU-only replication |
| Identity | Cognito, `eu-central-1` (already the case — see [ADR 0003](0003-cognito-identity-boundary.md)) |
| Backups | Same region; no cross-region copy outside the EU |
| Logs and AI traces | EU-hosted, or self-hosted in `eu-central-1` |

AWS is a single processor across all of these. That is deliberate: every
additional vendor is another data processing agreement to hold, another entry in
the Article 30 record, and another residency claim to evidence when a client asks.
For a one-person team selling under residency clauses, the administrative
consolidation is worth more than per-unit cost savings elsewhere.

### Effect on the model gateway

[ADR 0005](0005-llm-gateway.md)'s `data_classification` field becomes
load-bearing rather than advisory. The gateway must:

- Route any client-scoped payload to a Bedrock EU adapter, and to nothing else.
- **Refuse** an unclassified payload rather than applying a default. A default is
  how residency breaches happen quietly.
- Record the resolved provider, region and classification on every call, so that
  residency is auditable per invocation and not merely asserted in a document.

`fallback_policy` inherits the constraint: an authorised fallback may only name a
model reachable in the same region. There is no cross-region fallback.

## Consequences

**Hosted server-side tools are unavailable.** Bedrock does not offer hosted web
search, web fetch or code execution. The Knowledge/RAG and Data Sourcing agents
assume web search exists. That capability must be built as a client-side tool
against an EU-hosted search service, and it is unbudgeted scope that belongs in
the Phase plan rather than being discovered during agent implementation.

**Pricing is Bedrock's, not first-party.** Bedrock is partner-operated with its
own rate card. Budget estimation in the gateway must price against the Bedrock
rate card version, not published first-party rates.

**Pseudonymization is upstream.** Row-level client data is pseudonymized by the
client before upload. That reduces but does not remove personal-data obligations:
re-identification risk needs a written position, and the pseudonymization
boundary should be asserted at ingest rather than assumed.

**Development uses synthetic data only.** No client data in any non-EU
environment, and none in development regardless of region.

## What would make us revisit

- The first-party Anthropic API gaining an EU inference geography.
- A client contract that expressly permits non-EU processing, which would widen
  provider choice for that client's studies only — never globally.
- A hosted EU search or code-execution capability appearing on Bedrock, which
  would remove the build-it-yourself consequence above.
