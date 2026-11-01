"""The Lead's accepted edits are the vocabulary's operations, logged as the turn's
(working-copy-edit-ops WCE2d; ADR 0029 decisions 3 and 8).

A person accepts what a Lead turn proposed; ``decide_edits`` applies it through
``application/working_copy.apply_edit_ops``: each edit logged under its own operation, made by the
researcher's Lead for that turn; an edit that writes a locked Sociomap input refused alone; a copy
whose ids the web keeps settled, so a reworded research question keeps its links (F-WCE1-1).
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from sqlalchemy import select

from aia_core.application.research_lead import ResearchLead
from aia_core.domain.edit_log import ActorKind, OpSource, WriteBy
from aia_core.domain.item_ids import SIDECAR_KEYS, with_item_ids
from aia_core.domain.workflow_templates import RESEARCH_LEAD_TURN
from aia_core.infrastructure.researcher_lead_repository import ResearcherLeadRepository
from aia_core.infrastructure.study_workspace_repository import (
    StudyWorkspaceRepository,
    WorkspaceConflict,
)
from aia_core.infrastructure.tables import ApprovalDecisionRow
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_core.infrastructure.workspace_edit_repository import WorkspaceEditRepository

WHY = "Zadání to potřebuje."
RQ = "Kdo kupuje kávu?"
CONTENT: dict[str, Any] = {
    "title": "Fiktivní koncept",
    "goal": "Otestovat koncept",
    "sections": [
        {
            "id": "s1",
            "type": "questions",
            "questions": [
                {
                    "id": "q1",
                    "text": "Jak často kupujete kávu?",
                    "typ": "skala",
                    "skala": [1, 5],
                    "research_questions": [RQ],
                },
                {"id": "q2", "text": "Znáte značku?", "typ": "vyber", "kategorie": ["Ano", "Ne"]},
            ],
        }
    ],
    "research_plan": {"objectives": ["Ověřit zájem"], "research_questions": [RQ]},
}


def _ready(scoped: Any, session: Any, content: dict[str, Any], edits: list[dict[str, Any]]) -> Any:
    """A hatched researcher, ``content`` saved and one completed Lead turn proposing ``edits``."""
    scope = scoped.scope(user="lead")
    org = scoped.resolver.organization_context(scoped.principal(scoped.users["lead"]))
    ResearcherLeadRepository(session, org).hatch()
    StudyWorkspaceRepository(session).save(
        scope,
        content=content,
        base_revision=None,
        by=WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI),
    )
    lead = ResearchLead(session, scope, enabled=True)
    turns = lead.post(kind="message", stage="brief", text="Uprav to.", focus=None)
    workflows = WorkflowRepository(session, scope)
    work = workflows.claim_next(worker_id="w", kinds={RESEARCH_LEAD_TURN})
    assert work is not None
    workflows.complete_attempt(
        work.attempt_id,
        worker_id="w",
        output={
            "lead_output": {"reply": "Navrhuji změny.", "edits": edits},
            "dropped": [],
            "self_update_applied": None,
            "data_class": "CLASS_C_INTERNAL",
        },
    )
    return scope, lead, turns[-1]["turn_id"]


def _accept(scope: Any, session: Any, lead: ResearchLead, turn_id: str, n: int) -> dict[str, Any]:
    base = StudyWorkspaceRepository(session).content(scope).revision
    return lead.decide_edits(turn_id, decision="accept", indices=range(n), base_revision=base)


def test_an_accepted_edit_is_logged_as_its_operation_made_by_the_turns_lead(
    scoped: Any, session: Any
) -> None:
    edits = [
        {"op": "set_text", "field": "title", "value": "Nový název", "why": WHY},
        {"op": "list_add", "list": "plan.objectives", "value": "Ověřit cenu", "why": WHY},
    ]
    scope, lead, turn_id = _ready(scoped, session, CONTENT, edits)
    before = StudyWorkspaceRepository(session).content(scope).revision
    decided = _accept(scope, session, lead, turn_id, 2)
    assert [r["status"] for r in decided["results"]] == ["accepted", "accepted"]

    rows = WorkspaceEditRepository(session, scope).rows(after_revision=before)
    assert {r.by for r in rows} == {
        WriteBy(ActorKind.LEAD, scope.actor_id, OpSource.LEAD_TURN, turn_id)
    }
    assert {(r.base_revision, r.result_revision) for r in rows} == {
        (before, decided["workspace_revision"])
    }
    assert len({r.batch_id for r in rows}) == 1
    by_op = {(r.item_key, r.field): r.op for r in rows}
    # Each edit is its own operation, without the Lead's reasoning; the copy holds the rest.
    assert by_op[("content:brief:title", "text")] == {
        "op": "set_text",
        "field": "title",
        "value": "Nový název",
    }
    added = [k for k, op in by_op.items() if op.get("op") == "list_add"]
    assert len(added) == 1 and added[0][0].startswith("content:objective:")
    others = {op["op"] for op in by_op.values()} - {"set_text", "list_add"}
    assert others == {"whole_copy"}  # the stages' state and the analysis the plan edit wrote
    assert all("why" not in op for op in by_op.values())


def test_an_edit_of_a_locked_sociomap_input_is_refused_and_the_rest_apply(
    scoped: Any, session: Any
) -> None:
    declared = copy.deepcopy(CONTENT)
    declared["sections"][0]["questions"][0]["sociomap_rating"] = True
    edits = [
        {"op": "question_edit", "question_id": "q1", "text": "Jak moc často?", "why": WHY},
        {"op": "set_text", "field": "title", "value": "Nový název", "why": WHY},
    ]
    scope, lead, turn_id = _ready(scoped, session, declared, edits)
    decided = _accept(scope, session, lead, turn_id, 2)
    assert decided["results"] == [
        {"index": 0, "status": "refused", "reason": "sociomap_input_locked"},
        {"index": 1, "status": "accepted", "reason": None},
    ]
    working = StudyWorkspaceRepository(session).content(scope).content
    assert working is not None and working["title"] == "Nový název"
    assert working["sections"][0]["questions"][0]["text"] == "Jak často kupujete kávu?"


def test_a_reworded_research_question_keeps_its_links_in_a_copy_that_keeps_ids(
    scoped: Any, session: Any
) -> None:
    """F-WCE1-1: with the web's ids stored, a reword accepted by a click carries its links, as the
    same edit accepted in the browser does."""
    with_ids, _ = with_item_ids(CONTENT)
    edits = [
        {
            "op": "list_replace",
            "list": "plan.research_questions",
            "old": RQ,
            "value": "Kdo pije kávu?",
            "why": WHY,
        }
    ]
    scope, lead, turn_id = _ready(scoped, session, with_ids, edits)
    assert _accept(scope, session, lead, turn_id, 1)["results"][0]["status"] == "accepted"
    working = StudyWorkspaceRepository(session).content(scope).content
    assert working is not None
    assert working["research_plan"]["research_questions"] == ["Kdo pije kávu?"]
    assert working["sections"][0]["questions"][0]["research_questions"] == ["Kdo pije kávu?"]


def test_a_copy_without_ids_is_given_none(scoped: Any, session: Any) -> None:
    """With the web's switch off nothing writes an id: the server writes none either, and the
    link names the old wording, as before."""
    edits = [
        {
            "op": "list_replace",
            "list": "plan.research_questions",
            "old": RQ,
            "value": "Kdo pije kávu?",
            "why": WHY,
        }
    ]
    scope, lead, turn_id = _ready(scoped, session, CONTENT, edits)
    _accept(scope, session, lead, turn_id, 1)
    working = StudyWorkspaceRepository(session).content(scope).content
    assert working is not None
    assert SIDECAR_KEYS.isdisjoint(working["research_plan"])
    assert working["sections"][0]["questions"][0]["research_questions"] == [RQ]


def _declared(content: dict[str, Any]) -> dict[str, Any]:
    """``content`` with q1 marked a Sociomap rating question: a locked input."""
    declared = copy.deepcopy(content)
    declared["sections"][0]["questions"][0]["sociomap_rating"] = True
    return declared


def test_an_automatic_accept_takes_the_unlocked_text_edit_and_refuses_the_locked_one(
    scoped: Any, session: Any
) -> None:
    """The researcher's standing choice takes text edits only, and a text edit of a locked input is
    refused alone, as a click's is (review of #801)."""
    edits = [
        {"op": "question_edit", "question_id": "q1", "text": "Jak moc často?", "why": WHY},
        {"op": "set_text", "field": "title", "value": "Nový název", "why": WHY},
    ]
    scope, lead, turn_id = _ready(scoped, session, _declared(CONTENT), edits)
    org = scoped.resolver.organization_context(scoped.principal(scoped.users["lead"]))
    ResearcherLeadRepository(session, org).set_preferences(auto_accept_text_edits=True)
    base = StudyWorkspaceRepository(session).content(scope).revision
    decided = lead.decide_edits(
        turn_id, decision="accept", indices=[0, 1], base_revision=base, auto=True
    )
    assert decided["results"] == [
        {"index": 0, "status": "refused", "reason": "sociomap_input_locked"},
        {"index": 1, "status": "accepted", "reason": None},
    ]
    working = StudyWorkspaceRepository(session).content(scope).content
    assert working is not None and working["title"] == "Nový název"
    assert working["sections"][0]["questions"][0]["text"] == "Jak často kupujete kávu?"
    assert [r.decision for r in _ledger(session)] == ["accept"]


