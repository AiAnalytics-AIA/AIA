"""Import contract, import validation, weight resolution and binding resolution.

Pure-domain tests. Bundles are synthetic and built in memory through the same
types the parser produces, so nothing here needs the withheld archive. One test
family runs a 400-field synthetic contract end to end, so validation is exercised
at the production width rather than on a toy schema only.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from aia_core.domain.population import (
    CZ_SYNTHETIC_V17,
    DatasetVersion,
    DerivedOrigin,
    ImportReport,
    KnownVersion,
    ParsedDictionary,
    ParsedPanel,
    Population,
    PopulationBinding,
    PopulationError,
    PopulationImportContract,
    PopulationKind,
    PopulationNotEstablished,
    PopulationSelector,
    PopulationView,
    PromotionRecord,
    ResolutionMode,
    RuntimePopulation,
    UnknownDatasetVersion,
    VersionNotRuntimeEligible,
    WeightResolution,
    WeightResolutionError,
    WeightScheme,
    analysis_weights,
    content_sha256,
    dataset_version_id,
    field_names_fingerprint,
    parse_weight,
    plan_establish,
    resolve_binding,
    resolve_weight_scheme,
    validate_import,
)

AT = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)

# --------------------------------------------------------------------------- #
# A synthetic bundle builder
# --------------------------------------------------------------------------- #

ENRICHMENT = ("life_stage_derived", "dominant_media_derived")


def synthetic_contract(
    fields: tuple[str, ...],
    rows: list[dict[str, str | None]],
    dictionary_bytes: bytes,
    *,
    known: tuple[KnownVersion, ...] = (),
    static_label: str = "static",
) -> PopulationImportContract:
    total = sum(float(r["w_main"] or 0) for r in rows)
    return PopulationImportContract(
        contract_id="synthetic/v1",
        dataset_id="synthetic_population",
        field_count=len(fields),
        field_names_sha256=field_names_fingerprint(fields),
        dictionary_sha256=content_sha256(dictionary_bytes),
        primary_key="row_id",
        expected_rows=len(rows),
        weight_schemes=(
            WeightScheme("main", "w_main", expected_total=total, tolerance=1e-6),
            WeightScheme("alt", "w_alt"),
        ),
        default_weight_role="main",
        known_versions=known or (KnownVersion(static_label, content_sha256(b"static"), 1),),
        static_reference_label=static_label,
        enrichment_fields=ENRICHMENT,
        text_fields=frozenset({"occupation_code"}),
        forbidden_prefixes=("D_", "P_"),
    )


BASE_FIELDS = ("row_id", "age", "occupation_code", "w_main", "w_alt")


def base_rows() -> list[dict[str, str | None]]:
    return [
        {"row_id": "1", "age": "34", "occupation_code": "0110", "w_main": "1.5", "w_alt": "2"},
        {"row_id": "2", "age": "71", "occupation_code": "0310", "w_main": "0.5", "w_alt": None},
        {"row_id": "3", "age": None, "occupation_code": "2512", "w_main": "2.0", "w_alt": "1"},
    ]


POLICY_COLUMNS = (
    "field",
    "block",
    "source",
    "evidence_status",
    "production_grade",
    "recommended_use",
    "description",
    "persona_eligible",
)


def dictionary_of(fields: tuple[str, ...]) -> ParsedDictionary:
    """A parsed dictionary whose every row carries a mapped policy."""
    rows = tuple(
        {
            "field": f,
            "block": "core",
            "source": "synthetic",
            "evidence_status": "POPULATION_ANCHOR",
            "production_grade": "A",
            "recommended_use": "PERSONA_OR_ANALYSIS_WITH_SCOPE",
            "description": None,
            "persona_eligible": "yes",
        }
        for f in fields
    )
    return ParsedDictionary(fields, rows=rows, columns=POLICY_COLUMNS)


def panel_of(fields: tuple[str, ...], rows: list[dict[str, str | None]]) -> ParsedPanel:
    return ParsedPanel(
        header=fields,
        columns=tuple(tuple(r.get(f) for r in rows) for f in fields),
        row_count=len(rows),
    )


class Bundle:
    """A synthetic bundle and the contract it satisfies, mutable per test."""

    def __init__(self, fields: tuple[str, ...] = BASE_FIELDS) -> None:
        self.fields = fields
        self.rows = base_rows() if fields == BASE_FIELDS else wide_rows(fields)
        self.dictionary_bytes = ("field\n" + "\n".join(fields)).encode()
        self.contract = synthetic_contract(fields, self.rows, self.dictionary_bytes)
        self.panel_bytes = b"synthetic panel bytes"
        self.label = "candidate"

    def validate(self, **overrides: Any) -> ImportReport:
        contract = overrides.pop("contract", self.contract)
        kwargs: dict[str, Any] = {
            "label": self.label,
            "panel_sha256": content_sha256(self.panel_bytes),
            "panel_byte_size": len(self.panel_bytes),
            "dictionary_sha256": content_sha256(self.dictionary_bytes),
            "dictionary": dictionary_of(self.fields),
            "panel": panel_of(self.fields, self.rows),
        }
        kwargs.update(overrides)
        return validate_import(contract, **kwargs)


WIDE_FIELDS = (
    "row_id",
    "occupation_code",
    "w_main",
    "w_alt",
    *(f"field_{i:03d}" for i in range(396)),
)


def wide_rows(fields: tuple[str, ...]) -> list[dict[str, str | None]]:
    rows: list[dict[str, str | None]] = []
    for i in range(4):
        row: dict[str, str | None] = dict.fromkeys(fields, f"v{i}")
        row.update({"row_id": str(i), "w_main": "1.25", "w_alt": "1", "occupation_code": "0110"})
        rows.append(row)
    return rows


def failed(report: ImportReport) -> set[str]:
    return {c.check for c in report.checks if not c.passed}


# --------------------------------------------------------------------------- #
# The production contract
# --------------------------------------------------------------------------- #


def test_cz_contract_declares_the_preserved_shape() -> None:
    c = CZ_SYNTHETIC_V17
    assert c.dataset_id == "cz_synthetic_population"
    assert c.field_count == 400
    assert c.expected_rows == 18_766
    assert c.primary_key == "panel_row_id"
    assert "occupation_isco08" in c.text_fields
    assert c.forbidden_prefixes == ("D_", "P_")


def test_cz_contract_keeps_three_distinct_versions_with_their_lineage() -> None:
    labels = {v.label: v for v in CZ_SYNTHETIC_V17.known_versions}
    assert set(labels) == {"v17_0_BASE", "v17_1_2", "v17_4_0"}
    assert len({v.sha256 for v in labels.values()}) == 3
    assert labels["v17_0_BASE"].parent_label is None
    assert labels["v17_1_2"].parent_label == "v17_0_BASE"
    assert labels["v17_4_0"].parent_label == "v17_1_2"
    assert CZ_SYNTHETIC_V17.static_reference_label == "v17_1_2"
    assert labels["v17_4_0"].sha256.startswith("864f8dbcd101")


def test_cz_contract_declares_four_weight_roles_and_the_canonical_default() -> None:
    c = CZ_SYNTHETIC_V17
    assert {s.role: s.column for s in c.weight_schemes} == {
        "default_current": "vaha_strukturalni_2025",
        "demographic_current_approx": "vaha_populace_2025_aprox",
        "census_2021": "vaha_kalibrovana",
        "party_2021_aggregate": "vaha_strana_2021_benchmark",
    }
    assert c.default_weight_role == "default_current"
    assert c.weight_scheme("default_current").expected_total == 8_956_290.3618
    assert c.weight_scheme("census_2021").expected_total == 8_533_116.0
    # Totals the reference never asserted are not invented.
    assert c.weight_scheme("party_2021_aggregate").expected_total is None


def test_cz_contract_names_exactly_eight_derived_runtime_fields() -> None:
    derived = CZ_SYNTHETIC_V17.derived_fields
    assert len(derived) == 8
    assert [d.name for d in derived if d.origin is DerivedOrigin.ANALYSIS_WEIGHT] == [
        "_analysis_weight"
    ]
    assert len([d for d in derived if d.origin is DerivedOrigin.ENRICHMENT]) == 7
    assert all(not d.in_source_dictionary for d in derived)
    assert all(not d.client_claims_allowed for d in derived)


def test_field_names_fingerprint_depends_on_order() -> None:
    assert field_names_fingerprint(("a", "b")) != field_names_fingerprint(("b", "a"))
    assert field_names_fingerprint(("a", "b")) == field_names_fingerprint(["a", "b"])


# --------------------------------------------------------------------------- #
# Contract construction guards
# --------------------------------------------------------------------------- #


def contract_kwargs() -> dict[str, Any]:
    b = Bundle()
    c = b.contract
    return {f: getattr(c, f) for f in c.__dataclass_fields__}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"default_weight_role": "nope"}, "default weight role"),
        (
            {"weight_schemes": (WeightScheme("a", "x"), WeightScheme("a", "y"))},
            "roles must be unique",
        ),
        (
            {"weight_schemes": (WeightScheme("main", "x"), WeightScheme("b", "x"))},
            "only one role",
        ),
        (
            {
                "known_versions": (
                    KnownVersion("static", content_sha256(b"s"), 1),
                    KnownVersion("copy", content_sha256(b"s"), 1),
                )
            },
            "distinct",
        ),
        ({"static_reference_label": "absent"}, "static reference"),
        ({"enrichment_fields": ("_analysis_weight",)}, "unique"),
        ({"dictionary_sha256": "x"}, "sha256"),
        ({"field_count": 0}, "positive"),
    ],
)
def test_contract_refuses_an_incoherent_declaration(change: dict[str, Any], message: str) -> None:
    kwargs = contract_kwargs() | change
    with pytest.raises(ValueError, match=message):
        PopulationImportContract(**kwargs)


def test_known_version_guards() -> None:
    with pytest.raises(ValueError, match="sha256"):
        KnownVersion("x", "nothex", 1)
    with pytest.raises(ValueError, match="own parent"):
        KnownVersion("x", content_sha256(b"x"), 1, parent_label="x")
    with pytest.raises(ValueError, match="parent"):
        PopulationImportContract(
            **contract_kwargs()
            | {
                "known_versions": (
                    KnownVersion("static", content_sha256(b"s"), 1, parent_label="ghost"),
                )
            }
        )


def test_weight_scheme_guards() -> None:
    with pytest.raises(ValueError, match="together"):
        WeightScheme("r", "c", expected_total=1.0)
    with pytest.raises(ValueError, match="negative"):
        WeightScheme("r", "c", expected_total=1.0, tolerance=-1)


# --------------------------------------------------------------------------- #
# Weight resolution -- no default column, no fallback (F11)
# --------------------------------------------------------------------------- #


def test_default_role_resolves_to_its_declared_column() -> None:
    resolution = resolve_weight_scheme(CZ_SYNTHETIC_V17)
    assert resolution == WeightResolution(
        "default_current", "vaha_strukturalni_2025", "cz_synthetic_population/v17"
    )


def test_an_explicit_role_resolves_to_its_own_column() -> None:
    assert resolve_weight_scheme(CZ_SYNTHETIC_V17, "census_2021").column == "vaha_kalibrovana"


def test_an_unknown_role_is_an_error_not_the_census_weight() -> None:
    # F11 scenario 1: the reference returned "vaha_kalibrovana" here.
    with pytest.raises(WeightResolutionError) as caught:
        resolve_weight_scheme(CZ_SYNTHETIC_V17, "UNKNOWN_ROLE")
    assert caught.value.reason == "unknown_weight_role"


@pytest.mark.parametrize("text", ["1", "0", "1.5", "0.25", ".5", "3.", "1e3", "+2", "8.1E-2"])
def test_parse_weight_accepts_plain_decimals(text: str) -> None:
    assert parse_weight(text) == float(text)


@pytest.mark.parametrize(
    "text", ["nan", "inf", "-inf", "Infinity", "1_000", " 1", "1 ", "", "-1", "1,5", "0x1", "1e999"]
)
def test_parse_weight_refuses_anything_else(text: str) -> None:
    with pytest.raises(ValueError):
        parse_weight(text)


def test_analysis_weights_come_from_the_resolved_column_only() -> None:
    resolution = WeightResolution("main", "w_main", "c")
    assert analysis_weights(("1.5", "0.5", "2"), resolution) == (1.5, 0.5, 2.0)


@pytest.mark.parametrize(
    "cells",
    [
        ("1", None, "2"),  # a null is not a zero
        ("1", "-0.5", "2"),  # a negative is not clipped
        ("1", "nan", "2"),
        ("1", "abc", "2"),
        ("0", "0", "0"),  # a population that weighs nothing
        (),
    ],
)
def test_analysis_weights_refuse_an_unusable_column(cells: tuple[str | None, ...]) -> None:
    with pytest.raises(WeightResolutionError) as caught:
        analysis_weights(cells, WeightResolution("main", "w_main", "c"))
    assert caught.value.reason == "unusable_weight"


def test_analysis_weight_error_counts_every_defect() -> None:
    with pytest.raises(WeightResolutionError, match="2 null and 1 malformed of 5"):
        analysis_weights((None, "x", None, "1", "2"), WeightResolution("main", "w_main", "c"))


# --------------------------------------------------------------------------- #
# Import validation
# --------------------------------------------------------------------------- #


def test_a_conforming_bundle_passes_every_check() -> None:
    report = Bundle().validate()
    assert report.passed, report.failures
    assert not report.companions_validated
    record = report.as_record()
    assert record["passed"] is True
    assert record["companions_validated"] is False


def test_a_conforming_400_field_bundle_passes() -> None:
    fields = WIDE_FIELDS
    bundle = Bundle(fields)
    report = bundle.validate()
    assert len(fields) == 400
    assert report.passed, report.failures


def test_a_400_field_bundle_with_one_field_renamed_fails() -> None:
    fields = WIDE_FIELDS
    bundle = Bundle(fields)
    renamed = (*fields[:-1], "field_renamed")
    report = bundle.validate(
        dictionary=dictionary_of(renamed), panel=panel_of(renamed, bundle.rows)
    )
    # Panel and dictionary renamed consistently: the header still equals the
    # dictionary, so only the pinned fingerprint can tell. That is its job.
    assert failed(report) == {"dictionary.field_names"}


def test_a_dropped_column_fails() -> None:
    bundle = Bundle()
    fewer = tuple(f for f in BASE_FIELDS if f != "age")
    report = bundle.validate(panel=panel_of(fewer, bundle.rows))
    assert {"schema.column_count", "schema.columns_in_order"} <= failed(report)


def test_reordered_columns_fail_and_name_the_position() -> None:
    bundle = Bundle()
    swapped = ("row_id", "occupation_code", "age", "w_main", "w_alt")
    report = bundle.validate(panel=panel_of(swapped, bundle.rows))
    assert failed(report) == {"schema.columns_in_order"}
    assert "column 1 is 'occupation_code'" in report.failures[0]


def test_a_reordered_dictionary_fails_its_fingerprint() -> None:
    bundle = Bundle()
    swapped = ("row_id", "occupation_code", "age", "w_main", "w_alt")
    report = bundle.validate(dictionary=dictionary_of(swapped))
    assert "dictionary.field_names" in failed(report)


def test_a_swapped_dictionary_file_fails_its_checksum() -> None:
    report = Bundle().validate(dictionary_sha256=content_sha256(b"another dictionary"))
    assert "dictionary.checksum" in failed(report)


def test_duplicate_columns_are_reported_not_collapsed() -> None:
    bundle = Bundle()
    doubled = (*BASE_FIELDS[:-1], "age")
    report = bundle.validate(panel=panel_of(doubled, bundle.rows))
    assert "schema.unique_columns" in failed(report)


def test_wrong_row_count_fails() -> None:
    bundle = Bundle()
    report = bundle.validate(panel=panel_of(BASE_FIELDS, bundle.rows[:2]))
    assert "rows.count" in failed(report)


@pytest.mark.parametrize("keys", [("1", "1", "3"), ("1", None, "3")])
def test_primary_key_must_be_unique_and_non_null(keys: tuple[str | None, ...]) -> None:
    bundle = Bundle()
    rows = [r | {"row_id": k} for r, k in zip(bundle.rows, keys, strict=True)]
    report = bundle.validate(panel=panel_of(BASE_FIELDS, rows))
    assert failed(report) == {"rows.primary_key"}


def test_forbidden_prefixes_fail() -> None:
    fields = (*BASE_FIELDS, "D_leak")
    bundle = Bundle()
    bundle.fields = fields
    report = bundle.validate(dictionary=dictionary_of(fields), panel=panel_of(fields, bundle.rows))
    assert "schema.forbidden_prefixes" in failed(report)


def test_a_derived_runtime_field_in_the_source_fails() -> None:
    # The 8 runtime fields are not source fields; a source that carries one is
    # pretending otherwise.
    fields = (*BASE_FIELDS, "_analysis_weight")
    bundle = Bundle()
    report = bundle.validate(dictionary=dictionary_of(fields), panel=panel_of(fields, bundle.rows))
    assert "schema.derived_not_in_source" in failed(report)


def test_a_missing_text_field_fails() -> None:
    bundle = Bundle()
    contract = replace(bundle.contract, text_fields=frozenset({"absent_code"}))
    report = bundle.validate(contract=contract)
    assert failed(report) == {"schema.text_fields_present"}


def test_a_missing_weight_column_fails() -> None:
    # F11 scenario 3: the reference silently reweighted onto another column.
    bundle = Bundle()
    fields = tuple(f for f in BASE_FIELDS if f != "w_main")
    report = bundle.validate(panel=panel_of(fields, bundle.rows))
    assert "weights.main.present" in failed(report)


def test_all_weight_columns_missing_fails_every_scheme() -> None:
    # F11 scenario 4: the reference went fully unweighted.
    bundle = Bundle()
    fields = ("row_id", "age", "occupation_code")
    report = bundle.validate(panel=panel_of(fields, bundle.rows))
    assert {"weights.main.present", "weights.alt.present"} <= failed(report)


def test_a_malformed_weight_fails() -> None:
    bundle = Bundle()
    rows = [*bundle.rows[:2], bundle.rows[2] | {"w_alt": "n/a"}]
    report = bundle.validate(panel=panel_of(BASE_FIELDS, rows))
    assert failed(report) == {"weights.alt.parseable"}


def test_a_weight_total_outside_tolerance_fails() -> None:
    bundle = Bundle()
    rows = [*bundle.rows[:2], bundle.rows[2] | {"w_main": "2.5"}]
    report = bundle.validate(panel=panel_of(BASE_FIELDS, rows))
    assert failed(report) == {"weights.main.total"}


def test_a_null_in_an_undeclared_total_scheme_is_not_a_failure() -> None:
    # w_alt has a null in row 2. No total is declared for it, so nothing is
    # asserted -- but a load that selects it will refuse (see analysis_weights).
    assert Bundle().validate().passed


def test_every_check_runs_after_the_first_failure() -> None:
    bundle = Bundle()
    report = bundle.validate(
        dictionary_sha256=content_sha256(b"x"), panel=panel_of(BASE_FIELDS, bundle.rows[:1])
    )
    assert {"dictionary.checksum", "rows.count", "weights.main.total"} <= failed(report)
    assert len(report.failures) == len(failed(report))


def test_a_preserved_label_must_carry_its_preserved_bytes() -> None:
    bundle = Bundle()
    bundle.label = "static"  # known, with sha256(b"static") and 1 byte
    report = bundle.validate()
    assert {"identity.checksum", "identity.byte_size"} <= failed(report)


def test_preserved_bytes_cannot_be_imported_under_another_label() -> None:
    bundle = Bundle()
    report = bundle.validate(panel_sha256=content_sha256(b"static"))
    assert "identity.distinct_labels" in failed(report)


def test_occupation_codes_survive_validation_as_text() -> None:
    bundle = Bundle()
    panel = panel_of(BASE_FIELDS, bundle.rows)
    assert bundle.validate(panel=panel).passed
    assert panel.column("occupation_code") == ("0110", "0310", "2512")


def test_parsed_panel_guards_its_shape() -> None:
    with pytest.raises(ValueError, match="one column per header"):
        ParsedPanel(header=("a", "b"), columns=(("1",),), row_count=1)
    with pytest.raises(ValueError, match="cells"):
        ParsedPanel(header=("a",), columns=(("1", "2"),), row_count=1)
    with pytest.raises(KeyError):
        ParsedPanel(header=("a",), columns=(("1",),), row_count=1).column("b")


# --------------------------------------------------------------------------- #
# Binding resolution
# --------------------------------------------------------------------------- #


def version(label: str, parent: DatasetVersion | None, contract_id: str) -> DatasetVersion:
    sha = content_sha256(label.encode())
    return DatasetVersion(
        version_id=dataset_version_id("cz_synthetic_population", sha),
        dataset_id="cz_synthetic_population",
        label=label,
        content_sha256=sha,
        byte_size=1,
        row_count=1,
        column_count=1,
        contract_id=contract_id,
        dictionary_sha256=CZ_SYNTHETIC_V17.dictionary_sha256,
        field_names_sha256=CZ_SYNTHETIC_V17.field_names_sha256,
        parent_version_id=parent.version_id if parent else None,
        storage_location="mem://p",
        dictionary_location="mem://d",
        provenance="synthetic",
        imported_at=AT,
        imported_by="importer",
    )


class Registry:
    def __init__(self) -> None:
        cid = CZ_SYNTHETIC_V17.contract_id
        self.base = version("v17_0_BASE", None, cid)
        self.static_v = version("v17_1_2", self.base, cid)
        self.live_v = version("v17_4_0", self.static_v, cid)
        self.versions = {v.version_id: v for v in (self.base, self.static_v, self.live_v)}
        self.populations: list[Population] = []
        self.promotions: list[PromotionRecord] = []
        for pid, kind, v in (
            ("CZ_STATIC_REFERENCE", PopulationKind.STATIC, self.static_v),
            ("CZ_LIVE", PopulationKind.LIVE, self.live_v),
        ):
            population, record = plan_establish(
                population_id=pid,
                kind=kind,
                version=v,
                versions=self.versions,
                populations=self.populations,
                static_label="v17_1_2",
                actor_id="owner",
                reason="establish",
                at=AT,
            )
            self.populations.append(population)
            self.promotions.append(record)

    def resolve(
        self,
        selector: PopulationSelector,
        *,
        weight_role: str | None = None,
        view: PopulationView = PopulationView.ANALYSIS,
    ) -> PopulationBinding:
        return resolve_binding(
            selector,
            contract=CZ_SYNTHETIC_V17,
            versions=self.versions,
            populations=self.populations,
            promotions=self.promotions,
            view=view,
            weight_role=weight_role,
            at=AT,
        )


def test_live_resolves_to_its_current_version_and_the_default_weight() -> None:
    reg = Registry()
    binding = reg.resolve(PopulationSelector.population("CZ_LIVE"))
    assert binding.version_id == reg.live_v.version_id
    assert binding.version_label == "v17_4_0"
    assert binding.resolution is ResolutionMode.LIVE_CURRENT
    assert binding.population_id == "CZ_LIVE"
    assert (binding.weight_role, binding.weight_column) == (
        "default_current",
        "vaha_strukturalni_2025",
    )
    assert binding.content_sha256 == reg.live_v.content_sha256


def test_static_resolves_to_the_static_reference() -> None:
    reg = Registry()
    binding = reg.resolve(PopulationSelector.population("CZ_STATIC_REFERENCE"))
    assert binding.version_label == "v17_1_2"
    assert binding.resolution is ResolutionMode.STATIC_REFERENCE


def test_a_pin_resolves_exactly_and_names_no_population() -> None:
    reg = Registry()
    binding = reg.resolve(PopulationSelector.pinned(reg.static_v.version_id))
    assert binding.version_id == reg.static_v.version_id
    assert binding.resolution is ResolutionMode.PINNED
    assert binding.population_id is None


def test_the_lineage_root_cannot_be_pinned() -> None:
    reg = Registry()
    with pytest.raises(VersionNotRuntimeEligible):
        reg.resolve(PopulationSelector.pinned(reg.base.version_id))


def test_an_unestablished_population_is_refused_not_substituted() -> None:
    reg = Registry()
    with pytest.raises(PopulationNotEstablished):
        reg.resolve(PopulationSelector.population("CZ_SOMETHING_ELSE"))


def test_an_unknown_pin_is_refused() -> None:
    with pytest.raises(UnknownDatasetVersion):
        Registry().resolve(PopulationSelector.pinned("cz_synthetic_population@sha256:00"))


def test_an_unknown_weight_role_is_refused_at_resolution() -> None:
    with pytest.raises(WeightResolutionError):
        Registry().resolve(PopulationSelector.population("CZ_LIVE"), weight_role="UNKNOWN_ROLE")


def test_an_explicit_weight_role_is_recorded() -> None:
    binding = Registry().resolve(
        PopulationSelector.population("CZ_LIVE"), weight_role="census_2021"
    )
    assert (binding.weight_role, binding.weight_column) == ("census_2021", "vaha_kalibrovana")


def test_a_version_imported_under_another_contract_is_refused() -> None:
    reg = Registry()
    foreign = replace(reg.live_v, contract_id="cz_synthetic_population/v18")
    reg.versions[foreign.version_id] = foreign
    with pytest.raises(PopulationError) as caught:
        reg.resolve(PopulationSelector.population("CZ_LIVE"))
    assert caught.value.reason == "contract_mismatch"


def test_the_binding_records_its_provenance() -> None:
    binding = Registry().resolve(PopulationSelector.population("CZ_LIVE"))
    record = binding.as_record()
    assert record["version_label"] == "v17_4_0"
    assert record["resolution"] == "LIVE_CURRENT"
    assert record["weight_column"] == "vaha_strukturalni_2025"
    assert record["view"] == "ANALYSIS"
    assert record["resolved_at"] == AT.isoformat()


def test_selector_takes_exactly_one_target() -> None:
    with pytest.raises(ValueError):
        PopulationSelector()
    with pytest.raises(ValueError):
        PopulationSelector(population_id="CZ_LIVE", version_id="v")


def test_binding_guards_its_own_coherence() -> None:
    binding = Registry().resolve(PopulationSelector.population("CZ_LIVE"))
    with pytest.raises(PopulationError):
        replace(binding, resolution=ResolutionMode.PINNED)  # pinned but names a population
    with pytest.raises(PopulationError):
        replace(binding, content_sha256="short")
    with pytest.raises(PopulationError):
        replace(binding, weight_column="")
    with pytest.raises(PopulationError):
        replace(binding, resolved_at=datetime(2026, 9, 22))


# --------------------------------------------------------------------------- #
# RuntimePopulation cannot be forged
# --------------------------------------------------------------------------- #


def test_a_runtime_population_cannot_be_constructed_outside_the_loader() -> None:
    binding = Registry().resolve(PopulationSelector.population("CZ_LIVE"))
    with pytest.raises(PopulationError) as caught:
        RuntimePopulation(
            binding=binding,
            source_fields=("a",),
            derived_fields=(),
            row_count=1,
            _columns={"a": ("1",)},
            _analysis_weight=None,
            _issuer=object(),
        )
    assert caught.value.reason == "forged_population"
