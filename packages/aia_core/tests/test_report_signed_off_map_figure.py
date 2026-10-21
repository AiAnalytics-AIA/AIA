"""The signed-off map's report figures, drawn as the AIA panel draws them from the stored map.

The drawing is a port of the methodology's renderer (``sociomap_3d.render`` and
``render_respondents``); it was compared with it pixel for pixel on stored maps outside the
repo (the methodology's code is not part of it). Here: which figures a map gets, that every
drawn thing is read from the stored artifact, and the Czech words.
"""

from __future__ import annotations

import random
from functools import cache

import numpy as np
import pytest
from matplotlib.collections import PathCollection
from matplotlib.figure import Figure

from aia_core.application import report_maps
from aia_core.application.report_maps import compose_map_sections
from aia_core.domain.report.model import Callout, Paragraph, SociomapFigure
from aia_core.domain.sociomap import (
    AIA_SOCIOMAP_V3,
    ObjectMapInputs,
    RatingItem,
    SociomapArtifactV3,
    compute_object_map,
    read_object_maps,
)
from aia_core.domain.sociomap.models_v3 import RespondentMap, SegmentHint
from aia_core.domain.sociomap.specification import AIA_SOCIOMAP_V5, SociomapSpecV3
from aia_core.domain.sociomap_register import SOCIOMAP_REGISTER, MethodologyStatus
from aia_core.infrastructure.report_docx.object_map_figure import object_map_snapshots
from aia_core.infrastructure.report_docx.signed_off_map_figure import (
    SEG_COLORS,
    SEG_GREY,
    VIEWS,
    Camera,
    render_objects,
    render_respondents,
)

OBJECTS = ("pop", "rock", "jazz", "metal", "opera", "folk", "punk", "techno")


@cache
def tastes(spec: SociomapSpecV3 = AIA_SOCIOMAP_V5) -> dict:
    """Two fictional taste groups of 120 each: the first rates the first four objects high and
    the last four low, the second the other way round; some of each rate everything alike."""
    rng = random.Random(7)
    values = []
    for k in range(240):
        if k % 40 == 0:
            values.append((5.0,) * len(OBJECTS))  # a flat profile: never placed
            continue
        high = k < 120
        values.append(
            tuple(
                float(min(10, max(1, round(rng.gauss(8 if (i < 4) == high else 3, 1.6)))))
                for i in range(len(OBJECTS))
            )
        )
    data = ObjectMapInputs(
        respondent_ids=tuple(f"FIC-{i}" for i in range(240)),
        donor_ids=tuple(f"DONOR-{i}" for i in range(240)),
        items=tuple(RatingItem(item_id=o, scale_min=1, scale_max=10) for o in OBJECTS),
        values=tuple(values),
        weights=(1.0,) * 240,
        object_ids=OBJECTS,
        object_items=OBJECTS,
        roles=dict.fromkeys(OBJECTS, "primary"),
    )
    artifact = compute_object_map(data, spec, connectedness_interval=False)
    return {
        "methodology_status": "INTERNAL_ONLY",
        "batteries": [
            {
                "battery_id": "fictional",
                "title": "Fiktivní žánry",
                "objects": [{"id": o, "label": o.capitalize()} for o in OBJECTS],
                "maps": {spec.methodology_version: artifact.to_payload()},
            }
        ],
    }


def stored(spec: SociomapSpecV3 = AIA_SOCIOMAP_V5) -> SociomapArtifactV3:
    ((_, artifact),) = read_object_maps(tastes(spec)["batteries"][0])
    return artifact


def axes(view: str = "side") -> tuple[Figure, Camera]:
    w = 380 if view == "top" else 534
    fig = Figure(figsize=(w / 96, 380 / 96), dpi=96)
    fig.add_axes((0, 0, 1, 1))
    return fig, Camera(w, 380, **VIEWS[view])


def words(fig: Figure) -> str:
    return " | ".join(t.get_text() for t in fig.axes[0].texts)


