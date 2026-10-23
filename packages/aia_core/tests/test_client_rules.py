"""A client's rules (settings-backends SB7): its data posture and wallet ceiling, set by an
OWNER or ADMIN, audited, and the posture pinned on a Deep Research run at enqueue."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select

from aia_core.application.deep_research import DeepResearchRuns
from aia_core.domain.client_rules import DataPosture, effective_posture
from aia_core.domain.scope import ScopeDenied
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import AccessAuditRow

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
