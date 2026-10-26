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

Behind the worker's ``AIA_AI_FIELDWORK_QUOTA_FILL`` (RQC7b, version 2), for a panel run:

* ``fieldwork_sample``: once per attempt, once the gateway's preflight passed and before its
  first respondent: the sample's quota fields and the cells allotted respondents, each with its
  key (:func:`~.population.sampling.quota_keys`), its values and its allotment. How ``n`` is
  spread, never a promise of support. None for a sample drawn without quota fields.
* ``fieldwork_progress``'s ``cells``: the respondents answered in each cell since the attempt's
  previous report, by key (a respondent without a cell is not in it); ``None`` when the attempt
  reports no cells (the switch off, a roster run). A cell's fill is the sum of its counts, never
  estimated. Carried by the report fieldwork writes anyway, so it adds no write of its own: a
  replayed attempt writes exactly the reports it always did.

Why a step stopped is not a fieldwork event: the engine's ``STEP_RECOVERY`` carries the
executor's own reason as ``error_reason``, for every executor (``workflow_repository``).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Final

from .population.sampling import PanelSample, quota_keys

__all__ = [
    "FIELDWORK_EVENTS_VERSION",
    "HEARTBEAT_SECONDS",
    "PAYLOAD_KEYS",
    "FieldworkEvent",
    "progress",
    "progress_due",
    "respondent_cells",
    "sample",
]

FIELDWORK_EVENTS_VERSION: Final = "aia-fieldwork-events-2"
HEARTBEAT_SECONDS: Final = 30.0
#: How many respondents a fieldwork_progress reports at most, by default: the AI runtime's batch and
#: the fictional source's (artifact-fieldwork FLD12), so Průběh reads both alike.
PROGRESS_EVERY: Final = 10


class FieldworkEvent(StrEnum):
    PROGRESS = "fieldwork_progress"
    SAMPLE = "fieldwork_sample"


PAYLOAD_KEYS: Final[dict[FieldworkEvent, tuple[str, ...]]] = {
    FieldworkEvent.PROGRESS: ("version", "respondents", "of", "sent", "replayed", "cells"),
    FieldworkEvent.SAMPLE: ("version", "quota_fields", "cells"),
}


def progress(
    *,
    respondents: int,
    of: int,
    sent: int,
    replayed: int,
    cells: Mapping[str, int] | None = None,
) -> dict[str, object]:
    """A ``fieldwork_progress`` payload: respondents answered of ``of``; blocks sent, replayed;
    and, for a panel run reporting its cells, those answered in each cell since the last report."""
    return {
        "version": FIELDWORK_EVENTS_VERSION,
        "respondents": respondents,
        "of": of,
        "sent": sent,
        "replayed": replayed,
        "cells": None if cells is None else dict(cells),
    }


def progress_due(*, respondents: int, of: int, idle_seconds: float, every: int) -> bool:
    """Whether a ``fieldwork_progress`` is due: every ``every`` respondents, at the last, or once
    :data:`HEARTBEAT_SECONDS` have passed since the step last wrote one."""
    return (
        respondents == of
        or (respondents > 0 and respondents % max(1, every) == 0)
        or idle_seconds >= HEARTBEAT_SECONDS
    )


def sample(drawn: PanelSample) -> dict[str, object] | None:
    """A ``fieldwork_sample`` payload: the sample's quota fields and the cells the sampler
    allotted respondents to, in its order, each ``{key, values, n}``; ``None`` for a sample drawn
    without quota fields. A cell allotted none is left out: nobody will answer in it."""
    keys = quota_keys(drawn.quota_cells)
    cells = [
        {"key": key, "values": list(cell.values), "n": cell.n}
        for key, cell in zip(keys, drawn.quota_cells, strict=True)
        if cell.n > 0
    ]
    if not cells:
        return None
    return {
        "version": FIELDWORK_EVENTS_VERSION,
        "quota_fields": list(drawn.audit.quota_fields),
        "cells": cells,
    }


def respondent_cells(drawn: PanelSample) -> tuple[str | None, ...]:
    """Each sampled respondent's quota cell key, in sample order (``None`` without one)."""
    keys = quota_keys(drawn.quota_cells)
    return tuple(None if r.quota_cell is None else keys[r.quota_cell] for r in drawn.respondents)
