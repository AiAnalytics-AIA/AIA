---
status: in-progress
chunks:
  - "[x] 1. Confirm F-K1 and refresh the bounded fix onto the merged application and AIA-90"
  - "[x] 2. Persist a proposal's base revision and refuse stale acceptance without changes"
  - "[x] 3. Verify API conflicts, legacy proposals and real PostgreSQL contention"
  - "[x] 4. Complete merged-base PostgreSQL checks and prepare the publication candidate"
  - "[ ] 5. Publish, pass CI, review and integrate; reconcile shared documentation separately"
---
# Client knowledge revision safety (AIA-88)

Owner: Codex. Started: 2026-10-08.
Publication base: [PR #200](https://github.com/AiAnalytics-AIA/AIA/pull/200),
commit `9ab587180021c38a5c21e9f7a64c5e1f7a457109`, over merged develop `09b75227`.
Parent: [AIA-88](https://makli.atlassian.net/browse/AIA-88), F-K1 in the
[published knowledge design](https://github.com/AiAnalytics-AIA/AIA/pull/195).

## Contract

An edit proposal captures the exact current item revision when prepared. An
acceptance checks that revision under the existing transaction before appending
anything. A newer correction causes an explicit conflict, leaving the proposal
pending and the item/history unchanged. Rejection is still allowed. Rebase means
preparing a new proposal explicitly against the current revision, preserving the
old proposal; no automatic merge or retry.

Store the base as a typed nullable column, not user-controlled provenance. New
items have no base. Existing pending edits with no recorded base fail closed and
must be re-proposed; do not guess their original revision during migration.
Existing approved/rejected records remain readable.

Serialize knowledge writes on the scoped client row before taking proposal/item
locks, so different approvals also allocate unique client context revisions.
Refresh locked ORM objects, including preloaded proposal/item rows. Check before
marking a proposal decided, so a caught conflict cannot be committed as approval.

Transport returns 409 with the expected/current revision. The approval policy
from ADR 0019, source eligibility and canonical methodology remain unchanged.

## Verification

Reproduce old proposal -> newer correction -> attempted acceptance; assert no
replacement, revision, approval or audit append. Cover fresh re-proposal,
rejection, explicit stale creation, missing legacy base, scope refusals and
stale identity-map reads. Use real PostgreSQL competing transactions for two
edits of one item, duplicate decisions and context revision allocation across
different items. Verify migration upgrade/check/downgrade/re-upgrade on a
disposable database. This work does not implement the wider knowledge redesign.

## Shared documentation follow-up

Describe the recorded base revision, 409 conflict/re-proposal behavior and legacy
pending-edit refusal in CLAUDE.md's Client Knowledge contract. Record the
client -> proposal -> item lock order and populate_existing refresh in AGENTS.md;
close F-K1 with regression evidence in the next docs-only reconciliation.

## Measured evidence, 2026-10-08

Historical verification base: develop `4d8f07d934e88a9d15b9da47c78c42a1b01ca019`.
The following measurements refer to that earlier candidate; the publication
refresh is recorded below. AIA-88 remains In Progress until review and
integration. This is a correction to existing approval semantics, not an
approval of the K1-K4 knowledge redesign.

- `test_stale_acceptance_leaves_the_correction_and_pending_proposal_unchanged`
  commits the caught refusal and reads item, proposal, history and audit count
  back through a fresh session. Explicit re-proposal then succeeds.
- `test_a_legacy_pending_edit_has_no_guessed_base_and_can_be_rejected` refuses
  an unknown legacy base without changing the item and allows rejection.
- `test_competing_acceptances_use_fresh_locked_rows_and_unique_context_revisions`
  uses PostgreSQL 16, separate transactions and deliberately preloaded ORM rows:
  same item, same proposal and different items all pass.
- Targeted repository/API suite: 49 passed and 3 PostgreSQL-only skips on SQLite;
  all 52 passed on PostgreSQL with `AIA_REQUIRE_POSTGRES=1`.
- Full Python regression on SQLite: 6,061 passed, 117 conditional skips.
  Three of those skips are the contention cases independently executed above.
- Disposable migration probe: populated legacy pending/approved proposals keep
  NULL bases; item and revision history survive upgrade/downgrade/re-upgrade;
  nonpositive bases are rejected. Full-chain base -> head and Alembic check pass.
  One migration head: `c8b4e1d9a602`.
- Python lint/format, all 304 source files under mypy, 100 layering rules, seven
  reference-exposure rules, plan validation and whitespace checks pass.

- Full PostgreSQL regression: 6,101 passed, 77 conditional reference-dependent
  skips, no failures. Concurrency/worker-process cases execute on PostgreSQL.
- The three AIA-90 connected cases also pass with this core/API implementation
  and AIA-90's executor/test code together on PostgreSQL.

The review package is prepared locally. Publish AIA-90 first (including its two
existing download-test compatibility corrections), then base this fix on that
change and run the complete pre-commit verification on the resulting committed
candidate. Web code itself is unchanged here; AIA-90's full web verification and
build pass. CI/review/merge and docs-only reconciliation are still outstanding.
The unavailable reference comparisons are not claimed as executed.
Publication requires the explicit Git permission in CLAUDE.md section 5.

## Publication refresh, 2026-10-08

The fix is stacked on the exact committed AIA-90 base above. PRs #195, #197 and
#198 are now merged into develop and included in this candidate. No shared
architecture/plan file is changed; the AIA-90 plan is inherited from its base.
The earlier combined #198/AIA-88/AIA-90 candidate passed all 342 executor tests
and all 12 knowledge revision tests on PostgreSQL, including process/contention
cases with no skips. The populated migration and full-chain rollback/re-upgrade
checks were repeated and passed.

Merged-base verification passed: 5,403 core + 355 API + 62 worker + 342 executor
tests = 6,162 Python passes on PostgreSQL 16, with 77 reference-dependent core
skips. No contention/process case was skipped. All 639 web tests across 40 files
passed. Python/web lint, types across 307 source files, formatting, web design,
101 layering rules, seven exposure rules and plan checks passed. The populated
migration and full-chain rollback/re-upgrade rehearsal passed again.

The Python checks passed during the complete pre-commit sequence; its first web
run and subsequent retries were interrupted by Mac maintenance sleep. System
power logs record those pauses, including 1,595 seconds during one retry.
The affected cases passed independently, and the unchanged full web suite passed
with its existing deadlines while the machine remained awake. Failed-run logs
are retained in the review package; no tests or timeouts were weakened.

PR #200's blocking CI checks passed at its exact committed base above. Merge it
before this fix; this fix's CI, human review, integration and docs-only
reconciliation remain outstanding.
