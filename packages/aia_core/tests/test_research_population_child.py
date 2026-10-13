"""A research run over a child its study selected (population-operations P4e2).

A study may run over a materialized child of its own client instead of LIVE: the run records
that child's binding (``PINNED``, no population), the selection is part of the run's identity,
a start that finds its run keeps what it recorded, and a retry keeps the original's. Another
client's child -- in the same organization or another -- answers as unknown, as a scope miss
does, and nothing is started. Over the fictional population in ``conftest.py``.
"""

from __future__ import annotations

import io
from typing import Any

import pytest

from aia_core.application.population import PopulationRuntime, child_binding
from aia_core.application.population_characteristics import shared_version_policy
from aia_core.application.research import ResearchRuns
from aia_core.domain.fieldwork import FieldworkSource
from aia_core.domain.population import (
    MaterializedKind,
    PopulationKind,
    ResolutionMode,
    UnknownDatasetVersion,
    VersionOwner,
)
from aia_core.domain.population.definition import (
    DimensionDefinition,
    EvidenceAnchor,
    MissingnessRule,
    PredictorSpec,
)
from aia_core.domain.population.derivation import numeric_column
from aia_core.domain.population.policy import FieldUse
from aia_core.infrastructure.population_parser import parse_panel
from aia_core.infrastructure.population_store import RoutingPopulationSource, S3PopulationStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository
from aia_core.infrastructure.workflow_repository import WorkflowRepository

AI = FieldworkSource.AI_RUNTIME
LIVE = "SYN_LIVE"
DESIGN = {
    "title": "Ranní nápoj",
    "goal": "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
    "n": 120,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]}
            ],
        }
    ],
}


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


def _operator() -> Any:
    from aia_core.application.population_authority import (
        PopulationAuthority,
        PopulationOperatorConfig,
    )
    from aia_core.application.scope import AuthenticatedPrincipal

    config = PopulationOperatorConfig.from_names({"operator": ("POPULATION_ESTABLISH",)})
    return PopulationAuthority(config).operator_context(
        AuthenticatedPrincipal(user_id="operator", organization_id="platform")
    )


@pytest.fixture
def world(session: Any, scoped: Any, synthetic_population: Any) -> dict[str, Any]:
    """LIVE established, and a materialize-ready base: its runtime, store and a predictor."""
    pop = synthetic_population
    store = S3PopulationStore("pop-bucket", region_name="eu-central-1", client=_FakeS3())
    runtime = PopulationRuntime(
        session, contract=pop.contract, source=RoutingPopulationSource(pop.source, store)
    )
    versions = {
        label: runtime.import_version(
            label=label,
            panel_location=pop.location(label),
            dictionary_location=pop.dictionary_location,
            provenance="fictional test bundle",
            imported_by="importer",
        )
        for label in ("v1_BASE", "v1_1", "v1_4")
    }
    for pid, kind, label in (
        ("SYN_STATIC", PopulationKind.STATIC, "v1_1"),
        (LIVE, PopulationKind.LIVE, "v1_4"),
    ):
        runtime.establish(
            operator=_operator(),
            population_id=pid,
            kind=kind,
            version_id=versions[label].version_id,
            reason="fictional",
        )
    base = versions["v1_4"]
    kept = shared_version_policy(session, contract=pop.contract, version=base)
    assert kept is not None
    dictionary, policy = kept
    panel = parse_panel(pop.source.read(base.storage_location))
    predictor = next(
        f
        for f in dictionary.fields
        if policy.decide(f, FieldUse.PERSONA_CONSTRUCTION).allowed
        and f in panel.header
        and (values := numeric_column(panel.column(f))) is not None
        and len({v for v in values if v is not None}) > 1
    )
    definition = DimensionDefinition(
        dimension_id="pije_kavu_rano",
        version=1,
        construct="morning coffee",
        label="Pije kávu ráno",
        kind=MaterializedKind.BINARY,
        target=0.34,
        evidence=EvidenceAnchor("KNW-fictional", 1, "34 % ráno"),
        predictors=(PredictorSpec(predictor),),
        missingness=MissingnessRule.PREDICTOR_MEAN,
        range=(0.0, 1.0),
    )

    def child_of(scope: Any) -> str:
        owner = VersionOwner(organization_id=scope.organization_id, client_id=scope.client_id)
        return runtime.materialize_child(
            base_version_id=base.version_id,
            definition=definition,
            owner=owner,
            store=store,
            actor_id=scope.actor_id,
        ).version.version_id

    return {"pop": pop, "base": base, "child_of": child_of, "runtime": runtime, "store": store}


def _runs(session: Any, scope: Any, world: dict[str, Any]) -> ResearchRuns:
    return ResearchRuns(
        session, scope, population_contract=world["pop"].contract, population_id=LIVE
    )


