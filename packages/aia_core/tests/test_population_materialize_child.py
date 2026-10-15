"""A materialized child, made inside the one loader (population-operations P4d3).

Over the fictional population in ``conftest.py``: ``PopulationRuntime.materialize_child`` reads
the base as every load does, asks each predictor again of its policy, derives the values with
P4b's rule, writes the child once to the population store (``S3PopulationStore`` over a
stand-in client with S3's conditional put), and registers it with its extension. The child's
bytes read back as the base's columns plus the new one; a retry and a second client behave as
P4c's identity says they must.
"""

from __future__ import annotations

import io
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.application.population import PopulationRuntime
from aia_core.application.population_characteristics import shared_version_policy
from aia_core.domain.population import (
    MaterializedKind,
    VersionOwner,
    check_child_version,
)
from aia_core.domain.population.definition import (
    DimensionDefinition,
    EvidenceAnchor,
    MissingnessRule,
    PredictorSpec,
)
from aia_core.domain.population.derivation import (
    DerivationRefused,
    derive_dimension,
    numeric_column,
)
from aia_core.domain.population.policy import FieldUse
from aia_core.infrastructure.population_parser import parse_panel
from aia_core.infrastructure.population_repository import PopulationRegistryRepository
from aia_core.infrastructure.population_store import RoutingPopulationSource, S3PopulationStore

OURS = VersionOwner(organization_id="ORG-ours", client_id="CLI-ours")
THEIRS = VersionOwner(organization_id="ORG-theirs", client_id="CLI-theirs")


class _ClientError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class _FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.puts = 0

    def put_object(self, **kw: Any) -> None:
        self.puts += 1
        if kw.get("IfNoneMatch") == "*" and kw["Key"] in self.objects:
            raise _ClientError("PreconditionFailed")
        self.objects[kw["Key"]] = kw["Body"]

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803 - boto3's
        if Key not in self.objects:
            raise _ClientError("NoSuchKey")
        return {"Body": io.BytesIO(self.objects[Key])}


@pytest.fixture
def world(session: Session, synthetic_population: Any) -> dict[str, Any]:
    pop = synthetic_population
    runtime = PopulationRuntime(session, contract=pop.contract, source=pop.source)
    base = runtime.import_version(
        label="v1_BASE",
        panel_location=pop.location("v1_BASE"),
        dictionary_location=pop.dictionary_location,
        provenance="fictional test bundle",
        imported_by="importer",
    )
    kept = shared_version_policy(session, contract=pop.contract, version=base)
    assert kept is not None
    dictionary, policy = kept
    panel = parse_panel(pop.source.read(base.storage_location))
    numeric = [
        f
        for f in dictionary.fields
        if policy.decide(f, FieldUse.PERSONA_CONSTRUCTION).allowed
        and f in panel.header
        and (values := numeric_column(panel.column(f))) is not None
        and len({v for v in values if v is not None}) > 1
    ]
    assert numeric, "the fictional panel has a varying numeric persona field"
    s3 = _FakeS3()
    store = S3PopulationStore("pop-bucket", region_name="eu-central-1", client=s3)
    return {
        "pop": pop,
        "base": base,
        "panel": panel,
        "predictor": numeric[0],
        "refused": [
            f
            for f in dictionary.fields
            if not policy.decide(f, FieldUse.PERSONA_CONSTRUCTION).allowed
        ],
        "s3": s3,
        "store": store,
    }


def definition(predictor: str, **change: Any) -> DimensionDefinition:
    fields: dict[str, Any] = {
        "dimension_id": "pije_kavu_rano",
        "version": 1,
        "construct": "morning coffee",
        "label": "Pije kávu ráno",
        "kind": MaterializedKind.BINARY,
        "target": 0.34,
        "evidence": EvidenceAnchor("KNW-fictional", 1, "34 % ráno"),
        "predictors": (PredictorSpec(predictor),),
        "missingness": MissingnessRule.PREDICTOR_MEAN,
        "range": (0.0, 1.0),
    }
    fields.update(change)
    return DimensionDefinition(**fields)


def runtime(session: Session, w: dict[str, Any]) -> PopulationRuntime:
    return PopulationRuntime(
        session,
        contract=w["pop"].contract,
        source=RoutingPopulationSource(w["pop"].source, w["store"]),
    )


def materialize(session: Session, w: dict[str, Any], d: DimensionDefinition, owner=OURS) -> Any:
    return runtime(session, w).materialize_child(
        base_version_id=w["base"].version_id,
        definition=d,
        owner=owner,
        store=w["store"],
        actor_id="USR-researcher",
    )


