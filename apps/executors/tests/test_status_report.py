"""``aia_executors.status_report`` (plan ops-status-report): the deployment's state as one line of
codes, counts and ids. A failed step's reason code and a parked step whatever its age are listed;
free text in a reason, a switch or a kind prints ``uncoded``; a key off the allowlist is never
printed; no database is one error line, never a traceback."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from aia_core.infrastructure.operations_status import PROBLEM_LIMIT, code_or_uncoded
from aia_core.infrastructure.tables import (
    AIUsageEventRow,
    BudgetReservationRow,
    DeepResearchSettingApprovalRow,
    DeepResearchSettingVersionRow,
    StepAttemptRow,
    StepRunRow,
    WorkflowRunRow,
)
from aia_executors import status_report
from aia_executors.status_report import main, switches
from sqlalchemy.orm import Session, sessionmaker

NOW = datetime.now(UTC)
SECRET_TEXT = "Traceback: password=hunter2 at https://user:pw@internal.example/x"


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


@pytest.fixture
def operator_db(
    monkeypatch: pytest.MonkeyPatch, sessions: sessionmaker[Session]
) -> sessionmaker[Session]:
    class _Kept:  # the command disposes what it is given; the fixture owns the engine
        def dispose(self) -> None:
            return

    monkeypatch.setattr(status_report, "engine_from_env", lambda: (_Kept(), sessions))
    return sessions


def _run(session: Session, world: Any, *, workflow_type: str, status: str, at: datetime) -> str:
    run_id = _id("RUN")
    session.add(
        WorkflowRunRow(
            run_id=run_id,
            organization_id=world.organization_id,
            client_id=world.client_id,
            study_id=world.study_id,
            project_id=world.project_id,
            project_revision=1,
            workflow_type=workflow_type,
            status=status,
            idempotency_key=run_id,
            created_at=at,
            updated_at=at,
        )
    )
    return run_id


def _step(
    session: Session,
    run_id: str,
    *,
    kind: str,
    status: str,
    at: datetime,
    waiting_reason: str | None = None,
    attempts: list[dict[str, Any]] = (),  # type: ignore[assignment]
) -> None:
    step_id = _id("STP")
    session.add(
        StepRunRow(
            step_id=step_id,
            run_id=run_id,
            node_key=kind,
            kind=kind,
            status=status,
            waiting_reason=waiting_reason,
            created_at=at,
            updated_at=at,
        )
    )
    session.flush()
    for number, error in enumerate(attempts, start=1):
        session.add(
            StepAttemptRow(
                attempt_id=_id("ATT"),
                step_id=step_id,
                attempt_number=number,
                status="FAILED",
                failure_class=error.pop("failure_class", None),
                error_json=error,
            )
        )


def _usage(
    session: Session,
    world: Any,
    *,
    model: str,
    outcome: str,
    cost: float,
    call_id: str | None = None,
) -> None:
    session.add(
        AIUsageEventRow(
            event_id=_id("EVT"),
            call_id=call_id or _id("CALL"),
            outcome=outcome,
            purpose="research",
            organization_id=world.organization_id,
            client_id=world.client_id,
            study_id=world.study_id,
            actor_id="worker",
            agent_id="aia.research.respondent",
            agent_version="1",
            prompt_id="p",
            prompt_version="1",
            capability="SIMULATION",
            policy_version="v",
            runtime_version="r",
            provider="aws_bedrock",
            model=model,
            route_id="bedrock-eu-primary",
            data_class="CLASS_C_INTERNAL",
            residency_zone="EU",
            input_tokens=100,
            output_tokens=10,
            cost_usd=cost,
            cost_basis="METERED",
            occurred_at=NOW,
        )
    )


@pytest.fixture
def populated(world: Any, sessions: sessionmaker[Session]) -> Any:
    with sessions() as session:
        old = NOW - timedelta(days=30)
        recent = NOW - timedelta(hours=2)
        done = _run(session, world, workflow_type="research", status="SUCCEEDED", at=recent)
        _step(session, done, kind="research_compile", status="SUCCEEDED", at=recent)
        failed = _run(session, world, workflow_type="research_lead", status="FAILED", at=recent)
        _step(
            session,
            failed,
            kind="research_lead_turn",
            status="FAILED",
            at=recent,
            attempts=[
                {"reason": "first_try", "failure_class": "TRANSIENT"},
                {"reason": "model_access_denied", "failure_class": "PERMANENT"},
            ],
        )
        leaky = _run(session, world, workflow_type="research", status="FAILED", at=recent)
        _step(
            session,
            leaky,
            kind="research_report",
            status="FAILED",
            at=recent,
            attempts=[{"reason": SECRET_TEXT, "message": SECRET_TEXT}],
        )
        # Parked a month ago: outside the window, still live, so still listed.
        parked = _run(session, world, workflow_type="research", status="WAITING_PROVIDER", at=old)
        _step(
            session,
            parked,
            kind="research_fieldwork",
            status="WAITING_PROVIDER",
            at=old,
            waiting_reason="ai_runtime_unavailable",
        )
        # Failed a month ago: outside the window, not listed.
        stale = _run(session, world, workflow_type="research", status="FAILED", at=old)
        _step(session, stale, kind="research_aggregate", status="FAILED", at=old)
        _usage(
            session, world, model="eu.anthropic.claude-sonnet-4-5", outcome="SUCCEEDED", cost=0.5
        )
        _usage(
            session, world, model="eu.anthropic.claude-sonnet-4-5", outcome="SUCCEEDED", cost=0.25
        )
        # One call answered, one dispatched with no outcome yet: the second is open.
        answered, open_call = _id("CALL"), _id("CALL")
        for call_id, outcome in ((answered, "DISPATCHED"), (answered, "SUCCEEDED")):
            _usage(session, world, model="m", outcome=outcome, cost=0.0, call_id=call_id)
        _usage(session, world, model="m", outcome="DISPATCHED", cost=0.0, call_id=open_call)
        session.add(
            BudgetReservationRow(
                reservation_id=_id("RES"),
                client_id=world.client_id,
                study_id=world.study_id,
                amount_usd=1.5,
                status="RESERVED",
            )
        )
        for key, version in (("brave_search", None), ("brave_search", 3), ("budget", 1)):
            if version is not None:
                session.add(
                    DeepResearchSettingVersionRow(
                        version_id=_id("DRV"),
                        organization_id=world.organization_id,
                        setting_key=key,
                        version_number=version,
                        value={"v": version},
                        value_sha256="0" * 64,
                        created_by=world.owner_id,
                    )
                )
                session.flush()
            session.add(
                DeepResearchSettingApprovalRow(
                    organization_id=world.organization_id,
                    setting_key=key,
                    version_number=version,
                    approved_by=world.owner_id,
                )
            )
            session.flush()
        session.commit()
    return world


def _report(capsys: Any, argv: list[str] | None = None) -> dict[str, Any]:
    assert main(argv or []) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1 and out[0].startswith("aia-status ")
    return json.loads(out[0].removeprefix("aia-status "))


def test_one_line_names_every_problem_step_by_its_codes(
    operator_db: sessionmaker[Session], populated: Any, capsys: Any
) -> None:
    report = _report(capsys)
    failed = {p["kind"]: p for p in report["failed_steps"]}
    # The month-old failure is outside the window.
    assert set(failed) == {"research_lead_turn", "research_report"}
    lead = failed["research_lead_turn"]
    assert (lead["status"], lead["error_reason"], lead["failure_class"]) == (
        "FAILED",
        "model_access_denied",  # the last attempt's, not the first's
        "PERMANENT",
    )
    assert lead["workflow_type"] == "research_lead"
    # Parked a month ago: outside the window, still live, so listed and counted.
    [parked] = report["live_problem_steps"]
    assert (parked["kind"], parked["status"], parked["waiting_reason"]) == (
        "research_fieldwork",
        "WAITING_PROVIDER",
        "ai_runtime_unavailable",
    )
    assert report["runs"]["research_lead"] == {"FAILED": 1}
    assert report["runs"]["research"] == {"SUCCEEDED": 1, "FAILED": 1, "WAITING_PROVIDER": 1}
    assert report["steps"]["WAITING_PROVIDER"] == 1
    assert report["steps"]["SUCCEEDED"] == 1
    assert report["window_days"] == 7


def test_free_text_never_reaches_the_line(
    operator_db: sessionmaker[Session], populated: Any, capsys: Any
) -> None:
    report = _report(capsys)
    assert {p["kind"]: p for p in report["failed_steps"]}["research_report"][
        "error_reason"
    ] == "uncoded"
    text = json.dumps(report)
    for fragment in ("hunter2", "password", "internal.example", "Traceback", "owner@art-chain.io"):
        assert fragment not in text


def test_model_calls_holds_and_approvals_are_counted(
    operator_db: sessionmaker[Session], populated: Any, capsys: Any
) -> None:
    report = _report(capsys)
    assert report["open_calls"] == 1
    assert [c for c in report["model_calls"] if c["model"] != "m"] == [
        {
            "model": "eu.anthropic.claude-sonnet-4-5",
            "outcome": "SUCCEEDED",
            "rows": 2,
            "input_tokens": 200,
            "output_tokens": 20,
            "cost_usd": 0.75,
        }
    ]
    assert report["open_holds"] == {"reserved": 1, "reserved_usd": 1.5, "settled_uncertain": 0}
    # The newest approval per setting wins.
    assert report["deep_research_approvals"] == {
        populated.organization_id: {"brave_search": 3, "budget": 1}
    }


def test_switches_print_the_allowlist_only_and_codes_only() -> None:
    env = {
        "AIA_AI_RUNTIME_ENABLED": "true",
        "AIA_AI_ROUTE_APPROVED_FOR": "CLASS_A_CLIENT_CONFIDENTIAL,CLASS_C_INTERNAL",
        "AIA_BEDROCK_MODEL_ID": "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "AIA_DEEP_RESEARCH_WEB_SEARCH": "brave https://user:pw@x",
        "AIA_DEEP_RESEARCH_BRAVE_API_KEY": "BSA-secret-value",
        "AIA_ONLYOFFICE_JWT_SECRET": "0123456789abcdef0123456789abcdef",
    }
    shown = switches(env)
    assert shown["AIA_AI_RUNTIME_ENABLED"] == "true"
    assert shown["AIA_AI_ROUTE_APPROVED_FOR"] == "CLASS_A_CLIENT_CONFIDENTIAL,CLASS_C_INTERNAL"
    assert shown["AIA_BEDROCK_MODEL_ID"] == "eu.anthropic.claude-sonnet-4-5-20250929-v1:0"
    assert shown["AIA_DEEP_RESEARCH_WEB_SEARCH"] == "uncoded"
    assert shown["AIA_AI_ANALYSIS_ENABLED"] is None
    assert "AIA_DEEP_RESEARCH_BRAVE_API_KEY" not in shown
    assert "AIA_ONLYOFFICE_JWT_SECRET" not in shown
    assert not any(
        word in key for key in status_report.SWITCHES for word in ("KEY", "SECRET", "TOKEN", "DSN")
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ai_runtime_unavailable", "ai_runtime_unavailable"),
        ("eu.anthropic.claude-sonnet-5-5", "eu.anthropic.claude-sonnet-5-5"),
        ("two words", "uncoded"),
        ("x" * 65, "uncoded"),
        (42, "uncoded"),
        ("", None),
        (None, None),
    ],
)
def test_a_reason_is_printed_only_as_a_code(value: object, expected: str | None) -> None:
    assert code_or_uncoded(value) == expected


def test_without_a_database_it_says_so_in_one_line(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    monkeypatch.setenv("DATABASE_URL", "")
    assert main([]) == 1
    assert capsys.readouterr().out.strip() == "aia-status-error no_database_url"


def test_a_window_out_of_range_is_refused(capsys: Any) -> None:
    assert main(["--days", "0"]) == 1
    assert capsys.readouterr().out.strip() == "aia-status-error days_out_of_range"


def test_old_parked_steps_are_never_crowded_out_by_recent_failures(
    operator_db: sessionmaker[Session], world: Any, capsys: Any
) -> None:
    with operator_db() as session:
        parked = _run(
            session,
            world,
            workflow_type="research",
            status="RECOVERY_REQUIRED",
            at=NOW - timedelta(days=40),
        )
        _step(
            session,
            parked,
            kind="research_fieldwork",
            status="RECOVERY_REQUIRED",
            at=NOW - timedelta(days=40),
        )
        for n in range(PROBLEM_LIMIT + 5):
            run = _run(
                session,
                world,
                workflow_type="research",
                status="FAILED",
                at=NOW - timedelta(minutes=n),
            )
            _step(
                session, run, kind="research_report", status="FAILED", at=NOW - timedelta(minutes=n)
            )
        session.commit()
    report = _report(capsys)
    assert [p["status"] for p in report["live_problem_steps"]] == ["RECOVERY_REQUIRED"]
    failed = report["failed_steps"]
    assert len(failed) == PROBLEM_LIMIT
    assert failed == sorted(failed, key=lambda p: p["updated_at"], reverse=True)
