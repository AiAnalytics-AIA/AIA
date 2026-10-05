---
status: done
chunks:
  - "[x] 1. Domain: DeploymentEnvironment and the one fictional-material rule"
  - "[x] 2. API and worker ask that rule; the develop host declares AIA_ENV=develop"
  - "[x] 3. A test that starts both against deploy/develop's real Compose environment"
---
# The develop environment says what it is

**Branch:** `fix/develop-environment` from `develop` @ `0c42547`

## Problem

Every deploy of `develop` since run 54 (2026-10-02 18:18 UTC, `dfd8612`, PR #108) has
failed: migrations apply, then `aia-develop-api-1` never becomes healthy and
`bin/deploy.sh` stops at `compose up --wait`. The services had already been replaced,
so the site's API has been down since.

- PR #108 made the API refuse `AIA_AI_FICTIONAL_CLIENT_IDS` whenever `is_production`
  (`apps/api/src/aia_api/config.py:233-237 @ 0c42547`), and `is_production` is true for
  `staging` (`config.py:165-167 @ 0c42547`).
- The develop host runs `AIA_ENV: staging` (`deploy/develop/docker-compose.yml:28 @ 0c42547`)
  and sets the fictional clients on purpose (`deploy/develop/README.md:320 @ 0c42547`).
- The worker applies the same rule only when `AIA_ENV` is exactly `production`
  (`apps/executors/src/aia_executors/ai_runtime.py:195 @ 0c42547`), so the two processes
  disagreed about the same configuration and only the API refused it.

Reproduction: `Settings(env=staging, ai_fictional_client_ids="C1", …).validate_for_production()`
raises `AIA_AI_FICTIONAL_CLIENT_IDS is refused in production` at `056eca2`.

## Approach

Develop is not staging. It is a deployed environment that always hosts fictional data.
Give it its own name instead of exempting staging from a production rule:

- `aia_core.domain.deployment.DeploymentEnvironment`: local, test, develop, staging,
  production, and what each allows, stated once. `develop` keeps every deployed-environment
  guard (PostgreSQL, S3, build SHA, Cognito, no fixture fieldwork). Fictional material is
  allowed in local, test and develop, and refused in staging and production.
- `fictional_material_problem(env, ids)` is the one rule; the API's startup validation and
  the worker's AI runtime both call it. An unset or unknown `AIA_ENV` refuses fictional ids.
- `deploy/develop` declares `AIA_ENV: develop`; the smoke test expects it.
- A test reads `deploy/develop/docker-compose.yml` and runs both startup checks against its
  environment with representative Parameter Store values: the test that would have caught #108.

Trade-off: a fifth environment value every guard must place. Each property now names its
environments explicitly, so a new value cannot silently inherit the wrong side of a rule.

Not done here: `bin/deploy.sh` replaces the services before it knows the new API is
healthy and does not roll back. That turned a configuration error into a multi-day outage
and needs its own change.

## Findings

- The API and the worker held two copies of the fictional-material rule with different
  conditions (anchors above). Fixed by chunk 2.
- `bin/deploy.sh` has no rollback when `up --wait` fails (`deploy/develop/bin/deploy.sh`
  § replacing services @ 0c42547). Open; a separate change.
