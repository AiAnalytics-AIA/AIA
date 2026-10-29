---
status: in-progress
chunks:
  - "[ ] 1. Advisory allowed in every AIA_ENV: data_class_gates_problem and its four callers removed; enforce stays the default; the tests that pinned the refusal pin the new rule"
---
# Advisory class gates in every environment for the MVP

**Drafted:** 2026-10-28 · **Branch:** `feature/class-advisory-everywhere` from `develop` @ `d2139903`
· **Decision record:** ADR 0008, Amendment 2026-10-28 (docs PR
`chore/class-advisory-everywhere-adr`)

## Decision (the product owner, Nigel Blount, 2026-10-28)

In the PM coordinator's session at 22:25 UTC: "For mvp i wanted to retire the data gates". Offered
advisory everywhere, develop only, or removing the gates, he chose "Advisory everywhere" at about
22:27 UTC: "A session drafts an ADR 0008 amendment that lets advisory run in staging and production
for the MVP, then a small code PR. Every class decision is still recorded, so the gates can be
switched back on later. Residency, licences and budgets are untouched."

## Chunk 1

- `data_class_gates_problem` (`packages/aia_core/src/aia_core/domain/deployment.py:123-139 @ d2139903`)
  is removed, and with it the refusal in its four callers: the API's `validate_for_production`
  (`apps/api/src/aia_api/config.py:477-481, 525-527`), the worker's settings
  (`apps/worker/src/aia_worker/settings.py:153-155`) and the executors' `data_class_gates_from_env`
  (`apps/executors/src/aia_executors/ai_runtime.py:1048-1050`). Keeping a function that always says
  "allowed" would be dead code; switching the refusal back is a revert of this chunk, and switching
  the gates back is `AIA_DATA_CLASS_GATES=enforce`, no code.
- **Unchanged:** `enforce` the default; a misspelt value still stops every process by name
  (`parse_data_class_gates`); every advisory still recorded; Brave's `any_class_when_advisory`
  unchanged (ADR 0008, Amendment 2026-10-28, open point 1 asks the owner about it for staging and
  production).
- The comments that said "develop only" now say where advisory runs: wherever a deployment sets it.
- **Deploy configuration:** nothing to change. `deploy/` and `infra/` hold develop alone
  (`deploy/develop/`, `infra/develop/`); no staging or production configuration exists to state the
  key in. Develop's Compose file keeps `AIA_DATA_CLASS_GATES: advisory` and its deploy check.

**Test:** the tests that pinned the refusal now pin acceptance, each failing before the change:
`apps/api/tests/test_config_and_security.py::test_every_environment_accepts_either_data_class_gates`,
`::test_an_unset_environment_accepts_advisory_data_class_gates`,
`apps/worker/tests/test_worker_settings.py::test_a_worker_in_any_environment_accepts_advisory_gates`,
`apps/executors/tests/test_develop_host_configuration.py::test_advisory_gates_under_staging_and_production_start_both`.

## Doc follow-up

- **CLAUDE.md §2**, `config.py`'s entry: replace "develop only (Compose), refused in staging,
  production and an unknown AIA_ENV" with "allowed in every AIA_ENV, set only where a deployment
  says so (develop's Compose); ADR 0008, Amendment 2026-10-28"; and `deployment.py`'s entry:
  "DataClassGates / data_class_gates_problem (AIA_DATA_CLASS_GATES, enforce | advisory: advisory
  refused outside local, test and develop; #594)" becomes "DataClassGates (AIA_DATA_CLASS_GATES,
  enforce | advisory, enforce by default, advisory allowed in every environment; #594, ADR 0008
  Amendment 2026-10-28)".
- **CLAUDE.md §2**, "A research run executes a Design Revision": "On develop
  (`AIA_DATA_CLASS_GATES=advisory`) a class-only refusal is a recorded pass" becomes "Wherever a
  deployment sets `AIA_DATA_CLASS_GATES=advisory` (develop today) …"; and the Deep Research
  paragraph's "on develop, under advisory gates" becomes "under advisory gates".
- **ARCHITECTURE.md**: nothing (it does not mention the class gates).
- **docs/architecture/adr/README.md**, ADR 0008's line, after the 2026-10-21 entry: "**amended
  2026-10-28** (the product owner): advisory allowed in every environment for the MVP, set only
  where a deployment says so, enforce the default; every pass still recorded; Brave's any-class
  exception in staging and production awaits his yes".
- **`.planning/plans/develop-class-advisory.md`** stays as written (done, history).
