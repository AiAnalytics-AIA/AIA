"""The field-level stale rule and merge of a proposal's accept (working-copy-edit-ops WCE5, D-06).

A proposal goes stale only when a field it changes, ``(item, field)``, also changed in the working
copy since its baseline; a newer Design Revision alone never stales it. The merge takes, for each
item the proposal changes, only the fields it changes. Against the real working copy and Design
Revision repositories.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from aia_core.application.proposal_accept import StaleProposal, accept_into_working_copy
from aia_core.domain.design_items import Documents, ItemKey
from aia_core.domain.edit_log import ActorKind, OpSource, WriteBy
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.study_workspace_repository import StudyWorkspaceRepository


def _q(ident: str, text: str, options: list[str] | None = None) -> dict[str, Any]:
    return {"id": ident, "text": text, "typ": "vyber", "kategorie": options or ["Ano", "Ne"]}


DESIGN: dict[str, Any] = {
    "title": "Fictional",
    "goal": "Test",
    "sections": [
        {"id": "A", "title": "Úvod", "questions": [_q("Q1", "Kupujete?"), _q("Q2", "Kde?")]},
        {"id": "B", "title": "Závěr", "questions": [_q("Q3", "Proč?")]},
    ],
}


def _study(session: Any, scoped: Any) -> tuple[Any, str]:
    scope = scoped.scope(user="lead")
    revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
        content=copy.deepcopy(DESIGN), source_stage="brief"
    )
    return scope, revision.revision_id


def _edit(session: Any, scope: Any, change: Any) -> int:
    workspaces = StudyWorkspaceRepository(session)
    now = workspaces.content(scope)
    content = copy.deepcopy(now.content or {})
    change(content)
    return workspaces.save(
        scope,
        content=content,
        base_revision=now.revision,
        by=WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI),
    ).revision


def _accept(session: Any, scope: Any, design: str, proposed: dict[str, Any]) -> Any:
    working = StudyWorkspaceRepository(session).content(scope).revision
    assert working is not None
    return accept_into_working_copy(
        session,
        scope,
        design_revision_id=design,
        proposed=Documents(content=proposed),
        expected_workspace_revision=working,
        source_stage="questionnaire",
        reason="ai_proposal_accepted",
        by=WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.PROPOSAL_ACCEPT, "RUN-1"),
    )


def _proposal(change: Any) -> dict[str, Any]:
    proposed = copy.deepcopy(DESIGN)
    change(proposed)
    return proposed


def _questions(content: dict[str, Any]) -> dict[str, list[str]]:
    return {s["id"]: [q["id"] for q in s["questions"]] for s in content["sections"]}


def _question(content: dict[str, Any], ident: str) -> dict[str, Any]:
    return next(q for s in content["sections"] for q in s["questions"] if q["id"] == ident)


def test_a_design_revision_submitted_elsewhere_does_not_stale_a_proposal_on_other_items(
    session: Any, scoped: Any
) -> None:
    """A job start, a rebuild or a visit to the Run stage submits a Design Revision; the proposal
    on Q3 is still accepted, on top of it, and the newer revision's edit of Q1 is kept."""
    scope, design = _study(session, scoped)
    _edit(session, scope, lambda c: _question(c, "Q1").update(text="Kupujete kávu?"))
    now = StudyWorkspaceRepository(session).content(scope)
    newer, created = StudyDesignRepository(session, scope).submit(
        content=now.content, source_stage="plan", workspace_revision=now.revision
    )
    assert created
    proposed = _proposal(lambda c: _question(c, "Q3").update(text="Proč ne?"))
    accepted = _accept(session, scope, design, proposed)
    assert accepted.created and accepted.revision.parent_revision == newer.revision
    merged = accepted.merged.content
    assert _question(merged, "Q1")["text"] == "Kupujete kávu?"
    assert _question(merged, "Q3")["text"] == "Proč ne?"


def test_another_field_of_the_same_item_merges(session: Any, scoped: Any) -> None:
    """D-06: the person rewords Q1, the proposal changes Q1's options; both are kept."""
    scope, design = _study(session, scoped)
    _edit(session, scope, lambda c: _question(c, "Q1").update(text="Kupujete kávu?"))
    proposed = _proposal(lambda c: _question(c, "Q1").update(kategorie=["Ano", "Ne", "Nevím"]))
    accepted = _accept(session, scope, design, proposed)
    q1 = _question(accepted.merged.content, "Q1")
    assert (q1["text"], q1["kategorie"]) == ("Kupujete kávu?", ["Ano", "Ne", "Nevím"])


def test_the_same_field_changed_on_both_sides_is_stale(session: Any, scoped: Any) -> None:
    scope, design = _study(session, scoped)
    _edit(session, scope, lambda c: _question(c, "Q1").update(text="Kupujete kávu?"))
    proposed = _proposal(lambda c: _question(c, "Q1").update(text="Kupujete čaj?"))
    with pytest.raises(StaleProposal) as refused:
        _accept(session, scope, design, proposed)
    details = refused.value.details()
    assert details["reason"] == "items_changed"
    assert details["conflicting_items"] == ["content:question:Q1"]
    assert details["conflicting_fields"] == ["content:question:Q1#text"]


