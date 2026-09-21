> [!WARNING]
> **SUPERSEDED — NOT CURRENT REQUIREMENTS.**
>
> This document describes the *original* AIA MVP: a single-case workspace that
> produced a copy/paste correlation matrix for **manual** Sociomapping. That scope
> was superseded by the production rebuild brief, which replaces the AIA
> application with the full NPC Panel research and simulation product.
>
> It is retained for historical context only. Do not implement from it, cite it as
> a requirement, or treat it as a backlog.
>
> **Current authoritative documentation:**
> - Product scope — [`docs/product/`](../../product/)
> - Architecture — [`docs/architecture/`](../../architecture/)
> - Migration status — [`docs/migration/status.md`](../../migration/status.md)

---

# AiA MVP Scope (v1)

## Objective
Ship a usable MVP that lets a user complete one end-to-end AiA workflow reliably, with clear ownership, basic auth, and a deployable staging environment.

## Must-have (in scope)
1. **Core workflow #1 (happy path)** works end-to-end.
2. **Auth foundation** (login + protected route/session baseline).
3. **User model persistence** for minimal account state.
4. **Staging deployment** reachable by URL.
5. **Basic observability** (health endpoint + error visibility in logs).

## Nice-to-have (only if must-haves are done)
- Improved UX polish for onboarding flow.
- Additional workflow variants.
- Better analytics instrumentation.

## Explicitly out of scope (v1)
- Multi-tenant enterprise controls.
- Advanced permissions matrix.
- Full automation marketplace/integrations.
- Deep reporting dashboards.

## Definition of done
- New user can sign in and complete core workflow #1 in staging without manual intervention.
- Team can deploy and verify health in under 10 minutes using documented steps.
- Known limitations are documented in `docs/BACKLOG.md`.
