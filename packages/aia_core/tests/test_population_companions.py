"""Companion assets and the joint-claim certificate.

Three layers: the fail-closed certificate gate (pure), companion-set validation
(pure, over synthetic assets built in ``conftest.py``), and the runtime rule that a
version whose contract declares companions is not usable without a valid set.
Parity with the reference's recorded identities and M03/M14 constants is in
``test_population_reference_parity.py``.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.application.population import PopulationRuntime
from aia_core.domain.population import (
    CompanionKind,
    CompanionsIncomplete,
    CompanionSpec,
    ImportRejected,
    JointState,
    JointStatus,
    ParsedPanel,
    PopulationError,
    PopulationKind,
    PopulationSelector,
    companion_set_sha256,
    content_sha256,
    evaluate_joint_certificate,
    validate_companions,
)

SHA = content_sha256(b"the panel")
OTHER = content_sha256(b"another panel")


# --------------------------------------------------------------------------- #
# The certificate gate
# --------------------------------------------------------------------------- #


def test_a_binding_certificate_grants_exactly_what_it_states(certificate_json: Any) -> None:
    status = evaluate_joint_certificate(certificate_json(SHA), panel_sha256=SHA)
    assert status.state is JointState.CERTIFIED
    assert status.certified
    assert status.core_same_person_joint is True
    assert status.descriptive_core_outputs_allowed is True
    assert status.client_joint_outputs_allowed is False
    assert status.cross_block_same_person_joint is False
    assert status.cross_block_joint_claims_allowed is False
    assert status.matched_blocks == {"marketing_behavior"}
    assert status.prediction_validation_status == "EXTERNAL_HOLDOUT_PENDING"


@pytest.mark.parametrize(
    ("data", "state"),
    [
        (None, JointState.MISSING),
        (b"{not json", JointState.UNPARSEABLE),
        (b"[1, 2]", JointState.UNPARSEABLE),
        (b"\xff\xfe", JointState.UNPARSEABLE),
    ],
)
def test_missing_or_unparseable_certificates_fall_back(
    data: bytes | None, state: JointState
) -> None:
    status = evaluate_joint_certificate(data, panel_sha256=SHA)
    assert status.state is state
    assert not status.certified
    assert not status.client_joint_outputs_allowed
    assert not status.descriptive_core_outputs_allowed


@pytest.mark.parametrize(
    ("overrides", "state"),
    [
        ({"status": "SOMETHING_NEW"}, JointState.UNKNOWN_STATUS),
        ({"status": None}, JointState.UNKNOWN_STATUS),
        ({"structure_status": "QC_FAILED"}, JointState.UNKNOWN_STATUS),
        ({"client_joint_outputs_allowed": "true"}, JointState.UNPARSEABLE),
        ({"cross_block_same_person_joint": 1}, JointState.UNPARSEABLE),
        ({"core_same_person_joint": None}, JointState.UNPARSEABLE),
        ({"matched_blocks": "politics"}, JointState.UNPARSEABLE),
        ({"panel_sha256": "short"}, JointState.UNPARSEABLE),
        ({"panel_sha256": OTHER}, JointState.NOT_THIS_PANEL),
    ],
)
def test_every_doubtful_certificate_falls_back_to_forbidden(
    certificate_json: Any, overrides: dict[str, Any], state: JointState
) -> None:
    status = evaluate_joint_certificate(certificate_json(SHA, **overrides), panel_sha256=SHA)
    assert status.state is state
    assert status.as_record()["descriptive_core_outputs_allowed"] is False


def test_a_missing_permission_flag_falls_back(certificate_json: Any) -> None:
    document = json.loads(certificate_json(SHA))
    del document["matched_block_outputs_allowed"]
    status = evaluate_joint_certificate(json.dumps(document).encode(), panel_sha256=SHA)
    assert status.state is JointState.UNPARSEABLE


def test_the_fallback_is_never_certified() -> None:
    with pytest.raises(ValueError):
        JointStatus.fallback(JointState.CERTIFIED, "no")


# --------------------------------------------------------------------------- #
# Joint decisions
# --------------------------------------------------------------------------- #


def certified(certificate_json: Any, **overrides: Any) -> JointStatus:
    return evaluate_joint_certificate(certificate_json(SHA, **overrides), panel_sha256=SHA)


def test_a_single_field_is_not_a_joint_claim(certificate_json: Any) -> None:
    uncertified = JointStatus.fallback(JointState.MISSING, "none")
    assert uncertified.decide({"vek": "core"}, client_facing=True).allowed


def test_client_joint_outputs_are_forbidden_when_the_certificate_says_so(
    certificate_json: Any,
) -> None:
    decision = certified(certificate_json).decide(
        {"vek": "core", "pohlavi": "core"}, client_facing=True
    )
    assert (decision.allowed, decision.reason) == (False, "client_joint_outputs_forbidden")


def test_internal_joint_use_within_the_core_is_allowed(certificate_json: Any) -> None:
    decision = certified(certificate_json).decide(
        {"vek": "core", "pohlavi": "population_anchor"}, client_facing=False
    )
    assert decision.allowed


def test_cross_block_same_person_claims_are_forbidden(certificate_json: Any) -> None:
    decision = certified(certificate_json).decide(
        {"vek": "core", "segment": "marketing_behavior"}, client_facing=False
    )
    assert (decision.allowed, decision.reason) == (False, "cross_block_same_person_forbidden")


def test_a_certificate_that_permits_cross_block_claims_is_honoured(certificate_json: Any) -> None:
    permissive = certified(
        certificate_json,
        cross_block_same_person_joint=True,
        cross_block_joint_claims_allowed=True,
        client_joint_outputs_allowed=True,
    )
    assert permissive.decide({"a": "core", "b": "marketing_behavior"}, client_facing=True).allowed


def test_an_uncertified_panel_permits_no_joint_use(certificate_json: Any) -> None:
    status = evaluate_joint_certificate(certificate_json(OTHER), panel_sha256=SHA)
    decision = status.decide({"a": "core", "b": "core"}, client_facing=False)
    assert (decision.allowed, decision.reason) == (False, "certificate_not_this_panel")


# --------------------------------------------------------------------------- #
# Companion-set validation
# --------------------------------------------------------------------------- #

PANEL = ParsedPanel(
    header=("row_id", "vek", "occupation_code", "segment", "w_main", "w_alt"),
    columns=tuple(("x",) * 6 for _ in range(6)),
    row_count=6,
)


def run(
    companions: Any, *, assets: dict[str, bytes] | None = None, certify: bool = True
) -> set[str]:
    report = validate_companions(
        companions.contract.companions,
        assets=companions.assets if assets is None else assets,
        panel=PANEL,
        panel_sha256=content_sha256(companions.population.panel_bytes("v1_4")),
        field_count=6,
        joint_must_certify=certify,
    )
    return {c[0] for c in report.checks if not c[1]}


def test_a_complete_valid_set_passes(synthetic_companions: Any) -> None:
    report = validate_companions(
        synthetic_companions.contract.companions,
        assets=synthetic_companions.assets,
        panel=PANEL,
        panel_sha256=content_sha256(synthetic_companions.population.panel_bytes("v1_4")),
        field_count=6,
        joint_must_certify=True,
    )
    assert report.passed, report.failures
    assert report.joint.certified
    assert report.set_sha256 == companion_set_sha256(report.hashes)
    assert report.as_record()["joint"]["state"] == "CERTIFIED"


def test_a_missing_companion_fails(synthetic_companions: Any) -> None:
    assets = dict(synthetic_companions.assets)
    del assets["RESPONDENT_AUDIT.csv"]
    assert run(synthetic_companions, assets=assets) == {"companions.RESPONDENT_AUDIT.csv.present"}


def test_an_undeclared_companion_fails(synthetic_companions: Any) -> None:
    assets = {**synthetic_companions.assets, "SURPRISE.csv": b"a\n1\n"}
    assert "companions.SURPRISE.csv.declared" in run(synthetic_companions, assets=assets)


def test_altered_bytes_fail_the_checksum(synthetic_companions: Any) -> None:
    assets = {**synthetic_companions.assets, "SCORECARD.csv": b"dimension,score\nvek,1\n"}
    failed = run(synthetic_companions, assets=assets)
    assert {"companions.SCORECARD.csv.checksum", "companions.SCORECARD.csv.rows"} <= failed


def test_shape_checks_run_on_top_of_the_hash(synthetic_companions: Any) -> None:
    # A spec pinned to deliberately wrong shape proves the shape checks run.
    specs = tuple(
        replace(s, rows=99) if s.asset_id == "PERSONA_CATALOG.csv" else s
        for s in synthetic_companions.contract.companions
    )
    report = validate_companions(
        specs,
        assets=synthetic_companions.assets,
        panel=PANEL,
        panel_sha256=SHA,
        field_count=6,
        joint_must_certify=False,
    )
    assert "companions.PERSONA_CATALOG.csv.rows" in {c[0] for c in report.checks if not c[1]}


def test_persona_catalog_columns_must_be_panel_columns(synthetic_companions: Any) -> None:
    catalog = b"column,label\nvek,age\nnot_a_column,x\n"
    specs = tuple(
        replace(s, sha256=content_sha256(catalog), byte_size=len(catalog))
        if s.asset_id == "PERSONA_CATALOG.csv"
        else s
        for s in synthetic_companions.contract.companions
    )
    report = validate_companions(
        specs,
        assets={**synthetic_companions.assets, "PERSONA_CATALOG.csv": catalog},
        panel=PANEL,
        panel_sha256=SHA,
        field_count=6,
        joint_must_certify=False,
    )
    assert "companions.PERSONA_CATALOG.csv.panel_columns" in {
        c[0] for c in report.checks if not c[1]
    }


def test_a_failed_respondent_audit_row_fails(synthetic_companions: Any) -> None:
    audit = b"panel_row_id,audit_status\n" + b"".join(
        f"R{i},{'FAIL' if i == 3 else 'PASS'}\n".encode() for i in range(1, 7)
    )
    specs = tuple(
        replace(s, sha256=content_sha256(audit), byte_size=len(audit))
        if s.asset_id == "RESPONDENT_AUDIT.csv"
        else s
        for s in synthetic_companions.contract.companions
    )
    report = validate_companions(
        specs,
        assets={**synthetic_companions.assets, "RESPONDENT_AUDIT.csv": audit},
        panel=PANEL,
        panel_sha256=SHA,
        field_count=6,
        joint_must_certify=False,
    )
    failures = [f for f in report.failures if "RESPONDENT_AUDIT.csv.status" in f]
    assert failures == ["companions.RESPONDENT_AUDIT.csv.status: 1 rows with audit_status = FAIL"]


def test_the_certified_version_needs_a_binding_certificate(synthetic_companions: Any) -> None:
    report = validate_companions(
        synthetic_companions.contract.companions,
        assets=synthetic_companions.assets,
        panel=PANEL,
        panel_sha256=OTHER,  # the certificate names v1_4's hash, not this one
        field_count=6,
        joint_must_certify=True,
    )
    assert "companions.CORE_JOINT_STATUS.json.certifies_panel" in {
        c[0] for c in report.checks if not c[1]
    }


def test_another_version_passes_with_joint_claims_fallen_back(synthetic_companions: Any) -> None:
    report = validate_companions(
        synthetic_companions.contract.companions,
        assets=synthetic_companions.assets,
        panel=PANEL,
        panel_sha256=OTHER,
        field_count=6,
        joint_must_certify=False,
    )
    assert report.passed
    assert report.joint.state is JointState.NOT_THIS_PANEL


def test_companion_set_digest_is_order_independent() -> None:
    assert companion_set_sha256({"a": SHA, "b": OTHER}) == companion_set_sha256(
        {"b": OTHER, "a": SHA}
    )
    assert companion_set_sha256({"a": SHA}) != companion_set_sha256({"a": OTHER})


def test_companion_spec_guards() -> None:
    with pytest.raises(ValueError, match="sha256"):
        CompanionSpec("x", CompanionKind.INTEGRITY_ONLY, "no", 1, "csv")
    with pytest.raises(ValueError, match="format"):
        CompanionSpec("x", CompanionKind.INTEGRITY_ONLY, SHA, 1, "xlsx")
    with pytest.raises(ValueError, match="together"):
        CompanionSpec("x", CompanionKind.RESPONDENT_AUDIT, SHA, 1, "csv", status_column="s")
    with pytest.raises(ValueError, match="JSON"):
        CompanionSpec("x", CompanionKind.CORE_JOINT_STATUS, SHA, 1, "csv")


def test_contract_companion_guards(synthetic_companions: Any) -> None:
    contract = synthetic_companions.contract
    spec = contract.companions[0]
    with pytest.raises(ValueError, match="unique"):
        replace(contract, companions=(spec, spec))
    with pytest.raises(ValueError, match="need a declared joint certificate"):
        replace(contract, companions=(spec,))
    with pytest.raises(ValueError, match="known versions"):
        replace(contract, joint_certified_labels=frozenset({"v9"}))


# --------------------------------------------------------------------------- #
# A version is usable only with its companions
# --------------------------------------------------------------------------- #


def runtime(session: Session, companions: Any) -> PopulationRuntime:
    return PopulationRuntime(session, contract=companions.contract, source=companions.source)


def import_label(
    rt: PopulationRuntime, companions: Any, label: str, *, with_companions: bool = True
) -> Any:
    pop = companions.population
    return rt.import_version(
        label=label,
        panel_location=pop.location(label),
        dictionary_location=pop.dictionary_location,
        provenance="synthetic",
        imported_by="importer",
        companion_locations=companions.locations(label) if with_companions else None,
    )


def establish_both(rt: PopulationRuntime, versions: dict[str, Any]) -> None:
    rt.establish(
        population_id="SYN_STATIC",
        kind=PopulationKind.STATIC,
        version_id=versions["v1_1"].version_id,
        actor_id="owner",
        reason="r",
    )
    rt.establish(
        population_id="SYN_LIVE",
        kind=PopulationKind.LIVE,
        version_id=versions["v1_4"].version_id,
        actor_id="owner",
        reason="r",
    )


def test_import_with_companions_records_a_usable_version(
    session: Session, synthetic_companions: Any
) -> None:
    from aia_core.infrastructure.population_repository import PopulationRegistryRepository

    rt = runtime(session, synthetic_companions)
    versions = {
        label: import_label(rt, synthetic_companions, label)
        for label in ("v1_BASE", "v1_1", "v1_4")
    }
    establish_both(rt, versions)
    binding = rt.resolve(PopulationSelector.population("SYN_LIVE"))
    assert binding.version_id == versions["v1_4"].version_id

    registry = PopulationRegistryRepository(session)
    assert registry.validation_record(versions["v1_4"].version_id)["companions_validated"] is True
    live_set = registry.companion_set(versions["v1_4"].version_id)
    static_set = registry.companion_set(versions["v1_1"].version_id)
    assert live_set is not None and static_set is not None
    assert live_set.joint_state is JointState.CERTIFIED
    # The same certificate does not bind to the static panel: joint claims fall back.
    assert static_set.joint_state is JointState.NOT_THIS_PANEL
    assert set(live_set.assets) == {s.asset_id for s in synthetic_companions.contract.companions}


def test_a_version_without_companions_is_registered_but_not_usable(
    session: Session, synthetic_companions: Any
) -> None:
    from aia_core.infrastructure.population_repository import PopulationRegistryRepository

    rt = runtime(session, synthetic_companions)
    base = import_label(rt, synthetic_companions, "v1_BASE", with_companions=False)
    static = import_label(rt, synthetic_companions, "v1_1", with_companions=False)
    record = PopulationRegistryRepository(session).validation_record(static.version_id)
    assert record is not None and record["companions_validated"] is False
    with pytest.raises(CompanionsIncomplete):
        rt.establish(
            population_id="SYN_STATIC",
            kind=PopulationKind.STATIC,
            version_id=static.version_id,
            actor_id="owner",
            reason="r",
        )
    assert base.version_id != static.version_id


def test_companions_can_be_attached_once_after_import(
    session: Session, synthetic_companions: Any
) -> None:
    rt = runtime(session, synthetic_companions)
    import_label(rt, synthetic_companions, "v1_BASE", with_companions=False)
    static = import_label(rt, synthetic_companions, "v1_1", with_companions=False)
    attached = rt.attach_companions(
        version_id=static.version_id,
        companion_locations=synthetic_companions.locations("v1_1"),
        attached_by="importer",
    )
    assert attached.joint_state is JointState.NOT_THIS_PANEL
    rt.establish(
        population_id="SYN_STATIC",
        kind=PopulationKind.STATIC,
        version_id=static.version_id,
        actor_id="owner",
        reason="r",
    )
    with pytest.raises(PopulationError) as caught:
        rt.attach_companions(
            version_id=static.version_id,
            companion_locations=synthetic_companions.locations("v1_1"),
            attached_by="importer",
        )
    assert caught.value.reason == "companions_already_attached"


def test_a_failing_companion_rejects_the_whole_import(
    session: Session, synthetic_companions: Any
) -> None:
    from aia_core.infrastructure.population_repository import PopulationRegistryRepository

    rt = runtime(session, synthetic_companions)
    import_label(rt, synthetic_companions, "v1_BASE")
    synthetic_companions.source.put("companions/SCORECARD.csv", b"dimension,score\n")
    with pytest.raises(ImportRejected) as caught:
        import_label(rt, synthetic_companions, "v1_1")
    assert any("SCORECARD.csv.checksum" in f for f in caught.value.failures)
    assert (
        PopulationRegistryRepository(session).version_by_label(
            synthetic_companions.contract.dataset_id, "v1_1"
        )
        is None
    )


def test_the_certified_version_is_refused_with_a_non_binding_certificate(
    session: Session, synthetic_companions: Any, certificate_json: Any
) -> None:
    rt = runtime(session, synthetic_companions)
    import_label(rt, synthetic_companions, "v1_BASE")
    import_label(rt, synthetic_companions, "v1_1")
    # v1_4's certificate location now holds one that certifies another panel.
    wrong = certificate_json(OTHER)
    contract = synthetic_companions.contract
    specs = tuple(
        replace(s, sha256=content_sha256(wrong), byte_size=len(wrong))
        if s.kind is CompanionKind.CORE_JOINT_STATUS
        else s
        for s in contract.companions
    )
    rt_wrong = PopulationRuntime(
        session, contract=replace(contract, companions=specs), source=synthetic_companions.source
    )
    synthetic_companions.source.put("companions/v1_4/CORE_JOINT_STATUS.json", wrong)
    with pytest.raises(ImportRejected) as caught:
        import_label(rt_wrong, synthetic_companions, "v1_4")
    assert any("certifies_panel" in f for f in caught.value.failures)


def test_promotion_to_a_version_without_companions_is_refused(
    session: Session, synthetic_companions: Any
) -> None:
    rt = runtime(session, synthetic_companions)
    versions = {
        label: import_label(rt, synthetic_companions, label)
        for label in ("v1_BASE", "v1_1", "v1_4")
    }
    establish_both(rt, versions)
    pop = synthetic_companions.population
    pop.source.put("panels/v1_5.csv.gz", pop.rebuild("v1_4", lambda r: r[0].update(segment="c")))
    newer = rt.import_version(
        label="v1_5",
        panel_location="panels/v1_5.csv.gz",
        dictionary_location=pop.dictionary_location,
        provenance="synthetic",
        imported_by="importer",
        parent_version_id=versions["v1_4"].version_id,
    )
    with pytest.raises(CompanionsIncomplete):
        rt.promote_live(
            population_id="SYN_LIVE",
            target_version_id=newer.version_id,
            expected_current_version_id=versions["v1_4"].version_id,
            actor_id="owner",
            reason="r",
        )


def test_resolving_a_pinned_version_without_companions_is_refused(
    session: Session, synthetic_companions: Any
) -> None:
    # A pin to a superseded-then-stripped version cannot arise, but a pin must still
    # pass the usability rule rather than the population's.
    rt = runtime(session, synthetic_companions)
    import_label(rt, synthetic_companions, "v1_BASE", with_companions=False)
    with pytest.raises(PopulationError):
        rt.resolve(
            PopulationSelector.pinned(
                import_label(rt, synthetic_companions, "v1_1", with_companions=False).version_id
            )
        )
