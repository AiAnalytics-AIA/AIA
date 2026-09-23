# AI runtime ↔ step executor contract

**Owners:** ai-runtime (the gateway side) and platform-runtime (the worker and
`WorkflowRepository` side). **Status:** the ai-runtime side is implemented; the
step executor that consumes it does not exist yet (PROGRESS *Next* #2).

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
rsv_id   = workflow.reserve_budget(attempt_id=…, amount_usd=<step budget>, provider=<paid provider>)
journal  = WorkflowCallJournal(workflow=…, usage=AIUsageRepository(session, scope),
                               attempt_id=claimed.attempt_id, commit=session.commit)
context  = ExecutionContext(scope=scope, runtime_version=BUILD, journal=journal,
                            run_id=…, step_id=…, attempt_id=…,
                            reservation=ReservationView(rsv_id, amount),
                            is_cancelled=lambda: workflow.is_cancel_requested(step_id))
try:
    result = await gateway.invoke(request, context)
    workflow.complete_attempt(attempt_id, output=…, actual_cost_usd=result.total_cost_usd,
                              reservation_id=rsv_id)
except ModelCallFailed as failure:
    inputs = recovery_inputs(failure)
    workflow.fail_attempt(attempt_id, failure=inputs.failure, error=dict(inputs.error),
                          reservation_id=rsv_id, quota_reset_at=inputs.quota_reset_at)
```

A subscription-only step passes no reservation; the gateway refuses a metered
call without one (`paid_call_without_reservation`), rather than calling unbudgeted.

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
3. **Dispatch is durable before the call leaves.** `record_dispatch` must have
   committed when it returns. `WorkflowCallJournal` calls the injected `commit`
   after writing the `DISPATCHED` ledger row and `mark_paid_call_dispatched`.
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

1. **The step executor itself** (`apps/worker/`), built to the sequence above.
2. **Heartbeats during a long call.** A model call can outlast a 120 s lease. The
   worker must heartbeat concurrently with `invoke`, or pass a lease long enough
   for the agent's timeout. A lapsed lease during a paid call is
   `RECOVERY_REQUIRED` — safe, but a person is paged for nothing.
3. **Settling an uncertain reservation from a ledger resolution.**
   `AIUsageRepository.resolve_uncertain` corrects the *ledger*; the study's
   `spent_usd` still carries the `SETTLED_UNCERTAIN` reservation amount.
   `.planning/open-items.md` OI-6.
4. **The commit hook.** `WorkflowCallJournal` commits the session it is given.
   If the claim transaction must stay open across the call, supply a separate
   session for the journal instead; the obligation is durability, not this
   particular mechanism.

## Out of scope for this contract

Agent-internal loops (LangGraph, ADR 0006) sit *inside* one `invoke` caller and
may call `invoke` several times within one attempt; each call is ledgered and
budget-checked individually. A graph must not outlive the attempt, and its own
retries must surface quota as a park rather than retrying internally.
