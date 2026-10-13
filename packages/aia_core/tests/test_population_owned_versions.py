"""An owned child version in storage, seen by its organization only (population-operations P4c).

Against the ``session`` fixture (PostgreSQL when ``DATABASE_URL`` is set, else SQLite): an owned
child stores and reads back with its owner and extension; two clients' identical children are two
versions; the registry's reads return the shared versions plus only the asking organization's
own, and the import's lookups see shared versions alone; the database refuses a half-owned row;
an extension is kept once and refused when it no longer hashes to its key; and a version's
characteristics, for its own organization, carry the added fields with the fixed M3 policy.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aia_core.application.population import PopulationRuntime
from aia_core.application.population_characteristics import version_characteristics
from aia_core.domain.population import (
    DatasetVersion,
    MaterializedField,
    MaterializedKind,
    PopulationContractExtension,
    UnknownDatasetVersion,
    VersionIntegrityError,
    VersionOwner,
    content_sha256,
    dataset_version_id,
    owned_version_id,
)
from aia_core.domain.population.derivation import (
    DERIVATION_METHOD_ID,
    DERIVATION_METHOD_VERSION,
)
from aia_core.domain.population.policy import FieldUse
from aia_core.infrastructure.population_repository import PopulationRegistryRepository
from aia_core.infrastructure.tables import (
    PopulationContractExtensionRow,
    PopulationDatasetVersionRow,
)

DATASET = "synthetic_population"
AT = datetime(2026, 10, 12, 15, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Owners:
    ours: VersionOwner
    our_other_client: VersionOwner
    theirs: VersionOwner


@pytest.fixture
def owners(session: Session, scoped: Any) -> Owners:
    """Our organization's two clients, and a client of another organization."""
    from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
    from aia_core.infrastructure.scope_repository import ScopeRepository

    repo = ScopeRepository(session)
    org, owner = repo.create_organization(
        slug="elsewhere", name="Elsewhere", owner_email="owner@elsewhere.test", owner_name="O"
    )
    admin = ScopeResolver(session).organization_context(
        AuthenticatedPrincipal(user_id=owner.user_id, organization_id=org.organization_id)
    )
    theirs = repo.create_client(admin, slug="theirs", name="Their client")
    session.flush()
    return Owners(
        ours=VersionOwner(scoped.organization_id, scoped.clients["primary"].client_id),
        our_other_client=VersionOwner(scoped.organization_id, scoped.clients["other"].client_id),
        theirs=VersionOwner(org.organization_id, theirs.client_id),
    )


def _extension(base: DatasetVersion, name: str = "pije_kavu_rano") -> PopulationContractExtension:
    return PopulationContractExtension(
        base_contract_id=base.contract_id,
        base_field_names_sha256=base.field_names_sha256,
        base_dictionary_sha256=base.dictionary_sha256,
        fields=(
            MaterializedField(
                name=name,
                kind=MaterializedKind.BINARY,
                definition_sha256=content_sha256(b"fictional definition: " + name.encode()),
                method_id=DERIVATION_METHOD_ID,
                method_version=DERIVATION_METHOD_VERSION,
            ),
        ),
    )


def _child(
    base: DatasetVersion,
    owner: VersionOwner,
    extension: PopulationContractExtension,
    *,
    content: bytes = b"fictional child panel",
    label: str = "v1_BASE+pije_kavu_rano",
) -> DatasetVersion:
    sha = content_sha256(content)
    return DatasetVersion(
        version_id=owned_version_id(base.dataset_id, sha, owner),
        dataset_id=base.dataset_id,
        label=label,
        content_sha256=sha,
        byte_size=len(content),
        row_count=base.row_count,
        column_count=base.column_count + len(extension.fields),
        contract_id=base.contract_id,
        dictionary_sha256=base.dictionary_sha256,
        field_names_sha256=content_sha256(b"fictional child field names"),
        parent_version_id=base.version_id,
        storage_location=f"materialized/{label}.csv.gz",
        dictionary_location=base.dictionary_location,
        provenance="fictional materialized child",
        imported_at=AT,
        imported_by="USR-researcher",
        owner=owner,
        extension_sha256=extension.sha256,
    )


