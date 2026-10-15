"""Start and follow AI proposals from a client's document (lifecycle K2d4).

A person asks for proposals from one of the client's sources. The run is the client's own
work (``start_client_work``): no study, paid by the client's budget. It pins the source's
reading as it stands, so the worker reads exactly that reading or refuses
(``reading_changed``).

**One run per reading.** Asking again while a run for the same reading is queued,
running, waiting or finished returns that run. Only after a run for it has failed, been
cancelled, or stopped for recovery with every paid call's outcome known does asking again
start another; what that run already answered is replayed from the client's journal, not
paid again. A run left with a paid call of unknown outcome is never restarted from here.
A source read again since is a new reading, and asking about it starts a new run.

A source this work does not extract is refused before anything is queued, by the same
names the step uses (``dataset_not_extracted``, ``no_text``, ``nothing_read``), so a person
is told at once rather than after a run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final

from sqlalchemy.orm import Session

from aia_core.domain.client_sources import SourceFamily
from aia_core.domain.scope import ClientContext, ClientPermission, ClientWorkContext, ScopeDenied
from aia_core.domain.source_proposals import HARNESS_VERSION, NotExtractable
from aia_core.domain.workflow import WorkflowRunStatus
from aia_core.domain.workflow_templates import CLIENT_SOURCE_PROPOSALS
from aia_core.infrastructure.client_source_repository import ClientSourceRepository, ReadingPin
from aia_core.infrastructure.storage import ArtifactStore
from aia_core.infrastructure.workflow_repository import WorkflowRepository

from .client_work import client_work_project, start_client_work

__all__ = [
    "STEP",
    "ProposalsRun",
    "latest_source_proposals",
    "start_source_proposals",
]

#: The run's one step (``workflow_templates.steps_for_workflow``).
STEP: Final = "extract"
#: Runs after which asking again starts another; any other run is the answer, except one
#: whose step stopped for recovery with every outcome known (``_restartable``).
_ENDED_WITHOUT_RESULT: Final = frozenset({WorkflowRunStatus.FAILED, WorkflowRunStatus.CANCELLED})
#: A paid call left with its outcome unknown: it may have been billed, so nothing restarts
#: the run; an operator settles it first.
UNCERTAIN: Final = "paid_external_call_side_effect_uncertain"
#: The runs read for one source; a person asks again only after a run fails.
_SCAN: Final = 200


@dataclass(frozen=True, slots=True)
class ProposalsRun:
    """A proposals run as a person follows it."""

    run_id: str
    source_id: str
    reading_sha256: str
    status: WorkflowRunStatus
    #: The step's state (``QUEUED``, ``RUNNING``, ``AWAITING_BUDGET``, ``SUCCEEDED`` …).
    step_status: str
    #: Why the step stopped or waits, as the step or the worker named it; ``None`` when it
    #: has not.
    reason: str | None
    #: Whether the reading the run pinned is still the source's reading.
    current: bool
    created_at: datetime | None
    finished_at: datetime | None
    #: What the step reported when it succeeded: ``batches``, ``proposed``, ``dropped``.
    output: dict[str, Any] = field(default_factory=dict)
    #: False when an existing run answered the request and nothing was queued.
    created: bool = False
    #: Whether asking again starts a new run: this one ended without a result and left no
    #: paid call with its outcome unknown. What it answered is replayed, not paid again.
    restartable: bool = False


def _same(client: ClientContext, work: ClientWorkContext) -> None:
    if (client.organization_id, client.client_id, client.actor_id) != (
        work.organization_id,
        work.client_id,
        work.actor_id,
    ):
        raise ScopeDenied("not found", reason="scope_mismatch")


def _require_extractable(pin: ReadingPin) -> str:
    """The pinned reading's hash, or the step's own refusal by name."""
    if pin.family is SourceFamily.DATASET:
        raise NotExtractable("dataset_not_extracted")
    if pin.family is not SourceFamily.DOCUMENT:
        raise NotExtractable("no_text")
    if pin.reading_sha256 is None or pin.segments == 0:
        raise NotExtractable("nothing_read")
    return pin.reading_sha256


def _key_prefix(source_id: str, reading_sha256: str | None = None) -> str:
    """The idempotency keys of the runs about a source, or about one reading of it."""
    prefix = f"{CLIENT_SOURCE_PROPOSALS}:{source_id}:"
    return prefix if reading_sha256 is None else f"{prefix}{reading_sha256}:{HARNESS_VERSION}:"


def _runs(session: Session, work: ClientWorkContext, prefix: str) -> list[dict[str, Any]]:
    """The client's proposal runs whose key starts with ``prefix``, newest first."""
    return WorkflowRepository(session, work).list_runs(
        project_id=client_work_project(session, work),
        workflow_type=CLIENT_SOURCE_PROPOSALS,
        key_prefix=prefix,
        limit=_SCAN,
    )


