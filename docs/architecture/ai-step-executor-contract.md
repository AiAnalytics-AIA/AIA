# AI runtime ↔ step executor contract

**Owners:** ai-runtime (the gateway side) and platform-runtime (the worker and
`WorkflowRepository` side). **Status:** both sides are implemented. The AI step
executor's bridge is `apps/executors/src/aia_executors/ai_step.py`
(`StepModelCaller`, `StepCallJournal`), used by the `research_fieldwork` step's
`ai_runtime` source (`ai_fieldwork.py`); `WorkflowCallJournal` remains the
reference journal for a caller that holds its own session.

This is the whole interface between the two. It exists so that neither side
edits the other's implementation to integrate. Anything not written here is
private to one side and may change without coordination.

Code: `packages/aia_core/src/aia_core/domain/ai_execution.py` (the contract),
`packages/aia_core/src/aia_core/infrastructure/ai_call_journal.py`
(`WorkflowCallJournal`, the durable implementation over `WorkflowRepository`'s
public methods only).

## The shape

```python
# domain/ai_execution.py
class ModelGateway(Protocol):
    async def invoke(self, request: ModelRequest, context: ExecutionContext) -> ModelResult: ...

@dataclass(frozen=True)
class ExecutionContext:
    scope: StudyContext            # issued by ScopeResolver; refused by type otherwise
    runtime_version: str
    journal: CallJournal
    run_id / step_id / attempt_id: str | None
    reservation: ReservationView | None   # from reserve_budget, never from a request
    is_cancelled: Callable[[], bool]
    clock: Callable[[], datetime]

class CallJournal(Protocol):
    def record_dispatch(self, event: AIUsageEvent) -> None   # MUST be committed on return
    def record_outcome(self, event: AIUsageEvent) -> None
    def committed_usd(self) -> float

def recovery_inputs(error: ModelCallFailed) -> RecoveryInputs  # -> fail_attempt(...)
```

## What the step executor does, per attempt

```
claimed  = workflow.claim_next(worker_id=…)
rsv_id   = workflow.reserve_budget(attempt_id=…, worker_id=WORKER,
                                   amount_usd=<step budget>, provider=<paid provider>)
journal  = WorkflowCallJournal(workflow=…, usage=AIUsageRepository(session, scope),
                               attempt_id=claimed.attempt_id, worker_id=WORKER,
                               commit=session.commit)
context  = ExecutionContext(scope=scope, runtime_version=BUILD, journal=journal,
                            run_id=…, step_id=…, attempt_id=…,
                            reservation=ReservationView(rsv_id, amount),
                            is_cancelled=lambda: workflow.is_cancel_requested(step_id))
try:
    result = await gateway.invoke(request, context)
    workflow.complete_attempt(attempt_id, worker_id=WORKER, output=…,
                              actual_cost_usd=result.total_cost_usd, reservation_id=rsv_id)
except ModelCallFailed as failure:
    inputs = recovery_inputs(failure)
    workflow.fail_attempt(attempt_id, worker_id=WORKER, failure=inputs.failure,
                          error=dict(inputs.error), reservation_id=rsv_id,
                          quota_reset_at=inputs.quota_reset_at)
```

A subscription-only step passes no reservation; the gateway refuses a metered
call without one (`paid_call_without_reservation`), rather than calling unbudgeted.

## How a worker step keeps it (`aia_executors.ai_step`, D11 resolved 2026-09-25)

```
paid     = context.reserve(amount_usd=<per request>, provider=AWS_BEDROCK)   # BudgetExceeded -> park
journal  = StepCallJournal(context, paid)
exec_ctx = ExecutionContext(scope=context.scope, runtime_version=BUILD, journal=journal,
                            run_id / step_id / attempt_id = context.step.…,
                            reservation=ReservationView(paid.reservation_id, paid.amount_usd),
                            is_cancelled=<context.checkpoint() raised?>)
result   = asyncio.run(gateway.invoke(request, exec_ctx))
  record_dispatch -> context.dispatching(paid)   # checkpoint + fenced paid_call_dispatched, committed
                  -> context.record_usage(DISPATCHED)
  record_outcome  -> context.record_usage(terminal)   # UNFENCED: survives a lost lease
context.settled(paid, actual_cost_usd=<sum of this request's terminal entries>)
# ModelCallFailed: settle only if the outcome is known; checkpoint (a stop surfaces as
# itself); raise StepFailed(recovery_inputs(...)) -> fail_attempt
```

