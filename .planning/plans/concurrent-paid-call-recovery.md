---
status: done
chunks:
  - "[x] 1. Derive a paid call's known outcome per hold, so one answered call never closes another in flight -- lands: column + migration, repository, worker context, call journal, tests"
---
# Concurrent paid calls: one answered call does not answer another

**Branch:** `fix/concurrent-paid-call-recovery` from `develop` @ `757154e` · **Started:** 2026-10-06

## Problem

A workflow attempt kept one paid-call outcome flag. `mark_paid_call_dispatched` set
`paid_call_outcome_known = False` (`packages/aia_core/src/aia_core/infrastructure/workflow_repository.py:1077-1095 @ 757154e`);
`settle_paid_call` set it `True` for whichever call it settled (`:1156 @ 757154e`), and the closing
rule (`:1267 @ 757154e`), `fail_attempt`, `recover_expired_attempts` and `release_attempt` read it.
With two calls dispatched in one attempt -- a fan-out, Deep Research's concurrent actions -- settling
the first made the attempt "known" while the second was still in flight. A worker that died then
was recovered as `RETRY` (`expired_lease_idempotent_or_subscription`) instead of
`RECOVERY_REQUIRED`, and the second call's hold was `RELEASED`: a call that may have been billed was
run again and recorded as free. `WorkflowCallJournal.record_outcome` had the same shape through
`mark_paid_call_outcome_known` (`packages/aia_core/src/aia_core/infrastructure/ai_call_journal.py:100 @ 757154e`).

Reproduced on `757154e`: reserve $2 and $3, dispatch twice, settle the first, lapse the lease,
`recover_expired_attempts()` -> `RETRY expired_lease_idempotent_or_subscription`, second hold
`RELEASED`.

## Approach

The schema recorded no per-hold dispatch state, so a flag cannot be derived from it without one
column: `budget_reservations.paid_call_in_flight` (migration `f1a3c5e7b9d2`). The dispatch mark
names its hold (`reservation_id`, now required on `mark_paid_call_dispatched` and
`mark_paid_call_outcome_known`); settling or recording the outcome clears that hold only. Every
decision asks `_paid_call_outcome_known(attempt)`: no open hold of the attempt is in flight. The
attempt's `paid_call_outcome_known` column stays, rewritten from the holds on every metering write,
for the views that read it; it is never a decision's input.

Required, not optional: every production caller has the hold (`StepContext.dispatching` holds the
`PaidCall`; the gateway refuses a metered call without one, so every metered `AIUsageEvent` carries
`reservation_id`). An unattributed dispatch would need a guess about which hold it meant. A
dispatch against a hold that is no longer `RESERVED` raises `ReservationClosed` before the call is
sent.

The migration backfills: every `RESERVED` hold of an attempt the old flag calls
dispatched-and-unknown is marked in flight, so an attempt in flight during the deploy is recovered
exactly as before.

Not the same defect: `StepToolMeter` (Deep Research tools) keeps its journal per `call_id` and
`InMemoryToolLedger.adopt` closes each open `DISPATCHED` entry separately
(`packages/aia_core/src/aia_core/domain/deep_research/tooling.py:256-301 @ 757154e`).

## Trade-off accepted

Every recovery decision and every metering write runs one more indexed count over the attempt's
holds (`ix_reservations_attempt`), and two calls dispatched concurrently against the *same* hold
remain one question -- the gateway sends a request's calls (primary, repair) one after another
against its one hold, so this is documented rather than counted.

## Findings

1. **A never-dispatched hold is charged as uncertain when another call of its attempt is in flight.**
   - Claim: `_settle_uncertain` converts *every* `RESERVED` hold of the attempt to
     `SETTLED_UNCERTAIN`, including holds whose call was never dispatched.
   - Anchor: `packages/aia_core/src/aia_core/infrastructure/workflow_repository.py:1214-1237 @ 757154e`
     (the `status == RESERVED` filter with no dispatch condition).
   - Reproduction: in `packages/aia_core/tests/test_workflow_reservations.py`'s fixtures, reserve
     $2 and $3, `mark_paid_call_dispatched` the $2 hold only, lapse the lease,
     `recover_expired_attempts()`: the $3 hold ends `SETTLED_UNCERTAIN` with
     `paid_call_in_flight = False`, `uncertain_usd = 5.0` (measured on this branch).
   - Consequence: a fan-out that had reserved but not yet sent a call when its worker died shows
     that call's ceiling as spent; the study's available budget shrinks by money that cannot have
     been billed. Fails safe (over-records), but a person reconciling uncertain exposure looks for
     a call that never existed.
   - Smallest fix: in `_settle_uncertain`, convert only holds with `paid_call_in_flight` and let the
     closing rule release the rest (now possible, since the per-hold state exists).
   - Test: the reproduction above, asserting the unsent hold `RELEASED` and `uncertain_usd == 2.0`.

## Doc follow-up

- **ARCHITECTURE.md** (the worker/accounting contract, where `paid_call_dispatched` /
  `paid_call_outcome_known` are described): "Whether a paid call's outcome is known is per hold:
  `budget_reservations.paid_call_in_flight` is set by `mark_paid_call_dispatched(reservation_id=…)`
  and cleared by `settle_paid_call` / `mark_paid_call_outcome_known` for that hold. An attempt's
  outcome is known only when none of its open holds is in flight
  (`WorkflowRepository._paid_call_outcome_known`); the attempt's `paid_call_outcome_known` column
  records that answer and is never a decision's input."
- **AGENTS.md** § SQLAlchemy and PostgreSQL (or a "Billing state" note), wrong and right side by side:

  ```python
  # WRONG -- one flag per attempt: the first of two concurrent calls to answer closes both
  attempt.paid_call_dispatched = True; attempt.paid_call_outcome_known = False   # dispatch
  attempt.paid_call_outcome_known = True                                         # any settle
  # RIGHT -- the open question lives on the hold its call is charged to; the attempt asks them all
  reservation.paid_call_in_flight = True                                         # dispatch
  reservation.paid_call_in_flight = False                                        # its own settle
  known = not count(holds of attempt where RESERVED and paid_call_in_flight)
  ```

  "A boolean summarising N concurrent things is a guess the moment N > 1. Put the state on the
  row each thing owns and derive the summary."
- **CLAUDE.md** § 2 map, `workflow_repository.py` line: add "a paid call's outcome per hold".
- `.planning/open-items.md`: Finding 1 above, numbered.