def test_a_signed_off_map_gets_the_panel_figures_and_its_respondent_map() -> None:
    frozen = tastes()
    images = object_map_snapshots(frozen)
    method = AIA_SOCIOMAP_V5.methodology_version
    assert set(images) == {("fictional", method, v) for v in ("top", "3d", "respondents")}
    assert all(png.startswith(b"\x89PNG") for png in images.values())
    assert images == object_map_snapshots(frozen)  # deterministic
    figures = [
        b
        for b in compose_map_sections(frozen, images, source="Frozen")[0].blocks
        if isinstance(b, SociomapFigure)
    ]
    assert [f.title for f in figures] == [
        f"Fiktivní žánry · {v} · {method}"
        for v in ("Pohled shora", "Prostorový pohled", "Mapa respondentů")
    ]
    assert "Objekty jsou popsané na mapě" in figures[0].alt
    assert "hustotu jasně umístěných respondentů" in figures[2].alt
    # An earlier method keeps its two snapshots, numbered against the legend.
    earlier = tastes(AIA_SOCIOMAP_V3)
    old = object_map_snapshots(earlier)
    assert {k[2] for k in old} == {"top", "3d"}
    (first, *_) = [
        b
        for b in compose_map_sections(earlier, old, source="Frozen")[0].blocks
        if isinstance(b, SociomapFigure)
    ]
    assert "Číslované objekty odpovídají legendě" in first.alt


def test_the_object_map_draws_the_stored_relations_heights_and_words() -> None:
    artifact = stored()
    names = [o.capitalize() for o in artifact.object_ids]
    m = len(names)
    rel = artifact.relations
    strongest = sorted(
        (
            (abs(rel.r[i][j]), i, j)  # type: ignore[arg-type]
            for i in range(m)
            for j in range(i + 1, m)
            if rel.status[i][j] == "reliable"
        ),
        reverse=True,
    )[:5]
    for view in ("top", "side"):
        fig, cam = axes(view)
        info = render_objects(fig.axes[0], artifact, names, cam, scale=(1.0, 10.0))
        assert info["lines"] == strongest
        text = words(fig)
        assert "Výška · Průměrné hodnocení (Relativní)" in text
        assert "nejnižší objekt na 15 % výšky" in text
        values = [1 + 9 * v for v in artifact.heights.values if v is not None]
        assert f"{min(values):.1f}".replace(".", ",") in text
        assert f"{max(values):.1f}".replace(".", ",") in text
        assert "typická nejistota polohy objektu" in text
        # Every label that fits is drawn once, and the note says how many fit when not all do.
        drawn = [t.get_text() for t in fig.axes[0].texts if t.get_text() in names]
        assert len(drawn) == len(set(drawn)) == info["labelled"] >= 1
        assert (f"{info['labelled']} z {m} objektů popsáno" in text) == (info["labelled"] < m)
        assert "Slabě určená mapa" not in text


def test_the_object_map_frame_is_the_stored_one() -> None:
    artifact = stored()
    fig, cam = axes()
    pm = render_objects(fig.axes[0], artifact, list(artifact.object_ids), cam, scale=None)["pm"]
    terrain = artifact.terrain
    centre = np.asarray(terrain.parameters.centre)  # type: ignore[union-attr]
    half = terrain.parameters.half_extent  # type: ignore[union-attr]
    assert np.allclose(pm, (np.asarray(artifact.layout.points) - centre) * 62.0 / half)  # type: ignore[union-attr]
    # The stored frame holds the methodology's: the objects span 70 % of the grid's half-width.
    assert np.isclose(np.abs(pm - (pm.max(0) + pm.min(0)) / 2).max(), 0.7 * 62.0)


