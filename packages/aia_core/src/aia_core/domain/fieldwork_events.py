"""The fieldwork event contract (run-qc-and-checkpoint RQC7, interface I7): what a run's fieldwork
step writes to the run's feed, so Sběr dat reads it without parsing sentences.

Each event is a ``STEP_PROGRESS`` row whose message is one of :class:`FieldworkEvent` and whose
payload holds exactly that event's keys (:data:`PAYLOAD_KEYS`); the web holds the same set to
``tests/fixtures/fieldwork_events/contract.json``. Counts are as reported, never estimated:

* ``fieldwork_progress``: respondents answered of the run's plans, and the respondent blocks this
  attempt sent to a model beside those replayed from the run's journal (RQC0) at no cost. Written
  every few respondents (the composition's ``progress_every``) and at the last; with the worker's
  ``AIA_AI_FIELDWORK_HEARTBEAT`` on, also between a respondent's blocks once
  :data:`HEARTBEAT_SECONDS` passed without one. A single call that takes longer writes nothing
  until it returns.

Why a step stopped is not a fieldwork event: the engine's ``STEP_RECOVERY`` carries the
executor's own reason as ``error_reason``, for every executor (``workflow_repository``).

Quota-cell fill and the respondent grid follow in RQC7b, under a new version.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

__all__ = [
    "FIELDWORK_EVENTS_VERSION",
    "HEARTBEAT_SECONDS",
    "PAYLOAD_KEYS",
    "FieldworkEvent",
    "progress",
    "progress_due",
]

FIELDWORK_EVENTS_VERSION: Final = "aia-fieldwork-events-1"
HEARTBEAT_SECONDS: Final = 30.0


class FieldworkEvent(StrEnum):
    PROGRESS = "fieldwork_progress"


PAYLOAD_KEYS: Final[dict[FieldworkEvent, tuple[str, ...]]] = {
    FieldworkEvent.PROGRESS: ("version", "respondents", "of", "sent", "replayed"),
}


def progress(*, respondents: int, of: int, sent: int, replayed: int) -> dict[str, object]:
    """A ``fieldwork_progress`` payload: respondents answered of ``of``; blocks sent, replayed."""
    return {
        "version": FIELDWORK_EVENTS_VERSION,
        "respondents": respondents,
        "of": of,
        "sent": sent,
        "replayed": replayed,
    }


def progress_due(*, respondents: int, of: int, idle_seconds: float, every: int) -> bool:
    """Whether a ``fieldwork_progress`` is due: every ``every`` respondents, at the last, or once
    :data:`HEARTBEAT_SECONDS` have passed since the step last wrote one."""
    return (
        respondents == of
        or (respondents > 0 and respondents % max(1, every) == 0)
        or idle_seconds >= HEARTBEAT_SECONDS
    )
