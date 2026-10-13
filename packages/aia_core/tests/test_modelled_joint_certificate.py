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
