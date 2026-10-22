"""A run computes the methodology in force when it started (ADR 0023 decision 6, plan A4).

The methodologist puts an edited object map in force on the Metodika tab; a run started
afterwards pins it under its own name and computes it through the real worker; a run started
before keeps what it pinned; a retry keeps the original's pin; going back to the preset gives
the code's pins again. With nothing stored, a run pins exactly what it pinned before the store
existed.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from aia_core.application.research import DesignNotReady, ResearchRuns, research_artifacts
from aia_core.domain.evidence.support import AIA_SUPPORT_V1
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.methodology.pins import UNIT_AGGREGATION_PIN, RunMethod, run_methods
from aia_core.domain.research_aggregate import AIA_AGGREGATE_V1
from aia_core.domain.research_design import AIA_READINESS_V1
from aia_core.domain.research_sociomap import default_methods
from aia_core.domain.respondent_behavior import AIA_RESPONSE_V1
from aia_core.domain.sociomap import AIA_SOCIOMAP_V3
from aia_core.domain.sociomap.models_v3 import SociomapArtifactV3, read_artifact
from aia_core.domain.sociomap.specification import AIA_SOCIOMAP_V5
from aia_core.domain.workflow import StepRunStatus, WorkflowRunStatus
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.methodology_repository import MethodologyRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_executors import workbench
from aia_worker.executor import StepExecutor
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy.orm import Session, sessionmaker

DESIGN = {
    "title": "Ranní nápoj",
    "n": 40,
    "sections": [
        {
            "type": "object_battery",
            "title": "Nápoje",
            "object_family": "nápoje",
            "objects": ["Káva", "Čaj", "Kakao", "Džus", "Voda"],
            "object_question": "Jak hodnotíte {object}?",
            "scale": [1, 10],
        }
    ],
}


@pytest.fixture
def worker(
    sessions: sessionmaker[Session],
    database_url: str,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
) -> Worker:
    executors: dict[str, StepExecutor] = workbench.workbench_registry_for(store=store, build=build)
    return Worker(
        session_factory=sessions,
        executors=executors,
        settings=WorkerSettings(
            database_url=database_url,
            executors="aia_executors.registry:build_registry",
            worker_id="methodology-pin-worker",
            lease_seconds=30,
            heartbeat_seconds=0.1,
            poll_seconds=0.05,
            maintenance_seconds=0.2,
        ),
    )


def _edit(world: Any, *, sigma: float, n_min: int, formulas: dict[str, str] | None = None) -> int:
    """Propose and put in force an edited object map, as the Metodika tab does."""
    spec = AIA_SOCIOMAP_V3.model_dump(mode="json")
    spec["terrain"]["sigma"] = sigma
    spec["relation"]["n_min"] = n_min
    with world.sessions() as session:
        repo = MethodologyRepository(session, world.admin_context(session))
        version = repo.propose(
            "sociomap",
            base_preset="aia-sociomap-3",
            spec=spec,
            formulas=formulas or {},
            note="test",
        )
        repo.activate("sociomap", version.version_number, reason="test")
        session.commit()
        return version.version_number


def _reset(world: Any) -> None:
    with world.sessions() as session:
        MethodologyRepository(session, world.admin_context(session)).activate("sociomap", None)
        session.commit()


def _start(world: Any) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=DESIGN, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
        )
        session.commit()
        return started.run_id


def _run(world: Any, run_id: str) -> dict[str, Any]:
    with world.sessions() as session:
        return ResearchRuns(session, world.lead_scope(session)).get(run_id)


def _drain(worker: Worker) -> None:
    while worker.run_once() is not None:
        pass


def _body(world: Any, store: InMemoryArtifactStore, run_id: str) -> dict[str, Any]:
    run = _run(world, run_id)
    assert run["status"] is WorkflowRunStatus.COMPLETED
    step = next(s for s in run["steps"] if s["node_key"] == "sociomap")
    assert step["status"] is StepRunStatus.SUCCEEDED, step
    with world.sessions() as session:
        research = research_artifacts(session, world.lead_scope(session), store)
        body: dict[str, Any] = research.read_json(step["output"]["artifact_id"])["sociomap"]
    return body


def _maps(world: Any, store: InMemoryArtifactStore, run_id: str) -> dict[str, Any]:
    body = _body(world, store, run_id)
    (battery,) = body["batteries"]
    maps: dict[str, Any] = battery["maps"]
    return maps


def test_with_nothing_stored_a_run_pins_the_codes_methods(world: Any) -> None:
    run = _run(world, _start(world))
    assert run["metadata"]["sociomap_methods"] == [
        m.model_dump(mode="json") for m in default_methods()
    ]
    assert "methodology" not in run["metadata"]


def test_a_run_computes_the_edited_methodology_in_force_when_it_started(
    world: Any, store: InMemoryArtifactStore, worker: Worker
) -> None:
    before = _start(world)
    number = _edit(world, sigma=0.3, n_min=12)
    after = _start(world)
    assert after != before  # the same revision under an edited methodology is another run
    metadata = _run(world, after)["metadata"]
    # The edited version alone: no reference map is pinned beside it.
    assert [m["method_id"] for m in metadata["sociomap_methods"]] == [f"aia-sociomap-3+e{number}"]
    assert metadata["methodology"]["name"] == f"aia-sociomap-3+e{number}"
    assert _start(world) == after  # and that run is idempotent
    _drain(worker)
    edited = read_artifact(_maps(world, store, after)[f"aia-sociomap-3+e{number}"])
    assert isinstance(edited, SociomapArtifactV3)
    assert edited.spec.methodology_version == f"aia-sociomap-3+e{number}"
    assert (edited.spec.terrain is not None and edited.spec.terrain.sigma) == 0.3
    assert edited.spec.relation.n_min == 12
    original = read_artifact(_maps(world, store, before)["aia-sociomap-5"])
    assert isinstance(original, SociomapArtifactV3)
    # The earlier run kept its pin: the code's aia-sociomap-5, exactly.
    assert original.spec.fingerprint() == AIA_SOCIOMAP_V5.fingerprint()


def test_a_retry_keeps_the_methodology_its_run_pinned(world: Any) -> None:
    number = _edit(world, sigma=0.3, n_min=12)
    run_id = _start(world)
    _reset(world)
    with world.sessions() as session:
        runs = ResearchRuns(session, world.lead_scope(session))
        runs.cancel(run_id)
        retried = runs.retry(run_id, fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE)
        session.commit()
    pinned = _run(world, retried.run_id)["metadata"]["sociomap_methods"]
    assert [m["method_id"] for m in pinned] == [f"aia-sociomap-3+e{number}"]


def test_back_to_the_preset_a_new_run_pins_the_codes_methods_again(world: Any) -> None:
    _edit(world, sigma=0.3, n_min=12)
    _reset(world)
    run = _run(world, _start(world))
    assert run["metadata"]["sociomap_methods"] == [
        m.model_dump(mode="json") for m in default_methods()
    ]


def test_a_run_computes_the_formula_its_methodology_replaced(
    world: Any, store: InMemoryArtifactStore, worker: Worker
) -> None:
    """A replaced kernel is the kernel the map's terrain is drawn with (plan S4c): the same
    parameters with the built-in kernel draw another terrain, and the body records what the
    version replaced beside the map it shaped."""
    kernel = "h * exp(-d2 / (sigma * sigma))"  # half the built-in's spread
    plain = _edit(world, sigma=0.25, n_min=30)
    run_plain = _start(world)
    edited = _edit(world, sigma=0.25, n_min=30, formulas={"f12.kernel": kernel})
    run_edited = _start(world)
    assert run_edited != run_plain
    (pinned,) = _run(world, run_edited)["metadata"]["sociomap_methods"]
    assert pinned["formulas"] == {"f12.kernel": kernel}
    _drain(worker)

    body = _body(world, store, run_edited)
    assert body["methods"][0] == {
        "method_id": f"aia-sociomap-3+e{edited}",
        "spec_fingerprint": pinned["spec_fingerprint"],
        "formulas": {"f12.kernel": kernel},
    }
    with_kernel = read_artifact(_maps(world, store, run_edited)[f"aia-sociomap-3+e{edited}"])
    # The plain version changes nothing of aia-sociomap-3, so it is pinned as the preset itself.
    assert plain >= 1
    without = read_artifact(_maps(world, store, run_plain)["aia-sociomap-3"])
    assert isinstance(with_kernel, SociomapArtifactV3) and isinstance(without, SociomapArtifactV3)
    assert with_kernel.layout == without.layout  # the kernel moves the terrain, nothing else
    assert with_kernel.terrain != without.terrain


# ------------------------------------------- S2c: the readiness warning's pair n_min --


def _support(readiness: Any) -> dict[str, Any]:
    checks = (
        readiness["checks"]
        if isinstance(readiness, dict)
        else readiness.model_dump(mode="json")["checks"]
    )
    (check,) = [c for c in checks if c["id"] == "sociomap_support"]
    return dict(check)


def _readiness(world: Any) -> Any:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=DESIGN, source_stage="run"
        )
        _spec, readiness = ResearchRuns(session, scope).readiness(revision.revision_id)
        session.commit()
        return readiness


def _preflight(world: Any, store: InMemoryArtifactStore, run_id: str) -> dict[str, Any]:
    run = _run(world, run_id)
    step = next(s for s in run["steps"] if s["node_key"] == "preflight")
    assert step["status"] is StepRunStatus.SUCCEEDED, step
    with world.sessions() as session:
        research = research_artifacts(session, world.lead_scope(session), store)
        readiness: dict[str, Any] = research.read_json(step["output"]["artifact_id"])["readiness"]
    return readiness


def test_readiness_warns_with_the_n_min_of_the_methodology_in_force(world: Any) -> None:
    # DESIGN asks 40 respondents: enough for the code's 30, not for an edit's 45.
    assert _support(_readiness(world))["status"] == "PASS"
    _edit(world, sigma=0.25, n_min=45)
    edited = _support(_readiness(world))
    assert edited["status"] == "WARN" and "45" in edited["message"]
    _reset(world)
    assert _support(_readiness(world))["status"] == "PASS"


def test_the_preflight_step_reads_the_runs_pin_not_what_is_in_force_later(
    world: Any, worker: Worker, store: InMemoryArtifactStore
) -> None:
    _edit(world, sigma=0.25, n_min=45)
    under_edit = _start(world)
    _reset(world)
    before_edit = _start(world)
    _edit(world, sigma=0.25, n_min=45)  # in force again while both run
    _drain(worker)
    edited = _support(_preflight(world, store, under_edit))
    assert edited["status"] == "WARN" and "45" in edited["message"]
    assert _support(_preflight(world, store, before_edit))["status"] == "PASS"
    # The tables beside the map read the same n_min as the warning did (S2b).
    # The map's own pairs read the same n_min as the warning did.
    maps = _maps(world, store, under_edit)
    (edited_map,) = maps.values()
    art = read_artifact(edited_map)
    assert isinstance(art, SociomapArtifactV3) and art.relations.n_min == 45


# ------------------------------------------------ G1c: the support rules a run pins --


def _start_with(world: Any, support: Any) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=DESIGN, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            support=support,
        )
        session.commit()
        return started.run_id


def _aggregate(world: Any, store: InMemoryArtifactStore, run_id: str) -> dict[str, Any]:
    run = _run(world, run_id)
    step = next(s for s in run["steps"] if s["node_key"] == "aggregate")
    assert step["status"] is StepRunStatus.SUCCEEDED, step
    with world.sessions() as session:
        research = research_artifacts(session, world.lead_scope(session), store)
        aggregate: dict[str, Any] = research.read_json(step["output"]["artifact_id"])["aggregate"]
    return aggregate


def test_with_nothing_stored_a_run_pins_both_support_rules_as_today(
    world: Any, worker: Worker, store: InMemoryArtifactStore
) -> None:
    run_id = _start(world)
    run = _run(world, run_id)
    assert run["metadata"]["support"] == AIA_SUPPORT_V1.model_dump(mode="json")
    assert "support_methodology" not in run["metadata"]
    _drain(worker)
    cell = next(iter(_aggregate(world, store, run_id)["batteries"].values()))["objects"]
    assert {o["n_guard_threshold"] for o in cell.values()} == {25.0}


def test_a_run_aggregates_under_the_support_rules_it_pinned(
    world: Any, worker: Worker, store: InMemoryArtifactStore
) -> None:
    strict = AIA_SUPPORT_V1.model_copy(
        update={
            "methodology_version": "aia-support-1+e1",
            "results": AIA_SUPPORT_V1.results.model_copy(
                update={"min_layer_donors": 900, "indicative_layer_donors": 950}
            ),
        }
    )
    today, edited = _start(world), _start_with(world, strict)
    assert today != edited  # another rule set is another run of the same revision
    _drain(worker)
    objects = next(iter(_aggregate(world, store, edited)["batteries"].values()))["objects"]
    assert {o["support_status"] for o in objects.values()} == {"SUPPRESS"}
    assert {o["n_guard_threshold"] for o in objects.values()} == {900.0}


def test_a_retry_keeps_the_support_rules_its_run_pinned(world: Any) -> None:
    strict = AIA_SUPPORT_V1.model_copy(
        update={
            "methodology_version": "aia-support-1+e1",
            "results": AIA_SUPPORT_V1.results.model_copy(
                update={"min_layer_donors": 900, "indicative_layer_donors": 950}
            ),
        }
    )
    run_id = _start_with(world, strict)
    with world.sessions() as session:
        runs = ResearchRuns(session, world.lead_scope(session))
        runs.cancel(run_id)
        retried = runs.retry(run_id, fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE)
        session.commit()
    run = _run(world, retried.run_id)
    assert run["metadata"]["support"] == strict.model_dump(mode="json")


# ------------------------------------------------ R1b: the response process a run pins --


def test_with_nothing_stored_a_run_pins_the_units_response_process(world: Any) -> None:
    run = _run(world, _start(world))
    assert run["metadata"]["response"] == AIA_RESPONSE_V1.model_dump(mode="json")
    assert "response_methodology" not in run["metadata"]


def test_a_retry_keeps_the_response_process_its_run_pinned(world: Any) -> None:
    edited = AIA_RESPONSE_V1.model_copy(
        update={"methodology_version": "aia-response-1+e1", "extremity": 0.5}
    )
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=DESIGN, source_stage="run"
        )
        runs = ResearchRuns(session, scope)
        run_id = runs.start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            response=edited,
        ).run_id
        runs.cancel(run_id)
        retried = runs.retry(run_id, fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE)
        session.commit()
    run = _run(world, retried.run_id)
    assert run["metadata"]["response"] == edited.model_dump(mode="json")
    assert _run(world, run_id)["metadata"]["response"] == edited.model_dump(mode="json")


def test_a_run_pins_the_response_version_in_force_and_one_started_before_keeps_the_units(
    world: Any,
) -> None:
    """Stored and put in force as the Metodika tab does (R1c); a run started afterwards pins
    it under its own name and is a new run of the revision; one started before keeps the unit's."""
    before = _start(world)
    spec = AIA_RESPONSE_V1.model_dump(mode="json")
    spec["extremity"] = 0.5
    with world.sessions() as session:
        repo = MethodologyRepository(session, world.admin_context(session))
        version = repo.propose(
            "response", base_preset="aia-response-1", spec=spec, formulas={}, note="test"
        )
        repo.activate("response", version.version_number, reason="test")
        session.commit()
    after = _start(world)
    assert after != before
    pinned = _run(world, after)["metadata"]
    assert pinned["response"]["extremity"] == 0.5
    assert pinned["response"]["methodology_version"] == "aia-response-1+e1"
    assert pinned["response_methodology"]["name"] == "aia-response-1+e1"
    assert _run(world, before)["metadata"]["response"] == AIA_RESPONSE_V1.model_dump(mode="json")