def _reason(step: dict[str, Any]) -> str | None:
    """Why the step waits or stopped, as specifically as it was named.

    A park's waiting reason is the worker's general one (``ai_runtime_unavailable``); the
    step's own reason (``client_source_proposals_unconfigured``,
    ``egress_route_not_approved_for_class`` …) is on its last attempt, and says what to
    change. A step waiting for budget waits on the budget, whatever an earlier attempt said.
    """
    if step["status"].value == "AWAITING_BUDGET" and step["waiting_reason"]:
        return str(step["waiting_reason"])
    if step["status"].value == "RECOVERY_REQUIRED":
        # Recovery keeps no waiting reason; the attempts say whether a call may be billed.
        return UNCERTAIN if _uncertain(step) else "max_attempts_exhausted"
    if step["status"].value != "SUCCEEDED":
        for attempt in reversed(step["attempts"]):
            error = attempt.get("error") or {}
            if error.get("reason"):
                return str(error["reason"])
    return str(step["waiting_reason"]) if step["waiting_reason"] else None


def _uncertain(step: dict[str, Any]) -> bool:
    """Whether an attempt sent a paid call whose outcome is not known."""
    return any(
        a["paid_call_dispatched"] and not a["paid_call_outcome_known"] for a in step["attempts"]
    )


def _restartable(run: dict[str, Any], step: dict[str, Any]) -> bool:
    """Whether asking again may start a new run in place of this one."""
    if run["status"] in _ENDED_WITHOUT_RESULT:
        return True
    return step["status"].value == "RECOVERY_REQUIRED" and not _uncertain(step)


def _follow(
    session: Session, work: ClientWorkContext, run_id: str, *, current: str | None, created: bool
) -> ProposalsRun:
    run = WorkflowRepository(session, work).get_run(run_id)
    step = next(s for s in run["steps"] if s["node_key"] == STEP)
    pinned = str(run["metadata"]["reading_sha256"])
    return ProposalsRun(
        run_id=run["run_id"],
        source_id=str(run["metadata"]["source_id"]),
        reading_sha256=pinned,
        status=run["status"],
        step_status=step["status"].value,
        reason=_reason(step),
        current=pinned == current,
        created_at=run["created_at"],
        finished_at=run["finished_at"],
        output=step["output"] if step["status"].value == "SUCCEEDED" else {},
        created=created,
        restartable=_restartable(run, step),
    )


def start_source_proposals(
    session: Session,
    client: ClientContext,
    work: ClientWorkContext,
    store: ArtifactStore,
    source_id: str,
) -> ProposalsRun:
    """Queue proposals from ``source_id``'s current reading, or return the run that has them.

    ``client`` and ``work`` are the same person's scopes on the same client; the person
    must be allowed to propose the client's knowledge. A source this work does not extract
    raises :class:`NotExtractable` before anything is written; another client's source is
    not found (``ScopeDenied``).
    """
    _same(client, work)
    client.require(ClientPermission.PROPOSE_CLIENT_KNOWLEDGE)
    pin = ClientSourceRepository(session, store).reading_pin(client, source_id)
    reading_sha256 = _require_extractable(pin)
    prefix = _key_prefix(pin.source_id, reading_sha256)
    same_reading = _runs(session, work, prefix)
    for run in same_reading:
        followed = _follow(session, work, run["run_id"], current=reading_sha256, created=False)
        if not followed.restartable:
            return followed
    started = start_client_work(
        session,
        work,
        workflow_type=CLIENT_SOURCE_PROPOSALS,
        # One run per reading, and one more after each run of it that ended without a result.
        idempotency_key=f"{prefix}{len(same_reading)}",
        step_inputs={
            STEP: {
                "source_id": pin.source_id,
                "reading_sha256": reading_sha256,
                "harness_version": HARNESS_VERSION,
            }
        },
        metadata={"source_id": pin.source_id, "reading_sha256": reading_sha256},
    )
    return _follow(session, work, started.run_id, current=reading_sha256, created=started.created)


def latest_source_proposals(
    session: Session,
    client: ClientContext,
    work: ClientWorkContext,
    store: ArtifactStore,
    source_id: str,
) -> ProposalsRun | None:
    """The newest proposals run about ``source_id``, whatever reading it pinned; ``None``
    when nobody has asked. ``current`` says whether its reading is still the source's."""
    _same(client, work)
    client.require(ClientPermission.VIEW_CLIENT_KNOWLEDGE)
    pin = ClientSourceRepository(session, store).reading_pin(client, source_id)
    runs = _runs(session, work, _key_prefix(pin.source_id))
    if not runs:
        return None
    return _follow(session, work, runs[0]["run_id"], current=pin.reading_sha256, created=False)
