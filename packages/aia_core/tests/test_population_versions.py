"""Dataset identity, lineage, STATIC/LIVE roles and explicit promotion.

Pure-domain tests: no database, no files. The lineage used throughout mirrors the
preserved population -- a root (``v17_0_BASE``), a static reference built from it
(``v17_1_2``) and a live version built from that (``v17_4_0``) -- but with synthetic
hashes, so nothing here depends on the withheld archive.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from aia_core.domain.population import (
    DatasetVersion,
    LineageError,
    Population,
    PopulationKind,
    PopulationNotEstablished,
    PromotionConflict,
    PromotionRecord,
    PromotionRefused,
    StaticReferenceImmutable,
    UnknownDatasetVersion,
    VersionNotRuntimeEligible,
    VersionStatus,
    ancestry,
    content_sha256,
    dataset_version_id,
    descends_from,
    is_sha256,
    plan_establish,
    plan_promotion,
    require_runtime_eligible,
    version_status,
)

DATASET = "cz_synthetic_population"
AT = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
DICT_SHA = content_sha256(b"dictionary")
NAMES_SHA = content_sha256(b"names")


def make_version(label: str, parent: DatasetVersion | None = None) -> DatasetVersion:
    sha = content_sha256(label.encode())
    return DatasetVersion(
        version_id=dataset_version_id(DATASET, sha),
        dataset_id=DATASET,
        label=label,
        content_sha256=sha,
        byte_size=100,
        row_count=10,
        column_count=5,
        contract_id="test-contract",
        dictionary_sha256=DICT_SHA,
        field_names_sha256=NAMES_SHA,
        parent_version_id=parent.version_id if parent else None,
        storage_location=f"mem://{label}",
        dictionary_location="mem://dictionary",
        provenance="synthetic",
        imported_at=AT,
        imported_by="importer",
    )


@pytest.fixture
def lineage() -> dict[str, DatasetVersion]:
    base = make_version("v17_0_BASE")
    static = make_version("v17_1_2", base)
    live = make_version("v17_4_0", static)
    return {"base": base, "static": static, "live": live}


@pytest.fixture
def versions(lineage: dict[str, DatasetVersion]) -> dict[str, DatasetVersion]:
    return {v.version_id: v for v in lineage.values()}


def establish(
    kind: PopulationKind,
    version: DatasetVersion,
    versions: dict[str, DatasetVersion],
    populations: list[Population],
    *,
    population_id: str | None = None,
) -> tuple[Population, PromotionRecord]:
    return plan_establish(
        population_id=population_id or f"CZ_{kind.value}",
        kind=kind,
        version=version,
        versions=versions,
        populations=populations,
        static_label="v17_1_2",
        actor_id="data-owner",
        reason="initial establishment",
        at=AT,
    )


@pytest.fixture
def established(
    lineage: dict[str, DatasetVersion], versions: dict[str, DatasetVersion]
) -> tuple[Population, Population, list[PromotionRecord]]:
    static, r1 = establish(PopulationKind.STATIC, lineage["static"], versions, [])
    live, r2 = establish(PopulationKind.LIVE, lineage["live"], versions, [static])
    return static, live, [r1, r2]


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #


def test_version_id_is_derived_from_content() -> None:
    sha = content_sha256(b"panel bytes")
    assert dataset_version_id(DATASET, sha) == f"{DATASET}@sha256:{sha[:16]}"
    assert dataset_version_id(DATASET, sha) == dataset_version_id(DATASET, sha)


def test_different_bytes_are_different_versions() -> None:
    a = dataset_version_id(DATASET, content_sha256(b"a"))
    b = dataset_version_id(DATASET, content_sha256(b"b"))
    assert a != b


def test_version_id_rejects_a_non_digest() -> None:
    with pytest.raises(ValueError, match="sha256"):
        dataset_version_id(DATASET, "v17_4_0")
    with pytest.raises(ValueError, match="sha256"):
        dataset_version_id(DATASET, "A" * 64)  # uppercase is not canonical
    with pytest.raises(ValueError, match="dataset_id"):
        dataset_version_id("", content_sha256(b"x"))


def test_is_sha256() -> None:
    assert is_sha256(content_sha256(b""))
    assert not is_sha256("abc")
    assert not is_sha256("g" * 64)


def test_a_version_whose_id_does_not_match_its_content_is_unrepresentable(
    lineage: dict[str, DatasetVersion],
) -> None:
    with pytest.raises(ValueError, match="derived"):
        replace(lineage["live"], content_sha256=content_sha256(b"other bytes"))


def test_a_version_cannot_be_its_own_parent(lineage: dict[str, DatasetVersion]) -> None:
    live = lineage["live"]
    with pytest.raises(ValueError, match="own parent"):
        replace(live, parent_version_id=live.version_id)


@pytest.mark.parametrize("field", ["label", "contract_id", "storage_location", "imported_by"])
def test_a_version_requires_its_identity_fields(
    lineage: dict[str, DatasetVersion], field: str
) -> None:
    with pytest.raises(ValueError, match=field):
        replace(lineage["live"], **{field: ""})


@pytest.mark.parametrize("field", ["byte_size", "row_count", "column_count"])
def test_a_version_requires_positive_counts(lineage: dict[str, DatasetVersion], field: str) -> None:
    with pytest.raises(ValueError, match=field):
        replace(lineage["live"], **{field: 0})


def test_a_version_requires_an_aware_timestamp(lineage: dict[str, DatasetVersion]) -> None:
    with pytest.raises(ValueError, match="timezone"):
        replace(lineage["live"], imported_at=datetime(2026, 9, 22))


def test_a_version_is_immutable(lineage: dict[str, DatasetVersion]) -> None:
    with pytest.raises(AttributeError):
        lineage["live"].label = "v99"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Lineage
# --------------------------------------------------------------------------- #


def test_ancestry_walks_to_the_root(
    lineage: dict[str, DatasetVersion], versions: dict[str, DatasetVersion]
) -> None:
    chain = ancestry(lineage["live"].version_id, versions)
    assert chain == (
        lineage["live"].version_id,
        lineage["static"].version_id,
        lineage["base"].version_id,
    )


def test_descends_from_is_strict(
    lineage: dict[str, DatasetVersion], versions: dict[str, DatasetVersion]
) -> None:
    live, static, base = (lineage[k].version_id for k in ("live", "static", "base"))
    assert descends_from(live, static, versions)
    assert descends_from(live, base, versions)
    assert not descends_from(static, live, versions)
    assert not descends_from(live, live, versions)


def test_ancestry_refuses_a_dangling_parent(lineage: dict[str, DatasetVersion]) -> None:
    only_live = {lineage["live"].version_id: lineage["live"]}
    with pytest.raises(LineageError, match="not registered"):
        ancestry(lineage["live"].version_id, only_live)


def test_ancestry_refuses_an_unknown_start(versions: dict[str, DatasetVersion]) -> None:
    with pytest.raises(UnknownDatasetVersion):
        ancestry("cz_synthetic_population@sha256:0000000000000000", versions)


def test_ancestry_refuses_a_cycle(lineage: dict[str, DatasetVersion]) -> None:
    base = replace(lineage["base"], parent_version_id=lineage["live"].version_id)
    cyclic = {v.version_id: v for v in (base, lineage["static"], lineage["live"])}
    with pytest.raises(LineageError, match="cycle"):
        ancestry(lineage["live"].version_id, cyclic)


# --------------------------------------------------------------------------- #
# Establishment
# --------------------------------------------------------------------------- #


def test_static_is_established_with_the_declared_label(
    lineage: dict[str, DatasetVersion], versions: dict[str, DatasetVersion]
) -> None:
    static, record = establish(PopulationKind.STATIC, lineage["static"], versions, [])
    assert static.kind is PopulationKind.STATIC
    assert static.current_version_id == lineage["static"].version_id
    assert record.from_version_id is None
    assert record.to_version_id == lineage["static"].version_id


@pytest.mark.parametrize("label", ["base", "live"])
def test_static_refuses_any_other_version(
    lineage: dict[str, DatasetVersion], versions: dict[str, DatasetVersion], label: str
) -> None:
    with pytest.raises(StaticReferenceImmutable):
        establish(PopulationKind.STATIC, lineage[label], versions, [])


def test_live_requires_the_static_population_first(
    lineage: dict[str, DatasetVersion], versions: dict[str, DatasetVersion]
) -> None:
    with pytest.raises(PopulationNotEstablished):
        establish(PopulationKind.LIVE, lineage["live"], versions, [])


def test_live_may_not_be_the_static_reference(
    lineage: dict[str, DatasetVersion], versions: dict[str, DatasetVersion]
) -> None:
    static, _ = establish(PopulationKind.STATIC, lineage["static"], versions, [])
    with pytest.raises(StaticReferenceImmutable):
        establish(PopulationKind.LIVE, lineage["static"], versions, [static])


def test_live_must_descend_from_the_static_reference(
    lineage: dict[str, DatasetVersion], versions: dict[str, DatasetVersion]
) -> None:
    static, _ = establish(PopulationKind.STATIC, lineage["static"], versions, [static_dummy()])
    with pytest.raises(LineageError, match="descend"):
        establish(PopulationKind.LIVE, lineage["base"], versions, [static])


def static_dummy() -> Population:
    # A population of a different dataset, to prove the rules are per dataset.
    return Population(
        population_id="OTHER_STATIC",
        dataset_id="other_dataset",
        kind=PopulationKind.STATIC,
        current_version_id="other_dataset@sha256:0000000000000000",
        established_at=AT,
        established_by="x",
    )


def test_a_population_is_established_once(
    lineage: dict[str, DatasetVersion],
    versions: dict[str, DatasetVersion],
    established: tuple[Population, Population, list[PromotionRecord]],
) -> None:
    static, live, _ = established
    with pytest.raises(PromotionRefused, match="already established"):
        establish(PopulationKind.STATIC, lineage["static"], versions, [static, live])


def test_one_static_per_dataset(
    lineage: dict[str, DatasetVersion],
    versions: dict[str, DatasetVersion],
    established: tuple[Population, Population, list[PromotionRecord]],
) -> None:
    static, live, _ = established
    with pytest.raises(PromotionRefused, match="already has a STATIC"):
        establish(
            PopulationKind.STATIC,
            lineage["static"],
            versions,
            [static, live],
            population_id="SECOND_STATIC",
        )


def test_establishing_requires_actor_and_reason(
    lineage: dict[str, DatasetVersion], versions: dict[str, DatasetVersion]
) -> None:
    for actor, reason in (("", "why"), ("who", "  ")):
        with pytest.raises(PromotionRefused):
            plan_establish(
                population_id="CZ_STATIC",
                kind=PopulationKind.STATIC,
                version=lineage["static"],
                versions=versions,
                populations=[],
                static_label="v17_1_2",
                actor_id=actor,
                reason=reason,
                at=AT,
            )


def test_establishing_refuses_an_unregistered_version(lineage: dict[str, DatasetVersion]) -> None:
    with pytest.raises(UnknownDatasetVersion):
        establish(PopulationKind.STATIC, lineage["static"], {}, [])


# --------------------------------------------------------------------------- #
# Promotion
# --------------------------------------------------------------------------- #


def promote(
    population: Population,
    target: DatasetVersion,
    versions: dict[str, DatasetVersion],
    populations: list[Population],
    *,
    expected: str | None = None,
) -> tuple[Population, PromotionRecord]:
    return plan_promotion(
        population=population,
        target_version_id=target.version_id,
        expected_current_version_id=expected or population.current_version_id,
        versions=versions,
        populations=populations,
        actor_id="data-owner",
        reason="approved calibration",
        at=AT,
    )


def test_live_promotion_moves_the_pointer_and_records_history(
    lineage: dict[str, DatasetVersion],
    versions: dict[str, DatasetVersion],
    established: tuple[Population, Population, list[PromotionRecord]],
) -> None:
    static, live, history = established
    newer = make_version("v17_5_0", lineage["live"])
    versions[newer.version_id] = newer

    promoted, record = promote(live, newer, versions, [static, live])

    assert promoted.current_version_id == newer.version_id
    assert record.from_version_id == lineage["live"].version_id
    assert record.to_version_id == newer.version_id
    # The original is untouched: promotion returns a new value.
    assert live.current_version_id == lineage["live"].version_id

    populations = [static, promoted]
    records = [*history, record]
    assert version_status(newer.version_id, populations, records) is VersionStatus.LIVE_CURRENT
    assert (
        version_status(lineage["live"].version_id, populations, records) is VersionStatus.SUPERSEDED
    )


def test_static_has_no_promotion_path(
    lineage: dict[str, DatasetVersion],
    versions: dict[str, DatasetVersion],
    established: tuple[Population, Population, list[PromotionRecord]],
) -> None:
    static, live, _ = established
    with pytest.raises(StaticReferenceImmutable):
        promote(static, lineage["live"], versions, [static, live])


def test_promotion_is_compare_and_set(
    lineage: dict[str, DatasetVersion],
    versions: dict[str, DatasetVersion],
    established: tuple[Population, Population, list[PromotionRecord]],
) -> None:
    static, live, _ = established
    newer = make_version("v17_5_0", lineage["live"])
    versions[newer.version_id] = newer
    with pytest.raises(PromotionConflict):
        promote(live, newer, versions, [static, live], expected=lineage["static"].version_id)


def test_promotion_refuses_a_no_op(
    lineage: dict[str, DatasetVersion],
    versions: dict[str, DatasetVersion],
    established: tuple[Population, Population, list[PromotionRecord]],
) -> None:
    static, live, _ = established
    with pytest.raises(PromotionRefused, match="already current"):
        promote(live, lineage["live"], versions, [static, live])


def test_promotion_refuses_the_static_reference(
    lineage: dict[str, DatasetVersion],
    versions: dict[str, DatasetVersion],
    established: tuple[Population, Population, list[PromotionRecord]],
) -> None:
    static, live, _ = established
    with pytest.raises(StaticReferenceImmutable):
        promote(live, lineage["static"], versions, [static, live])


def test_promotion_refuses_a_target_outside_the_static_lineage(
    lineage: dict[str, DatasetVersion],
    versions: dict[str, DatasetVersion],
    established: tuple[Population, Population, list[PromotionRecord]],
) -> None:
    static, live, _ = established
    sibling = make_version("v17_1_2_fork", lineage["base"])
    versions[sibling.version_id] = sibling
    with pytest.raises(LineageError, match="descend"):
        promote(live, sibling, versions, [static, live])
    with pytest.raises(LineageError, match="descend"):
        promote(live, lineage["base"], versions, [static, live])


def test_promotion_refuses_an_unregistered_target(
    lineage: dict[str, DatasetVersion],
    versions: dict[str, DatasetVersion],
    established: tuple[Population, Population, list[PromotionRecord]],
) -> None:
    static, live, _ = established
    with pytest.raises(UnknownDatasetVersion):
        promote(live, make_version("never_imported", lineage["live"]), versions, [static, live])


def test_promotion_refuses_another_dataset(
    lineage: dict[str, DatasetVersion],
    versions: dict[str, DatasetVersion],
    established: tuple[Population, Population, list[PromotionRecord]],
) -> None:
    static, live, _ = established
    sha = content_sha256(b"foreign")
    foreign = replace(
        lineage["live"],
        dataset_id="other_dataset",
        version_id=dataset_version_id("other_dataset", sha),
        content_sha256=sha,
    )
    versions[foreign.version_id] = foreign
    with pytest.raises(PromotionRefused, match="belongs to"):
        promote(live, foreign, versions, [static, live])


def test_promotion_requires_actor_and_reason(
    lineage: dict[str, DatasetVersion],
    versions: dict[str, DatasetVersion],
    established: tuple[Population, Population, list[PromotionRecord]],
) -> None:
    static, live, _ = established
    newer = make_version("v17_5_0", lineage["live"])
    versions[newer.version_id] = newer
    with pytest.raises(PromotionRefused, match="reason"):
        plan_promotion(
            population=live,
            target_version_id=newer.version_id,
            expected_current_version_id=live.current_version_id,
            versions=versions,
            populations=[static, live],
            actor_id="data-owner",
            reason="",
            at=AT,
        )


# --------------------------------------------------------------------------- #
# Status and runtime eligibility
# --------------------------------------------------------------------------- #


def test_version_status_distinguishes_all_three_preserved_roles(
    lineage: dict[str, DatasetVersion],
    established: tuple[Population, Population, list[PromotionRecord]],
) -> None:
    static, live, history = established
    pops = [static, live]
    assert (
        version_status(lineage["static"].version_id, pops, history)
        is VersionStatus.STATIC_REFERENCE
    )
    assert version_status(lineage["live"].version_id, pops, history) is VersionStatus.LIVE_CURRENT
    assert version_status(lineage["base"].version_id, pops, history) is VersionStatus.REGISTERED


def test_the_lineage_root_is_not_runtime_eligible(
    lineage: dict[str, DatasetVersion],
    established: tuple[Population, Population, list[PromotionRecord]],
) -> None:
    static, live, history = established
    base_id = lineage["base"].version_id
    status = version_status(base_id, [static, live], history)
    with pytest.raises(VersionNotRuntimeEligible):
        require_runtime_eligible(base_id, status)


@pytest.mark.parametrize(
    "status",
    [VersionStatus.STATIC_REFERENCE, VersionStatus.LIVE_CURRENT, VersionStatus.SUPERSEDED],
)
def test_bound_versions_are_runtime_eligible(status: VersionStatus) -> None:
    require_runtime_eligible("v", status)
    assert status.runtime_eligible
