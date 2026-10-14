"""A run can load an owned child (population-operations P4e1).

Over the fictional population in ``conftest.py``, established STATIC and LIVE: a child
materialized over LIVE resolves for its own organization (``resolve_child``, pinned) and loads
through the one loader, which verifies the base by its own contract and the child by its
extension -- the base's columns cell for cell, the added ones by their kind. The added field
answers ``decide`` with the fixed M3 policy. Another organization's child is unknown, and a
child whose bytes or added values were altered is refused.
"""

from __future__ import annotations

import gzip
import io
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.application.population import PopulationRuntime
from aia_core.domain.population import (
    MaterializedKind,
    PopulationKind,
    PopulationView,
    ResolutionMode,
    UnknownDatasetVersion,
    VersionIntegrityError,
    VersionOwner,
)
from aia_core.domain.population.definition import (
    DimensionDefinition,
    EvidenceAnchor,
    MissingnessRule,
    PredictorSpec,
)
from aia_core.domain.population.policy import FieldUse
from aia_core.infrastructure.population_parser import parse_panel, write_panel
from aia_core.infrastructure.population_store import RoutingPopulationSource, S3PopulationStore
from aia_core.infrastructure.tables import ClientRow, OrganizationRow

OURS = VersionOwner(organization_id="ORG-ours", client_id="CLI-ours")


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

    return PopulationAuthority(
        PopulationOperatorConfig.from_names({"op": ("POPULATION_ESTABLISH",)})
    ).operator_context(AuthenticatedPrincipal(user_id="op", organization_id="platform"))


@pytest.fixture
def child(session: Session, synthetic_population: Any) -> dict[str, Any]:
    pop = synthetic_population
    session.add(OrganizationRow(organization_id=OURS.organization_id, slug="ours", name="O"))
    session.flush()
    session.add(
        ClientRow(
            client_id=OURS.client_id, organization_id=OURS.organization_id, slug="c", name="C"
        )
    )
    session.flush()
    s3 = _FakeS3()
    store = S3PopulationStore("pop-bucket", region_name="eu-central-1", client=s3)
    runtime = PopulationRuntime(
        session, contract=pop.contract, source=RoutingPopulationSource(pop.source, store)
    )
    versions = {
        label: runtime.import_version(
            label=label,
            panel_location=pop.location(label),
            dictionary_location=pop.dictionary_location,
            provenance="fictional",
            imported_by="importer",
        )
        for label in ("v1_BASE", "v1_1", "v1_4")
    }
    for pid, kind, label in (
        ("SYN_STATIC", PopulationKind.STATIC, "v1_1"),
        ("SYN_LIVE", PopulationKind.LIVE, "v1_4"),
    ):
        runtime.establish(
            population_id=pid,
            kind=kind,
            version_id=versions[label].version_id,
            operator=_operator(),
            reason="fictional",
        )
    made = runtime.materialize_child(
        base_version_id=versions["v1_4"].version_id,
        definition=DimensionDefinition(
            dimension_id="pije_kavu_rano",
            version=1,
            construct="morning coffee",
            label="Pije kávu ráno",
            kind=MaterializedKind.BINARY,
            target=0.4,
            evidence=EvidenceAnchor("KNW-fictional", 1, "40 %"),
            predictors=(PredictorSpec("vek"),),
            missingness=MissingnessRule.PREDICTOR_MEAN,
            range=(0.0, 1.0),
        ),
        owner=OURS,
        store=store,
        actor_id="USR-researcher",
    )
    return {
        "runtime": runtime,
        "child": made.version,
        "base": versions["v1_4"],
        "s3": s3,
        "contract": pop.contract,
        "source": RoutingPopulationSource(pop.source, store),
    }


