"""A client's rules (settings-backends SB7): its data posture and wallet ceiling, set by an
OWNER or ADMIN, audited, and the posture pinned on a Deep Research run at enqueue."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from aia_core.application.deep_research import DeepResearchRuns
from aia_core.domain.client_rules import DataPosture, effective_posture
from aia_core.domain.deep_research.contracts import DeepResearchRequest
from aia_core.domain.scope import ScopeDenied
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import AccessAuditRow, WorkflowRunRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository

NOW = datetime(2026, 10, 23, 5, 0, tzinfo=UTC)
DESIGN: dict[str, Any] = {
    "title": "Fiktivní značka",
    "goal": "Zjistit, jak lidé vnímají fiktivní značku.",
    "research_plan": {"research_questions": ["Jak lidé vnímají fiktivní značku?"]},
    "sections": [
        {
            "type": "questions",
            "questions": [{"id": "q1", "text": "Znáte značku?", "kategorie": ["Ano", "Ne"]}],
        }
    ],
}


def test_a_posture_never_set_reads_as_classified_never_open() -> None:
    assert effective_posture(None) is DataPosture.CLASSIFIED
    assert effective_posture("OPEN") is DataPosture.OPEN
    with pytest.raises(ValueError):
        effective_posture("MAYBE")


def test_an_administrator_sets_the_rules_and_each_change_is_audited(
    scoped: Any, session: Any
) -> None:
    repo, admin = scoped.scope_repo, scoped.admin_context
    client = scoped.clients["primary"].client_id
    fresh = repo.client_rules(admin, client)
    assert (fresh["data_posture"], fresh["effective_posture"]) == (None, "CLASSIFIED")
    assert fresh["wallet_ceiling_usd"] is None and fresh["set_by"] is None
    set_ = repo.set_client_rules(
        admin, client, changes={"data_posture": "OPEN", "wallet_ceiling_usd": 12.5}, now=NOW
    )
    assert (set_["effective_posture"], set_["wallet_ceiling_usd"]) == ("OPEN", 12.5)
    assert set_["set_by"] == admin.actor_id
    # The same again writes nothing; clearing the ceiling is a change of its own.
    repo.set_client_rules(admin, client, changes={"data_posture": "OPEN"}, now=NOW)
    repo.set_client_rules(admin, client, changes={"wallet_ceiling_usd": None}, now=NOW)
    rows = session.scalars(
        select(AccessAuditRow)
        .where(AccessAuditRow.action == "CLIENT_RULES_CHANGED")
        .order_by(AccessAuditRow.event_id)
    ).all()
    assert [r.payload for r in rows] == [
        {
            "data_posture": {"from": None, "to": "OPEN"},
            "wallet_ceiling_usd": {"from": None, "to": 12.5},
        },
        {"wallet_ceiling_usd": {"from": 12.5, "to": None}},
    ]
    listed = {r["client_id"]: r for r in repo.all_client_rules(admin)}
    assert listed[client]["data_posture"] == "OPEN"


def test_only_an_administrator_sets_them(scoped: Any) -> None:
    member = scoped.resolver.organization_context(scoped.principal(scoped.users["researcher"]))
    client = scoped.clients["primary"].client_id
    assert scoped.scope_repo.client_rules(member, client)["effective_posture"] == "CLASSIFIED"
    with pytest.raises(ScopeDenied):
        scoped.scope_repo.set_client_rules(
            member, client, changes={"data_posture": "OPEN"}, now=NOW
        )


def test_a_deep_research_run_pins_the_posture_and_a_retry_keeps_it(
    scoped: Any, session: Any
) -> None:
    scope = scoped.scope(user="lead")
    revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
        content=DESIGN, source_stage="brief"
    )
    runs = DeepResearchRuns(session, scope)
    first = runs.start(design_revision_id=revision.revision_id, preset_name="QUICK")
    assert first.run["metadata"]["client_posture"] == "CLASSIFIED"
    scoped.scope_repo.set_client_rules(
        scoped.admin_context, scope.client_id, changes={"data_posture": "OPEN"}, now=NOW
    )
    runs.cancel(first.run_id)
    again = runs.retry(first.run_id)
    assert again.run["metadata"]["client_posture"] == "CLASSIFIED"  # the original's
    fresh = runs.start(design_revision_id=revision.revision_id, preset_name="STANDARD")
    assert fresh.run["metadata"]["client_posture"] == "OPEN"


def _pinned_request(session: Any, scope: Any, run_id: str) -> DeepResearchRequest:
    payload = WorkflowRepository(session, scope).step_input(run_id, "plan")
    assert payload is not None
    return DeepResearchRequest.model_validate(payload["request"])


def test_the_posture_is_in_the_engine_request_a_retry_refreezes_from(
    scoped: Any, session: Any
) -> None:
    """ADR 0032 decision 2 (chunk 53): what the plan step reads is the request, so the posture
    is in it; a retry of a CLASSIFIED run stays CLASSIFIED after the client turns OPEN, and an
    OPEN run's retry stays OPEN after it turns back."""
    scope = scoped.scope(user="lead")
    revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
        content=DESIGN, source_stage="brief"
    )
    runs = DeepResearchRuns(session, scope)
    closed = runs.start(design_revision_id=revision.revision_id, preset_name="QUICK")
    request = _pinned_request(session, scope, closed.run_id)
    # CLASSIFIED is the request as it was before chunk 53: no posture key, the same keys.
    assert request.posture is None and "posture" not in request.model_dump(mode="json")
    assert "posture" not in request.method_identity()
    # OPEN or nothing: no other value is a posture a run can carry.
    for value in ("CLASSIFIED", "open", ""):
        with pytest.raises(ValidationError):
            DeepResearchRequest.model_validate(
                {**request.model_dump(mode="json"), "posture": value}
            )

    scoped.scope_repo.set_client_rules(
        scoped.admin_context, scope.client_id, changes={"data_posture": "OPEN"}, now=NOW
    )
    runs.cancel(closed.run_id)
    assert _pinned_request(session, scope, runs.retry(closed.run_id).run_id).posture is None

    opened = runs.start(design_revision_id=revision.revision_id, preset_name="STANDARD")
    open_request = _pinned_request(session, scope, opened.run_id)
    assert open_request.posture == "OPEN" and open_request.open_posture
    assert open_request.method_identity()["posture"] == "OPEN"
    assert opened.run["metadata"]["client_posture"] == "OPEN"

    scoped.scope_repo.set_client_rules(
        scoped.admin_context, scope.client_id, changes={"data_posture": "CLASSIFIED"}, now=NOW
    )
    runs.cancel(opened.run_id)
    again = runs.retry(opened.run_id)
    assert _pinned_request(session, scope, again.run_id).posture == "OPEN"
    assert again.run["metadata"]["client_posture"] == "OPEN"