# ------------------------------------------------ G3a: the aggregation a run pins --


def _start_aggregation(world: Any, aggregation: Any) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=DESIGN, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
            aggregation=aggregation,
        )
        session.commit()
        return started.run_id


def _wider_top_box() -> dict[str, Any]:
    spec = AIA_AGGREGATE_V1.model_dump(mode="json")
    spec["methodology_version"] = "aia-aggregate-1+e1"
    spec["top_box"] = 3
    return {"spec": spec, "formulas": {"agg.mean": "max(x)"}}


def test_with_nothing_stored_a_run_pins_the_units_aggregation_and_claims_no_deviation(
    world: Any, worker: Worker, store: InMemoryArtifactStore
) -> None:
    run_id = _start(world)
    run = _run(world, run_id)
    assert run["metadata"]["aggregation"] == UNIT_AGGREGATION_PIN
    assert "aggregation_methodology" not in run["metadata"]
    _drain(worker)
    assert "deviation" not in _aggregate(world, store, run_id)


def test_a_run_aggregates_under_the_aggregation_it_pinned_and_says_so(
    world: Any, worker: Worker, store: InMemoryArtifactStore
) -> None:
    today, edited = _start(world), _start_aggregation(world, _wider_top_box())
    assert today != edited  # another aggregation is another run of the same revision
    _drain(worker)
    unit, ours = _aggregate(world, store, today), _aggregate(world, store, edited)
    assert ours["deviation"]["changed"] == [{"path": "top_box", "unit": 2, "used": 3}]
    assert ours["deviation"]["replaced_formulas"] == ["agg.mean"]
    unit_objects = next(iter(unit["batteries"].values()))["objects"]
    our_objects = next(iter(ours["batteries"].values()))["objects"]
    for oid, cell in our_objects.items():
        if cell["prumer"] is not None:
            # max(x) as the mean: each object's mean is its largest answer
            assert cell["prumer"] == round(max(float(k) for k in cell["rozlozeni"]), 2), oid
            assert cell["prumer"] >= unit_objects[oid]["prumer"], oid