def test_the_respondent_map_draws_every_placed_respondent_in_its_segment_colour() -> None:
    artifact = stored()
    resp = artifact.respondents
    assert isinstance(resp, RespondentMap) and resp.segments is not None
    seg = resp.segments
    assert seg.decision == "SEGMENTS" and seg.label is not None and seg.coloured is not None
    fig, cam = axes()
    info = render_respondents(fig.axes[0], artifact, [o.capitalize() for o in OBJECTS], cam)
    placed = [p != "NOT_PLACED" for p in resp.placement]
    assert len(info["pr"]) == sum(placed) == resp.counts["PLACED"] + resp.counts["FADED"]
    dots = [c for c in fig.axes[0].collections if isinstance(c, PathCollection)]
    assert sum(len(c.get_offsets()) for c in dots) == sum(placed)
    colours = [tuple(np.round(rgba[:3], 3)) for c in dots for rgba in c.get_facecolors()]
    hexed = {
        tuple(np.round([int(h[i : i + 2], 16) / 255 for i in (1, 3, 5)], 3)): h
        for h in (*SEG_COLORS, SEG_GREY)
    }
    expected = [
        SEG_COLORS[lab] if col else SEG_GREY
        for lab, col, ok in zip(seg.label, seg.coloured, placed, strict=True)
        if ok
    ]
    assert sorted(hexed[c] for c in colours) == sorted(expected)
    text = words(fig)
    assert "Výška · Shluky respondentů" in text
    assert "Chuťové segmenty" in text and "není jasně v jednom segmentu" in text
    for j, share in enumerate(seg.shares):
        assert f"Segment {j + 1} · {100 * share:.0f} %" in text
    assert f"bez polohy: {resp.counts['NOT_PLACED']} respondentů" in text


def test_a_weakly_determined_map_is_veiled_behind_its_statement_on_both_maps() -> None:
    rng = random.Random(92)
    objects = ("a", "b", "c", "d", "e", "f")
    data = ObjectMapInputs(
        respondent_ids=tuple(f"FIC-{i}" for i in range(60)),
        donor_ids=tuple(f"DONOR-{i}" for i in range(60)),
        items=tuple(RatingItem(item_id=o, scale_min=1, scale_max=10) for o in objects),
        values=tuple(tuple(float(rng.randint(1, 10)) for _ in objects) for _ in range(60)),
        weights=(1.0,) * 60,
        object_ids=objects,
        object_items=objects,
        roles=dict.fromkeys(objects, "primary"),
    )
    artifact = compute_object_map(data, AIA_SOCIOMAP_V5, connectedness_interval=False)
    c = artifact.credibility
    assert c is not None and c.weakly_determined
    title = "Slabě určená mapa" if c.split_half is not None else "Žádná spolehlivá struktura"
    fig, cam = axes()
    assert render_objects(fig.axes[0], artifact, list(objects), cam, scale=None)["statement"]
    assert title in words(fig)
    if isinstance(artifact.respondents, RespondentMap):
        fig, cam = axes()
        assert render_respondents(fig.axes[0], artifact, list(objects), cam)["statement"]
        assert title in words(fig)


def _with(artifact: SociomapArtifactV3, **fields: object) -> SociomapArtifactV3:
    return artifact.model_copy(update=fields)


def test_labels_go_to_the_tallest_hills_first() -> None:
    artifact = stored()
    names = [o.capitalize() for o in artifact.object_ids]
    fig, cam = axes()
    render_objects(fig.axes[0], artifact, names, cam, scale=None)
    drawn = [t.get_text() for t in fig.axes[0].texts if t.get_text() in names]
    rel = artifact.heights.relative
    assert rel is not None
    by_height = [names[i] for i in sorted(range(len(names)), key=lambda i: -(rel[i] or 0))]
    assert drawn == [n for n in by_height if n in drawn]


