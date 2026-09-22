"""The Czech synthetic population import contract, v17.

Every value here is sourced, not chosen. Anchors are into
``AiAnalytics-AIA/AIA-reference`` @ ``678e298`` (tag
``reference-18.6.6-gemo-2026-09-11-v1``), which measured them from the
authoritative archive:

======================================  ===============================================
Value                                   Source
======================================  ===============================================
three versions, bytes, SHA256, lineage  ``data-import-contracts/czech-population.md``
                                        IDENTITY + LINEAGE; ``dataset-ledger.json``
18,766 rows x 400 columns               same, VALIDATION; ``DATA_CONTRACT_v17.json``
dictionary SHA256                       ``field-policy.json`` ``source_sha256``
ordered field-name fingerprint          computed from ``field-policy.json`` ``fields``
four weight roles                       ``golden-fixtures/F11`` ``declared_schemes``
two weight totals and tolerances        import contract VALIDATION; F11
7 enrichment + 1 weight runtime field   ``field-policy.json``
                                        ``runtime_columns_without_dictionary_entry``; F10
``occupation_isco08`` stays text        import contract, "Special parsing"; R9
companion set: hash, bytes, shape       ``dataset-ledger.json``; import contract
                                        VALIDATION; methodology M14; subsystem §9
joint certificate binds ``v17_4_0``      import contract VALIDATION; methodology M03
no ``D_`` / ``P_`` prefixes             import contract VALIDATION (``release_gate``)
======================================  ===============================================

The parity tier re-derives each of these from the reference repository and fails
if any drifts (``tests/test_population_reference_parity.py``).

What is deliberately **not** here: the 400 field names and their per-field
epistemic policy. They are detailed reference material; they arrive with the
panel as ``FIELD_DICTIONARY_v17_1.csv`` and are checked against the two hashes
below.

**Not asserted, because the reference did not assert it:** a population total for
``vaha_populace_2025_aprox`` or ``vaha_strana_2021_benchmark``, and whether the
two weight totals hold for ``v17_0_BASE`` and ``v17_1_2`` as well as ``v17_4_0``
(they were measured on ``v17_4_0``). The totals are applied to every import; if the
first real import of an earlier version fails them, that is a finding to record,
not a check to loosen.
"""

from __future__ import annotations

from typing import Final

from .companions import CompanionKind, CompanionSpec
from .contract import KnownVersion, PopulationImportContract, WeightScheme

__all__ = [
    "CZ_DATASET_ID",
    "CZ_LIVE",
    "CZ_STATIC_REFERENCE",
    "CZ_SYNTHETIC_V17",
]

CZ_DATASET_ID: Final = "cz_synthetic_population"

#: Population ids. The names are the reference's; the kinds are the product rule.
CZ_STATIC_REFERENCE: Final = "CZ_STATIC_REFERENCE"
CZ_LIVE: Final = "CZ_LIVE"

_K = CompanionKind

