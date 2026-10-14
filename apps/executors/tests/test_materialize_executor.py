"""The materialize step under the real worker loop (population-operations P4d3).

A researcher asks from a study (``prepare_materialization`` + ``start_materialization``); the
worker claims the ``population_materialize`` step and registers the owned child over a small
fictional population on disk, written once to the population store (a stand-in S3 client with
S3's conditional put). Without a store the run parks and nothing is written.
"""

from __future__ import annotations

import csv
import gzip
import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from aia_core.application.materialize import prepare_materialization, start_materialization
from aia_core.application.population import PopulationRuntime
from aia_core.application.population_authority import (
    PopulationAuthority,
    PopulationOperatorConfig,
)
from aia_core.application.scope import AuthenticatedPrincipal
from aia_core.domain.population import (
    KnownVersion,
    MaterializedKind,
    PopulationImportContract,
    PopulationKind,
    WeightScheme,
    content_sha256,
    field_names_fingerprint,
)
from aia_core.domain.population.definition import (
    DimensionDefinition,
    EvidenceAnchor,
    MissingnessRule,
    PredictorSpec,
)
from aia_core.domain.workflow import (
    RUNTIME_UNAVAILABLE_REASON,
    FailureClass,
    StepRunStatus,
    WorkflowRunStatus,
)
from aia_core.infrastructure.population_parser import parse_panel
from aia_core.infrastructure.population_repository import PopulationRegistryRepository
from aia_core.infrastructure.population_source import FilesystemPopulationSource
from aia_core.infrastructure.population_store import S3PopulationStore
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.workflow_repository import WorkflowRepository
from aia_executors.materialize import MaterializeExecutor
from aia_executors.registry import registry_for
from aia_worker.executor import StepExecutor
from aia_worker.settings import WorkerSettings
from aia_worker.worker import Worker
from sqlalchemy.orm import Session, sessionmaker

FIELDS = ("row_id", "vek", "segment", "w_main")


def _panel(segment: str = "s") -> bytes:
    ages = ("34", "71", "", "18", "45", "100", "29", "52")
    weights = ("1.5", "0.5", "2.0", "1.0", "3.25", "0.75", "1.0", "1.0")
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(FIELDS)
    for i, (age, w) in enumerate(zip(ages, weights, strict=True), start=1):
        writer.writerow([f"R{i}", age, segment, w])
    return gzip.compress(buffer.getvalue().encode("utf-8"), mtime=0)


def _dictionary() -> bytes:
    rows = {
        "row_id": ("provenance", "PROVENANCE_OR_CORE", "T", "AUDIT_ONLY", "no"),
        "vek": ("population_anchor", "POPULATION_ANCHOR", "A", "PERSONA_OR_ANALYSIS_WITH_SCOPE",
                "yes"),
        "segment": ("core", "CANONICAL_CORE", "C", "HISTORICAL_OR_EXPLORATORY", "yes"),
        "w_main": ("weight", "NEW_WEIGHT", "T", "AUDIT_ONLY", "no"),
    }  # fmt: skip
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["field", "block", "source", "evidence_status", "production_grade",
                     "recommended_use", "description", "persona_eligible"])  # fmt: skip
    for name in FIELDS:
        block, status, grade, use, persona = rows[name]
        writer.writerow([name, block, "fictional", status, grade, use, name, persona])
    return buffer.getvalue().encode("utf-8")


class _ClientError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class _FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, **kw: Any) -> None:
        if kw.get("IfNoneMatch") == "*" and kw["Key"] in self.objects:
            raise _ClientError("PreconditionFailed")
        self.objects[kw["Key"]] = kw["Body"]

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803 - boto3's
        if Key not in self.objects:
            raise _ClientError("NoSuchKey")
        return {"Body": io.BytesIO(self.objects[Key])}


