"""``aia_executors.smoke_record``: a deploy's smoke lines kept for Settings (settings-backends
SB4). Labels and results only; a secret shape and any address but the public hostname's are
cleaned from a label before it is kept; no check line is nothing kept, and says so."""

from __future__ import annotations

import io
from typing import Any

import pytest
from aia_core.infrastructure.tables import DeploySmokeResultRow
from aia_executors import smoke_record
from aia_executors.smoke_record import clean_label, main
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

SHA = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture
def operator_db(
    monkeypatch: pytest.MonkeyPatch, engine: Engine, sessions: sessionmaker[Session]
) -> sessionmaker[Session]:
    class _Kept:  # the command disposes what it is given; the fixture owns the engine
        def dispose(self) -> None:
            return

    monkeypatch.setattr(smoke_record, "engine_from_env", lambda: (_Kept(), sessions))
    return sessions


def test_the_lines_are_kept_as_labels_and_results(
    monkeypatch: pytest.MonkeyPatch, operator_db: sessionmaker[Session], capsys: Any
) -> None:
    lines = (
        "ok    web: /version reports build\n"
        "FAIL  api: /health is ok\n"
        '      {"detail": "internal"}\n'
        "NOT_RUNNABLE  ai: a paid model call\n"
        "smoke: FAILED\n"
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(lines))
    assert main(["--build", SHA, "--public-hostname", "aia-develop.example"]) == 0
    assert "3 checks kept" in capsys.readouterr().out
    with operator_db() as session:
        rows = session.scalars(
            select(DeploySmokeResultRow).order_by(DeploySmokeResultRow.position)
        ).all()
    assert [(r.position, r.check_label, r.status, r.build_sha) for r in rows] == [
        (0, "web: /version reports build", "ok", SHA),
        (1, "api: /health is ok", "FAIL", SHA),
        (2, "ai: a paid model call", "NOT_RUNNABLE", SHA),
    ]
    assert len({r.run_id for r in rows}) == 1


def test_no_check_line_keeps_nothing(
    monkeypatch: pytest.MonkeyPatch, operator_db: sessionmaker[Session]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("smoke: FAILED\n"))
    assert main(["--build", SHA]) == 1
    with operator_db() as session:
        assert session.scalars(select(DeploySmokeResultRow)).all() == []


def test_a_label_keeps_the_public_hostname_and_nothing_internal() -> None:
    label = (
        "api: https://aia-develop.example/api/v1/health and http://glitchtip:8000/x "
        "and https://user:pw@aia-develop.example/ with Bearer abcdefghijklmnopqrstuvwxyz0123456789"
    )
    cleaned = clean_label(label, public_hostname="aia-develop.example")
    assert "https://aia-develop.example/api/v1/health" in cleaned
    assert "glitchtip" not in cleaned and "pw@" not in cleaned
    assert "abcdefghijklmnopqrstuvwxyz0123456789" not in cleaned