def test_a_reword_whose_links_follow_onto_a_locked_question_refuses_the_whole_accept(
    scoped: Any, session: Any
) -> None:
    """The edge left to WCE8: with the web's ids kept, the reword itself is unlocked, but its link
    follows onto a locked rating question. The save refuses the accept whole, 409 by the router,
    and nothing is written: no revision, no log row, no ledger row."""
    with_ids, _ = with_item_ids(_declared(CONTENT))
    edits = [
        {
            "op": "list_replace",
            "list": "plan.research_questions",
            "old": RQ,
            "value": "Kdo pije kávu?",
            "why": WHY,
        }
    ]
    scope, lead, turn_id = _ready(scoped, session, with_ids, edits)
    session.commit()  # the turn and the copy exist before the accept is tried
    before = StudyWorkspaceRepository(session).content(scope).revision
    with pytest.raises(WorkspaceConflict) as refused:
        _accept(scope, session, lead, turn_id, 1)
    assert refused.value.reason == "sociomap_input_locked"
    session.rollback()
    assert StudyWorkspaceRepository(session).content(scope).revision == before
    assert WorkspaceEditRepository(session, scope).rows(after_revision=before) == []
    assert _ledger(session) == []


def _ledger(session: Any) -> list[ApprovalDecisionRow]:
    return list(
        session.scalars(
            select(ApprovalDecisionRow).where(ApprovalDecisionRow.subject_type == "lead_edit")
        )
    )