def test_the_legend_reads_the_declared_floor_and_names_the_objects_nobody_rated() -> None:
    artifact = stored()
    floor = artifact.spec.terrain.relative_height_floor  # type: ignore[union-attr]
    assert floor is not None
    fig, cam = axes()
    render_objects(
        fig.axes[0], _with(artifact, objects_not_placed=("x",)), list(OBJECTS), cam, scale=None
    )
    text = words(fig)
    assert f"nejnižší objekt na {100 * floor:.0f} % výšky" in text
    assert "neumístěno: 1 objekt, nikdo ho nehodnotil" in text
    terrain = artifact.spec.terrain.model_copy(update={"relative_height_floor": 0.3})  # type: ignore[union-attr]
    edited = _with(artifact, spec=artifact.spec.model_copy(update={"terrain": terrain}))
    fig, cam = axes()
    render_objects(
        fig.axes[0],
        _with(edited, objects_not_placed=("x", "y", "z")),
        list(OBJECTS),
        cam,
        scale=None,
    )
    assert "nejnižší objekt na 30 % výšky" in words(fig)
    assert "neumístěno: 3 objekty, nikdo je nehodnotil" in words(fig)


def test_the_sparse_note_shows_only_when_no_statement_veils_the_map() -> None:
    artifact = stored()
    sparse = _with(artifact, sparse_design=artifact.sparse_design.model_copy(update={"flag": True}))  # type: ignore[union-attr]
    note = "Řídký design: polohy málokdy společně hodnocených objektů jsou určeny slabě"
    fig, cam = axes()
    render_objects(fig.axes[0], sparse, list(OBJECTS), cam, scale=None)
    assert note in words(fig)
    credibility = artifact.credibility.model_copy(update={"weakly_determined": True})  # type: ignore[union-attr]
    fig, cam = axes()
    render_objects(
        fig.axes[0], _with(sparse, credibility=credibility), list(OBJECTS), cam, scale=None
    )
    assert note not in words(fig) and "Slabě určená mapa" in words(fig)


def test_the_respondent_map_says_why_it_shows_no_segments() -> None:
    artifact = stored()
    resp = artifact.respondents
    assert isinstance(resp, RespondentMap) and resp.segments is not None
    seg = resp.segments

    def line(**update: object) -> str:
        fig, cam = axes()
        segments = seg.model_copy(update=update)
        render_respondents(
            fig.axes[0],
            _with(artifact, respondents=resp.model_copy(update={"segments": segments})),
            list(OBJECTS),
            cam,
        )
        return words(fig)

    hint = SegmentHint(k=2, shares=(0.6, 0.4), profiles=seg.profiles[:2])
    borderline = line(decision="BORDERLINE", reason=None, hint=hint)
    assert (
        "Náznak 2 skupin · nejisté, body nejsou obarvené" in borderline
        and "Segment 1" not in borderline
    )
    assert "Chuťové segmenty se nehledají (málo dat)" in line(
        decision="NONE", reason="TOO_FEW_RESPONDENTS", hint=None
    )
    assert "Žádné zřetelné chuťové segmenty" in line(
        decision="NONE", reason="NO_CLEAR_SEGMENTS", hint=None
    )
    # The overlap is named only when the shown segments are not distinct.
    assert "překrývají se" not in line(distinct=True)
    assert "Chuťové segmenty · překrývají se, příslušnost nejistá" in line(distinct=False)


def test_a_map_where_nobody_is_placed_is_drawn_without_dots() -> None:
    # Two objects and fifty random raters: mapped, but no respondent's direction is placeable.
    rng = random.Random(3)
    objects = ("a", "b")
    data = ObjectMapInputs(
        respondent_ids=tuple(f"FIC-{i}" for i in range(50)),
        donor_ids=tuple(f"DONOR-{i}" for i in range(50)),
        items=tuple(RatingItem(item_id=o, scale_min=1, scale_max=10) for o in objects),
        values=tuple(tuple(float(rng.randint(1, 10)) for _ in objects) for _ in range(50)),
        weights=(1.0,) * 50,
        object_ids=objects,
        object_items=objects,
        roles=dict.fromkeys(objects, "primary"),
    )
    artifact = compute_object_map(data, AIA_SOCIOMAP_V5, connectedness_interval=False)
    resp = artifact.respondents
    assert isinstance(resp, RespondentMap) and resp.counts["PLACED"] + resp.counts["FADED"] == 0
    images = object_map_snapshots(
        {
            "batteries": [
                {
                    "battery_id": "two",
                    "title": "Dva",
                    "objects": [{"id": o, "label": o} for o in objects],
                    "maps": {AIA_SOCIOMAP_V5.methodology_version: artifact.to_payload()},
                }
            ]
        }
    )
    assert ("two", AIA_SOCIOMAP_V5.methodology_version, "respondents") in images
    fig, cam = axes()
    assert len(render_respondents(fig.axes[0], artifact, list(objects), cam)["pr"]) == 0
    assert "bez polohy: 50 respondentů" in words(fig)