@pytest.fixture
def population(world: Any, tmp_path: Path) -> dict[str, Any]:
    """The fictional population on disk, imported, STATIC and LIVE established on one version."""
    static, panel, dictionary = _panel("s1"), _panel("s4"), _dictionary()
    (tmp_path / "static.csv.gz").write_bytes(static)
    (tmp_path / "panel.csv.gz").write_bytes(panel)
    (tmp_path / "dictionary.csv").write_bytes(dictionary)
    contract = PopulationImportContract(
        contract_id="fictional_population/v1",
        dataset_id="fictional_population",
        field_count=len(FIELDS),
        field_names_sha256=field_names_fingerprint(FIELDS),
        dictionary_sha256=content_sha256(dictionary),
        primary_key="row_id",
        expected_rows=8,
        weight_schemes=(WeightScheme("main", "w_main", expected_total=11.0, tolerance=1e-9),),
        default_weight_role="main",
        known_versions=(
            KnownVersion("f1_1", content_sha256(static), len(static)),
            KnownVersion("f1_4", content_sha256(panel), len(panel), "f1_1"),
        ),
        static_reference_label="f1_1",
        enrichment_fields=(),
    )
    shared = FilesystemPopulationSource(tmp_path)
    operator = PopulationAuthority(
        PopulationOperatorConfig.from_names({"op": ("POPULATION_ESTABLISH",)})
    ).operator_context(AuthenticatedPrincipal(user_id="op", organization_id="platform"))
    with world.sessions() as session:
        runtime = PopulationRuntime(session, contract=contract, source=shared)
        versions = {
            label: runtime.import_version(
                label=label,
                panel_location=location,
                dictionary_location="dictionary.csv",
                provenance="fictional",
                imported_by="op",
            )
            for label, location in (("f1_1", "static.csv.gz"), ("f1_4", "panel.csv.gz"))
        }
        for pid, kind, label in (
            ("FIC_STATIC", PopulationKind.STATIC, "f1_1"),
            ("FIC_LIVE", PopulationKind.LIVE, "f1_4"),
        ):
            runtime.establish(
                population_id=pid,
                kind=kind,
                version_id=versions[label].version_id,
                operator=operator,
                reason="fictional",
            )
        version = versions["f1_4"]
        session.commit()
    return {"contract": contract, "shared": shared, "base": version}


DEFINITION = DimensionDefinition(
    dimension_id="pije_kavu_rano",
    version=1,
    construct="morning coffee",
    label="Pije kávu ráno",
    kind=MaterializedKind.BINARY,
    target=0.4,
    evidence=EvidenceAnchor("KNW-fictional", 1, "40 % ráno"),
    predictors=(PredictorSpec("vek"),),
    missingness=MissingnessRule.PREDICTOR_MEAN,
    range=(0.0, 1.0),
)


def _start(world: Any, population: dict[str, Any]) -> str:
    with world.sessions() as session:
        scope = world.lead_scope(session)
        request = prepare_materialization(
            session,
            scope,
            definition=DEFINITION,
            contract=population["contract"],
            population_id="FIC_LIVE",
        )
        started = start_materialization(session, scope, request)
        again = start_materialization(session, scope, request)
        assert again.run_id == started.run_id and not again.created
        session.commit()
        return started.run_id


@pytest.fixture
def worker_with(
    sessions: sessionmaker[Session], database_url: str
) -> Callable[[dict[str, StepExecutor]], Worker]:
    def build(executors: dict[str, StepExecutor]) -> Worker:
        return Worker(
            session_factory=sessions,
            executors=executors,
            settings=WorkerSettings(
                database_url=database_url,
                executors="aia_executors.registry:build_registry",
                worker_id="materialize-worker",
                lease_seconds=30,
                heartbeat_seconds=0.1,
                poll_seconds=0.05,
                maintenance_seconds=0.2,
            ),
        )

    return build


def _drain(worker: Worker) -> list[str]:
    endings: list[str] = []
    while (result := worker.run_once()) is not None:
        endings.append(result.ending)
    return endings


