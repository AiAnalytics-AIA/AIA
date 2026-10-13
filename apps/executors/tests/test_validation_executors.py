"""A confirmation run's sample and arms under the real worker (panel-grounded-respondents 7e4).

Over the fictional grounded population and a scripted caller in place of the gateway: nothing
leaves the process. The run is started from a stored preregistration, as the service starts it;
the score step has no executor yet (7e4b), so the run stops after its arms.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from aia_core.application.validation import ValidationRuns, validation_artifacts
from aia_core.domain.evidence.validation import respondent_system_fingerprint
from aia_core.domain.holdout.bank import HoldoutItem, ItemBank, Option, SourceDocument
from aia_core.domain.holdout.preregistration import (
    ARMS,
    MODEL_ARMS,
    PREREGISTRATION_VERSION,
    THRESHOLDS,
    Preregistration,
)
from aia_core.domain.holdout.run import ARM_ARTIFACT, SAMPLE_ARTIFACT, arm_node_key
from aia_core.domain.holdout.scoring import SCORING_VERSION
from aia_core.domain.panel_source import pinned_components
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass
from aia_core.domain.workflow import StepRunStatus
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.holdout_repository import HoldoutRepository
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_executors.ai_fieldwork import AIFieldwork, AIFieldworkConfig
from aia_executors.registry import registry_for
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy.orm import Session, sessionmaker

N = 200
MODEL, ROUTE = "model-x", "route-x"
BINDING = f"{Provider.AWS_BEDROCK.value}/{MODEL}/{ROUTE}"
OPTIONS = (Option("1", "Rozhodně ano"), Option("2", "Spíše ano"), Option("3", "Ne"))
WORDING = {
    "c1": "Do jaké míry souhlasíte: rodina je základ společnosti?",
    "c2": "Jak často se vídáte se svými sourozenci?",
    "c3": "Jak jste spokojen se svou prací?",
}
BLOCKS = [["c1", "c2"], ["c3"]]


def _bank() -> ItemBank:
    return ItemBank(
        items=tuple(
            HoldoutItem(
                field=field,
                survey="ISSP_2022_CZ",
                domain="family" if field != "c3" else "work",
                wording=WORDING[field],
                options=OPTIONS,
                measured_ages=None,
                ordinal=True,
                source=SourceDocument("https://example.org/q.pdf", "d" * 64, "3", field),
            )
            for field in ("c1", "c2", "c3")
        ),
        sha256="b" * 64,
    )


def _preregistration(live_version: str, *, binding: str = BINDING) -> Preregistration:
    system = {**pinned_components(live_version), "model_binding": binding}
    return Preregistration(
        document={
            "preregistration_version": PREREGISTRATION_VERSION,
            "bank_sha256": "b" * 64,
            "pool_sha256": "p" * 64,
            "split": {
                "seed": 1,
                "development_share": 0.4,
                "near_duplicate": 0.7,
                "development": ["d1"],
                "confirmation": ["c1", "c2", "c3"],
                "duplicates": [],
            },
            "blocks": [
                {
                    "items": ["c1", "c2"],
                    "excluded": [
                        {"field": "c1", "item": "c1", "reason": "ITEM", "association": None},
                        {"field": "c2", "item": "c2", "reason": "ITEM", "association": None},
                        {
                            "field": "vzdelani",
                            "item": "c1",
                            "reason": "ASSOCIATED",
                            "association": 0.4,
                        },
                    ],
                    "signals": [],
                },
                {
                    "items": ["c3"],
                    "excluded": [
                        {"field": "c3", "item": "c3", "reason": "ITEM", "association": None}
                    ],
                    "signals": [],
                },
            ],
            "arms": list(ARMS),
            "model_arms": list(MODEL_ARMS),
            "n": N,
            "sample_seed": 5,
            "replicate_seeds": [11, 12, 13],
            "bootstrap": {"seed": 7, "resamples": 10_000},
            "thresholds": dict(THRESHOLDS),
            "scoring_version": SCORING_VERSION,
            "population_version": live_version,
            "respondent_system": {
                "components": system,
                "fingerprint": respondent_system_fingerprint(system),
            },
            "cost_ceiling_usd": 500.0,
        }
    )


class _Caller:
    """Puts 0.6, 0.3, 0.1 on every item's options; records what it was asked."""

    def __init__(self, *, model: str = MODEL) -> None:
        self.requests: list[Any] = []
        self.model = model

    def preflight(self, request: Any) -> Any:
        return SimpleNamespace(route_id=ROUTE, model=self.model)

    def invoke(self, request: Any) -> Any:
        self.requests.append(request)
        contract = request.agent.output_contract
        output = contract.model_validate(
            {
                field.alias or name: {"probabilities": [0.6, 0.3, 0.1]}
                for name, field in contract.model_fields.items()
            }
        )
        call = f"c{len(self.requests)}"
        return SimpleNamespace(
            output=output,
            call_id=call,
            provider_request_id="p",
            resolved_model=self.model,
            provenance=SimpleNamespace(route_id=ROUTE, policy_version="v", schema_fingerprint="s"),
            total_cost_usd=0.001,
            cost_basis=SimpleNamespace(value="estimated"),
            usage_events=(SimpleNamespace(call_id=call),),
        )