def test_the_respondent_alt_text_names_segment_colours_only_when_they_are_shown() -> None:
    def respondent_alt(frozen: dict) -> str:
        battery = frozen["batteries"][0]
        method = AIA_SOCIOMAP_V5.methodology_version
        images = {
            (battery["battery_id"], method, v): b"\x89PNG" for v in ("top", "3d", "respondents")
        }
        blocks = compose_map_sections(frozen, images, source="Frozen")[0].blocks
        return [b for b in blocks if isinstance(b, SociomapFigure)][-1].alt

    assert "barva bodu chuťový segment" in respondent_alt(tastes())
    # Random ratings: no taste segments, so the dots are not coloured.
    rng = random.Random(92)
    objects = ("a", "b", "c", "d", "e", "f")
    data = ObjectMapInputs(
        respondent_ids=tuple(f"FIC-{i}" for i in range(60)),
        donor_ids=tuple(f"DONOR-{i}" for i in range(60)),
        items=tuple(RatingItem(item_id=o, scale_min=1, scale_max=10) for o in objects),
        values=tuple(tuple(float(rng.randint(1, 10)) for _ in objects) for _ in range(60)),
        weights=(1.0,) * 60,
        object_ids=objects,
        object_items=objects,
        roles=dict.fromkeys(objects, "primary"),
    )
    artifact = compute_object_map(data, AIA_SOCIOMAP_V5, connectedness_interval=False)
    assert isinstance(artifact.respondents, RespondentMap)
    assert (
        artifact.respondents.segments is not None
        and artifact.respondents.segments.decision != "SEGMENTS"
    )
    plain = {
        "batteries": [
            {
                "battery_id": "random",
                "title": "Náhodná",
                "objects": [{"id": o, "label": o} for o in objects],
                "maps": {AIA_SOCIOMAP_V5.methodology_version: artifact.to_payload()},
            }
        ]
    }
    assert "barva bodu chuťový segment" not in respondent_alt(plain)


def test_the_client_report_leaves_the_respondent_map_out(monkeypatch: pytest.MonkeyPatch) -> None:
    # As if the register approved this method for clients (it approves no signed-off one yet).
    method = AIA_SOCIOMAP_V5.methodology_version
    monkeypatch.setattr(
        report_maps, "recorded_statuses", lambda _result: {method: SOCIOMAP_REGISTER[0]}
    )
    assert SOCIOMAP_REGISTER[0].status is MethodologyStatus.CLIENT_FACING
    frozen = tastes()
    images = object_map_snapshots(frozen)
    client = [
        b
        for b in compose_map_sections(frozen, images, source="Frozen", client=True)[0].blocks
        if isinstance(b, SociomapFigure)
    ]
    assert [f.title.split(" · ")[1] for f in client] == ["Pohled shora", "Prostorový pohled"]
    internal = [
        b
        for b in compose_map_sections(frozen, images, source="Frozen")[0].blocks
        if isinstance(b, SociomapFigure)
    ]
    assert len(internal) == 3


