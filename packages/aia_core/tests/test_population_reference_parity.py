"""Population parity against AIA-reference: field policy, dataset ledger, F10, F11.

Reads the **committed** contracts and golden fixtures of
``AiAnalytics-AIA/AIA-reference`` -- never the withheld archive, never licensed
data. Skips cleanly when the checkout is absent (``AIA_REFERENCE_REPO``), and is
marked ``parity`` so it runs under ``make test-parity``. A skip is reported, never
counted as a pass.

Three things are proven here that the unit suite cannot prove on its own:

1. **The pinned contract is the reference's contract.** Every value in
   ``domain.population.czech`` is re-derived from the reference and compared.
2. **The real 400 field names pass real validation.** A synthetic panel is built
   with the actual ordered field names from ``field-policy.json`` and imported
   through ``PopulationRuntime`` under the production contract's own field
   fingerprint, primary key, text fields, prefixes and derived fields.
3. **F10 and F11 behave as INTENTIONAL_DIFFERENCE.** One loader where the
   reference had two; every silent weight fallback the reference had is a refusal.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.application.population import PopulationRuntime
from aia_core.domain.population import (
    CZ_SYNTHETIC_V17,
    ClaimRule,
    CompanionKind,
    DerivedOrigin,
    FieldPolicy,
    FieldUse,
    ImportRejected,
    JointState,
    KnownVersion,
    ParsedPanel,
    PopulationKind,
    PopulationSelector,
    PopulationView,
    WeightResolutionError,
    WeightScheme,
    build_field_policy,
    content_sha256,
    evaluate_joint_certificate,
    field_names_fingerprint,
    resolve_weight_scheme,
)
from aia_core.infrastructure.population_parser import parse_dictionary
from aia_core.infrastructure.population_source import InMemoryPopulationSource

pytestmark = pytest.mark.parity


def _operator(*permissions: str) -> Any:
    """An issued population-operator context, the only thing establish/promote accept."""
    from aia_core.application.population_authority import (
        PopulationAuthority,
        PopulationOperatorConfig,
    )
    from aia_core.application.scope import AuthenticatedPrincipal

    config = PopulationOperatorConfig.from_names(
        {"owner": permissions or ("POPULATION_ESTABLISH", "POPULATION_PROMOTE")}
    )
    return PopulationAuthority(config).operator_context(
        AuthenticatedPrincipal(user_id="owner", organization_id="platform")
    )


OPERATOR = _operator()

REPO = Path(__file__).resolve().parents[3]
CZ = CZ_SYNTHETIC_V17


def load(reference_repo: Path, relative: str) -> Any:
    return json.loads((reference_repo / relative).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def field_policy(reference_repo: Path) -> Any:
    return load(reference_repo, "field-policy.json")


@pytest.fixture(scope="module")
def field_names(field_policy: Any) -> tuple[str, ...]:
    return tuple(f["field"] for f in field_policy["fields"])


@pytest.fixture(scope="module")
def f10(reference_repo: Path) -> Any:
    return load(reference_repo, "golden-fixtures/F10_dual_panel_loader_divergence.json")


@pytest.fixture(scope="module")
def f11(reference_repo: Path) -> Any:
    return load(reference_repo, "golden-fixtures/F11_analysis_weight_fallback_chains.json")


# --------------------------------------------------------------------------- #
# 1. The pinned contract is the reference's contract
# --------------------------------------------------------------------------- #


def test_reference_is_the_snapshot_this_repository_points_at(
    reference_repo: Path, field_policy: Any
) -> None:
    manifest = json.loads((REPO / "docs/migration/reference-manifest.json").read_text())
    assert field_policy["reference_zip_sha256"] == manifest["authoritative_source"]["sha256"]
    for fixture in load(reference_repo, "golden-fixtures/manifest.json")["fixtures"]:
        assert fixture["reference_zip_sha256"] == manifest["authoritative_source"]["sha256"]


def test_dictionary_hash_and_field_count_match(
    field_policy: Any, field_names: tuple[str, ...]
) -> None:
    assert field_policy["source_file"] == "FIELD_DICTIONARY_v17_1.csv"
    assert field_policy["source_sha256"] == CZ.dictionary_sha256
    assert field_policy["declared_field_count"] == CZ.field_count == 400
    assert len(field_names) == len(set(field_names)) == 400


def test_ordered_field_name_fingerprint_matches(field_names: tuple[str, ...]) -> None:
    assert field_names_fingerprint(field_names) == CZ.field_names_sha256


def test_schema_critical_fields_are_source_fields(field_names: tuple[str, ...]) -> None:
    assert CZ.primary_key in field_names
    assert CZ.text_fields <= set(field_names)
    assert set(CZ.weight_columns) <= set(field_names)
    assert not [f for f in field_names if f.startswith(CZ.forbidden_prefixes)]


def test_the_eight_runtime_fields_are_exactly_the_undictionaried_ones(
    field_policy: Any, field_names: tuple[str, ...]
) -> None:
    undictionaried = {c["field"] for c in field_policy["runtime_columns_without_dictionary_entry"]}
    assert {d.name for d in CZ.derived_fields} == undictionaried
    assert len(undictionaried) == 8
    assert not undictionaried & set(field_names)
    assert all(
        c["status"] == "NO_DICTIONARY_ENTRY"
        for c in field_policy["runtime_columns_without_dictionary_entry"]
    )


def test_occupation_isco08_is_declared_as_text_in_the_reference(field_policy: Any) -> None:
    entry = next(f for f in field_policy["fields"] if f["field"] == "occupation_isco08")
    # The dictionary itself says the code is text with significant leading zeros.
    assert "ISCO-08" in entry["description"]
    assert "occupation_isco08" in CZ.text_fields


def test_the_three_versions_match_the_dataset_ledger(reference_repo: Path) -> None:
    ledger = {
        d["path"].rsplit("/", 1)[-1]: d
        for d in load(reference_repo, "dataset-ledger.json")["datasets"]
    }
    expected = {
        "v17_0_BASE": ("FINALNI_KOMPLETNI_PANEL_v17_0_BASE.csv.gz", "LINEAGE_ROOT"),
        "v17_1_2": ("FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz", "CZ_STATIC_REFERENCE"),
        "v17_4_0": ("FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz", "CZ_LIVE"),
    }
    for label, (filename, role) in expected.items():
        known = CZ.known_version(label)
        entry = ledger[filename]
        assert known is not None
        assert (known.sha256, known.byte_size) == (entry["sha256"], entry["bytes"])
        assert (entry["rows"], entry["columns"]) == (CZ.expected_rows, CZ.field_count)
        assert entry["primary_key"] == CZ.primary_key
        assert entry["role"] == role
    assert CZ.static_reference_label == "v17_1_2"
    dictionary = ledger["FIELD_DICTIONARY_v17_1.csv"]
    assert (dictionary["sha256"], dictionary["rows"]) == (CZ.dictionary_sha256, 400)


# --------------------------------------------------------------------------- #
# 1b. Field policy against the reference's own extraction
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def cz_policy(field_policy: Any) -> FieldPolicy:
    """The production policy built from the real dictionary content."""
    parsed = parse_dictionary(reconstructed_dictionary(field_policy))
    return build_field_policy(
        parsed.rows,
        dictionary_sha256=CZ.dictionary_sha256,
        weight_columns=CZ.weight_columns,
        derived_fields=[
            (d.name, d.origin is DerivedOrigin.ANALYSIS_WEIGHT) for d in CZ.derived_fields
        ],
    )


def test_policy_maps_every_one_of_the_400_fields(cz_policy: FieldPolicy) -> None:
    assert cz_policy.unmapped == ()
    assert len(cz_policy.entries) == 408  # 400 dictionary fields + 8 derived


def test_claim_rules_equal_the_reference_extraction_field_for_field(
    field_policy: Any, cz_policy: FieldPolicy
) -> None:
    for f in field_policy["fields"]:
        entry = cz_policy.entry(f["field"])
        assert entry is not None
        assert {r.value for r in entry.claim_rules} == set(f["claim_rules"]), f["field"]
        assert entry.provenance_class.value == f["provenance_class"], f["field"]
        assert entry.persona_eligible is f["persona_eligible"], f["field"]


def test_the_catalogue_of_rules_is_the_reference_catalogue(field_policy: Any) -> None:
    assert {r["rule_id"] for r in field_policy["claim_rule_catalogue"]} == {
        r.value for r in ClaimRule
    }


def reference_flag(f: Any, flag: str) -> bool:
    return bool(f["eligibility"][flag])


@pytest.mark.parametrize(
    ("use", "flag"),
    [
        (FieldUse.AGGREGATE_ANALYSIS, "analysis"),
        (FieldUse.AUDIENCE_FILTERING, "filtering"),
        (FieldUse.PERSONA_CONSTRUCTION, "persona_construction"),
        (FieldUse.WEIGHTING, "weighting"),
    ],
)
def test_internal_uses_equal_the_reference_flags(
    field_policy: Any, cz_policy: FieldPolicy, use: FieldUse, flag: str
) -> None:
    for f in field_policy["fields"]:
        assert cz_policy.decide(f["field"], use).allowed is reference_flag(f, flag), f["field"]


def test_simulation_differs_only_where_the_reference_let_audit_metadata_in(
    field_policy: Any, cz_policy: FieldPolicy
) -> None:
    # INTENTIONAL_DIFFERENCE: the reference script allowed simulation for any
    # MODELLED field, including five "technical/provenance only" AUDIT_ONLY fields.
    differ = [
        f
        for f in field_policy["fields"]
        if cz_policy.decide(f["field"], FieldUse.SIMULATION).allowed
        is not reference_flag(f, "simulation")
    ]
    assert len(differ) == 5
    assert all(reference_flag(f, "simulation") for f in differ)  # we are only stricter
    assert {f["recommended_use_verbatim"] for f in differ} == {"technical/provenance only"}


def test_client_measured_claims_are_never_more_permissive_than_the_reference(
    field_policy: Any, cz_policy: FieldPolicy
) -> None:
    ours = {
        f["field"]
        for f in field_policy["fields"]
        if cz_policy.decide(f["field"], FieldUse.CLIENT_MEASURED_CLAIM).allowed
    }
    reference = {
        f["field"]
        for f in field_policy["fields"]
        if reference_flag(f, "client_facing_measured_claim")
    }
    assert ours <= reference
    assert field_policy["counts"]["client_facing_measured_claim_allowed"] == len(reference) == 287
    # Every field we admit is measured evidence under a phrase naming analysis.
    for name in ours:
        entry = cz_policy.entry(name)
        assert entry is not None
        assert entry.provenance_class.is_measured
        assert entry.recommended_use == "PERSONA_OR_ANALYSIS_WITH_SCOPE"
    # Pinned so a policy change is a visible diff, not a silent widening.
    assert len(ours) == 115


@pytest.mark.parametrize(
    "rule", [ClaimRule.NEVER_MEASURED_FACT, ClaimRule.NEVER_DIRECT_SCHWARTZ, ClaimRule.AUDIT_ONLY]
)
def test_the_critical_rules_never_reach_a_client(
    field_policy: Any, cz_policy: FieldPolicy, rule: ClaimRule
) -> None:
    carriers = [f["field"] for f in field_policy["fields"] if rule.value in f["claim_rules"]]
    assert carriers
    for name in carriers:
        for use in (FieldUse.CLIENT_MEASURED_CLAIM, FieldUse.CLIENT_MODELLED_CLAIM):
            assert not cz_policy.decide(name, use).allowed, (name, use)


def test_derived_runtime_fields_are_refused_until_classified(cz_policy: FieldPolicy) -> None:
    for derived in CZ.derived_fields:
        uses = {u for u in FieldUse if cz_policy.decide(derived.name, u).allowed}
        expected = (
            {FieldUse.WEIGHTING} if derived.origin is DerivedOrigin.ANALYSIS_WEIGHT else set()
        )
        assert uses == expected, derived.name


# --------------------------------------------------------------------------- #
# 2. The real 400 names through real validation
# --------------------------------------------------------------------------- #


class ConstantEnricher:
    """Stands in for the unrecovered enrichment so the ANALYSIS shape can be checked."""

    enricher_id = "parity-constant"

    def derive(self, panel: ParsedPanel) -> dict[str, tuple[str, ...]]:
        return dict.fromkeys(CZ.enrichment_fields, ("x",) * panel.row_count)


def reconstructed_dictionary(field_policy: Any, *, rename: dict[str, str] | None = None) -> bytes:
    """``FIELD_DICTIONARY_v17_1.csv`` rebuilt from ``field-policy.json``, in its layout.

    The real file is withheld with the archive; ``field-policy.json`` preserves every
    policy column of it verbatim (``recommended_use_verbatim``), and ``persona_eligible``
    as the boolean the reference parsed from ``yes``. Its bytes differ from the real
    file, so it is pinned by a synthetic hash; its content is the real policy.
    """
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "field",
            "block",
            "source",
            "evidence_status",
            "production_grade",
            "recommended_use",
            "description",
            "persona_eligible",
        ]
    )
    for f in field_policy["fields"]:
        writer.writerow(
            [
                (rename or {}).get(f["field"], f["field"]),
                f["block"],
                f["source"],
                f["evidence_status"],
                f["production_grade"],
                f["recommended_use_verbatim"],
                f["description"],
                "yes" if f["persona_eligible"] else "no",
            ]
        )
    return buffer.getvalue().encode("utf-8")


def synthetic_cz_bundle(
    field_policy: Any,
    gzip_csv: Any,
    *,
    drop: tuple[str, ...] = (),
    rename: dict[str, str] | None = None,
) -> tuple[Any, InMemoryPopulationSource]:
    """A 5-row panel over the real 400 field names and the real dictionary policy,
    under a contract that keeps every production rule except those tied to the
    real bytes."""
    field_names = tuple((rename or {}).get(f["field"], f["field"]) for f in field_policy["fields"])
    rows = []
    for i in range(5):
        row = dict.fromkeys(field_names, "x")
        row["panel_row_id"] = f"SYN{i}"
        row["occupation_isco08"] = "0110"
        for column in CZ.weight_columns:
            row[column] = "2.5"
        rows.append(row)
    header = tuple(f for f in field_names if f not in drop)
    panels = {
        # Distinct bytes per version: the key carries the label.
        label: gzip_csv(
            header, [r | {"panel_row_id": f"{label}-{r['panel_row_id']}"} for r in rows]
        )
        for label in ("syn_root", "syn_static", "syn_live")
    }
    dictionary = reconstructed_dictionary(field_policy, rename=rename)
    contract = replace(
        CZ,
        contract_id="cz_synthetic_population/v17-parity",
        dictionary_sha256=content_sha256(dictionary),
        expected_rows=5,
        weight_schemes=tuple(
            WeightScheme(s.role, s.column, expected_total=12.5, tolerance=1e-9)
            if s.expected_total is not None
            else s
            for s in CZ.weight_schemes
        ),
        known_versions=(
            KnownVersion("syn_root", content_sha256(panels["syn_root"]), len(panels["syn_root"])),
            KnownVersion(
                "syn_static",
                content_sha256(panels["syn_static"]),
                len(panels["syn_static"]),
                "syn_root",
            ),
            KnownVersion(
                "syn_live",
                content_sha256(panels["syn_live"]),
                len(panels["syn_live"]),
                "syn_static",
            ),
        ),
        static_reference_label="syn_static",
        # Companion bytes are withheld with the archive; companions have their own
        # parity tests below, against the ledger and methodology M03/M14.
        companions=(),
        joint_certified_labels=frozenset(),
    )
    source = InMemoryPopulationSource({"dictionary.csv": dictionary})
    for label, data in panels.items():
        source.put(f"{label}.csv.gz", data)
    return contract, source


def established_runtime(session: Session, contract: Any, source: Any) -> PopulationRuntime:
    rt = PopulationRuntime(session, contract=contract, source=source, enricher=ConstantEnricher())
    ids = {}
    for label in ("syn_root", "syn_static", "syn_live"):
        ids[label] = rt.import_version(
            label=label,
            panel_location=f"{label}.csv.gz",
            dictionary_location="dictionary.csv",
            provenance="parity",
            imported_by="parity",
        ).version_id
    rt.establish(
        population_id="CZ_STATIC_REFERENCE",
        kind=PopulationKind.STATIC,
        version_id=ids["syn_static"],
        operator=OPERATOR,
        reason="parity",
    )
    rt.establish(
        population_id="CZ_LIVE",
        kind=PopulationKind.LIVE,
        version_id=ids["syn_live"],
        operator=OPERATOR,
        reason="parity",
    )
    return rt


def test_the_real_400_field_names_import_under_the_production_rules(
    session: Session, field_policy: Any, field_names: tuple[str, ...], gzip_csv_writer: Any
) -> None:
    contract, source = synthetic_cz_bundle(field_policy, gzip_csv_writer)
    assert contract.field_names_sha256 == CZ.field_names_sha256  # the real fingerprint
    rt = established_runtime(session, contract, source)
    base = rt.load(rt.resolve(PopulationSelector.population("CZ_LIVE"), view=PopulationView.BASE))
    assert base.fields == field_names
    assert base.column("occupation_isco08")[0] == "0110"


def test_a_real_field_renamed_is_rejected(
    session: Session, field_policy: Any, gzip_csv_writer: Any
) -> None:
    contract, source = synthetic_cz_bundle(
        field_policy, gzip_csv_writer, rename={"vek": "vek_renamed"}
    )
    contract = replace(contract, field_names_sha256=CZ.field_names_sha256)
    rt = PopulationRuntime(session, contract=contract, source=source)
    with pytest.raises(ImportRejected) as caught:
        rt.import_version(
            label="syn_root",
            panel_location="syn_root.csv.gz",
            dictionary_location="dictionary.csv",
            provenance="parity",
            imported_by="parity",
        )
    assert any(f.startswith("dictionary.field_names") for f in caught.value.failures)


# --------------------------------------------------------------------------- #
# 3. F10 -- one canonical loader, named views
# --------------------------------------------------------------------------- #


def test_f10_fixture_is_anchored_to_the_live_version(f10: Any) -> None:
    live = CZ.known_version("v17_4_0")
    assert live is not None
    assert f10["dataset_sha256"] == live.sha256
    assert tuple(f10["input"]["declared_shape"]) == (CZ.expected_rows, CZ.field_count)
    assert f10["parity_type"] == "INTENTIONAL_DIFFERENCE"


def test_f10_the_analysis_view_is_the_reference_research_loaders_shape(
    session: Session,
    f10: Any,
    field_policy: Any,
    field_names: tuple[str, ...],
    gzip_csv_writer: Any,
) -> None:
    loader_b = f10["expected_output"]["loader_b"]
    contract, source = synthetic_cz_bundle(field_policy, gzip_csv_writer)
    rt = established_runtime(session, contract, source)
    analysis = rt.load(rt.resolve(PopulationSelector.population("CZ_LIVE")))

    extra = sorted(set(analysis.fields) - set(field_names))
    assert extra == sorted(loader_b["extra_vs_400"])
    assert len(analysis.fields) == loader_b["n_columns"] == 408
    assert loader_b["has_analysis_weight"] is True
    assert analysis.origin(CZ.analysis_weight_field).value == DerivedOrigin.ANALYSIS_WEIGHT


def test_f10_the_only_loader_divergence_is_now_a_named_view(
    session: Session,
    f10: Any,
    field_policy: Any,
    field_names: tuple[str, ...],
    gzip_csv_writer: Any,
) -> None:
    divergence = f10["expected_output"]["divergence"]
    loader_a = f10["expected_output"]["loader_a"]
    assert divergence["columns_only_in_b"] == [CZ.analysis_weight_field]
    assert divergence["rows_dropped_by_b"] == 0
    # The reference's HTTP loader (A) is the enrichment without the weight.
    assert sorted(loader_a["extra_vs_400"]) == sorted(CZ.enrichment_fields)

    contract, source = synthetic_cz_bundle(field_policy, gzip_csv_writer)
    rt = established_runtime(session, contract, source)
    base = rt.load(rt.resolve(PopulationSelector.population("CZ_LIVE"), view=PopulationView.BASE))
    analysis = rt.load(rt.resolve(PopulationSelector.population("CZ_LIVE")))
    # Same bytes, same binding target: the views differ only by the declared
    # derived fields, and the difference is recorded on each binding.
    assert set(analysis.fields) - set(base.fields) == {d.name for d in CZ.derived_fields}
    assert base.binding.version_id == analysis.binding.version_id
    assert (base.binding.view, analysis.binding.view) == (
        PopulationView.BASE,
        PopulationView.ANALYSIS,
    )


def test_f10_weight_totals_match_the_contract(f10: Any) -> None:
    sums = f10["expected_output"]["loader_b"]["weight_sums"]
    for column, total in sums.items():
        scheme = next(s for s in CZ.weight_schemes if s.column == column)
        assert scheme.expected_total == total
    assert (
        f10["expected_output"]["loader_b"]["analysis_weight"]["sum"]
        == sums[resolve_weight_scheme(CZ).column]
    )


# --------------------------------------------------------------------------- #
# 4. F11 -- every silent weight fallback is a refusal
# --------------------------------------------------------------------------- #


def test_f11_declared_schemes_match(f11: Any) -> None:
    declared = f11["expected_output"]["declared_schemes"]
    assert {s.role: s.column for s in CZ.weight_schemes} == declared
    totals = f11["expected_output"]["measured_totals"]
    for column, total in totals.items():
        assert next(s for s in CZ.weight_schemes if s.column == column).expected_total == total


def test_f11_scenario_1_declared_roles_resolve_and_unknown_is_refused(f11: Any) -> None:
    chain = f11["expected_output"]["fallback_chains"]["1_role_resolution"]
    for role, column in chain.items():
        if role in ("UNKNOWN_ROLE", "classification"):
            continue
        assert resolve_weight_scheme(CZ, role).column == column
    # Reference: UNKNOWN_ROLE -> "vaha_kalibrovana" (Census 2021). Here: an error.
    assert chain["UNKNOWN_ROLE"] == "vaha_kalibrovana"
    with pytest.raises(WeightResolutionError):
        resolve_weight_scheme(CZ, "UNKNOWN_ROLE")


def test_f11_scenario_2_the_default_is_the_declared_structural_weight(f11: Any) -> None:
    scenario = f11["expected_output"]["fallback_chains"]["2_weight_present"]
    assert resolve_weight_scheme(CZ).column == scenario["resolved"]
    assert scenario["classification"] == "intended"


@pytest.mark.parametrize("scenario", ["3_declared_column_missing", "4_all_weights_missing"])
def test_f11_scenarios_3_and_4_a_missing_weight_column_is_rejected(
    session: Session,
    f11: Any,
    field_policy: Any,
    gzip_csv_writer: Any,
    scenario: str,
) -> None:
    chain = f11["expected_output"]["fallback_chains"][scenario]
    dropped = chain["dropped"] if isinstance(chain["dropped"], list) else [chain["dropped"]]
    # The reference silently reweighted (3) or went unweighted (4).
    assert chain["classification"].startswith("DEFECT")
    contract, source = synthetic_cz_bundle(field_policy, gzip_csv_writer, drop=tuple(dropped))
    rt = PopulationRuntime(session, contract=contract, source=source)
    with pytest.raises(ImportRejected) as caught:
        rt.import_version(
            label="syn_root",
            panel_location="syn_root.csv.gz",
            dictionary_location="dictionary.csv",
            provenance="parity",
            imported_by="parity",
        )
    roles = {s.role for s in CZ.weight_schemes if s.column in dropped}
    for role in roles:
        assert any(f.startswith(f"weights.{role}.present") for f in caught.value.failures)


# --------------------------------------------------------------------------- #
# 5. Companion assets and the joint certificate
# --------------------------------------------------------------------------- #

# Ledger assets that are not per-version companions: the panels themselves, the
# dictionary (validated as the version's dictionary), the dataset manifest whose
# content this contract *is*, and two global rule/anchor files that
# population-subsystem.md §9 does not list as companions.
NOT_COMPANIONS = {
    "FINALNI_KOMPLETNI_PANEL_v17_1_2.csv.gz",
    "FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz",
    "FINALNI_KOMPLETNI_PANEL_v17_0_BASE.csv.gz",
    "FIELD_DICTIONARY_v17_1.csv",
    "DATA_CONTRACT_v17.json",
    "PRODUCT_POLICY.json",
    "VALIDATION_ANCHORS.json",
}


@pytest.fixture(scope="module")
def ledger(reference_repo: Path) -> dict[str, Any]:
    datasets = load(reference_repo, "dataset-ledger.json")["datasets"]
    return {d["path"].rsplit("/", 1)[-1]: d for d in datasets}


@pytest.fixture(scope="module")
def m03(reference_repo: Path) -> Any:
    entries = load(reference_repo, "methodology-ledger.json")
    entries = entries.get("entries", entries) if isinstance(entries, dict) else entries
    return next(e for e in entries if e["id"] == "M03")


def test_the_companion_set_is_the_ledger_less_the_non_companions(ledger: dict[str, Any]) -> None:
    assert {c.asset_id for c in CZ.companions} == set(ledger) - NOT_COMPANIONS
    assert len(CZ.companions) == 15


def test_every_companion_identity_matches_the_ledger(ledger: dict[str, Any]) -> None:
    for spec in CZ.companions:
        entry = ledger[spec.asset_id]
        assert (spec.sha256, spec.byte_size) == (entry["sha256"], entry["bytes"]), spec.asset_id
        assert entry["hash_verified"] is True
        if spec.fmt == "csv":
            assert (spec.rows, spec.columns) == (entry["rows"], entry["columns"]), spec.asset_id


def test_m14_shape_invariants_are_encoded(reference_repo: Path) -> None:
    entries = load(reference_repo, "methodology-ledger.json")
    entries = entries.get("entries", entries) if isinstance(entries, dict) else entries
    m14 = next(e for e in entries if e["id"] == "M14")["constants"]
    specs = {c.kind: c for c in CZ.companions}
    assert specs[CompanionKind.PERSONA_SIGNAL_CATALOG].rows == int(m14["persona catalog rows"])
    assert specs[CompanionKind.RESPONDENT_AUDIT].rows == int(m14["respondent audit rows"])
    assert int(m14["respondent audit hard failures allowed"]) == 0
    assert specs[CompanionKind.RESPONDENT_AUDIT].forbidden_status == "FAIL"
    assert specs[CompanionKind.DIMENSION_SCORECARD].rows == CZ.field_count == 400
    assert specs[CompanionKind.PERSONA_SIGNAL_CATALOG].panel_column_field == "column"


def m03_certificate(m03: Any, panel_sha: str) -> bytes:
    """``CORE_JOINT_STATUS.json`` rebuilt from the constants M03 recorded from it."""
    restrictions = m03["claim_restrictions"]
    document = {
        "status": "COHERENT_CORE_MATCHED_BLOCKS",
        "structure_status": "QC_PASSED",
        "panel_sha256": panel_sha,
        "matched_blocks": m03["matched_blocks"],
        "core_same_person_joint": True,
        **{k: v for k, v in restrictions.items() if isinstance(v, bool)},
        "prediction_validation_status": restrictions["prediction_validation_status"],
    }
    return json.dumps(document).encode()


def test_m03_the_certificate_binds_only_the_live_panel(m03: Any) -> None:
    live = CZ.known_version("v17_4_0")
    static = CZ.known_version("v17_1_2")
    assert live is not None and static is not None
    assert m03["constants"]["panel_sha256"].startswith(live.sha256)
    certificate = m03_certificate(m03, live.sha256)

    on_live = evaluate_joint_certificate(certificate, panel_sha256=live.sha256)
    assert on_live.state is JointState.CERTIFIED
    for flag, value in m03["claim_restrictions"].items():
        if isinstance(value, bool):
            assert getattr(on_live, flag) is value, flag
    assert on_live.matched_blocks == set(m03["matched_blocks"])
    assert on_live.prediction_validation_status == "EXTERNAL_HOLDOUT_PENDING"

    on_static = evaluate_joint_certificate(certificate, panel_sha256=static.sha256)
    assert on_static.state is JointState.NOT_THIS_PANEL
    assert CZ.joint_certified_labels == {"v17_4_0"}


def test_m03_client_joint_and_cross_block_claims_stay_forbidden(m03: Any) -> None:
    live = CZ.known_version("v17_4_0")
    assert live is not None
    status = evaluate_joint_certificate(m03_certificate(m03, live.sha256), panel_sha256=live.sha256)
    assert not status.decide({"vek": "core", "pohlavi": "core"}, client_facing=True).allowed
    decision = status.decide({"vek": "core", "party": "politics"}, client_facing=False)
    assert (decision.allowed, decision.reason) == (False, "cross_block_same_person_forbidden")
    assert status.decide(
        {"vek": "core", "pohlavi": "population_anchor"}, client_facing=False
    ).allowed