def test_a_retry_keeps_the_aggregation_its_run_pinned(world: Any) -> None:
    pin = _wider_top_box()
    run_id = _start_aggregation(world, pin)
    with world.sessions() as session:
        runs = ResearchRuns(session, world.lead_scope(session))
        runs.cancel(run_id)
        retried = runs.retry(run_id, fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE)
        session.commit()
    assert _run(world, retried.run_id)["metadata"]["aggregation"] == pin


def test_an_aggregation_pin_that_cannot_be_computed_is_refused_before_any_run(
    world: Any,
) -> None:
    bad = _wider_top_box()
    bad["formulas"] = {"agg.mean": "open('x')"}
    with pytest.raises(ValueError):
        _start_aggregation(world, bad)
    unknown = _wider_top_box()
    unknown["formulas"] = {"f6.distance": "1"}
    with pytest.raises(ValueError, match=r"no formula f6\.distance"):
        _start_aggregation(world, unknown)


# ------------------------------------------- G3b: an aggregation version put in force --


def test_a_run_pins_the_aggregation_version_in_force_and_its_aggregate_says_so(
    world: Any, worker: Worker, store: InMemoryArtifactStore
) -> None:
    """Stored and put in force as the Metodika tab does; a run started afterwards pins it,
    computes under it and labels its aggregate; a run started before keeps the unit's."""
    before = _start(world)
    spec = AIA_AGGREGATE_V1.model_dump(mode="json")
    spec["top_box"] = 1
    with world.sessions() as session:
        repo = MethodologyRepository(session, world.admin_context(session))
        version = repo.propose(
            "aggregation",
            base_preset="aia-aggregate-1",
            spec=spec,
            formulas={"agg.kish": "count(w)"},
            note="test",
        )
        repo.activate("aggregation", version.version_number, reason="test")
        session.commit()
    after = _start(world)
    assert after != before  # a stored version is new identity
    run = _run(world, after)
    assert run["metadata"]["aggregation"]["spec"]["methodology_version"] == "aia-aggregate-1+e1"
    assert run["metadata"]["aggregation"]["formulas"] == {"agg.kish": "count(w)"}
    assert run["metadata"]["aggregation_methodology"]["name"] == "aia-aggregate-1+e1"
    _drain(worker)
    edited, unit = _aggregate(world, store, after), _aggregate(world, store, before)
    assert edited["deviation"]["changed"] == [{"path": "top_box", "unit": 2, "used": 1}]
    assert edited["deviation"]["replaced_formulas"] == ["agg.kish"]
    assert "deviation" not in unit
    with world.sessions() as session:
        MethodologyRepository(session, world.admin_context(session)).activate("aggregation", None)
        session.commit()


