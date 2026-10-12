---
status: in-progress
chunks:
  - "[x] 1. Use pytest-scoped population helpers and prove combined collection"
  - "[ ] 2. Pass release checks and integrate the deployment blocker fix"
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
