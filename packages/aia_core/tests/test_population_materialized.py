"""A materialized dimension as an owned child version (population-operations P4a).

Pure-domain tests, synthetic hashes. The owner's P4 decisions (2026-10-12): a child
``DatasetVersion`` extends a shared base by a hash-pinned extension (M1); its values are
modelled (M2); its uses are fixed (M3); it belongs to one organization and is never a
shared population's version (M5).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from aia_core.domain.population import (
    FIELD_POLICY_VERSION,
    DatasetVersion,
    FieldPolicy,
    FieldUse,
    MaterializedField,
    MaterializedKind,
    Obligation,
    OwnedVersionNotShared,
    PopulationContractExtension,
    PopulationKind,
    VersionIntegrityError,
    VersionOwner,
    check_child_version,
    content_sha256,
    dataset_version_id,
    field_names_fingerprint,
    materialized_policy_entry,
    owned_version_id,
    plan_establish,
    plan_promotion,
    with_materialized_fields,
)

DATASET = "cz_synthetic_population"
AT = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
DICT_SHA = content_sha256(b"dictionary")
BASE_NAMES = ("panel_row_id", "vek", "pohlavi", "kraj", "vaha_strukturalni_2025")
OWNER = VersionOwner(organization_id="ORG-a", client_id="CLI-a")
DEFINITION = content_sha256(b"fictional dimension definition: ranni kava")


def version(
    label: str,
    parent: DatasetVersion | None = None,
    *,
    names: tuple[str, ...] = BASE_NAMES,
    owner: VersionOwner | None = None,
    extension: PopulationContractExtension | None = None,
) -> DatasetVersion:
    sha = content_sha256(label.encode())
    return DatasetVersion(
        version_id=(
            dataset_version_id(DATASET, sha)
            if owner is None
            else owned_version_id(DATASET, sha, owner)
        ),
        dataset_id=DATASET,
        label=label,
        content_sha256=sha,
        byte_size=100,
        row_count=10,
        column_count=len(names),
        contract_id="test-contract",
        dictionary_sha256=DICT_SHA,
        field_names_sha256=field_names_fingerprint(names),
        parent_version_id=parent.version_id if parent else None,
        storage_location=f"mem://{label}",
        dictionary_location="mem://dictionary",
        provenance="synthetic",
        imported_at=AT,
        imported_by="importer",
        owner=owner,
        extension_sha256=extension.sha256 if extension else None,
    )


def field(name: str = "pije_kavu_rano", kind: MaterializedKind = MaterializedKind.BINARY):
    return MaterializedField(
        name=name,
        kind=kind,
        definition_sha256=DEFINITION,
        method_id="npc-18.6.6-evidence-overlay",
        method_version="1",
    )


def extension(*fields: MaterializedField) -> PopulationContractExtension:
    return PopulationContractExtension(
        base_contract_id="test-contract",
        base_field_names_sha256=field_names_fingerprint(BASE_NAMES),
        base_dictionary_sha256=DICT_SHA,
        fields=fields or (field(),),
    )


@pytest.fixture
def world() -> dict[str, object]:
    root = version("v17_0_BASE")
    static = version("v17_1_2", root)
    live = version("v17_4_0", static)
    ext = extension()
    child = version(
        "v17_4_0+pije_kavu_rano",
        live,
        names=ext.field_names(BASE_NAMES),
        owner=OWNER,
        extension=ext,
    )
    versions = {v.version_id: v for v in (root, static, live, child)}
    return {"static": static, "live": live, "child": child, "ext": ext, "versions": versions}


# --------------------------------------------------------------------------- extension


def test_the_extension_is_identified_by_its_content_and_reads_back() -> None:
    ext = extension()
    assert ext.sha256 == extension().sha256
    assert PopulationContractExtension.from_payload(ext.payload()) == ext
    other = extension(field(kind=MaterializedKind.SCALE_1_10))
    assert other.sha256 != ext.sha256
    with pytest.raises(VersionIntegrityError):
        PopulationContractExtension.from_payload({**ext.payload(), "contract": "other/v9"})
    with pytest.raises(VersionIntegrityError):
        PopulationContractExtension.from_payload({**ext.payload(), "fields": [{"name": "x"}]})


def test_the_childs_fields_are_the_bases_in_order_then_the_added_ones() -> None:
    ext = extension(field("a"), field("b"))
    assert ext.field_names(BASE_NAMES) == (*BASE_NAMES, "a", "b")
    with pytest.raises(VersionIntegrityError, match="not the field names"):
        ext.field_names(tuple(reversed(BASE_NAMES)))
    names = (*BASE_NAMES, "vek_2")
    shadowing = PopulationContractExtension(
        base_contract_id="test-contract",
        base_field_names_sha256=field_names_fingerprint(names),
        base_dictionary_sha256=DICT_SHA,
        fields=(field("vek"),),
    )
    with pytest.raises(VersionIntegrityError, match="replace a base field"):
        shadowing.field_names(names)


def test_a_field_and_an_extension_refuse_what_they_cannot_name() -> None:
    with pytest.raises(ValueError, match="lowercase"):
        field("Ranní káva")
    with pytest.raises(ValueError, match="method"):
        MaterializedField("x", MaterializedKind.BINARY, DEFINITION, "", "1")
    with pytest.raises(ValueError, match="once"):
        extension(field("x"), field("x"))


# --------------------------------------------------------------------------- policy (M3)


def test_a_materialized_field_serves_the_fixed_uses_and_never_a_measured_claim() -> None:
    policy = with_materialized_fields(FieldPolicy(FIELD_POLICY_VERSION, DICT_SHA, {}), extension())
    decide = policy.decide
    name = "pije_kavu_rano"
    for use in (
        FieldUse.PERSONA_CONSTRUCTION,
        FieldUse.AUDIENCE_FILTERING,
        FieldUse.SIMULATION,
        FieldUse.AGGREGATE_ANALYSIS,
    ):
        assert decide(name, use).allowed, use
    assert Obligation.DISCLOSE_MODELLED in decide(name, FieldUse.PERSONA_CONSTRUCTION).obligations
    modelled = decide(name, FieldUse.CLIENT_MODELLED_CLAIM)
    assert modelled.allowed
    assert {Obligation.DISCLOSE_MODELLED, Obligation.AGGREGATE_ONLY} <= modelled.obligations
    assert not decide(name, FieldUse.CLIENT_MEASURED_CLAIM).allowed
    assert not decide(name, FieldUse.WEIGHTING).allowed
    entry = materialized_policy_entry(field())
    assert not entry.provenance_class.is_measured
    assert entry.source == "materialized:npc-18.6.6-evidence-overlay@1"


def test_a_materialized_field_may_not_take_a_name_the_base_already_has() -> None:
    base = with_materialized_fields(FieldPolicy(FIELD_POLICY_VERSION, DICT_SHA, {}), extension())
    with pytest.raises(VersionIntegrityError, match="collides"):
        with_materialized_fields(base, extension())


# --------------------------------------------------------------------------- the owned child


def test_an_owned_version_names_its_owner_its_extension_and_its_parent(world: dict) -> None:
    live = world["live"]
    with pytest.raises(ValueError, match="organization and its client"):
        VersionOwner(organization_id="ORG-a", client_id="")
    with pytest.raises(ValueError, match="names its extension"):
        replace(live, owner=OWNER)
    with pytest.raises(ValueError, match="names its extension"):
        replace(live, extension_sha256=world["ext"].sha256)
    with pytest.raises(ValueError, match="is a child"):
        replace(world["child"], parent_version_id=None)
    assert live.shared and not world["child"].shared


def test_a_child_that_is_exactly_its_base_extended_is_accepted(world: dict) -> None:
    check_child_version(
        base=world["live"],
        child=world["child"],
        extension=world["ext"],
        base_field_names=BASE_NAMES,
    )


@pytest.mark.parametrize(
    ("change", "said"),
    [
        ({"parent_version_id": "cz_synthetic_population:0000000000000000"}, "parent"),
        ({"dictionary_sha256": content_sha256(b"other")}, "dictionary"),
        ({"row_count": 11}, "rows"),
        ({"column_count": 5}, "column count"),
        ({"field_names_sha256": field_names_fingerprint(BASE_NAMES)}, "followed by the added"),
        ({"extension_sha256": content_sha256(b"other extension")}, "another extension"),
        ({"contract_id": "other-contract"}, "different contracts"),
    ],
)
def test_a_child_that_differs_from_its_base_extended_is_refused(
    world: dict, change: dict, said: str
) -> None:
    child = replace(world["child"], **change)
    with pytest.raises(VersionIntegrityError, match=said):
        check_child_version(
            base=world["live"], child=child, extension=world["ext"], base_field_names=BASE_NAMES
        )


def test_an_owned_versions_id_is_its_content_qualified_by_its_owner(world: dict) -> None:
    child = world["child"]
    assert child.version_id.startswith(dataset_version_id(DATASET, child.content_sha256) + "~")
    assert OWNER.organization_id not in child.version_id and OWNER.client_id not in child.version_id
    # The same bytes held by another client are another version, never a collision.
    other = VersionOwner(organization_id="ORG-a", client_id="CLI-b")
    assert owned_version_id(DATASET, child.content_sha256, other) != child.version_id
    with pytest.raises(ValueError, match="qualified by its owner"):
        replace(child, owner=other)
    with pytest.raises(ValueError, match="qualified by its owner"):
        replace(child, version_id=dataset_version_id(DATASET, child.content_sha256))


def test_a_child_is_never_built_on_another_child(world: dict) -> None:
    ext = world["ext"]
    grandchild = version(
        "grandchild", world["child"], names=ext.field_names(BASE_NAMES), owner=OWNER, extension=ext
    )
    with pytest.raises(VersionIntegrityError, match="itself an owned version"):
        check_child_version(
            base=world["child"],
            child=grandchild,
            extension=world["ext"],
            base_field_names=BASE_NAMES,
        )


def test_an_owned_child_is_never_a_shared_populations_version(world: dict) -> None:
    versions = world["versions"]
    static, _ = plan_establish(
        population_id="CZ_STATIC",
        kind=PopulationKind.STATIC,
        version=world["static"],
        versions=versions,
        populations=[],
        static_label="v17_1_2",
        actor_id="data-owner",
        reason="initial",
        at=AT,
    )
    with pytest.raises(OwnedVersionNotShared):
        plan_establish(
            population_id="CZ_LIVE",
            kind=PopulationKind.LIVE,
            version=world["child"],
            versions=versions,
            populations=[static],
            static_label="v17_1_2",
            actor_id="data-owner",
            reason="a client's dimension",
            at=AT,
        )
    live, _ = plan_establish(
        population_id="CZ_LIVE",
        kind=PopulationKind.LIVE,
        version=world["live"],
        versions=versions,
        populations=[static],
        static_label="v17_1_2",
        actor_id="data-owner",
        reason="initial",
        at=AT,
    )
    with pytest.raises(OwnedVersionNotShared) as refused:
        plan_promotion(
            population=live,
            target_version_id=world["child"].version_id,
            expected_current_version_id=live.current_version_id,
            versions=versions,
            populations=[static, live],
            actor_id="data-owner",
            reason="promote a client's dimension",
            at=AT,
        )
    assert refused.value.reason == "owned_version"
