# ADR 0012 — Serve the 18.6.6 interface on the product hostname, behind AIA sign-in, and rebuild behind it

**Status:** Accepted for the `develop` environment (data owner, 2026-09-23).
Supersedes one consequence of [ADR 0011](0011-vendor-legacy-product-unit.md):
"It never becomes a user-facing surface". Everything else in ADR 0011 stands.
**Date:** 2026-09-23

## Context

ADR 0011 vendored the working 18.6.6 product and ran it as a gated oracle on
its own hostname, with the plan that AIA would port each capability behind it
and re-home the screens last. Two things were wrong with that order for the
people who own the product:

- The product hostname kept showing a mock-up built before the decision to
  rebuild 18.6.6, and would have kept showing it for months, because the
  screens were the last slice of the plan.
- Progress was only visible as pull requests. Nobody could open the develop
  site and see 18.6.6 running on AIA's infrastructure, which is the goal.

The data owner decided on 2026-09-23 to change the order: the develop site
shows the 18.6.6 interface from the start, served first by the original engine,
and each feature is then rebuilt on AIA behind the same screens.

The interface allows this without editing the unit. `ui_app.html` reaches its
backend through one resolver (`apiUrl`, `API_BASE`) seeded by
`discoverBackend()`, which tries the page's own origin first
(`legacy/npc-panel-18.6.6/app/ui_app.html`, `discoverBackend`). Served at the
root of an origin that also answers the unit's paths, it works unchanged.

## Decision

1. **The product hostname serves the 18.6.6 interface at `/`.** Caddy routes,
   in order: `/api/v1/*` to the AIA API; AIA's own pages (`/login`, `/logout`,
   `/auth/*`, `/config`, `/version`, `/studies*`, `/_next/*`) to the web client;
   **everything else to the `legacy-panel` unit**, after a gate. The unit's
   own hostname behind basic auth stays, as the parity oracle.
2. **The gate is AIA identity, not a shared password.** Caddy's `forward_auth`
   asks `GET /api/v1/panel/gate` before every request it forwards to the unit.
   The gate reads an HttpOnly, SameSite=Lax session cookie set by
   `POST /api/v1/panel/session` from the Cognito id token the web client already
   holds, verifies it with the same `IdentityProvider` every API call uses,
   and admits only an active member whose organization role is `OWNER` or
   `ADMIN`. A browser navigation without a valid session is sent to `/login`;
   anything else gets 401. A state-changing request must carry the product
   origin in `Origin`, because the unit's own origin check is neutralised by its
   relay.
3. **Only organization owners and admins, for now.** The unit is single-tenant:
   every user of it sees every project in it, and it can store provider keys.
   Study-level scope cannot be applied to data the unit holds. Restricting the
   interface to organization administrators is the most restrictive choice that
   still lets the team use it (reference open decision D8, "default to the most
   restrictive role and relax deliberately"). Each feature rebuilt on AIA gets
   study scope as it moves.
4. **Develop only, behind a kill switch.** `AIA_LEGACY_PANEL_ENABLED` defaults to
   off, and `Settings.validate_for_production` refuses it when `AIA_ENV=production`.
   With it off, the gate answers 404 and the unit is unreachable on the product
   hostname.
5. **Rebuilding a feature moves its paths, not its screens.** When a feature is
   rebuilt, Caddy sends that feature's legacy paths to AIA instead of the unit,
   and AIA answers them in the shape the interface expects (a compatibility
   adapter over AIA's study-scoped use cases). The route ledger
   (`docs/migration/legacy-route-ledger.json`) records which paths moved; the
   parity gate against the oracle decides when. The screens are split into AIA's
   web client last, looking the same.

## Consequences

- The develop site looks and behaves like 18.6.6 on the day this deploys,
  provided `legacy-panel` is healthy with its data bundle (OI-39).
- There are now two ways into the unit: the product hostname for people (Google
  sign-in, admins only) and the legacy hostname for the parity harness (basic
  auth). Both reach one container, so they share its state.
- The id token is carried in a cookie. The cookie is HttpOnly, Secure in a
  deployed environment and SameSite=Lax; the token inside expires within an hour
  and is re-verified on every request, so an expired session sends the user
  back through `/login`, where the web client refreshes silently. A signed
  server-side session is the production shape and is not built here.
- Every request to the unit costs one gate round trip, including a membership
  read. Acceptable for a handful of develop users; measured before production.
- The mock-up pages under `/org/*` are deleted. The live `/studies` pages stay:
  they show AIA's own project and run model and are what rebuilt features will
  write to.
- `X-Frame-Options` on the product hostname becomes `SAMEORIGIN`, because the
  interface embeds its own generated maps in same-origin iframes.

## Alternatives considered

- **Keep the product hostname on AIA's own client and re-home screens last.**
  The original order. Rejected by the data owner: the site would not resemble
  the product for months.
- **Copy `ui_app.html` into the web client and patch it.** Rejected for now: the
  file names real clients' demos (decision D-L1 accepts that only inside
  `legacy/`), and a patched copy forks the interface before anything needs
  changing. The copy happens area by area when screens are re-homed.
- **Share the legacy hostname's basic-auth password with users.** Rejected: it
  bypasses AIA identity, cannot be revoked per person and leaves no audit trail.

## Revisit when

- The first rebuilt feature needs a study context that legacy-shaped requests do
  not carry (plan, slice 3).
- Production is planned: the cookie session, the admin-only rule and the gate's
  per-request cost are develop decisions.
