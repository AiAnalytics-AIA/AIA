"""The Sociomap input integration, end to end on a fictional study (plan § 8.2, S6 / I5).

One recorded, fictional study through the real application and executor path -- compile,
readiness, fieldwork, aggregate, Sociomap under the real worker loop -- with everything
§ 8.1 I5 names that exists in AIA today: two object families on different scales, a declared
standalone rating item, a context object, selected dimensions, an audience filter, missing
answers and a straight-liner. Then the stored artifacts are read back through the Study, the
map is recomputed from the stored inputs and is identical, and three new revisions -- a
dimension, an audience filter, a rating input -- each change the specification and start a
new run while the first run's pins stay as they were.

What this does not prove, and says so: the selection is recorded, not applied (no
materialization or population binding exists; S4); Results and the report draw only the v1
map (chunk 5); the Interpretation Research sidecar (Deep Research chunk 30/31) is not built
on this branch. Fixture success is not a claim of live population availability or client use.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from aia_core.application.research import ResearchRuns, research_artifacts
from aia_core.domain.fieldwork import FieldworkDataset, FieldworkSource
from aia_core.domain.research_design import (
    SELECTION_NOT_APPLIED,
    ResearchSpecification,
)
from aia_core.domain.research_sociomap import SociomapMethod, read_methods, research_sociomaps
from aia_core.domain.sociomap import (
    AIA_SOCIOMAP_V1,
    AIA_SOCIOMAP_V3,
    MapOutcome,
    SociomapArtifactV3,
    read_artifact,
)
from aia_core.domain.synthetic_fieldwork import synthetic_dataset
from aia_core.domain.workflow import WorkflowRunStatus
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.study_workspace_repository import WorkspaceConflict
from aia_executors.registry import registry_for
from aia_executors.research import research_registry
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy.orm import Session, sessionmaker

DESIGN: dict[str, Any] = {
    "title": "Ranní chvíle",
    "n": 120,
    "persona_dimensions": {"approved": ["finance", "media"]},
    "audience": {"source_mode": "population", "strategy": "filters", "filters": {"vek": [18, 29]}},
    "sections": [
        {
            "type": "questions",
            "questions": [
                {
                    "id": "q_kava",
                    "text": "Jak moc máte rádi kávu?",
                    "typ": "skala",
                    "skala": [1, 7],
                    "sociomap_rating": True,
                },
                {
                    "id": "q_vek",
                    "text": "Kolik vám je let (pásmo)?",
                    "typ": "skala",
                    "skala": [1, 6],
                },
            ],
        },
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
            "context_objects": ["Voda"],
        },
        {
            "type": "object_battery",
            "title": "Chvíle",
            "object_family": "chvíle",
            "objects": ["Ráno", "Poledne", "Večer", "Víkend"],
            "object_question": "Jak rádi pijete v {object}?",
            "scale": [1, 5],
        },
    ],
}
STRAIGHT_LINER = 0
MISSING = range(1, 11)


def _planted(spec: ResearchSpecification) -> FieldworkDataset:
    """The fictional synthetic source, with a straight-liner and missing answers planted."""
    dataset = synthetic_dataset(spec, seed=20261008)
    rated = [*spec.battery_questions(), *(q.id for q in spec.rating_questions())]
    drinks = spec.batteries[0]
    respondents = list(dataset.respondents)
    flat = respondents[STRAIGHT_LINER]
    respondents[STRAIGHT_LINER] = flat.model_copy(
        update={"answers": {**flat.answers, **dict.fromkeys(rated, 1)}}
    )
    for k in MISSING:
        r = respondents[k]
        respondents[k] = r.model_copy(
            update={"answers": {**r.answers, drinks.question_id(drinks.objects[0]): None}}
        )
    return dataset.model_copy(update={"respondents": tuple(respondents)})


@pytest.fixture
def worker(
    sessions: sessionmaker[Session],
    database_url: str,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
) -> Worker:
    return Worker(
        session_factory=sessions,
        executors={
            **registry_for(store=store, build=build),
            **research_registry(
                store=store,
                build=build,
                producers={FieldworkSource.SYNTHETIC_FIXTURE: _planted},
            ),
        },
        settings=WorkerSettings(
            database_url=database_url,
            executors="aia_executors.registry:build_registry",
            worker_id="sociomap-acceptance",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


#: The pins these acceptance runs take: the old default (the reference map beside
#: aia-sociomap-3), whose object map every assertion here reads. A stored run of it still
#: computes, and replays, exactly as it did; a new run's aia-sociomap-5 is accepted in
#: ``test_sociomap_frozen_methods.py``.
OLD_DEFAULT = (SociomapMethod.of(AIA_SOCIOMAP_V1), SociomapMethod.of(AIA_SOCIOMAP_V3))


def _scope(world: Any, session: Session, study_id: str | None) -> Any:
    if study_id is None:
        return world.lead_scope(session)
    from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver

    return ScopeResolver(session).study_context(
        AuthenticatedPrincipal(user_id=world.lead_id, organization_id=world.organization_id),
        study_id=study_id,
    )


def _sibling_study(world: Any) -> str:
    """A second ACTIVE study of the same client, with nothing in it."""
    from aia_core.domain.scope import StudyStatus
    from aia_core.infrastructure.scope_repository import ScopeRepository

    with world.sessions() as session:
        repo = ScopeRepository(session)
        study = repo.create_study(
            world.admin_context(session),
            client_id=world.client_id,
            slug="s2",
            name="S2",
            budget_usd=25.0,
        )
        session.flush()
        repo.set_study_status(_scope(world, session, study.study_id), StudyStatus.ACTIVE)
        session.commit()
        return str(study.study_id)


def _start(world: Any, design: dict[str, Any], study_id: str | None = None) -> str:
    with world.sessions() as session:
        scope = _scope(world, session, study_id)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=design, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            sociomap_methods=OLD_DEFAULT,
        )
        session.commit()
        return started.run_id


def _outputs(
    world: Any, store: InMemoryArtifactStore, run_id: str, study_id: str | None = None
) -> dict[str, Any]:
    with world.sessions() as session:
        runs = ResearchRuns(session, _scope(world, session, study_id))
        run = runs.get(run_id)
        research = research_artifacts(session, _scope(world, session, study_id), store)
        steps = {s["node_key"]: s for s in run["steps"]}
        return {
            "run": run,
            "spec": research.read_json(steps["compile"]["output"]["artifact_id"]),
            "dataset": research.read_json(steps["run"]["output"]["artifact_id"])["dataset"],
            "sociomap": research.read_json(steps["sociomap"]["output"]["artifact_id"])["sociomap"],
        }


def test_a_fictional_study_with_every_declared_input_reaches_its_maps(
    world: Any, store: InMemoryArtifactStore, worker: Worker
) -> None:
    run_id = _start(world, DESIGN)
    while worker.run_once() is not None:
        pass
    out = _outputs(world, store, run_id)
    assert out["run"]["status"] is WorkflowRunStatus.COMPLETED

    # The specification carries the selection (recorded, not applied), the rating item and
    # the roles; the undeclared numeric question stays a descriptor.
    spec = ResearchSpecification.model_validate(out["spec"]["specification"])
    assert spec.selection is not None
    assert spec.selection.dimensions == ("finance", "media")
    assert spec.selection.audience_filters == {"vek": [18, 29]}
    assert (spec.selection.applied, spec.selection.reason) == (False, SELECTION_NOT_APPLIED)
    assert [q.id for q in spec.rating_questions()] == ["q_kava"]
    drinks, moments = spec.batteries
    assert drinks.object_roles()["voda"] == "secondary" and drinks.roles_declared

    body = out["sociomap"]
    assert [m["method_id"] for m in body["methods"]] == ["aia-sociomap-1", "aia-sociomap-3"]
    assert [b["battery_id"] for b in body["batteries"]] == [drinks.id, moments.id]
    straight_liner = out["dataset"]["respondents"][STRAIGHT_LINER]["respondent_id"]
    for battery, set_body in zip(spec.batteries, body["batteries"], strict=True):
        art = read_artifact(set_body["maps"]["aia-sociomap-3"])
        assert isinstance(art, SociomapArtifactV3)
        # One rating universe for both families: every set's items and the declared q_kava,
        # each on its own declared scale; q_vek is not in it.
        assert [i.item_id for i in art.items] == [
            *(b.question_id(o) for b in spec.batteries for o in b.objects),
            "q_kava",
        ]
        assert {(i.item_id, i.scale_max) for i in art.items} >= {("q_kava", 7.0)}
        assert list(art.not_placed) == [straight_liner]
        assert art.support.respondents == 120
        # Both families have a map: drinks 0.081 (fair), moments 0.119 (weak) on this panel.
        assert art.outcome == MapOutcome.MAPPED and art.layout is not None
        assert art.support.not_placed == 1
        assert art.roles == battery.object_roles()
        # The map alone holds the relations over each person's scale and the scores (A3d).
        assert not {"relation_rescaled", "object_scores", "connectedness_100"} & set(set_body)
        assert art.scores["primary"] == [
            o.id for o in battery.objects if art.roles[o.id] == "primary"
        ]
        assert set_body["methodology_status"] == "INTERNAL_ONLY"
    drinks_map = read_artifact(body["batteries"][0]["maps"]["aia-sociomap-3"])
    assert isinstance(drinks_map, SociomapArtifactV3)
    # Ten planted missing answers on the first drink: its height rests on fewer people.
    assert drinks_map.heights.support_n[0] == 110
    assert drinks_map.scores["secondary"] == ["voda"]

    # Replay: the stored map is recomputed from the stored inputs and pins, unchanged.
    dataset = FieldworkDataset.model_validate(out["dataset"])
    replay = research_sociomaps(
        spec,
        dataset,
        methods=read_methods(out["run"]["metadata"]["sociomap_methods"]),
        connectedness_interval=False,
    )
    assert replay == body


@pytest.mark.parametrize(
    "change",
    ["dimension", "audience", "rating_input"],
)
def test_each_changed_input_is_a_new_specification_and_a_new_run(
    world: Any, store: InMemoryArtifactStore, worker: Worker, change: str
) -> None:
    first = _start(world, DESIGN)
    while worker.run_once() is not None:
        pass
    before = _outputs(world, store, first)
    edited = copy.deepcopy(DESIGN)
    study_id: str | None = None
    if change == "dimension":
        edited["persona_dimensions"] = {"approved": ["finance", "ekologie"]}
    elif change == "audience":
        edited["audience"]["filters"] = {"vek": [60, 80]}
    else:
        edited["sections"][0]["questions"][0]["skala"] = [1, 5]
        # A declared rating input is locked in its study's working copy (ADR 0029 decision 8):
        # changing it there is refused until a person records an unlock (WCE8). The engine's
        # answer to a changed rating input is read in a sibling study, where nothing is locked.
        with pytest.raises(WorkspaceConflict) as locked:
            _start(world, edited)
        assert locked.value.reason == "sociomap_input_locked"
        study_id = _sibling_study(world)
    second = _start(world, edited, study_id)
    assert second != first
    while worker.run_once() is not None:
        pass
    after = _outputs(world, store, second, study_id)
    spec_before = ResearchSpecification.model_validate(before["spec"]["specification"])
    spec_after = ResearchSpecification.model_validate(after["spec"]["specification"])
    assert spec_before.fingerprint() != spec_after.fingerprint()
    # The first run is untouched: its pins, its specification, its stored map.
    again = _outputs(world, store, first)
    assert (
        again["run"]["metadata"]["sociomap_methods"]
        == before["run"]["metadata"]["sociomap_methods"]
    )
    assert again["sociomap"] == before["sociomap"]
    if change == "rating_input":
        art = read_artifact(after["sociomap"]["batteries"][0]["maps"]["aia-sociomap-3"])
        assert isinstance(art, SociomapArtifactV3)
        assert ("q_kava", 5.0) in {(i.item_id, i.scale_max) for i in art.items}