# ------------------------------------------------ Z1a: a retry keeps where its pins came from --


def test_a_retry_keeps_the_stored_versions_its_pins_came_from(world: Any) -> None:
    """A retry pins its original's methods explicitly; it must still say they were stored
    versions, not the code's (plan methodology-tab Z1a)."""
    _edit(world, sigma=0.25, n_min=45)
    support = AIA_SUPPORT_V1.model_dump(mode="json")
    support["results"]["min_layer_donors"] = 20
    aggregation = AIA_AGGREGATE_V1.model_dump(mode="json")
    aggregation["top_box"] = 1
    response = AIA_RESPONSE_V1.model_dump(mode="json")
    response["extremity"] = 0.5
    with world.sessions() as session:
        repo = MethodologyRepository(session, world.admin_context(session))
        for module, base, spec in (
            ("support", "aia-support-1", support),
            ("aggregation", "aia-aggregate-1", aggregation),
            ("response", "aia-response-1", response),
        ):
            version = repo.propose(module, base_preset=base, spec=spec, formulas={}, note="test")
            repo.activate(module, version.version_number, reason="test")
        session.commit()
    _limits(world, sample_size__min=10)
    run_id = _start(world)
    with world.sessions() as session:
        runs = ResearchRuns(session, world.lead_scope(session))
        runs.cancel(run_id)
        retried = runs.retry(run_id, fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE)
        session.commit()
    original, retry = _run(world, run_id)["metadata"], _run(world, retried.run_id)["metadata"]
    for key in (
        "methodology",
        "support_methodology",
        "aggregation_methodology",
        "response_methodology",
        "readiness_methodology",
    ):
        assert retry[key] == original[key], key
    assert run_methods(retry) == {
        "sociomap": RunMethod("aia-sociomap-3+e1", stored=True),
        "support": RunMethod("aia-support-1+e1", stored=True),
        "aggregation": RunMethod("aia-aggregate-1+e1", stored=True),
        "response": RunMethod("aia-response-1+e1", stored=True),
        "readiness": RunMethod("aia-readiness-1+e1", stored=True),
    }