def test_the_child_is_the_base_plus_the_derived_column_written_once_and_registered(
    session: Session, world: dict[str, Any], owner_rows: None
) -> None:
    w = world
    d = definition(w["predictor"])
    child = materialize(session, w, d)
    assert child.created
    version = child.version
    assert version.owner == OURS and not version.shared
    assert version.parent_version_id == w["base"].version_id
    assert version.storage_location.startswith("s3://pop-bucket/materialized/")

    # The bytes read back as the base's columns, unchanged, followed by the new one.
    data = w["store"].read(version.storage_location)
    read = parse_panel(data)
    base = w["panel"]
    assert read.header == (*base.header, "pije_kavu_rano")
    assert read.columns[: len(base.header)] == base.columns
    # The values are P4b's derivation over the same inputs, bit for bit.
    contract = w["pop"].contract
    weight = next(s for s in contract.weight_schemes if s.role == contract.default_weight_role)
    expected = derive_dimension(
        tuple(str(c) for c in base.column(contract.primary_key)),
        {w["predictor"]: numeric_column(base.column(w["predictor"])) or []},
        numeric_column(base.column(weight.column)) or [],
        dimension_id="pije_kavu_rano",
        spec=d.evidence_spec(),
    )
    assert read.column("pije_kavu_rano") == tuple("1" if v else "0" for v in expected.values)
    assert (child.target, child.achieved) == (expected.target, expected.achieved)

    registry = PopulationRegistryRepository(session)
    assert registry.get_version(version.version_id) == version
    extension = registry.extension(version.extension_sha256 or "")
    assert extension is not None and extension.fields[0].definition_sha256 == d.sha256
    check_child_version(
        base=w["base"], child=version, extension=extension, base_field_names=base.header
    )
    record = registry.validation_record(version.version_id)
    assert record is not None and record["materialized"]["achieved"] == expected.achieved


def test_a_retry_finds_the_child_and_another_client_gets_its_own(
    session: Session, world: dict[str, Any], owner_rows: None
) -> None:
    w = world
    d = definition(w["predictor"])
    first = materialize(session, w, d)
    again = materialize(session, w, d)
    assert not again.created and again.version == first.version
    theirs = materialize(session, w, d, owner=THEIRS)
    assert theirs.created and theirs.version.version_id != first.version.version_id
    assert theirs.version.content_sha256 == first.version.content_sha256
    assert len(w["s3"].objects) == 1  # the same bytes are one object


def test_a_scale_child_writes_two_decimals_and_says_what_it_achieved(
    session: Session, world: dict[str, Any], owner_rows: None
) -> None:
    w = world
    d = definition(
        w["predictor"],
        dimension_id="ochota_platit",
        kind=MaterializedKind.SCALE_1_10,
        target=6.2,
        range=(1.0, 10.0),
    )
    child = materialize(session, w, d)
    column = parse_panel(w["store"].read(child.version.storage_location)).column("ochota_platit")
    assert all(cell is not None and len(cell.split(".")[1]) == 2 for cell in column)
    assert 1.0 <= child.achieved <= 10.0 and child.target == 6.2


def test_a_predictor_or_a_name_the_base_refuses_is_refused_before_anything_is_written(
    session: Session, world: dict[str, Any], owner_rows: None
) -> None:
    w = world
    assert w["refused"]
    with pytest.raises(DerivationRefused) as policy:
        materialize(session, w, definition(w["refused"][0]))
    assert policy.value.reason == "predictor_not_permitted"
    with pytest.raises(DerivationRefused) as taken:
        materialize(session, w, definition(w["predictor"], dimension_id=w["predictor"]))
    assert taken.value.reason == "name_taken"
    assert w["s3"].puts == 0


def test_a_child_is_never_made_from_an_owned_version(
    session: Session, world: dict[str, Any], owner_rows: None
) -> None:
    from aia_core.domain.population import OwnedVersionNotShared

    w = world
    child = materialize(session, w, definition(w["predictor"]))
    with pytest.raises(OwnedVersionNotShared):
        runtime(session, w).materialize_child(
            base_version_id=child.version.version_id,
            definition=definition(w["predictor"], dimension_id="druha"),
            owner=OURS,
            store=w["store"],
            actor_id="USR-researcher",
        )


@pytest.fixture
def owner_rows(session: Session) -> None:
    """The two owners' organization and client rows, which the version's foreign keys need."""
    from aia_core.infrastructure.tables import ClientRow, OrganizationRow

    for owner in (OURS, THEIRS):
        session.add(
            OrganizationRow(
                organization_id=owner.organization_id,
                slug=owner.organization_id.lower(),
                name=owner.organization_id,
            )
        )
        session.flush()
        session.add(
            ClientRow(
                client_id=owner.client_id,
                organization_id=owner.organization_id,
                slug=owner.client_id.lower(),
                name=owner.client_id,
            )
        )
    session.flush()
