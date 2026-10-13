"""A modelled run is judged under its population's certificate (complete-study-report B5a).

A client-facing claim needs a certified ``CORE_JOINT_STATUS``. A native research run used to be
judged with none, so no client claim of it could ever pass. A panel run now records the
certificate of the population its respondents were drawn from, with the panel SHA-256 the loader
verified it against; its evidence is judged under that, re-hashed and re-checked on every read.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from conftest import joint_certificate_json
from test_analysis_native import DATASET_SHA, run

from aia_core.application.analysis_results import SourcesRefused, _joint_certificate
from aia_core.domain.analysis.native import native_evidence
from aia_core.domain.evidence.support import REFERENCE_THRESHOLDS
from aia_core.domain.fieldwork import JOINT_CERTIFICATE_METADATA, DataOrigin

PANEL = "c" * 64
MODELLED = DataOrigin.MODELLED_AI_PANEL


def _record(data: bytes, panel: str = PANEL) -> dict[str, str]:
    text = data.decode("utf-8-sig")
    return {
        "certificate": text,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "panel_sha256": panel,
    }


def _certificate(**overrides: Any) -> bytes:
    return joint_certificate_json(PANEL, production_panel="PANEL_v1.csv.gz", **overrides)


def _evidence(certificate: tuple[bytes, str] | None) -> Any:
    spec, _, aggregate = run()
    return native_evidence(
        spec,
        {**aggregate, "data_origin": MODELLED.value},
        dataset_sha256=DATASET_SHA,
        origin=MODELLED,
        support=REFERENCE_THRESHOLDS,
        joint_certificate=certificate,
    )


def test_a_recorded_certificate_is_re_hashed_and_read_for_a_modelled_run_only() -> None:
    data = _certificate()
    meta = {JOINT_CERTIFICATE_METADATA: _record(data)}
    assert _joint_certificate(MODELLED, meta) == (data, PANEL)
    assert _joint_certificate(MODELLED, {}) is None
    # A simulated run is never judged for a client: whatever it recorded is not read.
    assert _joint_certificate(DataOrigin.SYNTHETIC_AI_FICTIONAL, meta) is None


def test_a_record_with_a_byte_order_mark_still_verifies() -> None:
    data = b"\xef\xbb\xbf" + _certificate()
    held = _joint_certificate(MODELLED, {JOINT_CERTIFICATE_METADATA: _record(data)})
    assert held is not None and json.loads(held[0])["panel_sha256"] == PANEL


@pytest.mark.parametrize(
    "bad",
    [
        {"certificate": "{}", "sha256": "0" * 64, "panel_sha256": PANEL},
        {"certificate": "{}", "sha256": "x"},
        ["not", "a", "record"],
    ],
)
def test_an_altered_or_incomplete_record_is_refused_never_read_as_none(bad: Any) -> None:
    with pytest.raises(SourcesRefused, match="certificate"):
        _joint_certificate(MODELLED, {JOINT_CERTIFICATE_METADATA: bad})


def test_the_evidence_is_certified_under_the_certificate_that_covered_its_respondents() -> None:
    certified = _evidence((_certificate(), PANEL))
    assert certified.joint_status.certified
    # Without one, or against another panel, nothing client-facing: as before.
    assert not _evidence(None).joint_status.certified
    assert not _evidence((_certificate(), "d" * 64)).joint_status.certified
    # The certificate enters the system fingerprint: a run judged under it is a different run.
    assert certified.system_fingerprint != _evidence(None).system_fingerprint


# --- the owner's client-report lift (B5b) ------------------------------------------------


def test_the_owners_lift_frees_modelled_items_for_the_client_report_only() -> None:
    from aia_core.domain.analysis.native import native_items
    from aia_core.domain.evidence import ClaimRule
    from aia_core.domain.evidence.instrument import (
        InstrumentPolicyRefused,
        instrument_declaration_sha256,
        instrument_policy_book,
    )
    from aia_core.domain.evidence.report_lift import MODELLED_CLIENT_REPORT_LIFT as LIFT

    spec, _, _ = run()
    items = native_items(spec)

    def internal(**kw: Any) -> bool:
        book = instrument_policy_book(items, origin=MODELLED, source="t", **kw)
        return any(book.get(f).has(ClaimRule.INTERNAL_ONLY) for f in book.fields)

    system = "a" * 64
    # Unlifted, -2 is internal; the lift frees it only for a run that names its system.
    assert internal(respondent_system=system)
    assert not internal(respondent_system=system, report_lift=LIFT)
    assert internal(report_lift=LIFT)
    # The lift is part of the declaration's identity: never confused with an unlifted book.
    assert instrument_declaration_sha256(
        items, origin=MODELLED, source="t", respondent_system=system, report_lift=LIFT
    ) != instrument_declaration_sha256(items, origin=MODELLED, source="t", respondent_system=system)
    # Simulated answers are never evidence, lift or no lift.
    with pytest.raises(InstrumentPolicyRefused):
        instrument_policy_book(
            items, origin=DataOrigin.SYNTHETIC_AI_FICTIONAL, source="t", report_lift=LIFT
        )
    assert LIFT.surface == "CLIENT_REPORT" and LIFT.decided_on.isoformat() == "2026-10-13"


def test_client_facing_analysis_stays_blocked_because_it_never_passes_the_lift() -> None:
    from aia_core.domain.analysis import ANALYSIS_MODULES
    from aia_core.domain.analysis.native import native_preflight
    from aia_core.domain.evidence import ClaimSurface, ViolationCode

    # Certified, with a respondent system: only the lift is missing, and analysis never has it.
    spec, _, aggregate = run()
    evidence = native_evidence(
        spec,
        {**aggregate, "data_origin": MODELLED.value},
        dataset_sha256=DATASET_SHA,
        origin=MODELLED,
        support=REFERENCE_THRESHOLDS,
        respondent_system="a" * 64,
        joint_certificate=(_certificate(), PANEL),
    )
    for module in ANALYSIS_MODULES:
        codes = {
            v.code
            for v in native_preflight(
                module, evidence, surface=ClaimSurface.CLIENT_FACING, research_questions=("?",)
            )
        }
        assert ViolationCode.FIELD_INTERNAL_ONLY in codes
