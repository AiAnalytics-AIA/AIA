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
)
