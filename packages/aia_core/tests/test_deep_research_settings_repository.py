"""The Deep Research settings store: who may change a value, what a change leaves behind,
and what is in force (ADR 0022, plan chunk 41).

Against a real database through the same scope path production uses.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from sqlalchemy import select

from aia_core.domain.deep_research.settings import CATALOGUE, Origin
from aia_core.domain.scope import OrganizationRole, ScopeDenied
from aia_core.infrastructure.deep_research_settings_repository import (
    DeepResearchSettingsReader,
    DeepResearchSettingsRepository,
    SettingRefused,
)
from aia_core.infrastructure.tables import AccessAuditRow, DeepResearchSettingVersionRow

RETENTION = "retention.snapshots"
CRAWL = "budgets.allowance.exhaustive.crawl_pages"
DENYLIST = "extraction.denylist"


def _admin(scoped: Any, email: str) -> Any:
    member = scoped.scope_repo.add_member(
        scoped.admin_context, email=email, role=OrganizationRole.ADMIN
    )
    return scoped.resolver.organization_context(scoped.principal(member.user_id))


def _member(scoped: Any) -> Any:
    return scoped.resolver.organization_context(scoped.principal(scoped.users["lead"]))


def _repo(scoped: Any, session: Any) -> DeepResearchSettingsRepository:
    return DeepResearchSettingsRepository(session, scoped.admin_context)


def _reader(scoped: Any, session: Any) -> DeepResearchSettingsReader:
    return DeepResearchSettingsReader(session, _member(scoped))


def _audit(session: Any) -> list[AccessAuditRow]:
    return list(
        session.scalars(
            select(AccessAuditRow)
            .where(AccessAuditRow.action.like("DR_SETTING_%"))
            .order_by(AccessAuditRow.event_id)
        )
    )


# ------------------------------------------------------------------ who may


def test_a_member_reads_but_only_an_administrator_changes(scoped: Any, session: Any) -> None:
    member = _member(scoped)
    assert not member.may_administer
    assert len(DeepResearchSettingsReader(session, member).overview()) == len(CATALOGUE)
    with pytest.raises(ScopeDenied) as denied:
        DeepResearchSettingsRepository(session, member)
    assert denied.value.reason == "insufficient_role"


def test_a_fresh_organization_has_every_proposed_default_in_force(
    scoped: Any, session: Any
) -> None:
    overview = _reader(scoped, session).overview()
    assert [o.definition.key for o in overview] == [d.key for d in CATALOGUE]
    assert {o.effective.origin for o in overview} == {Origin.PROPOSED_DEFAULT}
    assert {(o.version_count, o.latest_number) for o in overview} == {(0, None)}


def test_another_organization_sees_none_of_this_ones_values(scoped: Any, session: Any) -> None:
    repo = _repo(scoped, session)
    repo.propose(RETENTION, 90)
    repo.approve(RETENTION, 1)
    other_org, other_owner = scoped.scope_repo.create_organization(
        slug="other", name="Other", owner_email="o@example.org", owner_name="O"
    )
    principal = replace(
        scoped.principal(other_owner.user_id), organization_id=other_org.organization_id
    )
    owner = scoped.resolver.organization_context(principal)
    assert owner.organization_id == other_org.organization_id != scoped.organization_id
    mine = _reader(scoped, session).effective()[RETENTION]
    assert (mine.value, mine.origin) == (90, Origin.APPROVED)
    theirs = DeepResearchSettingsReader(session, owner).effective()[RETENTION]
    assert (theirs.value, theirs.origin) == (None, Origin.PROPOSED_DEFAULT)


# ------------------------------------------------------------------ proposing


def test_a_proposal_is_a_new_version_and_not_yet_in_force(scoped: Any, session: Any) -> None:
    repo = _repo(scoped, session)
    first = repo.propose(
        CRAWL, 400, source_url="https://example.org/decision", note="halve the crawl"
    )
    second = repo.propose(CRAWL, 300)
    assert (first.version_number, second.version_number) == (1, 2)
    assert first.value == 400 and first.source_url == "https://example.org/decision"
    assert _reader(scoped, session).effective()[CRAWL].origin is Origin.PROPOSED_DEFAULT
    assert [v.version_number for v in _reader(scoped, session).versions(CRAWL)] == [2, 1]
    assert [a.action for a in _audit(session)] == ["DR_SETTING_PROPOSED"] * 2


def test_a_list_is_stored_in_its_normal_form(scoped: Any, session: Any) -> None:
    stored = _repo(scoped, session).propose(DENYLIST, ["Shop.Example", "a.example"])
    assert stored.value == ("a.example", "shop.example")


@pytest.mark.parametrize(
    ("key", "value", "kwargs", "reason"),
    [
        (CRAWL, 5000, {}, "setting_invalid"),
        (RETENTION, "ninety", {}, "setting_invalid"),
        ("provider.search.api_key", "x", {}, "unknown_setting"),
        (RETENTION, 90, {"source_url": "http://example.org"}, "source_invalid"),
        (RETENTION, 90, {"note": "x" * 256}, "note_too_long"),
    ],
)
def test_a_wrong_proposal_is_refused_and_stores_nothing(
    scoped: Any, session: Any, key: str, value: object, kwargs: dict[str, str], reason: str
) -> None:
    with pytest.raises(SettingRefused) as refused:
        _repo(scoped, session).propose(key, value, **kwargs)
    assert refused.value.reason == reason
    assert session.scalars(select(DeepResearchSettingVersionRow)).all() == []
    assert _audit(session) == []


def test_a_version_is_never_updated(scoped: Any, session: Any) -> None:
    repo = _repo(scoped, session)
    repo.propose(RETENTION, 90)
    repo.propose(RETENTION, 30)
    rows = session.scalars(
        select(DeepResearchSettingVersionRow).order_by(DeepResearchSettingVersionRow.version_number)
    ).all()
    assert [r.value["value"] for r in rows] == [90, 30]


# ------------------------------------------------------------------ approving


def test_approving_puts_a_version_in_force_and_withdrawing_returns_the_default(
    scoped: Any, session: Any
) -> None:
    repo = _repo(scoped, session)
    repo.propose(RETENTION, 90)
    repo.propose(RETENTION, 30)
    in_force = repo.approve(RETENTION, 2, reason="the owner's decision")
    assert (in_force.value, in_force.origin, in_force.version) == (30, Origin.APPROVED, 2)
    assert in_force.approved_by == scoped.admin_context.actor_id
    back = repo.approve(RETENTION, None, reason="not decided after all")
    assert (back.value, back.origin) == (None, Origin.PROPOSED_DEFAULT)
    history = _reader(scoped, session).history(RETENTION)
    assert [h.version_number for h in history] == [None, 2]
    assert [a.action for a in _audit(session)][-2:] == [
        "DR_SETTING_APPROVED",
        "DR_SETTING_WITHDRAWN",
    ]


def test_approving_what_is_in_force_changes_nothing(scoped: Any, session: Any) -> None:
    repo = _repo(scoped, session)
    repo.propose(RETENTION, 90)
    repo.approve(RETENTION, 1)
    repo.approve(RETENTION, 1)
    assert len(_reader(scoped, session).history(RETENTION)) == 1


def test_an_unknown_version_is_refused(scoped: Any, session: Any) -> None:
    with pytest.raises(SettingRefused) as refused:
        _repo(scoped, session).approve(RETENTION, 7)
    assert refused.value.reason == "unknown_version"


def test_with_self_approval_off_the_proposer_does_not_approve_alone(
    scoped: Any, session: Any
) -> None:
    scoped.scope_repo.set_self_approval(scoped.admin_context, allowed=False)
    repo = _repo(scoped, session)
    repo.propose(RETENTION, 90)
    with pytest.raises(SettingRefused) as refused:
        repo.approve(RETENTION, 1)
    assert refused.value.reason == "self_approval_not_allowed"
    # Another administrator approves it; withdrawing is always allowed.
    other = DeepResearchSettingsRepository(session, _admin(scoped, "second@example.org"))
    assert other.approve(RETENTION, 1).origin is Origin.APPROVED
    assert repo.approve(RETENTION, None).origin is Origin.PROPOSED_DEFAULT
    # Approving again a version somebody else approved is not a new decision.
    assert repo.approve(RETENTION, 1).origin is Origin.APPROVED


def test_live_readiness_follows_the_approvals(scoped: Any, session: Any) -> None:
    repo = _repo(scoped, session)
    before = _reader(scoped, session).effective().missing_for_live()
    assert RETENTION in before
    repo.propose(RETENTION, 90)
    repo.approve(RETENTION, 1)
    after = _reader(scoped, session).effective().missing_for_live()
    assert RETENTION not in after and len(after) == len(before) - 1
