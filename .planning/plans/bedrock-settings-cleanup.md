# Bedrock settings cleanup — 2026-09-26

**Status:** done — merged in PR #57 @ `ff463a3` (2026-09-27), deployed by run 25. Native Bedrock design jobs continue in PR #63, which links this file; it moves to `done/` once #63 has merged.

User request: remove Claude Code connection settings and the Anthropic API-key
field from the AIA product, including the design-action notice.

## Scope and decisions

The deployed Bedrock runtime supports fictional respondent fieldwork. Legacy
research design jobs are not Bedrock jobs. Do not label them connected because
the fieldwork route is enabled. Settings shows nonsecret runtime configuration,
not a live provider health check; no provider login, key input or test call.

Retire legacy connection endpoints on the product hostname with gated HTTP 410.
Redirect classic settings to native AIA Settings and remove old connection
controls through the product wrapper. Keep the pinned archive, the separate
parity oracle and historical provider metadata unchanged.

## Chunks

1. Native Bedrock configuration card and accurate design failure message.
2. Product classic wrapper and endpoint retirement; matching local workbench.
3. Regression checks, routing validation, documentation and reviewable diff.
4. User-authorized Codex PR publication; merge/deploy approval remains separate.

Verification: `make verify` passed (core 2528 / API 199 / worker 43 /
executors 57 / web 747). Environment-dependent skips: core 99, worker 6;
PostgreSQL and archive/oracle checks require CI or their external fixtures.
Hydration/backup regression tests 7 passed, including default-off export checks
and interrupted first-install recovery; isolated adapted Caddy config passed
`tools/caddy_routes.py`. `make lint` passed with locked web dependencies. Live SQLite backup export is off by default until
separately approved by the owner.

Design generation through Bedrock requires client-scoped durable design jobs,
revision/provenance handling and governed calls; it is not implemented here.

## Study-loading defect discovered during the same session

The deployed startup hydrator overwrites changed `state_seed` databases, including
`data/project_store.sqlite`. AIA study bindings survive in PostgreSQL and then
point to missing projects. Preserve existing state seeds, regression-test two
starts with edited state, and investigate recovery without rebinding studies to
empty projects. This runtime wrapper is outside the pinned reference app.

## PR #57 review

The automated P2 finding identified a partial first seed left by an interrupted
copy. First installs now copy into a temporary sibling, sync the complete data,
and publish by atomic rename. `test_interrupted_first_seed_is_retryable_and_never_published_as_working_state`
checks that a partial copy is not preserved as working state and the next start
retries successfully. Existing edited state remains untouched.

The second P2 finding: `/config` counted only `"true"` as on, while the worker
accepts `1`, `yes` and `on` (`apps/executors/src/aia_executors/ai_runtime.py:63`).
Compose passes both services the same raw value, so Settings could say off while
respondent calls ran. `/config` now reads the switch with the worker's vocabulary
(`runtimeSwitch`), and reports a value the worker refuses as `null`, shown as
invalid rather than off. Tests: `route.test.ts` › *reads the switch with the
worker's vocabulary…* and *reports a value the worker refuses as unknown…* (both
fail on the old comparison); `ClientFirst.test.tsx` › *says a switch the worker
refuses is invalid…*; `test_ai_fieldwork.py` › *the settings page reads the switch with the workers vocabulary* compares the two word lists, so a change to either side fails.