def test_a_retry_of_a_run_frozen_without_a_posture_stays_classified(
    scoped: Any, session: Any
) -> None:
    """Security review of chunk 53: a run whose request carries no posture (frozen before it)
    ran CLASSIFIED; its retry stays CLASSIFIED after the client is set OPEN, whatever the run's
    metadata label says, never the client row's posture now."""
    scope = scoped.scope(user="lead")
    revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
        content=DESIGN, source_stage="brief"
    )
    runs = DeepResearchRuns(session, scope)
    first = runs.start(design_revision_id=revision.revision_id, preset_name="QUICK")
    runs.cancel(first.run_id)
    # As a run enqueued between #853 and chunk 53 for an OPEN client, or before #853: a label
    # that says OPEN, or none, over a request with no posture.
    for label in ("OPEN", None):
        run = session.get(WorkflowRunRow, first.run_id)
        assert run is not None
        meta = dict(run.metadata_json)
        if label is None:
            meta.pop("client_posture", None)
        else:
            meta["client_posture"] = label
        run.metadata_json = meta
        session.flush()
        scoped.scope_repo.set_client_rules(
            scoped.admin_context, scope.client_id, changes={"data_posture": "OPEN"}, now=NOW
        )
        frozen = runs.retry_spec(first.run_id)
        assert frozen.spec.engine_request.posture is None
