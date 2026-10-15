"""What the worker reports: a run broken for its owner, or a bug -- never a state the
interface already explains.

A real ``sentry_sdk`` client over a capturing transport, the real loop over the scripted
executor (``aia_worker.testing``).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from aia_core.domain.workflow import FailureClass, StepRunStatus
from aia_core.infrastructure import error_tracking
from aia_core.infrastructure.error_tracking import ErrorTrackingSettings
from aia_core.infrastructure.tables import ProjectRow, WorkflowRunRow
from aia_worker.worker import Worker
from sqlalchemy.orm import Session, sessionmaker

pytest.importorskip("sentry_sdk")
from sentry_sdk.transport import Transport

MakeWorker = Callable[..., Worker]
KEY = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz"


class Capture(Transport):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, Any]] = []

    def capture_envelope(self, envelope: Any) -> None:
        self.events.extend(i.payload.json for i in envelope.items if i.type == "event")


@pytest.fixture
def reported() -> Iterator[list[dict[str, Any]]]:
    transport = Capture()
    error_tracking.init(
        ErrorTrackingSettings(
            dsn="http://0123abcd@glitchtip:8000/2",
            service="worker",
            environment="test",
            release="abc123",
        ),
        transport=transport,
    )
    try:
        yield transport.events
    finally:
        error_tracking.close()


def test_a_step_left_failed_is_one_issue_grouped_by_kind_class_and_cause(
    study: Any, make_worker: MakeWorker, reported: list[dict[str, Any]]
) -> None:
    run_id = study.create_run({"fail": FailureClass.AUTHENTICATION.value})

    result = make_worker().run_once()

    assert result is not None and result.step_status is StepRunStatus.FAILED
    (event,) = reported
    assert event["level"] == "error"
    assert event["fingerprint"] == ["step-failed", "scripted", "AUTHENTICATION", ""]
    assert event["message"] == "scripted failed: AUTHENTICATION"
    tags = event["tags"]
    assert (tags["run_id"], tags["step_id"], tags["attempt_id"]) == (
        run_id,
        result.step_id,
        result.attempt_id,
    )
    assert (tags["step_kind"], tags["failure_class"], tags["study_id"]) == (
        "scripted",
        "AUTHENTICATION",
        study.study_id,
    )
    assert tags["worker_id"] == "worker-a"
    assert event["contexts"]["failure"]["error"] == {"attempt": 1}


def test_the_clients_own_work_is_reported_with_its_client_and_no_study(
    study: Any,
    make_worker: MakeWorker,
    sessions: sessionmaker[Session],
    reported: list[dict[str, Any]],
) -> None:
    """A run on the client itself has no study (client-budget): its events name the client,
    and tagging it never reads a study it does not have."""
    run_id = study.create_run({"fail": FailureClass.AUTHENTICATION.value}, key="client-own")
    with sessions() as session:
        run = session.get(WorkflowRunRow, run_id)
        assert run is not None
        project = session.get(ProjectRow, run.project_id)
        assert project is not None
        project.owner, project.study_id, run.study_id = "client_sources", None, None
        session.commit()

    result = make_worker().run_once()

    assert result is not None and result.step_status is StepRunStatus.FAILED
    (event,) = reported
    assert event["tags"]["client_id"] == study.client_id
    assert "study_id" not in event["tags"]


def test_an_unclassified_exception_is_reported_once_with_its_stack_and_no_secret(
    study: Any, make_worker: MakeWorker, reported: list[dict[str, Any]]
) -> None:
    study.create_run({"raise": f"boom with {KEY}"})

    result = make_worker().run_once()

    assert result is not None and result.step_status is StepRunStatus.FAILED
    # The exception's event, with its stack; the step's failure is not a second issue.
    (only,) = reported
    assert only["exception"]["values"][-1]["type"] == "RuntimeError"
    assert only["tags"]["step_kind"] == "scripted"
    assert KEY not in json.dumps(only)


def test_a_retry_that_later_succeeds_is_not_an_issue(
    study: Any, make_worker: MakeWorker, reported: list[dict[str, Any]]
) -> None:
    study.create_run({"fail": FailureClass.TRANSPORT.value, "fail_until_attempt": 2})
    worker = make_worker()

    first = worker.run_once()
    assert first is not None and first.step_status is StepRunStatus.RUNNABLE
    second = worker.run_once()
    assert second is not None and second.ending == "completed"
    assert reported == []


@pytest.mark.parametrize(
    "payload",
    [
        {"fail": FailureClass.QUOTA.value},
        {"fail": FailureClass.RUNTIME_UNAVAILABLE.value},
        {"approval": "Proceed?"},
        {"hold": 1000.0},
    ],
    ids=["quota-park", "runtime-park", "gate", "budget"],
)
def test_a_state_the_interface_explains_is_not_an_issue(
    study: Any,
    make_worker: MakeWorker,
    reported: list[dict[str, Any]],
    payload: dict[str, Any],
) -> None:
    study.create_run(payload)

    result = make_worker().run_once()

    assert result is not None and result.step_status is not StepRunStatus.FAILED
    assert reported == []


def test_a_malformed_dsn_stops_the_worker_before_it_claims_anything(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from aia_worker.__main__ import main

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:1/never")
    monkeypatch.setenv("AIA_WORKER_EXECUTORS", "aia_worker.testing:build_registry")
    monkeypatch.setenv("AIA_ERROR_TRACKING_DSN", "glitchtip:8000")
    assert main() == 2
    assert "AIA_ERROR_TRACKING_DSN" in capsys.readouterr().err
    assert not error_tracking.enabled()