@pytest.fixture
def grounded(world: Any) -> Any:
    from grounded_world import grounded_population

    with world.sessions() as session:
        return grounded_population(session)


def _fieldwork(caller: _Caller, grounded: Any, *, approved: bool = True) -> AIFieldwork:
    from aia_core.domain.ai_material import MaterialApproval, material_sha256
    from aia_core.domain.holdout.run import validation_specification

    spec = validation_specification(_bank(), _preregistration("unused"))
    approvals = (
        (
            MaterialApproval(
                sha256=material_sha256(spec.model_dump(mode="json")),
                data_class=DataClass.CLASS_C_INTERNAL,
                provenance="the public survey wording of the test bank",
            ),
        )
        if approved
        else ()
    )
    return AIFieldwork(
        gateway=None,  # type: ignore[arg-type]
        config=AIFieldworkConfig(
            policy_version="test",
            provider=Provider.AWS_BEDROCK,
            reservation_usd=0.01,
            max_output_tokens=1000,
            fictional_client_ids=frozenset(),
            material_approvals=approvals,
        ),
        build=BuildIdentity(sha="abc"),
        caller_factory=lambda **_: caller,
        population=grounded.loader(),
    )


def _start(world: Any, grounded: Any, prereg: Preregistration) -> str:
    from grounded_world import LIVE

    with world.sessions() as session:
        scope = world.lead_scope(session)
        HoldoutRepository(session, scope).record_preregistration(prereg)
        started = ValidationRuns(
            session, scope, population_contract=grounded.contract, population_id=LIVE
        ).start(bank=_bank(), reservation_usd=0.0001)
        session.commit()
        return started.run_id


def _live_version(world: Any, grounded: Any) -> str:
    from aia_core.application.population import live_binding
    from grounded_world import LIVE

    with world.sessions() as session:
        binding = live_binding(session, contract=grounded.contract, population_id=LIVE)
        assert binding is not None
        return binding.version_id


@pytest.fixture
def worker_with(
    sessions: sessionmaker[Session],
    database_url: str,
    store: InMemoryArtifactStore,
    build: BuildIdentity,
) -> Callable[[AIFieldwork | None], Worker]:
    def make(ai: AIFieldwork | None) -> Worker:
        return Worker(
            session_factory=sessions,
            executors=registry_for(store=store, build=build, ai_runtime=ai),
            settings=WorkerSettings(
                database_url=database_url,
                executors="aia_executors.registry:build_registry",
                worker_id="validation-worker",
                lease_seconds=30,
                heartbeat_seconds=0.1,
                poll_seconds=0.05,
                maintenance_seconds=0.2,
            ),
        )

    return make


def _drain(worker: Worker) -> list[str]:
    endings: list[str] = []
    while (result := worker.run_once()) is not None:
        endings.append(result.ending)
    return endings


def _steps(world: Any, run_id: str) -> dict[str, dict[str, Any]]:
    with world.sessions() as session:
        run = WorkflowRepository(session, world.lead_scope(session)).get_run(run_id)
    return {s["node_key"]: s for s in run["steps"]}