def _base(content: bytes = b"fictional base panel") -> DatasetVersion:
    sha = content_sha256(content)
    return DatasetVersion(
        version_id=dataset_version_id(DATASET, sha),
        dataset_id=DATASET,
        label="v1_BASE",
        content_sha256=sha,
        byte_size=len(content),
        row_count=6,
        column_count=6,
        contract_id="synthetic_population/v1",
        dictionary_sha256=content_sha256(b"d"),
        field_names_sha256=content_sha256(b"n"),
        parent_version_id=None,
        storage_location="panels/v1_BASE.csv.gz",
        dictionary_location="dictionary.csv",
        provenance="synthetic",
        imported_at=AT,
        imported_by="importer",
    )


def _store(registry: PopulationRegistryRepository, *versions: DatasetVersion) -> None:
    for v in versions:
        if v.extension_sha256 is not None and registry.extension(v.extension_sha256) is None:
            raise AssertionError("store the extension first")
        registry.insert_version(v, validation={})


# --------------------------------------------------------------------------- storage


def test_an_owned_child_stores_and_reads_back_with_its_owner_and_extension(
    session: Session, owners: Owners
) -> None:
    registry = PopulationRegistryRepository(session)
    base = _base()
    extension = _extension(base)
    registry.insert_version(base, validation={})
    registry.insert_extension(extension, recorded_at=AT, recorded_by="USR-researcher")
    child = _child(base, owners.ours, extension)
    _store(registry, child)
    assert registry.get_version(child.version_id) == child
    assert registry.extension(extension.sha256) == extension
    # Insert-once: the same extension again is the one already kept, not a second row.
    registry.insert_extension(extension, recorded_at=AT, recorded_by="someone else")
    assert session.query(PopulationContractExtensionRow).count() == 1


def test_two_clients_identical_children_are_two_versions(session: Session, owners: Owners) -> None:
    registry = PopulationRegistryRepository(session)
    base = _base()
    extension = _extension(base)
    registry.insert_version(base, validation={})
    registry.insert_extension(extension, recorded_at=AT, recorded_by="USR-researcher")
    ours, mine_too, theirs = (
        _child(base, owners.ours, extension),
        _child(base, owners.our_other_client, extension),
        _child(base, owners.theirs, extension),
    )
    _store(registry, ours, mine_too, theirs)
    assert len({ours.version_id, mine_too.version_id, theirs.version_id}) == 3
    # The same owner's same bytes stay one version.
    with pytest.raises(IntegrityError):
        registry.insert_version(replace(ours, label="another label"), validation={})
    session.rollback()


def test_one_owner_cannot_reuse_a_label_and_a_shared_label_stays_unique(
    session: Session, owners: Owners
) -> None:
    registry = PopulationRegistryRepository(session)
    base = _base()
    extension = _extension(base)
    registry.insert_version(base, validation={})
    registry.insert_extension(extension, recorded_at=AT, recorded_by="USR-researcher")
    _store(registry, _child(base, owners.ours, extension))
    # Another owner may use the same label; the same owner may not.
    _store(registry, _child(base, owners.theirs, extension))
    with pytest.raises(IntegrityError):
        registry.insert_version(
            _child(base, owners.ours, extension, content=b"other bytes"), validation={}
        )
    session.rollback()