def _run(world: Any, run_id: str) -> dict[str, Any]:
    with world.sessions() as session:
        return WorkflowRepository(session, world.lead_scope(session)).get_run(run_id)


def test_a_researcher_materializes_a_dimension_and_the_worker_registers_the_owned_child(
    world: Any,
    population: dict[str, Any],
    store: InMemoryArtifactStore,
    build: Any,
    worker_with: Callable[[dict[str, StepExecutor]], Worker],
) -> None:
    s3 = _FakeS3()
    pop_store = S3PopulationStore("pop-bucket", region_name="eu-central-1", client=s3)
    executor = MaterializeExecutor(
        store=pop_store, shared=population["shared"], contract=population["contract"]
    )
    run_id = _start(world, population)
    endings = _drain(worker_with(registry_for(store=store, build=build, materialize=executor)))
    assert endings == ["completed"]

    run = _run(world, run_id)
    assert run["status"] is WorkflowRunStatus.COMPLETED
    output = run["steps"][0]["output"]
    assert output["created"] is True and output["target"] == 0.4
    assert output["usable_predictors"] == ["vek"]

    with world.sessions() as session:
        child = PopulationRegistryRepository(session).get_version(output["version_id"])
    assert child is not None and child.owner is not None
    assert (child.owner.organization_id, child.owner.client_id) == (
        world.organization_id,
        world.client_id,
    )
    assert child.parent_version_id == population["base"].version_id
    panel = parse_panel(pop_store.read(child.storage_location))
    assert panel.header == (*FIELDS, "pije_kavu_rano")
    assert set(panel.column("pije_kavu_rano")) <= {"0", "1"}

    # P4d4: the run reads through its study, and the registry says what the child reached.
    from aia_core.application.materialize import child_outcome, materialization_run

    with world.sessions() as session:
        scope = world.lead_scope(session)
        read = materialization_run(session, scope, run_id)
        outcome = child_outcome(session, child)
    assert read["metadata"]["kind"] == "binary"
    assert outcome is not None and outcome.dimension_id == "pije_kavu_rano"
    assert (outcome.target, outcome.achieved) == (output["target"], output["achieved"])
    assert outcome.usable_predictors == ("vek",)
    assert outcome.target_met is (abs(output["achieved"] - 0.4) <= 0.005)


def test_without_a_population_store_the_run_parks_and_nothing_is_written(
    world: Any,
    population: dict[str, Any],
    store: InMemoryArtifactStore,
    build: Any,
    worker_with: Callable[[dict[str, StepExecutor]], Worker],
) -> None:
    run_id = _start(world, population)
    # The production composition with no store configured.
    assert _drain(worker_with(registry_for(store=store, build=build))) == ["failed"]
    step = _run(world, run_id)["steps"][0]
    assert step["status"] is StepRunStatus.WAITING_PROVIDER
    assert step["waiting_reason"] == RUNTIME_UNAVAILABLE_REASON
    last = step["attempts"][-1]
    assert last["failure_class"] is FailureClass.RUNTIME_UNAVAILABLE
    assert last["error"]["reason"] == "population_store_unconfigured"
    with world.sessions() as session:
        owned = [
            v
            for v in PopulationRegistryRepository(session)
            .versions("fictional_population", organization_id=world.organization_id)
            .values()
            if not v.shared
        ]
    assert owned == []


def test_the_composition_builds_one_store_from_both_keys_or_none() -> None:
    from aia_core.infrastructure.population_store import PopulationStoreError
    from aia_executors.registry import population_store

    assert population_store({}) is None
    env = {
        "AIA_POPULATION_STORE_BUCKET": "pop-bucket",
        "AIA_POPULATION_STORE_REGION": "eu-central-1",
    }
    built = population_store(env)
    assert isinstance(built, S3PopulationStore)
    assert built.location("k.csv.gz") == "s3://pop-bucket/materialized/k.csv.gz"
    with pytest.raises(PopulationStoreError):
        population_store({"AIA_POPULATION_STORE_BUCKET": "pop-bucket"})
