---
status: done
chunks:
  - "[x] 1. Use pytest-scoped population helpers and prove combined collection"
  - "[x] 2. Pass release checks and integrate the deployment blocker fix"
---
# Panel-source fixtures in the combined SQLite suite

Deployment gate CI 38295541712 failed five panel-source tests because importing
`conftest` directly resolved to the executor tree's module when all four test
trees ran together. Fix only test fixture lookup, using the existing
`population_kit` pytest fixture for the same gzip/dictionary/certificate writers
and issued population authority. Remove the second cross-test-module operator
import. Preserve every scenario and assertion; no runtime, data, permission or
scientific change. Existing AGENTS.md already documents the fixture rule.

Reproduce with panel-source tests collected beside API, worker and executor
tests on SQLite, then repeat the same command after the change. Full CI remains
the release gate. This fixes the pre-existing blocker for the requested
automatic deployment retention policy; shared docs need no new rule.

Combined-tree verification: collecting panel-source tests alongside test_settings_api.py, test_worker_processes.py and test_settings_presentation.py on SQLite now passes all five panel-source tests (40 other cases deselected). Every existing assertion remains. Lint, format, layer/exposure and all 72 plans pass. The prior CI receipt proves the original five ImportError failures in the complete combined suite; no test is skipped or weakened.

PR #349 passed full PR CI `38299488539` and merged at
`78dbae622c8dca4fb69dfbca6074085e9adc4bb8`. Full merged-base CI
[38302006413](https://github.com/AiAnalytics-AIA/AIA/actions/runs/38302006413)
passed, including the complete combined SQLite suite that originally failed.
Subsequent live deployment `38316829545` at `dbb0c704` passed smoke and applied
the requested retention policy. The fixture-import blocker is closed; no
runtime, scientific, data-access or approval semantics changed.
