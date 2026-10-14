---
status: in-progress
chunks:
  - "[x] 1. Identify the live CPU workload and preserve its evidence"
  - "[x] 2. Stop orphaned duplicate catalogue jobs without touching core services"
  - "[x] 3. Make catalogue classification linear in panel rows and guard against regression"
  - "[ ] 4. Pass CI, deploy and verify CPU, catalogue and service health"
---
# Stop audience catalogue generation from saturating develop

The develop instance `i-07159210266481227` alarmed above 90% CPU on
2026-10-13. Read-only host inspection found three one-off
`population_ops record-catalogue` containers at roughly 60–71% each, while
the API, web and database were idle. Two had run for over nine hours, and all
three belonged to deployment workflows that had already failed after waiting
for the host command. Neither established population version had a stored
audience catalogue. The 18,766-row panel is only about 7.3 MB per version.

In `audience_catalogue._factor`, `column_type(name, cells)` was called inside
the per-cell list comprehension. It scans the whole column, so this path
scaled quadratically with row count. Classify once per factor, then type its
cells. Exact catalogue parity remains the output gate; a call-count regression
test guards the performance property. A repeated 18,766-row fictional fixture
with 25 columns and 21 factors computes in 0.17 seconds on the local machine.
The exact catalogue fixture and neighboring population suites pass 98 tests;
the changed files pass lint and formatting checks.

The three verified duplicate containers were stopped through SSM. The web,
API, normal worker, Caddy and both PostgreSQL containers remained healthy;
there was no catalogue row to roll back. The catalogue will be recomputed by
the corrected version on the next deployment. Verify the exact live version,
catalogue rows, CPU alarm and smoke check before calling this complete.
