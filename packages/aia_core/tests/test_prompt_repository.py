"""The prompt store: who may change a prompt, what a change leaves behind, what runs.

Against a real database through the same scope path production uses (ADR 0019).
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from aia_core.domain.prompt_slots import get_slot, slots, wired_prompt_ids
from aia_core.domain.prompts import prompt_sha256
from aia_core.domain.scope import OrganizationRole, ScopeDenied
from aia_core.infrastructure.prompt_repository import (
    PromptRefused,
    PromptRepository,
    PromptResolver,
)
from aia_core.infrastructure.tables import AccessAuditRow, PromptVersionRow

CRITIQUE = "aia.research.critique_design"
BUILD = "aia.research.build_questionnaire"
RESPONDENT = "aia.respondent.block"


def _admin(scoped: Any, email: str) -> Any:
    member = scoped.scope_repo.add_member(
        scoped.admin_context, email=email, role=OrganizationRole.ADMIN
    )
    return scoped.resolver.organization_context(scoped.principal(member.user_id))


def _repo(scoped: Any, session: Any) -> PromptRepository:
    return PromptRepository(session, scoped.admin_context)


def _audit(session: Any) -> list[AccessAuditRow]:
    return list(
        session.scalars(
            select(AccessAuditRow)
            .where(AccessAuditRow.action.like("PROMPT_%"))
            .order_by(AccessAuditRow.event_id)
        )
    )


# ------------------------------------------------------------------ who may


def test_only_an_administrator_may_open_the_store(scoped: Any, session: Any) -> None:
    member = scoped.resolver.organization_context(scoped.principal(scoped.users["lead"]))
    assert not member.may_administer
    with pytest.raises(ScopeDenied) as denied:
        PromptRepository(session, member)
    assert denied.value.reason == "insufficient_role"


def test_the_resolver_reads_only_its_own_organization(scoped: Any, session: Any) -> None:
    scoped.scope_repo.set_self_approval(scoped.admin_context, allowed=True)  # one person here
    repo = _repo(scoped, session)
    repo.create_version(CRITIQUE, "Vlastní kritika.")
    repo.activate(CRITIQUE, 1)
    other_org, _ = scoped.scope_repo.create_organization(
        slug="other", name="Other", owner_email="o@example.org", owner_name="O"
    )
    # A different organization has nothing activated: it sees the code's wording.
    pin = PromptResolver(session, other_org.organization_id).pin_for(CRITIQUE)
    assert pin.origin == "baseline" and pin.version == "1"
    mine = PromptResolver(session, scoped.organization_id).pin_for(CRITIQUE)
    assert mine.origin == "stored" and mine.text == "Vlastní kritika."


# ------------------------------------------------------------------ the overview


def test_a_fresh_organization_runs_the_codes_wording_everywhere(scoped: Any, session: Any) -> None:
    overview = _repo(scoped, session).overview()
    assert [o.slot.prompt_id for o in overview] == [s.prompt_id for s in slots()]
    for item in overview:
        assert item.active.origin == "baseline"
        assert item.active.version_number is None
        assert (item.version_count, item.latest_number) == (0, None)
        assert item.active.text_sha256 == prompt_sha256(item.slot.baseline_text)
    assert {o.slot.prompt_id for o in overview if o.slot.wired} == wired_prompt_ids()


# ------------------------------------------------------------------ creating


def test_versions_are_numbered_per_prompt_and_never_change(scoped: Any, session: Any) -> None:
    repo = _repo(scoped, session)
    one = repo.create_version(CRITIQUE, "  První.  ", note="první pokus")
    two = repo.create_version(CRITIQUE, "Druhá.", based_on=one.label)
    other = repo.create_version("aia.research.design_copilot", "Jiná.")
    assert (one.version_number, one.label, one.text) == (1, "e1", "První.")
    assert (two.version_number, two.label, two.based_on) == (2, "e2", "e1")
    assert other.version_number == 1  # numbering is per prompt
    assert [v.label for v in repo.versions(CRITIQUE)] == ["e2", "e1"]  # newest first
    assert repo.get_version(CRITIQUE, 1) == one
    assert one.text_sha256 == prompt_sha256("První.")
    # Saving never activates: the code's wording still runs.
    assert repo.active(CRITIQUE).origin == "baseline"


def test_a_new_version_does_not_change_the_job_queued_before_it(scoped: Any, session: Any) -> None:
    repo = _repo(scoped, session)
    resolver = PromptResolver(session, scoped.organization_id)
    before = resolver.pin_for(CRITIQUE)
    repo.create_version(CRITIQUE, "Nová.")
    assert resolver.pin_for(CRITIQUE) == before  # still the baseline pin


@pytest.mark.parametrize(
    ("prompt_id", "text", "reason"),
    [
        (CRITIQUE, "", "empty"),
        (CRITIQUE, "a\x00b", "invalid_character"),
        (CRITIQUE, "x" * 12_001, "too_long"),
        (BUILD, "Bez zástupného znaku.", "missing_required_text"),
        ("aia.research.nope", "text", "unknown_prompt"),
        (RESPONDENT, "text", "not_editable"),
        ("aia.analysis.module", "text", "not_editable"),
    ],
)
def test_an_edit_that_cannot_run_is_refused_not_repaired(
    scoped: Any, session: Any, prompt_id: str, text: str, reason: str
) -> None:
    repo = _repo(scoped, session)
    with pytest.raises(PromptRefused) as refused:
        repo.create_version(prompt_id, text)
    assert refused.value.reason == reason
    assert session.scalar(select(PromptVersionRow)) is None  # nothing was written


def test_every_change_leaves_an_audit_row_naming_who_and_what(scoped: Any, session: Any) -> None:
    repo = _repo(scoped, session)
    version = repo.create_version(CRITIQUE, "Kritika.")
    other = PromptRepository(session, _admin(scoped, "second@art-chain.io"))
    other.activate(CRITIQUE, 1, reason="lepší než základ")
    created, activated = _audit(session)
    assert (created.action, created.actor_id) == ("PROMPT_VERSION_CREATED", scoped.owner_id)
    assert created.payload["text_sha256"] == version.text_sha256
    assert (activated.action, activated.payload["from"], activated.payload["to"]) == (
        "PROMPT_ACTIVATED",
        "1",
        "e1",
    )
    assert activated.payload["why"] == "lepší než základ"
    assert activated.organization_id == scoped.organization_id


# ------------------------------------------------------------------ activating


def test_the_author_does_not_put_their_own_version_live_by_default(
    scoped: Any, session: Any
) -> None:
    repo = _repo(scoped, session)
    repo.create_version(CRITIQUE, "Moje.")
    with pytest.raises(PromptRefused) as refused:
        repo.activate(CRITIQUE, 1)
    assert refused.value.reason == "self_activation_not_allowed"
    assert repo.active(CRITIQUE).origin == "baseline"
    assert not [a for a in _audit(session) if a.action == "PROMPT_ACTIVATED"]


def test_a_second_administrator_can_activate_it(scoped: Any, session: Any) -> None:
    _repo(scoped, session).create_version(CRITIQUE, "Moje.")
    second = PromptRepository(session, _admin(scoped, "second@art-chain.io"))
    active = second.activate(CRITIQUE, 1)
    assert (active.origin, active.label, active.activated_by) == (
        "stored",
        "e1",
        second._admin.actor_id,
    )


def test_an_organization_that_allows_self_approval_lets_the_author_activate(
    scoped: Any, session: Any
) -> None:
    scoped.scope_repo.set_self_approval(scoped.admin_context, allowed=True)
    repo = _repo(scoped, session)
    repo.create_version(CRITIQUE, "Moje.")
    assert repo.activate(CRITIQUE, 1).label == "e1"


def test_the_author_may_roll_back_to_a_version_someone_else_already_ran(
    scoped: Any, session: Any
) -> None:
    author = _repo(scoped, session)
    second = PromptRepository(session, _admin(scoped, "second@art-chain.io"))
    author.create_version(CRITIQUE, "Jedna.")
    author.create_version(CRITIQUE, "Dva.")
    second.activate(CRITIQUE, 1)
    second.activate(CRITIQUE, 2)
    # Version 1 was put live by somebody else: going back to it is not a new decision.
    assert author.activate(CRITIQUE, 1, reason="v2 zhoršila výsledky").label == "e1"
    # Version 2 was also reviewed by the second administrator.
    assert author.activate(CRITIQUE, 2).label == "e2"


def test_resetting_to_the_baseline_is_always_possible_and_recorded(
    scoped: Any, session: Any
) -> None:
    author = _repo(scoped, session)
    second = PromptRepository(session, _admin(scoped, "second@art-chain.io"))
    author.create_version(CRITIQUE, "Jedna.")
    second.activate(CRITIQUE, 1)
    state = author.activate(CRITIQUE, None, reason="zpět na základ")
    assert (state.origin, state.version_number, state.label) == ("baseline", None, "1")
    assert state.activated_by == scoped.owner_id and state.reason == "zpět na základ"
    assert PromptResolver(session, scoped.organization_id).pin_for(CRITIQUE).origin == "baseline"
    assert [a.action for a in _audit(session)][-1] == "PROMPT_RESET_TO_BASELINE"


def test_activating_what_already_runs_changes_nothing(scoped: Any, session: Any) -> None:
    repo = _repo(scoped, session)
    assert repo.activate(CRITIQUE, None).origin == "baseline"
    assert repo.history(CRITIQUE) == []
    assert _audit(session) == []


def test_activating_a_version_that_does_not_exist_is_refused(scoped: Any, session: Any) -> None:
    with pytest.raises(PromptRefused) as refused:
        _repo(scoped, session).activate(CRITIQUE, 7)
    assert refused.value.reason == "unknown_version"


def test_history_is_the_complete_record_newest_first(scoped: Any, session: Any) -> None:
    author = _repo(scoped, session)
    second = PromptRepository(session, _admin(scoped, "second@art-chain.io"))
    author.create_version(CRITIQUE, "Jedna.")
    second.activate(CRITIQUE, 1)
    author.activate(CRITIQUE, None, reason="zpět")
    history = author.history(CRITIQUE)
    assert [(h["label"], h["reason"]) for h in history] == [(None, "zpět"), ("e1", "")]
    assert history[0]["activated_by"] == scoped.owner_id


# ------------------------------------------------------------------ pins


def test_a_pin_is_the_exact_text_with_its_origin(scoped: Any, session: Any) -> None:
    repo = _repo(scoped, session)
    resolver = PromptResolver(session, scoped.organization_id)
    slot = get_slot(CRITIQUE)
    assert slot is not None
    assert resolver.pin_for(CRITIQUE) == slot.baseline_pin()
    repo.create_version(CRITIQUE, "Zkus mě.")
    # An inactive draft can be pinned explicitly -- this is how a draft is tested.
    draft = resolver.pin_for_version(CRITIQUE, 1)
    assert (draft.origin, draft.version, draft.text) == ("stored", "e1", "Zkus mě.")
    assert resolver.pin_for(CRITIQUE).origin == "baseline"  # and it runs for nobody else
    with pytest.raises(PromptRefused) as refused:
        resolver.pin_for_version(CRITIQUE, 9)
    assert refused.value.reason == "unknown_version"


def test_an_unwired_prompt_has_no_pin_to_give(scoped: Any, session: Any) -> None:
    with pytest.raises(PromptRefused) as refused:
        PromptResolver(session, scoped.organization_id).pin_for(RESPONDENT)
    assert refused.value.reason == "not_editable"