# ------------------------------------------- V1a: the readiness limits a run pins --


def _limits(world: Any, **change: Any) -> None:
    """Propose and put in force readiness limits, as the Metodika tab does."""
    spec = AIA_READINESS_V1.model_dump(mode="json")
    for path, value in change.items():
        part, field = path.split("__")
        spec[part][field] = value
    with world.sessions() as session:
        repo = MethodologyRepository(session, world.admin_context(session))
        version = repo.propose(
            "readiness", base_preset="aia-readiness-1", spec=spec, formulas={}, note="test"
        )
        repo.activate("readiness", version.version_number, reason="test")
        session.commit()


def _reset_limits(world: Any) -> None:
    with world.sessions() as session:
        MethodologyRepository(session, world.admin_context(session)).activate("readiness", None)
        session.commit()


def _start_design(world: Any, design: dict[str, Any]) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        revision, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content=design, source_stage="run"
        )
        started = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
        )
        session.commit()
        return started.run_id


def _check(readiness: Any, prefix: str) -> dict[str, Any] | None:
    checks = (
        readiness["checks"]
        if isinstance(readiness, dict)
        else readiness.model_dump(mode="json")["checks"]
    )
    return next((dict(c) for c in checks if str(c["id"]).startswith(prefix)), None)


def test_with_nothing_stored_a_run_pins_the_units_readiness_limits(world: Any) -> None:
    meta = _run(world, _start(world))["metadata"]
    assert meta["readiness"] == AIA_READINESS_V1.model_dump(mode="json")
    assert "readiness_methodology" not in meta