def _revision(session: Any, scope: Any) -> str:
    created, _ = StudyDesignRepository(session, scope).submit(content=DESIGN, source_stage="run")
    return created.revision_id


def _binding(session: Any, scope: Any, run_id: str) -> Any:
    return WorkflowRepository(session, scope).population_binding(run_id)


def test_a_run_over_the_studys_child_records_it_pinned_and_is_another_run_than_live(
    session: Any, scoped: Any, world: dict[str, Any]
) -> None:
    scope = scoped.scope()
    child = world["child_of"](scope)
    revision = _revision(session, scope)
    over_live = _runs(session, scope, world).start(design_revision_id=revision, fieldwork_source=AI)
    over_child = _runs(session, scope, world).start(
        design_revision_id=revision, fieldwork_source=AI, population_version_id=child
    )
    assert over_child.created and over_child.run_id != over_live.run_id
    binding = _binding(session, scope, over_child.run_id)
    assert binding.version_id == child and binding.population_id is None
    assert binding.resolution is ResolutionMode.PINNED
    assert _binding(session, scope, over_live.run_id).version_id == world["base"].version_id
    note = _runs(session, scope, world).get(over_child.run_id)["metadata"]["population"]
    assert note["version_id"] == child and note["read_by_fieldwork"] is False

    # The selection is identity: asking again finds the run, with what it recorded.
    again = _runs(session, scope, world).start(
        design_revision_id=revision, fieldwork_source=AI, population_version_id=child
    )
    assert again.run_id == over_child.run_id and not again.created


def test_a_sibling_study_of_the_client_may_select_the_child(
    session: Any, scoped: Any, world: dict[str, Any]
) -> None:
    child = world["child_of"](scoped.scope())
    sibling = scoped.scope(study="sibling")
    started = _runs(session, sibling, world).start(
        design_revision_id=_revision(session, sibling),
        fieldwork_source=AI,
        population_version_id=child,
    )
    assert _binding(session, sibling, started.run_id).version_id == child


def test_a_retry_keeps_the_child_its_original_recorded(
    session: Any, scoped: Any, world: dict[str, Any]
) -> None:
    scope = scoped.scope()
    child = world["child_of"](scope)
    runs = _runs(session, scope, world)
    original = runs.start(
        design_revision_id=_revision(session, scope),
        fieldwork_source=AI,
        population_version_id=child,
    ).run_id
    runs.cancel(original)
    retry = runs.retry(original, fieldwork_source=AI)
    assert retry.created and _binding(session, scope, retry.run_id).version_id == child


def test_another_clients_child_or_a_shared_version_is_unknown_and_nothing_starts(
    session: Any, scoped: Any, world: dict[str, Any]
) -> None:
    theirs = world["child_of"](scoped.scope(user="other_lead", study="other_client"))
    scope = scoped.scope()
    revision = _revision(session, scope)
    for version_id in (theirs, world["base"].version_id, "no-such-version"):
        with pytest.raises(UnknownDatasetVersion):
            _runs(session, scope, world).start(
                design_revision_id=revision, fieldwork_source=AI, population_version_id=version_id
            )
    assert _runs(session, scope, world).runs(limit=10) == []


def test_another_organizations_child_is_unknown(
    session: Any, scoped: Any, world: dict[str, Any]
) -> None:
    from aia_core.infrastructure.tables import ClientRow, OrganizationRow

    session.add(OrganizationRow(organization_id="ORG-theirs", slug="theirs", name="Theirs"))
    session.flush()
    session.add(ClientRow(client_id="CLI-theirs", organization_id="ORG-theirs", slug="c", name="C"))
    session.flush()

    class _Theirs:
        organization_id, client_id, actor_id = "ORG-theirs", "CLI-theirs", "USR-theirs"

    theirs = world["child_of"](_Theirs())
    with pytest.raises(UnknownDatasetVersion):
        child_binding(
            session,
            contract=world["pop"].contract,
            version_id=theirs,
            owner=VersionOwner(organization_id=scoped.organization_id, client_id="CLI-theirs"),
        )


def test_materializing_and_selecting_a_child_leaves_live_where_it_was(
    session: Any, scoped: Any, world: dict[str, Any]
) -> None:
    """P5: a dimension made and run over never moves a shared population or writes its history."""
    from aia_core.infrastructure.population_repository import PopulationRegistryRepository

    registry = PopulationRegistryRepository(session)
    dataset = world["pop"].contract.dataset_id
    live = registry.population(LIVE)
    assert live is not None
    before = (live.current_version_id, registry.promotions(dataset))

    scope = scoped.scope()
    child = world["child_of"](scope)
    _runs(session, scope, world).start(
        design_revision_id=_revision(session, scope),
        fieldwork_source=AI,
        population_version_id=child,
    )
    after = registry.population(LIVE)
    assert after is not None
    assert (after.current_version_id, registry.promotions(dataset)) == before
    assert after.current_version_id == world["base"].version_id != child