#: The companion set, from AIA-reference ``dataset-ledger.json`` (hash, bytes, rows,
#: columns, each recomputed from the authoritative archive) and the import
#: contract's VALIDATION table / methodology M14 (the shape checks). The first four
#: are the assets the import contract names; the rest are the ``DATA_CONTRACT``
#: companions that ``population-subsystem.md`` §9 says a version is not usable
#: without, pinned for identity and recorded shape.
_COMPANIONS: Final = (
    CompanionSpec(
        asset_id="DIMENSION_SCORECARD_v17_1.csv",
        kind=_K.DIMENSION_SCORECARD,
        sha256="687d52da3a9ad447a67cec53bfa1a55e3cb04e6cc7eb6aa1e31d11de03c9d862",
        byte_size=123_496,
        fmt="csv",
        rows=400,
        columns=14,
    ),
    CompanionSpec(
        asset_id="PERSONA_SIGNAL_CATALOG_v17.csv",
        kind=_K.PERSONA_SIGNAL_CATALOG,
        sha256="75e0acf7cabae4d13dbc9177d9546ca6b0eecb4a9e6a5ac2780ba19970a590d8",
        byte_size=20_237,
        fmt="csv",
        rows=117,
        columns=11,
        panel_column_field="column",
    ),
    CompanionSpec(
        asset_id="RESPONDENT_AUDIT_v17_1.csv",
        kind=_K.RESPONDENT_AUDIT,
        sha256="42ce6b3d73425e23c292281c436f4255a80299097fc1fc7d2a19773b05e11aed",
        byte_size=958_710,
        fmt="csv",
        rows=18_766,
        columns=11,
        status_column="audit_status",
        forbidden_status="FAIL",
    ),
    CompanionSpec(
        asset_id="CORE_JOINT_STATUS.json",
        kind=_K.CORE_JOINT_STATUS,
        sha256="bb1d49ce477892b6df4a976ed9a92dffb07301dc8b43babecc426691038ed5dd",
        byte_size=2_175,
        fmt="json",
    ),
    CompanionSpec(
        asset_id="DATA_PROVENANCE_REGISTRY_v17.csv",
        kind=_K.INTEGRITY_ONLY,
        sha256="3208a2459133005cb48bcbd14a49cb612326415628eecbf4d9ed3c88b6228ed8",
        byte_size=79_472,
        fmt="csv",
        rows=400,
        columns=7,
    ),
    CompanionSpec(
        asset_id="FINAL_SOURCE_CATALOG_v17.csv",
        kind=_K.INTEGRITY_ONLY,
        sha256="62e959077ba77683da7161fac0f8de856fc9934400df03fe0f79f992da5187ec",
        byte_size=338_455,
        fmt="csv",
        rows=945,
        columns=4,
    ),
    CompanionSpec(
        asset_id="OUT_OF_SAMPLE_VALIDATION_v17_1.csv",
        kind=_K.INTEGRITY_ONLY,
        sha256="c3e58952f8be4b0bb81525b40bd61d585201d9f6a294b7ed6f6e853e8a9fd041",
        byte_size=3_684,
        fmt="csv",
        rows=15,
        columns=13,
    ),
    CompanionSpec(
        asset_id="DONOR_COVERAGE_MATRIX_v17_1.csv",
        kind=_K.INTEGRITY_ONLY,
        sha256="11fdfce2c003feb980924824b260118c70b1d854b956e971a40cec39f44090e7",
        byte_size=92_534,
        fmt="csv",
        rows=980,
        columns=9,
    ),
    CompanionSpec(
        asset_id="CALIBRATION_REGISTRY.csv",
        kind=_K.INTEGRITY_ONLY,
        sha256="1b0d9cea2f7a0962fad7d2f1ffe8de67f0a5cce58eace746c7faf20a30d4a7a9",
        byte_size=19_832,
        fmt="csv",
        rows=75,
        columns=16,
    ),
    CompanionSpec(
        asset_id="DOMAIN_EVIDENCE_COVERAGE.csv",
        kind=_K.INTEGRITY_ONLY,
        sha256="de5c2ec6c5020fd9fa1fd1c4da00d24d365a9bc44d973f81ca53d6562c9e370e",
        byte_size=3_101,
        fmt="csv",
        rows=33,
        columns=8,
    ),
    CompanionSpec(
        asset_id="CORRELATION_MATRIX_QC_v17_1.csv",
        kind=_K.INTEGRITY_ONLY,
        sha256="3daa69ff1f22bc01ddf8c8c98e621d4800def9d7c848a1952d9a04f9bd20c35f",
        byte_size=165_453,
        fmt="csv",
        rows=1_287,
        columns=10,
    ),
    CompanionSpec(
        asset_id="PERSONA_VALUE_LABELS_v17.json",
        kind=_K.INTEGRITY_ONLY,
        sha256="9bc4866fbad7d2dede416a8053377c242de1e6c9589bda3e96fa777e8ffc29f5",
        byte_size=36_956,
        fmt="json",
    ),
    CompanionSpec(
        asset_id="BUILTIN_SUBPANELS_v17.json",
        kind=_K.INTEGRITY_ONLY,
        sha256="bcc0cead3fe4d06c0451c3e322802ec1d6bda114e333cec79deb22db1bde21a4",
        byte_size=11_415,
        fmt="json",
    ),
    CompanionSpec(
        asset_id="SPECIAL_PANEL_REGISTRY_v17.json",
        kind=_K.INTEGRITY_ONLY,
        sha256="6dd240f585138deab609545b69b8a6241bd6dfd60e125f6592c2f585cc47b000",
        byte_size=10_477,
        fmt="json",
    ),
    CompanionSpec(
        asset_id="LATENT_FACTOR_AUDIT_v17_1.csv.gz",
        kind=_K.INTEGRITY_ONLY,
        sha256="7473e4e57ff7823332d2c6fc8dcf51718fe200aa46a8cf498a0429cbedf22798",
        byte_size=1_256_871,
        fmt="gz",
    ),
)