def test_a_start_is_checked_under_the_readiness_limits_in_force(world: Any) -> None:
    # DESIGN asks 40 respondents: inside the code's 20-10 000, below an edit's 50.
    assert (_check(_readiness(world), "sample_size") or {}).get("status") == "PASS"
    _limits(world, sample_size__min=50)
    refused = _check(_readiness(world), "sample_size")
    assert refused is not None and refused["status"] == "FAIL" and "50" in refused["message"]
    with pytest.raises(DesignNotReady):
        _start(world)
    _reset_limits(world)
    assert (_check(_readiness(world), "sample_size") or {}).get("status") == "PASS"


def test_the_compile_and_preflight_steps_read_the_runs_pin_not_what_is_in_force_later(
    world: Any, worker: Worker, store: InMemoryArtifactStore
) -> None:
    # 41 items: more than the code lets a set have; 5 items: above an edit's recommended 4.
    wide = copy.deepcopy(DESIGN)
    wide["sections"][0]["objects"] = [f"Nápoj {i}" for i in range(41)]
    _limits(world, tracked_set__max=50, tracked_set__recommended_max=4)
    wide_run = _start_design(world, wide)
    warned_run = _start(world)
    _reset_limits(world)  # the preset in force again while both run
    _drain(worker)
    compiled = next(s for s in _run(world, wide_run)["steps"] if s["node_key"] == "compile")
    assert compiled["status"] is StepRunStatus.SUCCEEDED, compiled
    warned = _check(_preflight(world, store, warned_run), "battery_size:")
    assert warned is not None and warned["status"] == "WARN" and "4" in warned["message"]
    meta = _run(world, warned_run)["metadata"]
    assert meta["readiness_methodology"]["name"] == "aia-readiness-1+e1"
    assert meta["readiness"]["tracked_set"]["recommended_max"] == 4