def test_an_item_the_person_removed_conflicts_with_any_change_to_it(
    session: Any, scoped: Any
) -> None:
    scope, design = _study(session, scoped)
    _edit(session, scope, lambda c: c["sections"][0]["questions"].pop(0))
    proposed = _proposal(lambda c: _question(c, "Q1").update(kategorie=["Ano", "Ne", "Nevím"]))
    with pytest.raises(StaleProposal) as refused:
        _accept(session, scope, design, proposed)
    assert refused.value.conflicting_items == (ItemKey("content", "question", "Q1"),)


def test_a_question_added_to_a_section_the_person_removed_conflicts(
    session: Any, scoped: Any
) -> None:
    """The section's questions are no field of it: the proposal's new question names the section
    it goes into, and a section the person removed cannot take it."""
    scope, design = _study(session, scoped)
    _edit(session, scope, lambda c: c["sections"].pop(1))
    proposed = _proposal(lambda c: c["sections"][1]["questions"].append(_q("Q9", "Kolik?")))
    with pytest.raises(StaleProposal) as refused:
        _accept(session, scope, design, proposed)
    assert refused.value.conflicting_items == (ItemKey("content", "question", "Q9"),)


def test_a_proposals_move_between_sections_is_applied(session: Any, scoped: Any) -> None:
    """Before WCE5 the move touched sections A and B only, and the merge moved Q2 in neither."""
    scope, design = _study(session, scoped)
    _edit(session, scope, lambda c: c.update(goal="Test, edited"))

    def move(c: dict[str, Any]) -> None:
        c["sections"][1]["questions"].append(c["sections"][0]["questions"].pop(1))

    accepted = _accept(session, scope, design, _proposal(move))
    assert _questions(accepted.merged.content) == {"A": ["Q1"], "B": ["Q3", "Q2"]}
    assert accepted.merged.content["goal"] == "Test, edited"


def test_a_question_the_person_moved_stays_where_they_put_it(session: Any, scoped: Any) -> None:
    """The proposal rewords Q2 where it was; the person moved it. The move is the person's field
    (``section``), the wording the proposal's: both are kept."""
    scope, design = _study(session, scoped)

    def move(c: dict[str, Any]) -> None:
        c["sections"][1]["questions"].insert(0, c["sections"][0]["questions"].pop(1))

    _edit(session, scope, move)
    proposed = _proposal(lambda c: _question(c, "Q2").update(text="Kde nakupujete?"))
    accepted = _accept(session, scope, design, proposed)
    assert _questions(accepted.merged.content) == {"A": ["Q1"], "B": ["Q2", "Q3"]}
    assert _question(accepted.merged.content, "Q2")["text"] == "Kde nakupujete?"


def test_two_people_adding_questions_to_one_section_both_land(session: Any, scoped: Any) -> None:
    """The proposal's new question goes after its predecessor in the proposal (Q2), as every
    merge places what only the proposal has."""
    scope, design = _study(session, scoped)
    _edit(session, scope, lambda c: c["sections"][0]["questions"].append(_q("Q8", "Kdy?")))
    proposed = _proposal(lambda c: c["sections"][0]["questions"].append(_q("Q9", "Kolik?")))
    accepted = _accept(session, scope, design, proposed)
    assert _questions(accepted.merged.content)["A"] == ["Q1", "Q2", "Q9", "Q8"]


@pytest.mark.parametrize(
    "mine",
    [
        pytest.param(lambda c: c["sections"][1]["questions"].append(_q("Q8", "Kdy?")), id="added"),
        pytest.param(
            lambda c: c["sections"][1]["questions"].append(c["sections"][0]["questions"].pop(0)),
            id="moved",
        ),
    ],
)
def test_a_question_the_person_put_into_a_section_the_proposal_removes_conflicts(
    session: Any, scoped: Any, mine: Any
) -> None:
    """The mirror of a question added to a removed section: the person's question would go with
    the section, unseen (review of WCE5)."""
    scope, design = _study(session, scoped)
    _edit(session, scope, mine)
    with pytest.raises(StaleProposal) as refused:
        _accept(session, scope, design, _proposal(lambda c: c["sections"].pop(1)))
    assert ItemKey("content", "section", "B") in refused.value.conflicting_items


def test_a_section_whose_questions_are_not_keyed_is_merged_whole(session: Any, scoped: Any) -> None:
    """``questions`` that are not question objects are one value of their section, as
    ``design_items`` reads them: a proposal changing them is applied, never dropped."""
    scope, design = _study(session, scoped)
    _edit(session, scope, lambda c: c.update(goal="Test, edited"))
    proposed = _proposal(lambda c: c["sections"][1].update(questions=["Proč?", "Kdy?"]))
    accepted = _accept(session, scope, design, proposed)
    assert accepted.merged.content["sections"][1]["questions"] == ["Proč?", "Kdy?"]
    assert accepted.merged.content["goal"] == "Test, edited"