CZ_SYNTHETIC_V17: Final = PopulationImportContract(
    contract_id="cz_synthetic_population/v17",
    dataset_id=CZ_DATASET_ID,
    field_count=400,
    field_names_sha256="7a7604cc15a24f5a98b199eb9b3013244136e03e7b0a21150645a7e54bc9209f",
    dictionary_sha256="4f2defebc79a4bbf3caab8affa9e76ea1eae087a806c2d6252c2e79a3b58273c",
    primary_key="panel_row_id",
    expected_rows=18_766,
    weight_schemes=(
        WeightScheme(
            role="default_current",
            column="vaha_strukturalni_2025",
            expected_total=8_956_290.3618,
            tolerance=2.0,
        ),
        WeightScheme(role="demographic_current_approx", column="vaha_populace_2025_aprox"),
        WeightScheme(
            role="census_2021",
            column="vaha_kalibrovana",
            expected_total=8_533_116.0,
            tolerance=1e-3,
        ),
        WeightScheme(role="party_2021_aggregate", column="vaha_strana_2021_benchmark"),
    ),
    default_weight_role="default_current",
    known_versions=(
        # Lineage root. IRREPLACEABLE: its upstream microdata and build script are
        # not in the archive (R8). Build input only -- never bound to a population.
        KnownVersion(
            label="v17_0_BASE",
            sha256="5300c1aeeef4ead1deb07f183d87040e6031ab1273e816dd057ad3ddd6464105",
            byte_size=7_318_890,
        ),
        # CZ_STATIC_REFERENCE. Reproducible from v17_0_BASE (SEED 20260819).
        KnownVersion(
            label="v17_1_2",
            sha256="d6a9ef120b81982e195b360fbdb9539fd70b7845a296918a12622502f2400387",
            byte_size=7_324_528,
            parent_label="v17_0_BASE",
        ),
        # CZ_LIVE, the default runtime. Reproducible from v17_1_2 (SEED 20260820).
        KnownVersion(
            label="v17_4_0",
            sha256="864f8dbcd101e4be1b2a006ccebe4196a85f9bfcbf1a474af762b8135cc779ce",
            byte_size=7_324_827,
            parent_label="v17_1_2",
        ),
    ),
    static_reference_label="v17_1_2",
    enrichment_fields=(
        "ad_receptivity_tier_derived",
        "digital_engagement_tier_derived",
        "dominant_leisure_derived",
        "dominant_media_derived",
        "financial_capability_tier_derived",
        "life_stage_derived",
        "shopping_orientation_derived",
    ),
    analysis_weight_field="_analysis_weight",
    text_fields=frozenset({"occupation_isco08"}),
    forbidden_prefixes=("D_", "P_"),
    companions=_COMPANIONS,
    joint_certified_labels=frozenset({"v17_4_0"}),
)