def test_the_sample_is_drawn_once_and_every_arm_answers_the_same_people_through_fieldwork(
    world: Any, grounded: Any, store: InMemoryArtifactStore, worker_with: Any
) -> None:
    run_id = _start(world, grounded, _preregistration(_live_version(world, grounded)))
    caller = _Caller()
    assert _drain(worker_with(_fieldwork(caller, grounded))) == ["completed"] * 16
    steps = _steps(world, run_id)
    assert steps["score"]["status"] is not StepRunStatus.SUCCEEDED  # its executor is 7e4b's
    sample = steps["sample"]["output"]
    assert sample["respondents"] == N
    # One request per respondent per preregistered block per arm replicate: two blocks, even
    # though the questionnaire's own split would ask its three items as one.
    assert len(caller.requests) == N * len(BLOCKS) * 15
    with world.sessions() as session:
        artifacts = validation_artifacts(session, world.lead_scope(session), store)
        stored = artifacts.read_json(sample["artifact_id"])
        assert stored["kind"] == SAMPLE_ARTIFACT and len(stored["respondents"]) == N
        records = {
            (arm, k): artifacts.read_json(steps[arm_node_key(arm, k)]["output"]["artifact_id"])
            for arm in MODEL_ARMS
            for k in (1, 2, 3)
        }
    people = None
    for (arm, k), record in records.items():
        assert record["kind"] == ARM_ARTIFACT and (record["arm"], record["replicate"]) == (arm, k)
        assert record["sample_sha256"] == sample["sample_sha256"]
        assert record["model_binding"] == BINDING
        assert record["data_class"] == "CLASS_A_CLIENT_CONFIDENTIAL"
        assert set(record["answers"]) == {"c1", "c2", "c3"}
        # Every answer is a code, drawn from the probabilities stored beside it.
        for item in ("c1", "c2", "c3"):
            assert set(record["answers"][item].values()) <= {"1", "2", "3"}
            assert all(len(p) == 3 for p in record["probabilities"][item].values())
        respondents = set(record["answers"]["c1"])
        assert len(respondents) == N
        people = respondents if people is None else people
        assert respondents == people  # every arm, the same sampled people
    # Each replicate draws under its own seed.
    assert records[("D", 1)]["answers"] != records[("D", 2)]["answers"]


def test_an_arm_from_another_model_binding_fails_before_any_request(
    world: Any, grounded: Any, worker_with: Any
) -> None:
    run_id = _start(world, grounded, _preregistration(_live_version(world, grounded)))
    caller = _Caller(model="model-y")
    _drain(worker_with(_fieldwork(caller, grounded)))
    steps = _steps(world, run_id)
    assert steps["sample"]["status"] is StepRunStatus.SUCCEEDED
    arms = [steps[arm_node_key(a, k)] for a in MODEL_ARMS for k in (1, 2, 3)]
    tried = [arm for arm in arms if arm["attempts"]]
    # The first arm that runs fails for good and stops the run; no arm succeeds.
    assert tried and all(arm["status"] is StepRunStatus.FAILED for arm in tried)
    assert {arm["attempts"][-1]["error"]["reason"] for arm in tried} == {"model_binding_changed"}
    assert not any(arm["status"] is StepRunStatus.SUCCEEDED for arm in arms)
    assert caller.requests == []


def test_without_the_ai_runtime_the_arms_park_and_nothing_is_answered_instead(
    world: Any, grounded: Any, worker_with: Any
) -> None:
    run_id = _start(world, grounded, _preregistration(_live_version(world, grounded)))
    _drain(worker_with(None))
    steps = _steps(world, run_id)
    # Without the panel path the sample parks too: nothing draws from a population it cannot load.
    for key in ("sample", arm_node_key("D", 1)):
        if steps[key]["attempts"]:
            assert steps[key]["attempts"][-1]["error"]["reason"] in {
                "panel_personas_unavailable",
                "ai_runtime_unavailable",
            }
    assert steps["sample"]["status"] is not StepRunStatus.SUCCEEDED
    assert all(
        steps[arm_node_key(a, k)]["status"] is not StepRunStatus.SUCCEEDED
        for a in MODEL_ARMS
        for k in (1, 2, 3)
    )


def test_an_unclassified_questionnaire_parks_the_arm_and_sends_nothing(
    world: Any, grounded: Any, worker_with: Any
) -> None:
    run_id = _start(world, grounded, _preregistration(_live_version(world, grounded)))
    caller = _Caller()
    _drain(worker_with(_fieldwork(caller, grounded, approved=False)))
    steps = _steps(world, run_id)
    tried = [
        steps[arm_node_key(a, k)]
        for a in MODEL_ARMS
        for k in (1, 2, 3)
        if steps[arm_node_key(a, k)]["attempts"]
    ]
    assert tried
    assert {arm["attempts"][-1]["error"]["reason"] for arm in tried} == {
        "egress_unclassified_material"
    }
    assert caller.requests == []
