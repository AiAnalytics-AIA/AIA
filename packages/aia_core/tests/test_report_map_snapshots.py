"""Frozen map images in the main internal report, including genuine absence and fit."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from aia_core.application.report_maps import compose_map_sections
from aia_core.domain.report.model import Paragraph, SociomapFigure
from aia_core.domain.sociomap import (
    AIA_SOCIOMAP_V3,
    ObjectMapInputs,
    RatingItem,
    compute_object_map,
)
from aia_core.domain.sociomap.layout import correlation_distance
from aia_core.infrastructure.report_docx.cover import ASSET
from aia_core.infrastructure.report_docx.object_map_figure import object_map_snapshots


def result(*, flat: bool = False) -> dict:
    rng = random.Random(92)
    objects = ("a", "b", "c", "d")
    data = ObjectMapInputs(
        respondent_ids=tuple(f"FIC-{i}" for i in range(40)),
        donor_ids=tuple(f"DONOR-{i // 2}" for i in range(40)),
        items=tuple(RatingItem(item_id=o, scale_min=1, scale_max=10) for o in objects),
        values=tuple(
            tuple(5.0 if flat else float(rng.randint(1, 10)) for _ in objects) for _ in range(40)
        ),
        weights=(1.0,) * 40,
        object_ids=objects,
        object_items=objects,
        roles=dict.fromkeys(objects, "primary"),
    )
    artifact = compute_object_map(data, AIA_SOCIOMAP_V3, connectedness_interval=False)
    return {
        "methodology_status": "INTERNAL_ONLY",
        "batteries": [
            {
                "battery_id": "fictional",
                "title": "Fiktivní nabídky",
                "objects": [{"id": o, "label": f"Objekt {o}"} for o in objects],
                "maps": {AIA_SOCIOMAP_V3.methodology_version: artifact.to_payload()},
            }
        ],
    }


def test_both_views_preserve_the_frozen_artifact_and_are_deterministic() -> None:
    frozen = result()
    before = repr(frozen)
    images = object_map_snapshots(frozen)
    assert len(images) == 2
    assert images == object_map_snapshots(frozen)
    assert repr(frozen) == before
    sections = compose_map_sections(frozen, images, source="Frozen map SHA")
    figures = [b for b in sections[0].blocks if isinstance(b, SociomapFigure)]
    assert len(figures) == 2 and all(f.image_png.startswith(b"\x89PNG") for f in figures)
    assert all(f.methodology_status == "INTERNAL_ONLY" and f.stress_1 is not None for f in figures)
    prose = " ".join(
        i.text
        for b in sections[0].blocks
        if isinstance(b, Paragraph)
        for i in b.content
        if hasattr(i, "text")
    )
    assert "20" in prose and "donorů" in prose and "Prázdné oblasti" in prose


def test_no_map_does_not_become_a_fabricated_flat_image() -> None:
    frozen = result(flat=True)
    assert object_map_snapshots(frozen) == {}
    sections = compose_map_sections(frozen, {}, source="Frozen map SHA")
    assert not any(isinstance(b, SociomapFigure) for b in sections[0].blocks)
    assert any(
        isinstance(b, Paragraph) and "mapa nevznikla" in str(b.content) for b in sections[0].blocks
    )


def test_missing_snapshot_and_tampered_map_fail_closed() -> None:
    frozen = result()
    with pytest.raises(ValueError, match="missing map snapshot"):
        compose_map_sections(frozen, {}, source="Frozen map SHA")
    frozen["batteries"][0]["maps"]["aia-sociomap-3"]["artifact_fingerprint"] = "0" * 64
    with pytest.raises(ValueError, match="fingerprint"):
        object_map_snapshots(frozen)


def test_cover_artwork_is_the_original_packaged_design_asset() -> None:
    root = Path(__file__).resolve().parents[3]
    assert (
        ASSET.read_bytes()
        == (root / "design-system/assets/motif/report-cover-field.svg").read_bytes()
    )


def test_reading_guide_matches_signed_correlation_distance_not_link_strength() -> None:
    # A link's thickness can use |r|; the map target distance cannot drop its sign.
    assert correlation_distance(-0.8) > correlation_distance(0.0) > correlation_distance(0.8)
    frozen = result()
    sections = compose_map_sections(frozen, object_map_snapshots(frozen), source="Frozen map SHA")
    prose = " ".join(
        i.text
        for b in sections[0].blocks
        if isinstance(b, Paragraph)
        for i in b.content
        if hasattr(i, "text")
    )
    assert "z korelace se znaménkem" in prose
    assert "silný záporný vztah znamená větší cílovou vzdálenost" in prose
    assert "bez ohledu na znaménko" not in prose
