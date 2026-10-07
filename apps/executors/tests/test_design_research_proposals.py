"""Design Research proposes; a person accepts into a new Design Revision (chunk 29, ADR 0021).

Over the recorded journey's first pass -- a governed ``DESIGN_RESEARCH`` run that the worker
took through all six steps to a sealed bundle on a fictional client -- what is pinned:

* the proposal is the run's own bundle, by code: one item per subject, its accepted findings
  verbatim, a gap where there are none, the same ids every time it is read;
* a person's accept writes one new revision whose only change is the ``design_research`` key
  holding the items they took, and one approval-ledger row naming producer and acceptor;
* nothing lands on a design the run was not researched from, a second accept from the same
  run is stale, and the worker's scope, another Study and an empty or unknown selection are
  refused -- none of them writing a revision or a ledger row.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest
from aia_core.application.deep_research import DeepResearchRunNotFound, DeepResearchRuns
from aia_core.application.design_research import DesignResearchProposals
from aia_core.domain.deep_research.design_proposals import (
    DESIGN_PROPOSAL_CONTRACT,
    DESIGN_RESEARCH_KEY,
    ItemKind,
    selection_id,
)
from aia_core.domain.deep_research.quarantine import design_input
from aia_core.domain.design import DesignRejected
from aia_core.domain.scope import WORKER_PERMISSIONS, ScopeDenied
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.tables import ApprovalDecisionRow
from sqlalchemy import select
from test_deep_research_journey import (  # type: ignore[import-not-found]
    DESIGN,
    Journey,
    ResearchWorld,
    pass_one,  # noqa: F401  (the fixture)
    read,
    research,  # noqa: F401  (the fixture)
)


def _ledger(world: ResearchWorld) -> list[ApprovalDecisionRow]:
    with world.sessions() as session:
        return list(
            session.scalars(
                select(ApprovalDecisionRow).where(
                    ApprovalDecisionRow.subject_type == "design_research"
                )
            )
        )


def _latest(world: ResearchWorld) -> str:
    with world.sessions() as session:
        latest = StudyDesignRepository(session, world.lead_scope(session)).latest()
        assert latest is not None
        return latest.revision_id


def _baseline(journey: Journey) -> str:
    with journey.world.sessions() as session:
        run = DeepResearchRuns(session, journey.world.lead_scope(session)).get(journey.run_id)
    return str(run["metadata"]["lineage"]["design_revision_id"])


def _proposal(journey: Journey, store: InMemoryArtifactStore) -> Any:
    with journey.world.sessions() as session:
        return DesignResearchProposals(session, journey.world.lead_scope(session)).proposal(
            journey.run_id, store=store
        )


def _accept(
    journey: Journey,
    store: InMemoryArtifactStore,
    item_ids: list[str],
    *,
    expected: str | None = None,
    scope: Any = None,
) -> tuple[Any, bool, dict[str, Any]]:
    world = journey.world
    with world.sessions() as session:
        person = world.lead_scope(session)
        result = DesignResearchProposals(session, scope(person) if scope else person).accept(
            journey.run_id,
            item_ids=item_ids,
            expected_revision_id=expected or _baseline(journey),
            store=store,
        )
        session.commit()
        return result


def test_the_proposal_is_the_runs_own_bundle_by_subject_with_its_gaps(
    pass_one: Journey,  # noqa: F811
    store: InMemoryArtifactStore,
) -> None:
    _, bundle = read(pass_one.world, pass_one.run_id, store)
    proposal = _proposal(pass_one, store)
    assert proposal.admissible and proposal.fictional_client
    assert proposal.evidence_bundle_seal == bundle.sha256
    assert proposal.design_revision_id == _baseline(pass_one)
    assert [i.subject_key for i in proposal.items] == [s.key for s in bundle.subjects]
    view = design_input(bundle)
    for item in proposal.items:
        assert item.findings == view.findings[item.subject_key]
        assert item.kind is (ItemKind.EVIDENCE if item.findings else ItemKind.GAP)
    assert {i.kind for i in proposal.items} == {ItemKind.EVIDENCE, ItemKind.GAP}
    # Read again: the same ids.
    assert [i.item_id for i in _proposal(pass_one, store).items] == [
        i.item_id for i in proposal.items
    ]


def test_an_accept_writes_one_revision_changing_only_the_design_research_key(
    pass_one: Journey,  # noqa: F811
    store: InMemoryArtifactStore,
) -> None:
    world = pass_one.world
    baseline = _baseline(pass_one)
    proposal = _proposal(pass_one, store)
    taken = [next(i.item_id for i in proposal.items if i.kind is ItemKind.EVIDENCE)]

    revision, created, content = _accept(pass_one, store, taken)

    assert created and revision.revision_id != baseline and revision.source_stage == "plan"
    assert _latest(world) == revision.revision_id
    with world.sessions() as session:
        designs = StudyDesignRepository(session, world.lead_scope(session))
        stored = designs.content(revision.revision_id)
        before = designs.content(baseline)
    assert stored == content
    assert {k: v for k, v in stored.items() if k != DESIGN_RESEARCH_KEY} == before == DESIGN
    block = stored[DESIGN_RESEARCH_KEY]
    assert block["contract_version"] == DESIGN_PROPOSAL_CONTRACT
    assert list(block["items"]) == taken
    entry = block["items"][taken[0]]
    assert entry["role"] == "EXTERNAL_CONTEXT"
    assert entry["provenance"]["run_id"] == pass_one.run_id
    assert entry["provenance"]["fictional_client"] is True

    (row,) = _ledger(world)
    assert row.subject_id == selection_id(pass_one.run_id, taken)
    assert row.run_id == pass_one.run_id and row.decision == "accept"
    assert row.gate_type == "design_research" and row.artifact_type == "deep_research_bundle"
    assert json.loads(row.comment) == {
        "revision_id": revision.revision_id,
        "item_ids": taken,
        "artifact_id": proposal.evidence_bundle_artifact_id,
    }
    assert row.producer_user_id == world.lead_id == row.approver_user_id
    assert row.self_approved is True


def test_a_second_accept_from_the_same_run_is_stale_and_writes_nothing(
    pass_one: Journey,  # noqa: F811
    store: InMemoryArtifactStore,
) -> None:
    items = [i.item_id for i in _proposal(pass_one, store).items]
    first, _, _ = _accept(pass_one, store, items[:1])
    for expected in (None, first.revision_id):
        with pytest.raises(DesignRejected) as refused:
            _accept(pass_one, store, items[1:], expected=expected)
        assert refused.value.reason == "stale_proposal"
    assert _latest(pass_one.world) == first.revision_id
    assert len(_ledger(pass_one.world)) == 1


def test_a_design_edited_after_the_run_is_never_written_over(
    pass_one: Journey,  # noqa: F811
    store: InMemoryArtifactStore,
) -> None:
    world = pass_one.world
    with world.sessions() as session:
        edited, _ = StudyDesignRepository(session, world.lead_scope(session)).submit(
            content={**DESIGN, "goal": "Jiný cíl"}, source_stage="brief"
        )
        session.commit()
    items = [i.item_id for i in _proposal(pass_one, store).items]
    with pytest.raises(DesignRejected) as refused:
        _accept(pass_one, store, items)
    assert refused.value.reason == "stale_proposal"
    assert _latest(world) == edited.revision_id and _ledger(world) == []


@pytest.mark.parametrize(
    ("ids", "reason"), [([], "empty_selection"), (["DRP-" + "0" * 24], "unknown_item")]
)
def test_an_empty_or_unknown_selection_writes_nothing(
    pass_one: Journey,  # noqa: F811
    store: InMemoryArtifactStore,
    ids: list[str],
    reason: str,
) -> None:
    baseline = _baseline(pass_one)
    with pytest.raises(DesignRejected) as refused:
        _accept(pass_one, store, ids)
    assert refused.value.reason == reason
    assert _latest(pass_one.world) == baseline and _ledger(pass_one.world) == []


def test_the_workers_scope_cannot_accept(
    pass_one: Journey,  # noqa: F811
    store: InMemoryArtifactStore,
) -> None:
    """ADR 0019 decision 6: the worker holds ``EDIT_STUDY`` and no gate authority."""
    baseline = _baseline(pass_one)
    items = [i.item_id for i in _proposal(pass_one, store).items]
    with pytest.raises(ScopeDenied) as refused:
        _accept(
            pass_one,
            store,
            items,
            scope=lambda person: dataclasses.replace(person, permissions=WORKER_PERMISSIONS),
        )
    assert refused.value.reason == "insufficient_role"
    assert _latest(pass_one.world) == baseline and _ledger(pass_one.world) == []


def test_another_studys_scope_finds_no_such_run(
    pass_one: Journey,  # noqa: F811
    store: InMemoryArtifactStore,
) -> None:
    world = pass_one.world
    with world.sessions() as session:
        other = DesignResearchProposals(session, world.other_scope(session))
        with pytest.raises(DeepResearchRunNotFound):
            other.proposal(pass_one.run_id, store=store)
        with pytest.raises(DeepResearchRunNotFound):
            other.accept(pass_one.run_id, item_ids=["x"], expected_revision_id="REV-1", store=store)
    assert _ledger(world) == []


def test_a_run_that_has_not_completed_proposes_nothing(
    research: ResearchWorld,  # noqa: F811
    store: InMemoryArtifactStore,
) -> None:
    from test_deep_research_journey import start  # type: ignore[import-not-found]

    run_id = start(research)  # queued; no worker has run it
    with research.sessions() as session, pytest.raises(DesignRejected) as refused:
        DesignResearchProposals(session, research.lead_scope(session)).proposal(run_id, store=store)
    assert refused.value.reason == "proposal_not_ready"
