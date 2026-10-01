---
status: in-progress
chunks:
  - "[ ] 1. Skip the suites for a plans-and-ADRs-only pull request; run cheap documentation checks instead"
  - "[ ] 2. Run the SQLite domain suite on pushes to main and develop, not on pull requests"
  - "[ ] 3. Prove the docs-only skip on the next docs-only pull request, then widen or leave the list"
---
# CI: do not run the suites for a change that cannot affect them

**Branch:** `chore/ci-skip-docs-only` from `develop` @ `2de4093` · **Started:** 2026-10-01

## Problem

`ci.yml` runs every job on every pull_request push (`on:` and `concurrency` at
`.github/workflows/ci.yml:11-19 @ 2de4093`). [PR #94](https://github.com/AiAnalytics-AIA/AIA/pull/94)
adds one plan and one ADR and no code, and it started the full suite twice, the first run being
cancelled by the second push.

A full run on `develop` (run 36841844987) is about 24 billed minutes, counting each job's minute
rounding: Backend 11.6, Frontend 2.9, Application starts 1.1, and eight short jobs of about a
minute or less. A docs-only run needs about 2.

A second, smaller defect: `parity-status` runs under `if: always()` (`ci.yml:337 @ 2de4093`), so
a run superseded by a newer push still ran it against a partial set of artifacts and reported a
parity FAIL (run 36857545967 on #94: workflow `cancelled`, `Parity status` red). It is noise, and
it would read as a real parity failure.

## Approach

- A `changes` job lists the files the pull request changes (`git diff --name-only HEAD^1 HEAD` on
  the merge commit) and outputs `code=false` only when **every** file is under `.planning/` or
  `docs/architecture/adr/`. Those two were checked by search: no test, tool or CI step reads them
  (`tools/progress.py` is a manual command, not a CI job). Any other path, including `CLAUDE.md`,
  `docs/migration/**` (the parity tests read it) and the workflow itself, runs everything. A push
  to `main` or `develop`, a dispatch, or an empty or unreadable diff also runs everything.
- Every existing suite gets `needs: [changes]` and runs unless `code` is exactly `false`. So a
  failure of `changes` itself runs the full suite, never skips it.
- A skipped job counts as passed for a required check, so branch protection that names the suites
  is satisfied. The new `docs-checks` job covers what a doc change can still break: layering and
  exposure rules, plan front-matter, and the committed-key scan. Verified in a depth-2 clone, as
  the runner checks out: layer 70 rules, exposure 7 rules, 30 of 30 plans, no key.
- `parity-status` uses `!cancelled()` instead of `always()`, so a cancelled run no longer reports
  a failure of its own.

Linted with actionlint 1.7.12 (no findings) and the filter exercised against seven sample diffs.
Not yet run on GitHub: the workflow cannot be tested without a push, and this change touches the
workflow, so its own pull request runs the full suite once.

## Chunk 2: SQLite off the pull request

The Backend job runs the domain suite on PostgreSQL (2.3 min) and again on SQLite (3.7 min of the
job's 11.6, `ci.yml` step "Domain tests on SQLite"). The SQLite step now runs only when the event is
not a pull request. The deploy dispatch needs every job green on the push to `develop`, so a
SQLite-only failure still blocks the deploy; it is found one merge later than before.

`tools/parity_status.py` merges outcomes across the two runs and counts a pass on either as a pass
(`parity_status.py:121-126`), so a missing `sqlite.xml` does not change a verdict. Not run on GitHub
yet.

Dropped from the earlier list of options: skipping the oracle and golden jobs when their secrets are
absent. They are no-ops today (the reference checkout step is skipped even on `develop`, the oracle
suite takes 6 seconds), but `parity-status` reads their JUnit files to report NOT_EXECUTED rather
than a failure, so removing the jobs would change what that report says. About 2 minutes, not worth
the risk.

## Trade-off accepted

A docs-only change merges without the test suites. That is sound only while the list of paths
stays short and verified; a test that starts reading `docs/architecture/adr/` or `.planning/`
would stop being run for changes there. The list is commented in `ci.yml` to say so.

## Measured

About 24 billed minutes saved per docs-only push, down to about 2. From run 36841844987's job
start and end times, not from a billing report.

## Deliberately not done

- **Skipping drafts.** Every pull request from an agent is opened as a draft; skipping CI for
  drafts until ready for review would save more, but it hides CI from the author while they work.
  Your call.
- **Per-area filters** (Frontend only when `apps/web` changes, Backend only for Python). Larger
  saving, larger risk: the web client and the API share generated contracts and the ledgers.
- **Cancelling superseded runs on `develop`.** `cancel-in-progress` stays: runs 298, 301 and 303
  on `develop` were cancelled by a following merge, which skips that SHA's deploy dispatch. Left
  alone because the next run deploys the later SHA anyway.
- **Splitting Backend (11.6 min)** into parallel jobs. It changes wall-clock time, not billed
  minutes.

## Findings

- `parity-status` reports a parity FAIL when its run was cancelled (`ci.yml:337 @ 2de4093`).
  Reproduction: push twice in quick succession to a pull request and read the first run's
  `Parity status` job. Fix: `!cancelled()` (this PR). Test that would have caught it: none; it is
  workflow logic, verified only by a run.

## Doc follow-up

- `ARCHITECTURE.md` §8 (`ARCHITECTURE.md:463`) lists "pytest -- core + API, on PostgreSQL and on
  SQLite" as blocking. After chunk 2 it blocks the deploy, not the pull request.

- `CLAUDE.md` §3 or `ARCHITECTURE.md` §8 (CI tiers): one line saying a pull request that changes
  only `.planning/` and `docs/architecture/adr/` runs `Documentation checks` instead of the suites,
  and that the path list lives in `ci.yml` (`changes` job).