def test_the_registry_shows_a_child_to_its_organization_only(
    session: Session, owners: Owners
) -> None:
    registry = PopulationRegistryRepository(session)
    base = _base()
    extension = _extension(base)
    registry.insert_version(base, validation={})
    registry.insert_extension(extension, recorded_at=AT, recorded_by="USR-researcher")
    ours, theirs = _child(base, owners.ours, extension), _child(base, owners.theirs, extension)
    _store(registry, ours, theirs)

    assert set(registry.versions(DATASET)) == {base.version_id}  # no organization: shared only
    assert set(registry.versions(DATASET, organization_id=owners.ours.organization_id)) == {
        base.version_id,
        ours.version_id,
    }
    assert set(registry.versions(DATASET, organization_id=owners.theirs.organization_id)) == {
        base.version_id,
        theirs.version_id,
    }
    ours_org = owners.ours.organization_id
    assert registry.visible_version(ours.version_id, organization_id=ours_org) == ours
    assert registry.visible_version(theirs.version_id, organization_id=ours_org) is None
    assert registry.visible_version(base.version_id, organization_id=ours_org) == base
    # The import's lookups see shared versions alone: a child's bytes or label is no import.
    assert registry.version_by_sha(ours.content_sha256) is None
    assert registry.version_by_label(DATASET, ours.label) is None
    assert registry.version_by_label(DATASET, base.label) == base


@pytest.mark.parametrize(
    "change",
    [
        {"owner_client_id": None},  # an organization without its client
        {"extension_sha256": None},  # an owner without what it adds
        {"parent_version_id": None},  # an owned version that is no child
    ],
)
def test_the_database_refuses_a_half_owned_version(
    session: Session, owners: Owners, change: dict[str, Any]
) -> None:
    registry = PopulationRegistryRepository(session)
    base = _base()
    extension = _extension(base)
    registry.insert_version(base, validation={})
    registry.insert_extension(extension, recorded_at=AT, recorded_by="USR-researcher")
    child = _child(base, owners.ours, extension)
    _store(registry, child)
    session.commit()
    with pytest.raises(IntegrityError):
        session.execute(
            update(PopulationDatasetVersionRow)
            .where(PopulationDatasetVersionRow.version_id == child.version_id)
            .values(**change)
        )
        session.flush()
    session.rollback()


def test_an_extension_that_no_longer_hashes_to_its_key_is_refused(
    session: Session, owners: Owners
) -> None:
    registry = PopulationRegistryRepository(session)
    extension = _extension(_base())
    registry.insert_extension(extension, recorded_at=AT, recorded_by="USR-researcher")
    tampered = extension.payload()
    tampered["fields"][0]["kind"] = MaterializedKind.SCALE_1_10.value
    session.execute(
        update(PopulationContractExtensionRow)
        .where(PopulationContractExtensionRow.extension_sha256 == extension.sha256)
        .values(payload=tampered)
    )
    with pytest.raises(VersionIntegrityError, match="does not hash to its key"):
        registry.extension(extension.sha256)
    assert registry.extension(content_sha256(b"never stored")) is None


# --------------------------------------------------------------------------- characteristics


@pytest.fixture
def imported(session: Any, synthetic_population: Any) -> tuple[Any, DatasetVersion]:
    pop = synthetic_population
    runtime = PopulationRuntime(session, contract=pop.contract, source=pop.source)
    version = runtime.import_version(
        label="v1_BASE",
        panel_location=pop.location("v1_BASE"),
        dictionary_location=pop.dictionary_location,
        provenance="fictional test bundle",
        imported_by="importer",
    )
    return pop, version


