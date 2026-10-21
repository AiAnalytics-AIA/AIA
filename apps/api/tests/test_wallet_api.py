"""A study's wallet over HTTP (ADR 0028 decision 2, lead-orchestration LO1).

Off (the default), ``GET`` answers unavailable and ``PUT`` is 409 ``wallet_disabled`` with no
wallet row written; on, the researcher sets the cap inside the client's wallet ceiling and the
study's budget, each refusal named, and the change is one approval-ledger row.
"""

from __future__ import annotations

from typing import Any

import pytest
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.tables import ApprovalDecisionRow, ClientRow
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from aia_api.config import Settings

API = "/api/v1"


def _url(world: Any, study: str = "primary") -> str:
    return f"{API}/studies/{world.study_id(study)}/wallet"


def _ceiling(app: FastAPI, world: Any, usd: float | None) -> None:
    with create_session_factory(app.state.engine)() as session:
        client = session.get(ClientRow, world.clients["primary"].client_id)
        assert client is not None
        client.wallet_ceiling_usd = usd
        session.commit()


def _wallet_rows(app: FastAPI) -> list[Any]:
    from aia_core.domain.approval_ledger import ApprovalSubject

    with create_session_factory(app.state.engine)() as session:
        return list(
            session.scalars(
                select(ApprovalDecisionRow).where(
                    ApprovalDecisionRow.subject_type == ApprovalSubject.WALLET
                )
            ).all()
        )


def test_off_by_default_the_wallet_is_unavailable_and_nothing_is_written(
    app: FastAPI, researcher: TestClient, world: Any
) -> None:
    assert app.state.settings.study_wallet_enabled is False
    read = researcher.get(_url(world))
    assert read.status_code == 200
    assert read.json()["available"] is False
    assert read.json()["unavailable_reason"] == "wallet_disabled"
    put = researcher.put(_url(world), json={"cap_usd": 10.0})
    assert put.status_code == 409 and put.json()["code"] == "wallet_disabled"
    assert _wallet_rows(app) == []


class TestOn:
    @pytest.fixture
    def settings(self, settings: Settings) -> Settings:
        return settings.model_copy(update={"study_wallet_enabled": True})

    def test_the_researcher_sets_the_cap_and_reads_what_remains(
        self, app: FastAPI, researcher: TestClient, world: Any
    ) -> None:
        empty = researcher.get(_url(world)).json()
        assert empty["available"] is True and empty["wallet_id"] is None

        put = researcher.put(_url(world), json={"cap_usd": 40.0})
        assert put.status_code == 200, put.text
        body = put.json()
        assert (body["cap_usd"], body["effective_cap_usd"], body["remaining_usd"]) == (
            40.0,
            40.0,
            40.0,
        )
        assert (body["study_budget_usd"], body["client_ceiling_usd"]) == (500.0, None)
        assert [r["to_cap_usd"] for r in body["raises"]] == [40.0]
        assert body["charges"] == [] and body["charged_usd"] == 0.0
        assert [r.decision for r in _wallet_rows(app)] == ["set_cap"]
        assert researcher.get(_url(world)).json() == body

    def test_above_the_clients_ceiling_names_who_can_raise_it(
        self, app: FastAPI, researcher: TestClient, world: Any
    ) -> None:
        _ceiling(app, world, 25.0)
        refused = researcher.put(_url(world), json={"cap_usd": 30.0})
        assert refused.status_code == 409
        assert refused.json()["code"] == "above_client_ceiling"
        assert refused.json()["details"] == {
            "to_cap_usd": 30.0,
            "client_ceiling_usd": 25.0,
            "who_can_raise": ["OWNER", "ADMIN"],
        }
        assert _wallet_rows(app) == []

    def test_above_the_study_budget_is_refused(
        self, app: FastAPI, researcher: TestClient, world: Any
    ) -> None:
        refused = researcher.put(_url(world), json={"cap_usd": 501.0})
        assert refused.status_code == 409
        assert refused.json()["code"] == "above_study_budget"
        assert refused.json()["details"]["study_budget_usd"] == 500.0

    def test_a_negative_cap_is_invalid(self, researcher: TestClient, world: Any) -> None:
        assert researcher.put(_url(world), json={"cap_usd": -1}).status_code == 422

    def test_an_unknown_study_is_not_found(self, researcher: TestClient) -> None:
        url = f"{API}/studies/STU-00000000000000/wallet"
        assert researcher.get(url).status_code == 404
        assert researcher.put(url, json={"cap_usd": 1.0}).status_code == 404
