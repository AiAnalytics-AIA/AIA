---
status: done
chunks:
  - "[x] 1. Identify the live CPU workload and preserve its evidence"
  - "[x] 2. Stop orphaned duplicate catalogue jobs without touching core services"
  - "[x] 3. Make catalogue classification linear in panel rows and guard against regression"
  - "[x] 4. Pass CI, deploy and verify CPU, catalogue and service health"
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

## Chunk 4 verified (2026-10-27, infra session)

Read from AWS, not from the host: this session's identity may not run a command on the instance
(`ssm:SendCommand` is denied to it), so every fact below comes from the deploy commands' own stored
output (`ssm get-command-invocation`), CloudWatch metrics and alarm history, and the `/aia/develop`
log group.

- **The fix shipped.** `b22fc0f7` ("Classify each audience factor column once") reached develop
  in #370, merged as `02fd6461`; `git merge-base --is-ancestor b22fc0f7 02fd6461` holds and it is not
  in `25a1343b`, the deploy before.
- **Before and after, on the same host.** Deploy `25a1343b` (command
  `aia develop deploy 25a1343b…`, 2026-10-13 10:54 UTC) logged `record-catalogue did not finish in 5
  minutes and was stopped; no catalogue was kept`. Deploy `02fd6461` (11:43 UTC) logged
  `"recorded": ["cz_synthetic_population@sha256:864f8dbcd101e4be",
  "cz_synthetic_population@sha256:d6a9ef120b81982e"]` between 11:44:58 and the smoke at 11:45:42,
  both catalogues in at most 44 s. Every deploy since answers `already_kept` for both, the latest
  `f5916652` at 13:46:57 UTC today.
- **The catalogue is served.** `GET /api/v1/population/audience-catalogue` answered 200 in
  103-668 ms (the API's request log, 2026-10-25 and 2026-10-26); requests to it or the preview on 10
  of the last 14 days.
- **CPU.** `aia-develop-cpu-90-percent` (Average > 90 % for 6 × 300 s) went ALARM at 2026-10-13
  01:16 UTC and OK at 10:30 UTC, and has had no state change since. Over 2026-10-25 14:37 to
  2026-10-27 14:32 UTC (576 five-minute points) the median is 9.0 %; five points pass 50 %, the
  highest 75.8 % (2026-10-26 03:32), none two in a row. Daily averages 9.1-11.1 % over the week.
  The host was resized to `t3a.large` on 2026-10-22 (`report-editor-hosting` 4), so the week's
  figures are not the `t3a.medium` the alarm first fired on.
- **Service health.** Deploy `f5916652`'s smoke: every check `ok`, the AI row `NOT_RUNNABLE` by
  design, the schema at head `184381bbcfef`.

Not done, and why: the catalogue rows were not read from the database (no command on the host).
The deploy's `already_kept` comes from `population_ops record-catalogue` reading those rows, which
is the same fact one step removed.