def test_a_childs_characteristics_carry_its_added_fields_for_its_organization_only(
    session: Session, owners: Owners, imported: tuple[Any, DatasetVersion]
) -> None:
    pop, base = imported
    registry = PopulationRegistryRepository(session)
    extension = _extension(base)
    registry.insert_extension(extension, recorded_at=AT, recorded_by="USR-researcher")
    child = _child(base, owners.ours, extension)
    _store(registry, child)

    found = version_characteristics(
        session,
        contract=pop.contract,
        version_id=child.version_id,
        organization_id=owners.ours.organization_id,
    )
    # The child keeps no dictionary of its own: its base's is read, re-hashed.
    assert found.dictionary_kept and found.dictionary_sha256 == base.dictionary_sha256
    assert (found.owner_client_id, found.extension_sha256) == (
        owners.ours.client_id,
        extension.sha256,
    )
    names = [f.field for f in found.fields]
    assert names[-1] == "pije_kavu_rano" and names[: len(pop.fields)] == list(pop.fields)
    added = {f.field: f for f in found.fields}["pije_kavu_rano"]
    assert added.materialized and added.block == "materialized"
    assert added.provenance_class == "MODELLED"
    allowed = {u.use: u.allowed for u in added.uses}
    assert allowed[FieldUse.PERSONA_CONSTRUCTION] and allowed[FieldUse.AUDIENCE_FILTERING]
    assert not allowed[FieldUse.CLIENT_MEASURED_CLAIM] and not allowed[FieldUse.WEIGHTING]
    assert not any(f.materialized for f in found.fields if f.field != "pije_kavu_rano")
    assert dict(found.blocks)["materialized"] == 1

    with pytest.raises(UnknownDatasetVersion):
        version_characteristics(
            session,
            contract=pop.contract,
            version_id=child.version_id,
            organization_id=owners.theirs.organization_id,
        )
    shared = version_characteristics(
        session,
        contract=pop.contract,
        version_id=base.version_id,
        organization_id=owners.theirs.organization_id,
    )
    assert shared.owner_client_id is None and not any(f.materialized for f in shared.fields)


# --------------------------------------------------------------------------- the operator


def test_an_operator_can_neither_establish_nor_promote_to_an_owned_child(
    session: Session, owners: Owners, synthetic_population: Any
) -> None:
    from aia_core.application.population_authority import (
        PopulationAuthority,
        PopulationOperatorConfig,
    )
    from aia_core.application.scope import AuthenticatedPrincipal
    from aia_core.domain.population import OwnedVersionNotShared, PopulationKind

    operator = PopulationAuthority(
        PopulationOperatorConfig.from_names(
            {"owner": ("POPULATION_ESTABLISH", "POPULATION_PROMOTE")}
        )
    ).operator_context(AuthenticatedPrincipal(user_id="owner", organization_id="platform"))
    pop = synthetic_population
    runtime = PopulationRuntime(session, contract=pop.contract, source=pop.source)
    imported = {
        label: runtime.import_version(
            label=label,
            panel_location=pop.location(label),
            dictionary_location=pop.dictionary_location,
            provenance="fictional test bundle",
            imported_by="importer",
        )
        for label in ("v1_BASE", "v1_1", "v1_4")
    }
    registry = PopulationRegistryRepository(session)
    extension = _extension(imported["v1_4"])
    registry.insert_extension(extension, recorded_at=AT, recorded_by="USR-researcher")
    child = _child(imported["v1_4"], owners.ours, extension)
    _store(registry, child)

    with pytest.raises(OwnedVersionNotShared):
        runtime.establish(
            population_id="SYN_LIVE",
            kind=PopulationKind.LIVE,
            version_id=child.version_id,
            operator=operator,
            reason="a client's dimension",
        )
    runtime.establish(
        population_id="SYN_STATIC",
        kind=PopulationKind.STATIC,
        version_id=imported["v1_1"].version_id,
        operator=operator,
        reason="anchor",
    )
    live = runtime.establish(
        population_id="SYN_LIVE",
        kind=PopulationKind.LIVE,
        version_id=imported["v1_4"].version_id,
        operator=operator,
        reason="runtime",
    )
    with pytest.raises(OwnedVersionNotShared) as refused:
        runtime.promote_live(
            operator=operator,
            population_id="SYN_LIVE",
            target_version_id=child.version_id,
            expected_current_version_id=live.current_version_id,
            reason="promote a client's dimension",
        )
    assert refused.value.reason == "owned_version"