def _tiny() -> dict:
    """Eight fictional respondents rating five objects at random: mappable, no relation reliable
    (no split-half score), and fewer objects than an informative respondent map needs."""
    rng = random.Random(0)
    objects = ("a", "b", "c", "d", "e")
    data = ObjectMapInputs(
        respondent_ids=tuple(f"FIC-{i}" for i in range(8)),
        donor_ids=tuple(f"DONOR-{i}" for i in range(8)),
        items=tuple(RatingItem(item_id=o, scale_min=1, scale_max=5) for o in objects),
        values=tuple(tuple(float(rng.randint(1, 5)) for _ in objects) for _ in range(8)),
        weights=(1.0,) * 8,
        object_ids=objects,
        object_items=objects,
        roles=dict.fromkeys(objects, "primary"),
    )
    artifact = compute_object_map(data, AIA_SOCIOMAP_V5, connectedness_interval=False)
    return {
        "batteries": [
            {
                "battery_id": "tiny",
                "title": "Malá sada",
                "objects": [{"id": o, "label": o.upper()} for o in objects],
                "maps": {AIA_SOCIOMAP_V5.methodology_version: artifact.to_payload()},
            }
        ]
    }


def test_the_report_says_no_reliable_structure_as_the_figure_does() -> None:
    frozen = _tiny()
    ((_, artifact),) = read_object_maps(frozen["batteries"][0])
    assert artifact.credibility is not None and artifact.credibility.split_half is None
    blocks = compose_map_sections(frozen, object_map_snapshots(frozen), source="Frozen")[0].blocks
    titles = [b.title for b in blocks if isinstance(b, Callout) and b.title]
    assert "Žádná spolehlivá struktura" in titles and "Slabě určená mapa" not in titles
    fig, cam = axes()
    render_objects(fig.axes[0], artifact, list("ABCDE"), cam, scale=None)
    assert "Žádná spolehlivá struktura" in words(fig)


def test_a_small_set_notes_that_its_respondent_map_is_only_indicative() -> None:
    frozen = _tiny()
    ((_, artifact),) = read_object_maps(frozen["batteries"][0])
    resp = artifact.respondents
    assert isinstance(resp, RespondentMap) and not resp.informative
    fig, cam = axes()
    note = render_respondents(fig.axes[0], artifact, list("ABCDE"), cam)["note"]
    assert (
        note == "Sada má 5 objektů: mapa respondentů je jen orientační "
        f"(spolehlivá od {resp.min_objects})"
    )
    assert note in words(fig)
    # Fewer objects than a respondent's ratings need: nobody can be placed, and it says so.
    placing = artifact.spec.respondent_map
    assert placing is not None
    strict = artifact.spec.model_copy(
        update={"respondent_map": placing.model_copy(update={"min_ratings": 6})}
    )
    fig, cam = axes()
    note = render_respondents(fig.axes[0], _with(artifact, spec=strict), list("ABCDE"), cam)["note"]
    assert note == "Sada má 5 objektů: respondenty nelze umístit (potřeba aspoň 6 hodnocení)"
    # An informative map has no note.
    fig, cam = axes()
    assert (
        render_respondents(fig.axes[0], stored(), [o.capitalize() for o in OBJECTS], cam)["note"]
        is None
    )


def test_the_report_reads_the_declared_scale_and_explains_the_respondent_map() -> None:
    frozen = tastes()
    images = object_map_snapshots(frozen)
    blocks = compose_map_sections(frozen, images, source="Frozen")[0].blocks
    prose = " ".join(
        i.text for b in blocks if isinstance(b, Paragraph) for i in b.content if hasattr(i, "text")
    )
    floor = stored().spec.terrain.relative_height_floor  # type: ignore[union-attr]
    assert (
        "Výška a barva ukazují průměrné hodnocení na škále 1\u201310 vůči ostatním objektům sady: "
        f"nejvýše hodnocený objekt má plnou výšku, nejníže hodnocený {round(100 * floor)} % výšky."
        in prose
    )
    assert "převedené na škálu od nuly do jedné" not in prose
    assert "Mapa respondentů ukazuje každého umístěného respondenta jako bod" in prose
    assert "Barva bodu ukazuje chuťový segment" in prose and "alespoň 80 %" in prose
    # An earlier method keeps its 0-1 sentence and has no respondent paragraph.
    earlier = tastes(AIA_SOCIOMAP_V3)
    old = " ".join(
        i.text
        for b in compose_map_sections(earlier, object_map_snapshots(earlier), source="Frozen")[
            0
        ].blocks
        if isinstance(b, Paragraph)
        for i in b.content
        if hasattr(i, "text")
    )
    assert "převedené na škálu od nuly do jedné" in old and "Mapa respondentů ukazuje" not in old
    # The small set: its 1-5 scale, no segments sought and only indicative.
    small = " ".join(
        i.text
        for b in compose_map_sections(_tiny(), object_map_snapshots(_tiny()), source="Frozen")[
            0
        ].blocks
        if isinstance(b, Paragraph)
        for i in b.content
        if hasattr(i, "text")
    )
    assert "na škále 1\u20135" in small and "mapa respondentů je jen orientační" in small


