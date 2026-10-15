"""The Sociomap register: a method approved at its exact specification (B4)."""

from __future__ import annotations

from datetime import date
from typing import Any

from test_report_map_snapshots import result as stored_result

from aia_core.application.report_maps import compose_map_sections
from aia_core.domain.report.model import Callout, SociomapFigure, Text
from aia_core.domain.research_sociomap import SociomapMethod, default_methods
from aia_core.domain.sociomap.specification import AIA_SOCIOMAP_V1, AIA_SOCIOMAP_V3
from aia_core.domain.sociomap_register import (
    SOCIOMAP_REGISTER,
    MethodologyStatus,
    approval_of,
    method_status,
    recorded_statuses,
)
from aia_core.infrastructure.report_docx.object_map_figure import object_map_snapshots

V3 = SociomapMethod.of(AIA_SOCIOMAP_V3)
V1 = SociomapMethod.of(AIA_SOCIOMAP_V1)


def test_the_owners_decision_approves_aia_sociomap_3_exactly_as_the_code_computes_it() -> None:
    """If the preset changes, its fingerprint changes and this fails: a changed method is a
    new decision, never carried by the old entry."""
    (entry,) = SOCIOMAP_REGISTER
    assert (entry.method_id, entry.spec_fingerprint) == (V3.method_id, V3.spec_fingerprint)
    assert entry.status is MethodologyStatus.CLIENT_FACING
    assert entry.decided_on == date(2026, 10, 13)
    assert approval_of(V3.method_id, V3.spec_fingerprint) == entry
    # Every new run pins it (beside aia-sociomap-1, which draws the legacy picture).
    assert V3 in default_methods()


def test_anything_else_is_internal_never_presumed_approved() -> None:
    assert method_status(V1.method_id, V1.spec_fingerprint) is MethodologyStatus.INTERNAL_ONLY
    assert method_status(V3.method_id, "0" * 64) is MethodologyStatus.INTERNAL_ONLY
    assert (
        method_status("aia-sociomap-3+e1", V3.spec_fingerprint) is MethodologyStatus.INTERNAL_ONLY
    )
    # A stored version that replaced a formula is another method.
    edited = method_status(V3.method_id, V3.spec_fingerprint, {"F6.target": "1 - r"})
    assert edited is MethodologyStatus.INTERNAL_ONLY


def test_statuses_are_read_from_the_methods_a_stored_result_recorded() -> None:
    recorded = {
        "methods": [
            {"method_id": V1.method_id, "spec_fingerprint": V1.spec_fingerprint},
            {"method_id": V3.method_id, "spec_fingerprint": V3.spec_fingerprint},
        ]
    }
    statuses = recorded_statuses(recorded)
    assert statuses[V1.method_id] is None
    assert statuses[V3.method_id] is SOCIOMAP_REGISTER[0]
    assert recorded_statuses({}) == {}  # stored before methods were recorded: nothing approved


def _figures_and_callouts(frozen: dict[str, Any]) -> tuple[list[SociomapFigure], str]:
    sections = compose_map_sections(frozen, object_map_snapshots(frozen), source="Frozen map")
    blocks = sections[0].blocks
    words = " ".join(
        i.text for b in blocks if isinstance(b, Callout) for i in b.content if isinstance(i, Text)
    )
    return [b for b in blocks if isinstance(b, SociomapFigure)], words


def test_the_report_prints_an_approved_map_as_approved_with_its_note() -> None:
    frozen = stored_result()
    frozen["methods"] = [{"method_id": V3.method_id, "spec_fingerprint": V3.spec_fingerprint}]
    figures, words = _figures_and_callouts(frozen)
    assert figures and all(f.methodology_status == "CLIENT_FACING" for f in figures)
    assert "13. 10. 2026 schválil k použití ve zprávách" in words
    assert "čeká na schválení" not in words


def test_the_report_keeps_a_map_of_any_other_specification_internal() -> None:
    frozen = stored_result()
    frozen["methods"] = [{"method_id": V3.method_id, "spec_fingerprint": "1" * 64}]
    figures, words = _figures_and_callouts(frozen)
    assert figures and all(f.methodology_status == "INTERNAL_ONLY" for f in figures)
    assert "čeká na schválení" in words
