"""A scripted executor for tests, driven entirely by the step's payload.

It lives in the package rather than in ``tests/`` for the same reason
``aia_api.identity.testing`` does: the multi-process tests start real
``python -m aia_worker`` processes, and those must be able to import it
(``AIA_WORKER_EXECUTORS=aia_worker.testing:build_registry``). It does nothing
unless a step of kind ``scripted`` is created, and it makes no network call.

Payload keys, all optional:

``ledger``
    A file path. One JSON line is appended at ``start`` and at ``end`` of every
    execution -- ``O_APPEND`` writes, so several processes may share one file.
    This is how the tests count executions without trusting the worker's word.
``hold``
    Reserve this many dollars before working, and never dispatch -- a budget
    hold that cancellation or shutdown must give back.
``work_seconds``
    Run for this long, checkpointing every 20 ms -- only on the first
    ``slow_attempts`` attempts when that is given, so a recovered retry is quick.
``paid``
    ``{"reserve": 2.0, "cost": 1.5, "hang_seconds": 0, "crash_in_flight": false}``
    -- one metered call: reserve, dispatching, then hang (the call in flight, no
    checkpoint) and settle at ``cost``. With ``crash_in_flight`` the call never
    settles and the attempt fails with ``TRANSPORT`` -- a timeout after sending,
    the textbook possibly-billed failure.
``paid_overlapping``
    ``{"reserve": [2.0, 3.0], "cost": 1.0, "hang_seconds": 0, "crash_in_flight": false}``
    -- several metered calls in flight at once, as a fan-out sends them: every one
    reserved and dispatched before any is answered; then the first is settled at
    ``cost`` while the others are still in flight, and the process hangs there (no
    checkpoint). With ``crash_in_flight`` the rest never settle and the attempt fails
    with ``TRANSPORT``; otherwise each is settled at ``cost``.
``fail``
    A :class:`~aia_core.domain.workflow.FailureClass` name, returned as
    :class:`Failed` while ``attempt_number < fail_until_attempt`` (default:
    always).
``raise``
    Raise an unclassified ``RuntimeError`` with this message.
``approval``
    A question. Returns :class:`NeedsApproval` until a decision is on the step,
    then succeeds with the decision in its output.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from aia_core.domain.providers import Provider
from aia_core.domain.workflow import FailureClass

from .executor import (
    Failed,
    NeedsApproval,
    StepContext,
    StepExecutor,
    StepFailed,
    StepInput,
    StepOutcome,
    Succeeded,
)

__all__ = ["KIND", "ScriptedExecutor", "build_registry"]

KIND = "scripted"


def _ledger(path: str | None, step: StepInput, event: str) -> None:
    if not path:
        return
    line = json.dumps(
        {
            "event": event,
            "step_id": step.step_id,
            "attempt_id": step.attempt_id,
            "attempt_number": step.attempt_number,
            "pid": os.getpid(),
        }
    )
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, (line + "\n").encode())
    finally:
        os.close(fd)


class ScriptedExecutor:
    """Does what the step's payload says. See the module docstring."""

    def execute(self, step: StepInput, context: StepContext) -> StepOutcome:
        script: dict[str, Any] = dict(step.payload)
        ledger = script.get("ledger")
        _ledger(ledger, step, "start")

        if "hold" in script:
            context.reserve(amount_usd=float(script["hold"]), provider=Provider.ANTHROPIC)

        slow = step.attempt_number <= int(script.get("slow_attempts", 10**6))
        deadline = time.monotonic() + (float(script.get("work_seconds", 0)) if slow else 0.0)
        while time.monotonic() < deadline:
            context.checkpoint()
            time.sleep(0.02)
        context.checkpoint()

        paid = script.get("paid")
        if isinstance(paid, dict):
            call = context.reserve(
                amount_usd=float(paid.get("reserve", 1.0)), provider=Provider.ANTHROPIC
            )
            context.dispatching(call, provider_request_id=f"req-{step.attempt_id}")
            time.sleep(float(paid.get("hang_seconds", 0)))  # in flight: no checkpoint
            if paid.get("crash_in_flight"):
                raise StepFailed(FailureClass.TRANSPORT, "read timeout after sending")
            context.settled(call, actual_cost_usd=float(paid.get("cost", 0.0)))

        overlapping = script.get("paid_overlapping")
        if isinstance(overlapping, dict):
            calls = [
                context.reserve(amount_usd=float(amount), provider=Provider.ANTHROPIC)
                for amount in overlapping.get("reserve", [1.0, 1.0])
            ]
            for number, call in enumerate(calls):
                context.dispatching(call, provider_request_id=f"req-{step.attempt_id}-{number}")
            cost = float(overlapping.get("cost", 0.0))
            context.settled(calls[0], actual_cost_usd=cost)
            time.sleep(float(overlapping.get("hang_seconds", 0)))  # the rest in flight
            if overlapping.get("crash_in_flight"):
                raise StepFailed(FailureClass.TRANSPORT, "read timeout after sending")
            for call in calls[1:]:
                context.settled(call, actual_cost_usd=cost)

        if "raise" in script:
            raise RuntimeError(str(script["raise"]))

        failure = script.get("fail")
        if failure and step.attempt_number < int(script.get("fail_until_attempt", 10**6)):
            return Failed(FailureClass(str(failure)), {"attempt": step.attempt_number})

        question = script.get("approval")
        if question and not step.gate_decisions:
            return NeedsApproval(question=str(question))

        context.progress("done", attempt=step.attempt_number)
        _ledger(ledger, step, "end")
        return Succeeded(
            output={
                "attempt_number": step.attempt_number,
                "decisions": [d.option for d in step.gate_decisions],
            }
        )


def build_registry() -> dict[str, StepExecutor]:
    """The factory named by ``AIA_WORKER_EXECUTORS=aia_worker.testing:build_registry``."""
    return {KIND: ScriptedExecutor()}