def test_a_persons_batch_with_a_refused_edit_saves_nothing_in_its_own_transaction(
    scoped: Any, session: Any
) -> None:
    """working-copy-edit-ops WCE3a: a person's batch is all or nothing before anything is written,
    not only because the request rolls back: the same session reads the copy and the log as they
    were."""
    from aia_core.application.working_copy import EditsRefused, apply_person_edits
    from aia_core.domain.edit_ops import ListRemove, SetText

    scope = scoped.scope(user="lead")
    workspace = StudyWorkspaceRepository(session)
    workspace.save(
        scope,
        content=CONTENT,
        base_revision=None,
        by=WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI),
    )
    edits = [
        SetText(op="set_text", field="title", value="Jiný", why="person"),
        ListRemove(op="list_remove", list="plan.objectives", old="Žádný", why="person"),
    ]
    with pytest.raises(EditsRefused) as refused:
        apply_person_edits(session, scope, edits, base_revision=1, reason="autosave")
    assert refused.value.refused == {1: "unknown_item"}
    assert workspace.content(scope).revision == 1
    assert workspace.content(scope).content["title"] == CONTENT["title"]
    assert WorkspaceEditRepository(session, scope).rows(after_revision=1) == []

    saved, copy = apply_person_edits(session, scope, edits[:1], base_revision=1, reason="autosave")
    assert (saved.revision, copy.content["title"]) == (2, "Jiný")
    rows = WorkspaceEditRepository(session, scope).rows(after_revision=1)
    assert rows and all(
        r.by == WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI) for r in rows
    )


def test_a_reword_and_an_add_in_one_batch_keep_the_reworded_questions_links(
    scoped: Any, session: Any
) -> None:
    """Ids are settled after each edit, as the browser's store settles them (Codex on #1013):
    settled once over the batch, a list going from one item to two read the reword as a new item
    and left the questionnaire's link on the old wording."""
    from aia_core.application.working_copy import apply_person_edits
    from aia_core.domain.edit_ops import ListAdd, ListReplace

    scope = scoped.scope(user="lead")
    with_ids, _ = with_item_ids(CONTENT)
    StudyWorkspaceRepository(session).save(
        scope,
        content=with_ids,
        base_revision=None,
        by=WriteBy(ActorKind.PERSON, scope.actor_id, OpSource.UI),
    )
    edits = [
        ListReplace(
            op="list_replace",
            list="plan.research_questions",
            old=RQ,
            value="Kdo pije kávu?",
            why="person",
        ),
        ListAdd(op="list_add", list="plan.research_questions", value="Kde?", why="person"),
    ]
    _, copy = apply_person_edits(session, scope, edits, base_revision=1, reason="autosave")
    assert copy.content is not None
    assert copy.content["research_plan"]["research_questions"] == ["Kdo pije kávu?", "Kde?"]
    assert copy.content["sections"][0]["questions"][0]["research_questions"] == ["Kdo pije kávu?"]