def test_a_retry_keeps_the_readiness_limits_its_run_pinned(world: Any) -> None:
    _limits(world, sample_size__min=10)
    run_id = _start(world)
    _reset_limits(world)
    with world.sessions() as session:
        runs = ResearchRuns(session, world.lead_scope(session))
        runs.cancel(run_id)
        retried = runs.retry(run_id, fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE)
        session.commit()
    original, retry = _run(world, run_id)["metadata"], _run(world, retried.run_id)["metadata"]
    assert retry["readiness"] == original["readiness"]
    assert retry["readiness"]["sample_size"]["min"] == 10
    assert retry["readiness_methodology"] == original["readiness_methodology"]


def test_a_start_that_finds_its_run_returns_it_under_stricter_limits(world: Any) -> None:
    """The limits are not part of a run's key: a second start of a revision whose run began
    under looser limits returns that run, never refusing it under the limits now in force."""
    small = {**DESIGN, "n": 15}
    _limits(world, sample_size__min=10)
    first = _start_design(world, small)
    _reset_limits(world)  # 15 is below the preset's 20 again
    with world.sessions() as session:
        scope = world.lead_scope(session)
        designs = StudyDesignRepository(session, scope)
        revision, _ = designs.submit_as_working_copy(content=small, source_stage="run")
        again = ResearchRuns(session, scope).start(
            design_revision_id=revision.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
        )
        session.commit()
    assert again.run_id == first
    assert _run(world, first)["metadata"]["readiness"]["sample_size"]["min"] == 10
    # A revision with no run is still held to the limits in force.
    with world.sessions() as session, pytest.raises(DesignNotReady):
        scope = world.lead_scope(session)
        other, _ = StudyDesignRepository(session, scope).submit_as_working_copy(
            content={**small, "title": "Jiný nápoj"}, source_stage="run"
        )
        ResearchRuns(session, scope).start(
            design_revision_id=other.revision_id,
            fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE,
        )


# ------------------------------------------------- V1b: the places a run stores its numbers


