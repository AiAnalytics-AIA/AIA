"""Accepting a proposal across the move to stable item ids (working-copy-edit-ops WCE1).

A proposal's ``touched_items`` may have been recorded before item ids, in the keys of then; the
person may have reworded or removed the item the refusal has to name. Both against the real
working copy and Design Revision repositories.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from aia_core.application.proposal_accept import StaleProposal, accept_into_working_copy
from aia_core.domain.design_items import Documents, ItemKey
from aia_core.domain.item_ids import derived_id
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository

PLAN = {"research_questions": ["Jak cena mění zájem?", "Kdo kupuje?"]}
# A section with no id and a question with no id: keyed by place before ids (#0, #0#0), by the
# compiler's id after (uvod, uvod#0).
LEGACY = {
    "title": "Fictional",
    "goal": "Test",
    "research_plan": PLAN,
    "sections": [
        {"type": "questions", "title": "Úvod", "questions": [{"text": "x?", "typ": "otevrena"}]}
    ],
}


def _study(session: Any, scoped: Any, content: dict[str, Any]) -> tuple[Any, str]:
    scope = scoped.scope(user="lead")
    revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
        content=content, source_stage="brief"
    )
    return scope, revision.revision_id


def _edit(session: Any, scope: Any, change: Any) -> int:
    workspaces = StudyWorkspaceRepository(session)
    now = workspaces.content(scope)
    content = copy.deepcopy(now.content or {})
    change(content)
    return workspaces.save(scope, content=content, base_revision=now.revision).revision


def _accept(session: Any, scope: Any, design: str, proposed: dict[str, Any], **kw: Any) -> Any:
    working = StudyWorkspaceRepository(session).content(scope).revision
    assert working is not None
    return accept_into_working_copy(
        session,
        scope,
        design_revision_id=design,
        proposed=Documents(content=proposed),
        expected_workspace_revision=working,
        source_stage="brief",
        reason="ai_proposal_accepted",
        **kw,
    )


def _question(content: dict[str, Any]) -> dict[str, Any]:
    return content["sections"][0]["questions"][0]


def test_a_refusal_names_a_reworded_research_question_by_its_wording(
    session: Any, scoped: Any
) -> None:
    """The conflicting key is the baseline's id, which the person's copy no longer holds; the
    refusal carries its wording, so the browser says it in words, never by its hash."""
    scope, design = _study(session, scoped, {"title": "Fictional", "research_plan": PLAN})

    def mine(c: dict[str, Any]) -> None:
        c["research_plan"]["research_questions"][1] = "Kdo nakupuje online?"

    _edit(session, scope, mine)
    proposed = {
        "title": "Fictional",
        "research_plan": {
            **PLAN,
            "research_questions": [PLAN["research_questions"][0], "Kdo platí?"],
        },
    }
    with pytest.raises(StaleProposal) as refused:
        _accept(session, scope, design, proposed)
    key = f"content:research_question:{derived_id('rq_', 'research_question', 'Kdo kupuje?', 1)}"
    details = refused.value.details()
    assert details["reason"] == "items_changed"
    assert key in details["conflicting_items"]
    assert details["conflicting_wording"][key] == "Kdo kupuje?"


LEGACY_TOUCHED = [ItemKey("content", "question", "#0#0"), ItemKey("content", "section", "#0")]


def test_a_question_recorded_before_ids_still_conflicts_with_the_person_s_edit(
    session: Any, scoped: Any
) -> None:
    """Review of #543 (P3-1): a key recorded as ``#0#0`` named nothing after the section took
    the compiler's id, so the stale check passed over the person's edit and the merge dropped the
    proposal's change. It is read as the question it named."""
    scope, design = _study(session, scoped, LEGACY)
    _edit(session, scope, lambda c: _question(c).update(text="z?"))
    proposed = copy.deepcopy(LEGACY)
    _question(proposed)["text"] = "y?"
    with pytest.raises(StaleProposal) as refused:
        _accept(session, scope, design, proposed, touched=LEGACY_TOUCHED)
    assert refused.value.why == "items_changed"
    assert ItemKey("content", "question", "uvod#0") in refused.value.conflicting_items
    assert refused.value.details()["conflicting_wording"]["content:question:uvod#0"] == "z?"


def test_a_question_recorded_before_ids_is_applied_never_dropped(session: Any, scoped: Any) -> None:
    scope, design = _study(session, scoped, LEGACY)
    proposed = copy.deepcopy(LEGACY)
    _question(proposed)["text"] = "y?"
    accepted = _accept(session, scope, design, proposed, touched=LEGACY_TOUCHED)
    assert _question(accepted.merged.content)["text"] == "y?"


def test_a_recorded_item_neither_design_has_is_refused_not_dropped(
    session: Any, scoped: Any
) -> None:
    scope, design = _study(session, scoped, LEGACY)
    proposed = copy.deepcopy(LEGACY)
    _question(proposed)["text"] = "y?"
    working = StudyWorkspaceRepository(session).content(scope).revision
    with pytest.raises(StaleProposal) as refused:
        _accept(session, scope, design, proposed, touched=[ItemKey("content", "question", "#7#7")])
    assert refused.value.why == "unknown_baseline"
    assert StudyWorkspaceRepository(session).content(scope).revision == working


def test_a_place_two_designs_fill_with_different_sections_is_refused(
    session: Any, scoped: Any
) -> None:
    """Re-review of #543: ``#0`` is "Úvod" in the baseline and "Nový" in the proposal. Read by the
    baseline alone, "Nový" was dropped from the merge; the accept is refused instead."""
    scope, design = _study(session, scoped, LEGACY)
    proposed = copy.deepcopy(LEGACY)
    new = {"type": "questions", "title": "Nový", "questions": [{"text": "n?", "typ": "otevrena"}]}
    proposed["sections"].insert(0, new)
    recorded = [
        ItemKey("content", "section", "#0"),
        ItemKey("content", "section", "#1"),
        ItemKey("content", "question", "#0#0"),
        ItemKey("content", "question", "#1#0"),
    ]
    working = StudyWorkspaceRepository(session).content(scope).revision
    with pytest.raises(StaleProposal) as refused:
        _accept(session, scope, design, proposed, touched=recorded)
    assert refused.value.why == "unknown_baseline"
    assert StudyWorkspaceRepository(session).content(scope).revision == working
    # Computed now, by ids, the same proposal applies whole (in the person's order).
    # Order is no item.
    accepted = _accept(session, scope, design, proposed)
    assert sorted(s["title"] for s in accepted.merged.content["sections"]) == ["Nový", "Úvod"]