**D11's answer: one reservation per logical request**, not per attempt and not per
call. The gateway checks the primary call and an allowed schema repair against the
same reservation (`committed_usd` is the request's own spend); the reservation is
settled once with their sum. Per call would not work: `settle_paid_call` settles a
reservation once, so a repair's cost would be silently dropped. An uncertain
outcome leaves the reservation unsettled and the attempt dispatched-and-unknown,
so `fail_attempt` chooses `RECOVERY_REQUIRED`
(`test_ai_fieldwork.py::test_an_uncertain_call_needs_recovery_and_is_never_retried`).

`StepContext.record_usage` is the one unfenced write a step may make, and only to
the append-only, scope-checked ledger
(`::test_a_lease_lost_mid_call_still_leaves_the_answer_on_the_ledger`).

## The three obligations

1. **Scope is issued, never supplied.** `ExecutionContext` accepts only an issued
   `StudyContext`, checked by type. `ModelRequest` has no organization, client or
   study field. Tool arguments carrying a scope key are refused by `ToolRegistry`
   (`scope_in_model_arguments`). Ledger attribution comes from the egress
   decision, which came from the issued scope.
2. **The budget is the reservation.** The gateway checks every call's
   worst-case ceiling, plus `journal.committed_usd()`, against
   `context.reservation.amount_usd` using `check_budget`. A request naming a
   different reservation id is refused (`reservation_mismatch`).
3. **Dispatch is durable, and fenced, before the call leaves.** `record_dispatch`
   must have committed when it returns. `WorkflowCallJournal` calls
   `mark_paid_call_dispatched` first -- the lease fence: a worker that lost the
   attempt gets `LeaseLost` there and the adapter is never reached -- then writes
   the `DISPATCHED` ledger row, then commits
   (`test_a_worker_that_lost_the_lease_never_sends_and_ledgers_nothing`). An
   outcome's ledger row is committed *before* its fenced attempt write, so a lease
   lost mid-call still leaves the provider's answer on the ledger
   (`test_outcome_is_ledgered_even_when_the_lease_is_lost_mid_call`). Each outcome
   reports that call's own cost; the repository adds it to the attempt's known
   spend (`test_several_calls_in_one_attempt_are_charged_once_each`).
   `test_ai_usage_ledger.py::test_without_a_committed_dispatch_the_same_crash_is_retried`
   shows what happens otherwise: the mark rolls back with the dying worker and
   the step is retried — a second paid call.

## What each failure becomes

| Gateway failure (`ModelCallFailed.failure`) | `decide_recovery` outcome | Step state |
| --- | --- | --- |
| `QUOTA` (reference `WAITING_CREDITS`) | `PARK_PROVIDER`, `retry_after` = provider reset if plausible, attempt not consumed | `WAITING_PROVIDER` |
| `PROVIDER_CAPACITY` | `PARK_CAPACITY`, attempt not consumed. **No in-call retry** | `WAITING_CAPACITY` |
| `BUDGET_EXCEEDED` (ceiling does not fit reservation) | `PARK_BUDGET` | `AWAITING_BUDGET` |
| `TRANSPORT` with outcome known | `RETRY` while attempts remain | `RUNNABLE` |
| any failure with a paid call's outcome **unknown** | `RECOVERY_REQUIRED`, reservation → `SETTLED_UNCERTAIN` | `RECOVERY_REQUIRED` |
| `AUTHENTICATION`, `PERMISSION`, `MISSING_CONFIGURATION`, `MODEL_UNAVAILABLE`, `SCHEMA_VIOLATION`, `MAX_TURNS`, `SDK_OUTDATED`, `CANCELLED`, `UNKNOWN` | `FAIL` | `FAILED` |

`fail_attempt` reads the billing flags from the attempt row, which the journal
wrote. `recovery_inputs` deliberately does not pass them again.

## Asks of platform-runtime

These are not implemented by ai-runtime because they are platform-runtime's to
own. Filed so nothing is assumed:

1. ~~**The step executor itself**~~ — the worker landed (PR #23), and the AI
   step executor's bridge is `aia_executors.ai_step` (above). ~~What remains
   is ai-runtime's: an AI `StepExecutor` that builds this contract's
   `ExecutionContext` from `StepContext`.~~ Done. One reconciliation is open for it:
   `StepContext` meters **per call** (`reserve` → `dispatching` → `settled`),
   while this contract checks each call against **one attempt reservation**.
   Either the executor reserves per call through `StepContext`, or the worker
   exposes the attempt reservation; the choice is shared, and is recorded as
   D11 in `PROGRESS.md`. Also relevant: OI-21, which the worker's executor contract
   closes by settling a refused call at zero first -- the gateway already does
   this, because a provider refusal is a `RESPONDED` failure whose outcome is
   recorded as known before the step fails.
2. ~~**Heartbeats during a long call.**~~ Done: the worker's heartbeat thread keeps
   the lease while `invoke` blocks the executing thread
   (`::test_the_heartbeat_keeps_the_lease_through_a_call_longer_than_the_lease`).
   The original ask, for the record: A model call can outlast a 120 s lease. The
   worker now heartbeats (`aia_worker.heartbeat`); the AI executor must keep that
   running across `invoke`, or take a lease long enough for the agent's timeout. A lapsed lease during a paid call is
   `RECOVERY_REQUIRED` — safe, but a person is paged for nothing.
3. **Settling an uncertain reservation from a ledger resolution.**
   `AIUsageRepository.resolve_uncertain` corrects the *ledger*; the study's
   `spent_usd` still carries the `SETTLED_UNCERTAIN` reservation amount.
   `.planning/open-items.md` OI-36.
4. **The commit hook.** `WorkflowCallJournal` commits the session it is given.
   If the claim transaction must stay open across the call, supply a separate
   session for the journal instead; the obligation is durability, not this
   particular mechanism.

## Out of scope for this contract

Agent-internal loops (LangGraph, ADR 0006) sit *inside* one `invoke` caller and
may call `invoke` several times within one attempt; each call is ledgered and
budget-checked individually. A graph must not outlive the attempt, and its own
retries must surface quota as a park rather than retrying internally.