def test_a_run_stores_its_numbers_at_the_places_its_aggregation_pinned(
    world: Any, worker: Worker, store: InMemoryArtifactStore
) -> None:
    spec = AIA_AGGREGATE_V1.model_dump(mode="json")
    spec["methodology_version"] = "aia-aggregate-1+e1"
    spec["rounding"] = {"share_decimals": 0, "mean_decimals": 3}
    today, edited = _start(world), _start_aggregation(world, {"spec": spec, "formulas": {}})
    _drain(worker)
    unit, ours = _aggregate(world, store, today), _aggregate(world, store, edited)
    assert "rounding" not in unit
    assert ours["rounding"] == {"share_decimals": 0, "mean_decimals": 3}
    assert {c["path"] for c in ours["deviation"]["changed"]} == {
        "rounding.mean_decimals",
        "rounding.share_decimals",
    }
    for oid, cell in next(iter(ours["batteries"].values()))["objects"].items():
        if cell["prumer"] is not None:
            assert cell["prumer"] == round(cell["prumer"], 3), oid
            assert cell["top2box_pct"] == round(cell["top2box_pct"]), oid


def _put_in_force(world: Any, spec: dict[str, Any], base: str = "aia-sociomap-5") -> str:
    """Propose and put in force a version of ``base`` with ``spec``; its name."""
    with world.sessions() as session:
        repo = MethodologyRepository(session, world.admin_context(session))
        version = repo.propose("sociomap", base_preset=base, spec=spec, formulas={}, note="test")
        repo.activate("sociomap", version.version_number, reason="test")
        session.commit()
        return version.name


def test_the_preset_put_in_force_unchanged_is_pinned_under_its_own_name(
    world: Any, store: InMemoryArtifactStore, worker: Worker
) -> None:
    # Nothing changed: the run pins aia-sociomap-5 itself, so the register's entry holds.
    name = _put_in_force(world, AIA_SOCIOMAP_V5.model_dump(mode="json"))
    run_id = _start(world)
    metadata = _run(world, run_id)["metadata"]
    assert metadata["sociomap_methods"] == [m.model_dump(mode="json") for m in default_methods()]
    assert metadata["methodology"]["name"] == name  # the version in force, as recorded
    _drain(worker)
    assert _body(world, store, run_id)["methodology_status"] == "CLIENT_FACING"


def test_a_run_under_an_unchanged_retired_preset_in_force_is_retried_not_refused(
    world: Any,
) -> None:
    # An unchanged aia-sociomap-3 in force pins the preset's own name; the organization chose it,
    # so its run is retried as it pinned it, not refused as the code's old default.
    _put_in_force(world, AIA_SOCIOMAP_V3.model_dump(mode="json"), base="aia-sociomap-3")
    run_id = _start(world)
    assert [m["method_id"] for m in _run(world, run_id)["metadata"]["sociomap_methods"]] == [
        "aia-sociomap-3"
    ]
    with world.sessions() as session:
        runs = ResearchRuns(session, world.lead_scope(session))
        runs.cancel(run_id)
        retried = runs.retry(run_id, fieldwork_source=FieldworkSource.SYNTHETIC_FIXTURE)
        session.commit()
    assert retried.run_id != run_id
    pinned = _run(world, retried.run_id)["metadata"]["sociomap_methods"]
    assert [m["method_id"] for m in pinned] == ["aia-sociomap-3"]


def test_a_changed_version_in_force_is_pinned_under_its_own_name_and_stays_internal(
    world: Any, store: InMemoryArtifactStore, worker: Worker
) -> None:
    spec = AIA_SOCIOMAP_V5.model_dump(mode="json")
    spec["relation"]["n_min"] = 12
    name = _put_in_force(world, spec)
    assert name.startswith("aia-sociomap-5+e")
    run_id = _start(world)
    pinned = _run(world, run_id)["metadata"]["sociomap_methods"]
    assert [m["method_id"] for m in pinned] == [name]
    _drain(worker)
    assert _body(world, store, run_id)["methodology_status"] == "INTERNAL_ONLY"