def test_a_child_resolves_for_its_organization_and_loads_with_its_added_field(
    child: dict[str, Any],
) -> None:
    runtime = child["runtime"]
    binding = runtime.resolve_child(
        child["child"].version_id, organization_id=OURS.organization_id, view=PopulationView.BASE
    )
    assert binding.resolution is ResolutionMode.PINNED and binding.population_id is None
    assert binding.version_id == child["child"].version_id
    loaded = runtime.load(binding)
    assert "pije_kavu_rano" in loaded.fields
    assert set(loaded.column("pije_kavu_rano")) <= {"0", "1"}
    assert loaded.decide("pije_kavu_rano", FieldUse.PERSONA_CONSTRUCTION).allowed
    assert not loaded.decide("pije_kavu_rano", FieldUse.CLIENT_MEASURED_CLAIM).allowed
    # The base's fields read as the base's.
    base = runtime.load(runtime.resolve(_live(), view=PopulationView.BASE))
    assert loaded.column("vek") == base.column("vek")


def test_another_organizations_child_is_unknown(child: dict[str, Any]) -> None:
    with pytest.raises(UnknownDatasetVersion):
        child["runtime"].resolve_child(child["child"].version_id, organization_id="ORG-theirs")
    with pytest.raises(UnknownDatasetVersion):  # a shared version is not a child
        child["runtime"].resolve_child(
            child["base"].version_id, organization_id=OURS.organization_id
        )


def test_a_child_whose_added_values_are_not_its_kinds_or_whose_bytes_moved_is_refused(
    session: Session, child: dict[str, Any]
) -> None:
    from dataclasses import replace

    from aia_core.domain.population import content_sha256, owned_version_id
    from aia_core.infrastructure.population_repository import PopulationRegistryRepository

    runtime, version, s3 = child["runtime"], child["child"], child["s3"]
    registry = PopulationRegistryRepository(session)
    key = next(iter(s3.objects))
    panel = parse_panel(s3.objects[key])
    # A well-formed child in every respect but its values: a binary field holding 7.
    altered = write_panel(panel.header, (*panel.columns[:-1], ("7",) * panel.row_count))
    sha = content_sha256(altered)
    s3.objects[f"materialized/altered/{sha}.csv.gz"] = altered
    bad = replace(
        version,
        version_id=owned_version_id(version.dataset_id, sha, OURS),
        label=version.label + "-altered",
        content_sha256=sha,
        byte_size=len(altered),
        storage_location=f"s3://pop-bucket/materialized/altered/{sha}.csv.gz",
    )
    registry.insert_version(bad, validation={})
    binding = runtime.resolve_child(
        bad.version_id, organization_id=OURS.organization_id, view=PopulationView.BASE
    )
    with pytest.raises(VersionIntegrityError, match="cannot"):
        runtime.load(binding)
    # A child whose base column is not the base's, cell for cell.
    vek = panel.header.index("vek")
    moved = list(panel.columns)
    moved[vek] = tuple("99" for _ in moved[vek])
    shifted = write_panel(panel.header, tuple(moved))
    sha2 = content_sha256(shifted)
    s3.objects[f"materialized/shifted/{sha2}.csv.gz"] = shifted
    other = replace(
        version,
        version_id=owned_version_id(version.dataset_id, sha2, OURS),
        label=version.label + "-shifted",
        content_sha256=sha2,
        byte_size=len(shifted),
        storage_location=f"s3://pop-bucket/materialized/shifted/{sha2}.csv.gz",
    )
    registry.insert_version(other, validation={})
    with pytest.raises(VersionIntegrityError, match="rows and columns"):
        runtime.load(
            runtime.resolve_child(
                other.version_id, organization_id=OURS.organization_id, view=PopulationView.BASE
            )
        )
    # Bytes that no longer hash to the child's pin are refused before they are read.
    good = runtime.resolve_child(
        version.version_id, organization_id=OURS.organization_id, view=PopulationView.BASE
    )
    s3.objects[key] = gzip.compress(b"row_id\n", mtime=0)
    fresh = PopulationRuntime(session, contract=child["contract"], source=child["source"])
    with pytest.raises(VersionIntegrityError, match="swapped or altered"):
        fresh.load(good)


def _live() -> Any:
    from aia_core.domain.population import PopulationSelector

    return PopulationSelector.population("SYN_LIVE")
