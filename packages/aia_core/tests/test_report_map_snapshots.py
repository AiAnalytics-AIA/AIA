"""Frozen map images in the main internal report, including genuine absence and fit."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from aia_core.application.report_maps import (
    PAIR_STATUS,
    compose_map_sections,
    pair_status_means,
)
from aia_core.domain.report.model import Paragraph, SociomapFigure, Table, TextCell
from aia_core.domain.sociomap import (
    AIA_SOCIOMAP_V1,
    AIA_SOCIOMAP_V2,
    AIA_SOCIOMAP_V3,
    ArtifactIntegrityError,
    ObjectMapInputs,
    RatingItem,
    RatingsMatrix,
    RelationMatrix,
    SociomapInputs,
    SociomapSpecV3,
    compute_object_map,
    compute_sociomap,
    read_object_maps,
)
from aia_core.domain.sociomap.layout import correlation_distance
from aia_core.domain.sociomap.relations import PairStatus
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


def test_the_map_chapter_says_its_counts_and_pair_states_in_czech() -> None:
    # "4 objektů" broke Czech agreement and the pair table's state column printed the code
    # ("reliable") in English (cross-review): every state has its words, in the cells and in
    # the table's note.
    frozen = result()
    ((_, artifact),) = read_object_maps(frozen["batteries"][0])
    means = pair_status_means(artifact.relations)
    assert set(PAIR_STATUS) == set(PairStatus) == set(means)
    sections = compose_map_sections(frozen, object_map_snapshots(frozen), source="Frozen map SHA")
    prose = " ".join(
        i.text
        for b in sections[0].blocks
        if isinstance(b, Paragraph)
        for i in b.content
        if hasattr(i, "text")
    )
    assert "Metoda aia-sociomap-3 zahrnuje 4 objekty." in prose
    (table,) = [b for b in sections[0].blocks if isinstance(b, Table)]
    assert table.columns[-1].label == "Stav vztahu"
    states = [r.cells[-1].text for r in table.rows if isinstance(r.cells[-1], TextCell)]
    assert len(states) == 6 and set(states) <= set(PAIR_STATUS.values())
    for status in PairStatus:
        assert f"{PAIR_STATUS[status]}: {means[status]}" in table.notes[0]
    words = " ".join([*states, *table.notes])
    assert not any(code in words for code in ("reliable", "RELIABLE", "WEAK", "UNKNOWN"))


def weighted_result(spec: SociomapSpecV3) -> dict:
    """Five fictional objects, ten respondents weighted 5 and seventy weighted 1; ``d`` and
    ``e`` each unrated by sixteen of the latter, so the pair ``(d, e)`` keeps 48 common raters
    whose weights' effective n is 26.9, below the methods' n_min of 30."""
    rng = random.Random(92)
    objects = ("a", "b", "c", "d", "e")
    values: list[tuple[float | None, ...]] = []
    for k in range(80):
        row: list[float | None] = [float(rng.randint(1, 10)) for _ in objects]
        if 10 <= k < 26:
            row[3] = None
        if 26 <= k < 42:
            row[4] = None
        values.append(tuple(row))
    data = ObjectMapInputs(
        respondent_ids=tuple(f"FIC-{i}" for i in range(80)),
        donor_ids=tuple(f"DONOR-{i}" for i in range(80)),
        items=tuple(RatingItem(item_id=o, scale_min=1, scale_max=10) for o in objects),
        values=tuple(values),
        weights=(5.0,) * 10 + (1.0,) * 70,
        object_ids=objects,
        object_items=objects,
        roles=dict.fromkeys(objects, "primary"),
    )
    artifact = compute_object_map(data, spec, connectedness_interval=False)
    return {
        "methodology_status": "INTERNAL_ONLY",
        "batteries": [
            {
                "battery_id": "fictional",
                "title": "Fiktivní nabídky",
                "objects": [{"id": o, "label": f"Objekt {o}"} for o in objects],
                "maps": {spec.methodology_version: artifact.to_payload()},
            }
        ],
    }


def pair_table(frozen: dict) -> Table:
    sections = compose_map_sections(frozen, object_map_snapshots(frozen), source="Frozen map SHA")
    (table,) = [b for b in sections[0].blocks if isinstance(b, Table)]
    return table


def test_a_pair_state_is_explained_by_the_n_its_method_decided_it_on() -> None:
    # aia-sociomap-3 decides a pair's state on the effective n of its raters' weights, and
    # the note said "neznámý: málo společných odpovědí" beside 48 of them at n_min 30
    # (cross-review): under that basis the table prints the effective n, and no state is
    # explained by the count.
    table = pair_table(weighted_result(AIA_SOCIOMAP_V3))
    labels = [c.label for c in table.columns]
    assert labels == [
        "Dvojice objektů",
        "Korelace r",
        "Společné odpovědi",
        "Efektivní n",
        "Stav vztahu",
    ]
    cells = {
        r.cells[0].text: [c.text for c in r.cells if isinstance(c, TextCell)] for r in table.rows
    }
    assert cells["Objekt d \u00d7 Objekt e"][2:] == ["48", "26", "neznámý"]
    assert cells["Objekt a \u00d7 Objekt b"][2:4] == ["80", "45"]
    note = table.notes[0]
    assert "neznámý: efektivní n pod 30, nebo korelaci nelze spočítat" in note
    assert "spolehlivý: efektivní n aspoň 30 a interval korelace nezahrnuje nulu" in note
    # Weak: the interval includes zero, so the correlation is not told apart from zero ("od
    # žádného" read as "from any relation", cross-review).
    assert (
        "slabý: efektivní n aspoň 30, ale interval korelace zahrnuje nulu, takže korelaci "
        "nelze odlišit od nuly" in note
    )
    assert "žádného" not in note
    assert "stav vztahu se řídí jím, nikoli počtem společných odpovědí" in note
    assert "málo společných" not in note and "aspoň 30 společných" not in note
    # The same answers under the count: no effective n, and the states read the count.
    counted = pair_table(weighted_result(AIA_SOCIOMAP_V2))
    assert "Efektivní n" not in [c.label for c in counted.columns]
    assert (
        "neznámý: méně než 30 společných odpovědí, nebo korelaci nelze spočítat"
        in (counted.notes[0])
    )
    assert (
        "slabý: aspoň 30 společných odpovědí, ale interval korelace zahrnuje nulu, takže "
        "korelaci nelze odlišit od nuly" in counted.notes[0]
    )
    assert "efektivní n" not in counted.notes[0].lower()


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


def test_a_map_stored_under_another_method_is_refused_by_report_and_figure_alike() -> None:
    # Both readers go through read_object_maps: neither describes nor draws a map the run did
    # not compute under the name it is stored by (the figure renderer used not to check).
    frozen = result()
    maps = frozen["batteries"][0]["maps"]
    maps["aia-sociomap-2"] = maps.pop(AIA_SOCIOMAP_V3.methodology_version)
    with pytest.raises(ValueError, match="differs from its stored key"):
        object_map_snapshots(frozen)
    with pytest.raises(ValueError, match="differs from its stored key"):
        compose_map_sections(frozen, {}, source="Frozen map SHA")


def test_read_object_maps_reads_in_stored_order_and_refuses_another_contract() -> None:
    frozen = result()
    battery = frozen["batteries"][0]
    [(method, artifact)] = read_object_maps(battery)
    assert method == AIA_SOCIOMAP_V3.methodology_version
    assert artifact.spec.methodology_version == method
    assert read_object_maps({"maps": {}}) == () == read_object_maps({})
    # A genuine contract-2 map stored where a contract-3 one belongs is refused, not drawn.
    objects = ("a", "b", "c", "d")
    contract_2 = compute_sociomap(
        SociomapInputs(
            ratings=RatingsMatrix(
                respondent_ids=("p0", "p1", "p2", "p3"),
                object_ids=objects,
                values=((9, 3, 5, 1), (2, 8, 4, 7), (6, 6, 9, 2), (1, 2, 3, 10)),
            ),
            object_relation=RelationMatrix(
                entity_ids=objects,
                values=((0, 4, 9, 2), (6, 0, 3, 8), (7, 5, 0, 1), (3, 9, 2, 0)),
            ),
        ),
        AIA_SOCIOMAP_V1,
    ).to_payload()
    with pytest.raises(ArtifactIntegrityError, match="must use contract 3"):
        read_object_maps({"maps": {AIA_SOCIOMAP_V1.methodology_version: contract_2}})