def _four() -> SociomapArtifactV3:
    """Two fictional taste groups of 100 on four objects: fewer objects than a taste slope needs."""
    rng = random.Random(4)
    objects = ("a", "b", "c", "d")
    values = tuple(
        tuple(
            float(min(10, max(1, round(rng.gauss(8 if (i < 2) == (k < 100) else 3, 1.6)))))
            for i in range(4)
        )
        for k in range(200)
    )
    data = ObjectMapInputs(
        respondent_ids=tuple(f"FIC-{i}" for i in range(200)),
        donor_ids=tuple(f"DONOR-{i}" for i in range(200)),
        items=tuple(RatingItem(item_id=o, scale_min=1, scale_max=10) for o in objects),
        values=values,
        weights=(1.0,) * 200,
        object_ids=objects,
        object_items=objects,
        roles=dict.fromkeys(objects, "primary"),
    )
    return compute_object_map(data, AIA_SOCIOMAP_V5, connectedness_interval=False)


def test_too_few_objects_for_a_taste_and_the_boundary_at_the_declared_minimum() -> None:
    four = _four()
    resp = four.respondents
    assert isinstance(resp, RespondentMap) and resp.segments is not None
    assert resp.segments.reason == "TOO_FEW_OBJECTS"
    fig, cam = axes()
    render_respondents(fig.axes[0], four, list("ABCD"), cam)
    assert "Chuťové segmenty se nehledají (méně než 5 objektů)" in words(fig)
    assert "sada má méně než 5 objektů a chuť člověka se určuje z alespoň 5 hodnocení" in (
        report_maps._respondent_reading(four, resp)
    )
    # Exactly the declared five: the objects suffice; too few respondents is the reason then.
    ((_, five),) = read_object_maps(_tiny()["batteries"][0])
    tiny = five.respondents
    assert isinstance(tiny, RespondentMap) and tiny.segments is not None
    assert len(five.object_ids) == AIA_SOCIOMAP_V5.segments.min_ratings  # type: ignore[union-attr]
    assert tiny.segments.reason == "TOO_FEW_RESPONDENTS"


def test_a_set_with_as_many_objects_as_a_position_needs_is_placed_not_refused() -> None:
    ((_, five),) = read_object_maps(_tiny()["batteries"][0])
    placing = five.spec.respondent_map
    assert placing is not None
    at = five.spec.model_copy(
        update={"respondent_map": placing.model_copy(update={"min_ratings": 5})}
    )
    fig, cam = axes()
    note = render_respondents(fig.axes[0], _with(five, spec=at), list("ABCDE"), cam)["note"]
    assert note is not None and note.endswith("jen orientační (spolehlivá od 6)")
    # One more rating than objects: nobody can be placed, in the figure and the report alike.
    over = five.spec.model_copy(
        update={"respondent_map": placing.model_copy(update={"min_ratings": 6})}
    )
    resp = five.respondents
    assert isinstance(resp, RespondentMap)
    text = report_maps._respondent_reading(_with(five, spec=over), resp)
    assert text == (
        "Sada má méně objektů, než kolik hodnocení potřebuje poloha respondenta (6): "
        "respondenty nelze umístit."
    )
