"""A confirmation run under the real worker (panel-grounded-respondents 7e4): sample, arms, score.

Over the fictional grounded population and a scripted caller in place of the gateway: nothing
leaves the process. The run is started from a stored preregistration, as the service starts it.
The items are fields of that population, so the score step reads the sampled people's own answers.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from aia_core.application.validation import ValidationRuns, validation_artifacts
from aia_core.domain.deployment import DataClassGates
from aia_core.domain.evidence.validation import respondent_system_fingerprint
from aia_core.domain.holdout.bank import HoldoutItem, ItemBank, Option, SourceDocument
from aia_core.domain.holdout.preregistration import (
    ARMS,
    MODEL_ARMS,
    PREREGISTRATION_VERSION,
    THRESHOLDS,
    Preregistration,
)
from aia_core.domain.holdout.run import (
    ARM_ARTIFACT,
    SAMPLE_ARTIFACT,
    SCORE_ARTIFACT,
    arm_node_key,
)
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
# The items are fields of the grounded population, so the score reads real truths: each holds
# 0 or 1; the third option is one nobody stored.
OPTIONS = (Option("1", "Rozhodně ano"), Option("0", "Spíše ne"), Option("9", "Nevím"))
WORDING = {
    "is_parent": "Do jaké míry souhlasíte: rodina je základ společnosti?",
    "has_partner": "Jak často se vídáte se svými sourozenci?",
    "is_student": "Jak jste spokojen se svou prací?",
}
BLOCKS = [["is_parent", "has_partner"], ["is_student"]]


def _bank() -> ItemBank:
    return ItemBank(
        items=tuple(
            HoldoutItem(
                field=field,
                survey="ISSP_2022_CZ",
                domain="family" if field != "is_student" else "work",
                wording=WORDING[field],
                options=OPTIONS,
                measured_ages=None,
                ordinal=True,
                source=SourceDocument("https://example.org/q.pdf", "d" * 64, "3", field),
            )
            for field in ("is_parent", "has_partner", "is_student")
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
                "confirmation": ["is_parent", "has_partner", "is_student"],
                "duplicates": [],
            },
            "blocks": [
                {
                    "items": ["is_parent", "has_partner"],
                    "excluded": [
                        {
                            "field": "is_parent",
                            "item": "is_parent",
                            "reason": "ITEM",
                            "association": None,
                        },
                        {
                            "field": "has_partner",
                            "item": "has_partner",
                            "reason": "ITEM",
                            "association": None,
                        },
                        {
                            "field": "vzdelani",
                            "item": "is_parent",
                            "reason": "ASSOCIATED",
                            "association": 0.4,
                        },
                    ],
                    "signals": [],
                },
                {
                    "items": ["is_student"],
                    "excluded": [
                        {
                            "field": "is_student",
                            "item": "is_student",
                            "reason": "ITEM",
                            "association": None,
                        }
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


def _fieldwork(
    caller: _Caller,
    grounded: Any,
    *,
    approved: bool = True,
    class_gates: DataClassGates = DataClassGates.ENFORCE,
) -> AIFieldwork:
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
            class_gates=class_gates,
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
    assert _drain(worker_with(_fieldwork(caller, grounded))) == ["completed"] * 17
    steps = _steps(world, run_id)
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
        assert set(record["answers"]) == {"is_parent", "has_partner", "is_student"}
        # Every answer is a code, drawn from the probabilities stored beside it.
        for item in ("is_parent", "has_partner", "is_student"):
            assert set(record["answers"][item].values()) <= {"1", "0", "9"}
            assert all(len(p) == 3 for p in record["probabilities"][item].values())
        respondents = set(record["answers"]["is_parent"])
        assert len(respondents) == N
        people = respondents if people is None else people
        assert respondents == people  # every arm, the same sampled people
    # Each replicate draws under its own seed.
    assert records[("D", 1)]["answers"] != records[("D", 2)]["answers"]

    # The score: the sampled people's own answers against every arm, by the preregistered rules.
    score = steps["score"]["output"]
    assert score["verdict"] in {"PASS", "FAIL"}
    assert score["requests"] == len(caller.requests)
    assert score["total_cost_usd"] == pytest.approx(0.001 * len(caller.requests))
    with world.sessions() as session:
        artifacts = validation_artifacts(session, world.lead_scope(session), store)
        verdict = artifacts.read_json(score["artifact_id"])
    assert verdict["kind"] == SCORE_ARTIFACT
    assert verdict["sample_sha256"] == sample["sample_sha256"]
    assert verdict["verdict"]["verdict"] == score["verdict"]
    names = [c["name"] for c in verdict["verdict"]["criteria"]]
    assert names[0].startswith("P1") and names[-1].startswith("P8")
    assert set(verdict["verdict"]["arms"]) == set(MODEL_ARMS)
    assert set(verdict["baselines"]) == {"L0", "L1"}
    assert {m["item"] for m in verdict["baselines"]["L0"]} == {
        "is_parent",
        "has_partner",
        "is_student",
    }
    # Every sampled person holds a real 0/1 answer to each of these fields.
    assert verdict["scored"] == {"is_parent": N, "has_partner": N, "is_student": N}
    # A model that always leans to the first option has learnt nothing about the people: the
    # production persona cannot beat no persona, so the verdict must not pass.
    assert score["verdict"] == "FAIL"


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


def test_under_advisory_class_gates_an_unclassified_questionnaire_is_sent_and_says_so(
    world: Any, grounded: Any, worker_with: Any
) -> None:
    """Develop only (plan develop-class-advisory): the arm the test above parks is sent, judged
    as Class A as the gateway judges unknown material, and the step's own event and the arm's
    artifact name the refusal it would have made."""
    run_id = _start(world, grounded, _preregistration(_live_version(world, grounded)))
    caller = _Caller()
    _drain(
        worker_with(
            _fieldwork(caller, grounded, approved=False, class_gates=DataClassGates.ADVISORY)
        )
    )
    assert caller.requests
    assert {r.data_classification for r in caller.requests} == {
        DataClass.CLASS_A_CLIENT_CONFIDENTIAL
    }
    with world.sessions() as session:
        events = WorkflowRepository(session, world.lead_scope(session)).events(run_id, limit=2000)
    recorded = [e["payload"]["class_advisory"] for e in events if "class_advisory" in e["payload"]]
    assert recorded and all(
        r
        == {
            "gate": "validation_material",
            "rule": "egress_unclassified_material",
            "data_class": None,
            "advisory": True,
        }
        for r in recorded
    )
