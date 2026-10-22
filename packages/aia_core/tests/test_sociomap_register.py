"""The Sociomap register: a method approved at its exact specification (B4)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from test_report_map_snapshots import result as stored_result

from aia_core.application.report_maps import compose_map_sections
from aia_core.domain.fieldwork import FieldworkDataset
from aia_core.domain.report.model import Callout, SociomapFigure, Text
from aia_core.domain.research_design import compile_design
from aia_core.domain.research_sociomap import (
    SociomapMethod,
    SociomapNotApproved,
    default_methods,
    require_client_facing,
    research_sociomaps,
)
from aia_core.domain.sociomap.specification import (
    AIA_SOCIOMAP_V1,
    AIA_SOCIOMAP_V3,
    AIA_SOCIOMAP_V5,
)
from aia_core.domain.sociomap_register import (
    SOCIOMAP_REGISTER,
    MethodologyStatus,
    approval_of,
    method_status,
    recorded_statuses,
)
from aia_core.domain.synthetic_fieldwork import synthetic_dataset
from aia_core.infrastructure.report_docx.object_map_figure import object_map_snapshots

V3 = SociomapMethod.of(AIA_SOCIOMAP_V3)
V1 = SociomapMethod.of(AIA_SOCIOMAP_V1)
V5 = SociomapMethod.of(AIA_SOCIOMAP_V5)


def test_the_owners_decision_approves_aia_sociomap_3_exactly_as_the_code_computes_it() -> None:
    """If the preset changes, its fingerprint changes and this fails: a changed method is a
    new decision, never carried by the old entry."""
    entry, _ = SOCIOMAP_REGISTER
    assert (entry.method_id, entry.spec_fingerprint) == (V3.method_id, V3.spec_fingerprint)
    assert entry.status is MethodologyStatus.CLIENT_FACING
    assert entry.decided_on == date(2026, 10, 13)
    assert approval_of(V3.method_id, V3.spec_fingerprint) == entry
    # Kept for the runs that pinned it; no new run does.
    assert V3 not in default_methods()


def test_the_methodologists_decision_approves_aia_sociomap_5_exactly_as_new_runs_pin_it() -> None:
    _, entry = SOCIOMAP_REGISTER
    assert (entry.method_id, entry.spec_fingerprint) == (V5.method_id, V5.spec_fingerprint)
    assert entry.spec_fingerprint == AIA_SOCIOMAP_V5.fingerprint()
    assert entry.status is MethodologyStatus.CLIENT_FACING
    assert (entry.decided_by, entry.decided_on) == ("metodik AIA", date(2026, 10, 21))
    assert approval_of(V5.method_id, V5.spec_fingerprint) == entry
    # What every new run pins is exactly what the entry approves.
    assert default_methods() == (V5,)
    # An edited version, or the same spec with a replaced formula, is another method.
    assert approval_of("aia-sociomap-5+e1", V5.spec_fingerprint) is None
    assert approval_of(V5.method_id, V5.spec_fingerprint, {"f12.kernel": "h"}) is None


def _small_study() -> tuple[Any, FieldworkDataset]:
    spec, problems = compile_design(
        {
            "n": 60,
            "sections": [
                {
                    "type": "object_battery",
                    "object_family": "značky",
                    "objects": ["A", "B", "C", "D"],
                    "scale": [1, 10],
                }
            ],
        }
    )
    assert spec is not None, problems
    return spec, synthetic_dataset(spec, seed=15)


def test_a_new_runs_map_is_client_facing_and_an_edited_versions_is_not() -> None:
    spec, dataset = _small_study()
    new = research_sociomaps(spec, dataset, methods=default_methods(), connectedness_interval=False)
    assert new["methodology_status"] == "CLIENT_FACING"
    require_client_facing(new)  # passes: the register approves aia-sociomap-5 as pinned
    edited = AIA_SOCIOMAP_V5.model_copy(update={"methodology_version": "aia-sociomap-5+e1"})
    run = research_sociomaps(
        spec, dataset, methods=(SociomapMethod.of(edited),), connectedness_interval=False
    )
    assert run["methodology_status"] == "INTERNAL_ONLY"
    with pytest.raises(SociomapNotApproved):
        require_client_facing(run)


def test_the_client_report_shows_a_new_runs_maps_its_respondent_map_included() -> None:
    frozen = stored_result(spec=AIA_SOCIOMAP_V5)
    frozen["methods"] = [{"method_id": V5.method_id, "spec_fingerprint": V5.spec_fingerprint}]
    images = object_map_snapshots(frozen)
    (section,) = compose_map_sections(frozen, images, source="Frozen map", client=True)
    figures = [b for b in section.blocks if isinstance(b, SociomapFigure)]
    assert [f.id.rsplit("-", 1)[-1] for f in figures] == ["top", "3d", "respondents"]
    assert all(f.methodology_status == "CLIENT_FACING" for f in figures)
    words = " ".join(
        i.text
        for b in section.blocks
        if isinstance(b, Callout)
        for i in b.content
        if isinstance(i, Text)
    )
    assert "21. 10. 2026 schválil k použití ve zprávách" in words
    # The internal report draws the same three.
    (internal,) = compose_map_sections(frozen, images, source="Frozen map")
    views = [b.id.rsplit("-", 1)[-1] for b in internal.blocks if isinstance(b, SociomapFigure)]
    assert views == ["top", "3d", "respondents"]


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
