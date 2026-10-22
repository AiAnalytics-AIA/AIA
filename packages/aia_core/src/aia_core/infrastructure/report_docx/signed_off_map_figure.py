"""The signed-off methodology's maps (``aia-sociomap-5``) in the report, drawn as the AIA panel.

A port of the methodology's renderer (``sociomap_3d.render`` and ``render_respondents``): the
same camera, slab, terrain triangles, contours, relation lines, nodes, labels, legend and
statements, line for line. Only the inputs differ: the methodology fits the frame and computes
the terrain and the respondents' density from the layout; here all of it is read from the
stored artifact (the frame's centre and half-width, the relative envelope, the density, the
relative heights, the credibility), which the engine computed by the same rules. Nothing here
computes a methodological number. The words are the web map's, in Czech (:data:`CZECH`).
"""

from __future__ import annotations

import math
import textwrap
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final, cast

import contourpy
import numpy as np
from matplotlib import patheffects
from matplotlib.axes import Axes
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

from aia_core.domain.report.numbers import counted
from aia_core.domain.sociomap import SociomapArtifactV3
from aia_core.domain.sociomap.models_v3 import RespondentMap
from aia_core.domain.sociomap.specification import RelationEstimator
from aia_core.domain.sociomap.terrain import EnvelopeTerrain
from aia_core.infrastructure.report_docx.plotting import drawing, export, new_figure

STOPS: Final = np.array(
    [
        (4, 14, 60),
        (0, 82, 159),
        (0, 185, 205),
        (20, 210, 116),
        (124, 231, 0),
        (244, 232, 27),
        (255, 143, 22),
        (232, 35, 29),
    ],
    float,
)
SPAN: Final = 62.0  # the frame's half-width in drawing units
BG: Final = "#07090c"
WARM: Final = "#ffb35c"
COOL: Final = "#6fa8ff"
SEG_COLORS: Final = ("#7fd3ff", "#ffc46b", "#ff8fb1", "#b9f27c")
SEG_GREY: Final = "#9aa3ad"
CONTOURS: Final = (0.16, 0.28, 0.40, 0.52, 0.64, 0.76, 0.88)
#: The methodology's figure: 534 x 380 px at 96 dpi, legend at 1.2. Its top view is square, where
#: the legend runs into the line key; the report draws the top view at the same size as the side.
WIDTH_PX: Final = 534
HEIGHT_PX: Final = 380
LEGEND_SCALE: Final = 1.2
VIEWS: Final[dict[str, dict[str, Any]]] = {
    "top": {"yaw": 0.0, "pitch": 0.02, "zoom": 0.86, "pan": (0.0, 0.08 / (0.0087 * 0.86))},
    "side": {"yaw": -0.55, "pitch": 0.72, "zoom": 0.92},
}


@dataclass(frozen=True)
class FigureTexts:
    """Every word the figures print; a test swaps in the methodology's own to compare pixels."""

    height_title: str
    lowest: str  # {floor}
    line_key: str
    labelled: str  # {shown}, {total}
    not_placed_objects: Callable[[int], str]
    uncertainty: str
    weak_title: str
    weak_body: str  # {percent}
    none_title: str
    none_body: str
    sparse: str
    density_title: str
    few: str
    many: str
    dots_key: str
    respondents_not_placed: Callable[[int], str]
    segments_title: str
    segments_overlap: str
    segment_row: str  # {n}, {share}
    segment_likes: str  # {labels}
    segment_grey: str
    segments_none: str
    segments_too_few: str
    segments_hint: str  # {k}
    decimal_comma: bool


CZECH: Final = FigureTexts(
    height_title="Výška · Průměrné hodnocení (Relativní)",
    lowest="nejnižší objekt na {floor} % výšky",
    line_key="teplá = souhlasně · studená = opačně\n"
    "šířka = síla · 5 nejsilnějších spolehlivých dvojic",
    labelled="{shown} z {total} objektů popsáno",
    not_placed_objects=lambda n: (
        f"neumístěno: {counted(n, 'objekt', 'objekty', 'objektů')}, "
        + ("nikdo ho nehodnotil" if n == 1 else "nikdo je nehodnotil")
    ),
    uncertainty="typická nejistota polohy objektu",
    weak_title="Slabě určená mapa",
    weak_body="Dvě poloviny vzorku se shodnou jen v {percent} % srovnání „co je blíž“ "
    "(50 % = náhoda). Pozice na mapě nečtěte jako skupiny ani vzdálenosti.",
    none_title="Žádná spolehlivá struktura",
    none_body="Žádný vztah mezi objekty se neliší od náhody. Pozice na mapě nečtěte jako "
    "skupiny ani vzdálenosti.",
    sparse="Řídký design: polohy málokdy společně hodnocených objektů jsou určeny slabě",
    density_title="Výška · Shluky respondentů",
    few="málo",
    many="hodně",
    dots_key="body = respondenti (světlé: slabě umístění)\n"
    "blízko objektu = hodnotí ho nad svým průměrem",
    respondents_not_placed=lambda n: (
        f"bez polohy: {counted(n, 'respondent', 'respondenti', 'respondentů')}"
    ),
    segments_title="Chuťové segmenty",
    segments_overlap=" · překrývají se, příslušnost nejistá",
    segment_row="Segment {n} · {share} %",
    segment_likes=" · výš: {labels}",
    segment_grey="není jasně v jednom segmentu",
    segments_none="Žádné zřetelné chuťové segmenty",
    segments_too_few="Chuťové segmenty se nehledají (málo dat)",
    segments_hint="Náznak {k} skupin · nejisté, body nejsou obarvené",
    decimal_comma=True,
)


def is_signed_off(artifact: SociomapArtifactV3) -> bool:
    """Whether the signed-off methodology computed the map, whatever name it is pinned under."""
    return artifact.spec.relation.estimator == RelationEstimator.BASELINE_CORRECTED_PEARSON


class Camera:
    """The panel's orthographic camera (``projection66``), as the methodology's ``Cam``."""

    def __init__(
        self,
        w: float,
        h: float,
        yaw: float,
        pitch: float,
        zoom: float = 1.0,
        pan: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        self.w, self.h, self.yaw, self.pitch, self.pan = w, h, yaw, pitch, pan
        self.sc = min(w, h) * 0.0087 * zoom

    def __call__(self, x: Any, y: Any, z: Any) -> tuple[Any, Any, Any]:
        x, y, z = (
            np.asarray(x, float) - self.pan[0],
            np.asarray(y, float) - self.pan[1],
            np.asarray(z, float),
        )
        rx = x * math.cos(self.yaw) - y * math.sin(self.yaw)
        ry = x * math.sin(self.yaw) + y * math.cos(self.yaw)
        sx = self.w / 2 + rx * self.sc
        sy = 0.58 * self.h + (ry * math.cos(self.pitch) - z * math.sin(self.pitch)) * self.sc
        return sx, sy, ry * math.sin(self.pitch) + z * math.cos(self.pitch)


def color66(t: Any) -> Any:
    t = np.clip(np.nan_to_num(np.asarray(t, float), nan=0.0), 0, 1) * 7
    i = np.minimum(t.astype(int), 6)
    f = (t - i)[..., None]
    return STOPS[i] * (1 - f) + STOPS[i + 1] * f


def node_scale(m: int) -> float:
    return min(1.0, float((30.0 / max(m, 1)) ** 0.5))


def _grid(n: int) -> Any:
    return -SPAN + 2 * SPAN * np.arange(n + 1) / n


def _terrain_at(g: Any, z: Any, x: float, y: float) -> float:
    n = len(g) - 1
    step = g[1] - g[0]
    fx, fy = (x - g[0]) / step, (y - g[0]) / step
    i, j = int(np.clip(np.floor(fx), 0, n - 1)), int(np.clip(np.floor(fy), 0, n - 1))
    ax, ay = fx - i, fy - j
    return float(
        z[j, i] * (1 - ax) * (1 - ay)
        + z[j, i + 1] * ax * (1 - ay)
        + z[j + 1, i] * (1 - ax) * ay
        + z[j + 1, i + 1] * ax * ay
    )


def _frame(artifact: SociomapArtifactV3, x: Any) -> Any:
    """Ruler positions in frame units, by the stored frame (the methodology's ``frame_fit``)."""
    terrain = artifact.terrain
    assert isinstance(terrain, EnvelopeTerrain)
    centre = np.asarray(terrain.parameters.centre or (0.0, 0.0), float)
    # (n, 2) even for no point: a respondent map where nobody is placed draws no dot.
    return (np.asarray(x, float).reshape(-1, 2) - centre) * SPAN / terrain.parameters.half_extent


def _background(ax: Axes, cam: Camera) -> None:
    ax.set_xlim(0, cam.w)
    ax.set_ylim(cam.h, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), cam.w, cam.h, color=BG, zorder=0))


def _triangles(cam: Camera, g: Any, t: Any) -> tuple[Any, Any]:
    """The terrain's two triangles per cell in painter's order, coloured by height."""
    n = len(g) - 1
    gx, gy = np.meshgrid(g, g)
    sx, sy, dp = cam(gx, gy, 26 * t)
    tris, tm, dm = [], [], []
    for a, b, c in (((0, 0), (0, 1), (1, 1)), ((0, 0), (1, 1), (1, 0))):
        ia = (slice(a[0], n + a[0]), slice(a[1], n + a[1]))
        ib = (slice(b[0], n + b[0]), slice(b[1], n + b[1]))
        ic = (slice(c[0], n + c[0]), slice(c[1], n + c[1]))
        tri = np.stack(
            [
                np.stack([sx[ia], sy[ia]], -1),
                np.stack([sx[ib], sy[ib]], -1),
                np.stack([sx[ic], sy[ic]], -1),
            ],
            -2,
        ).reshape(-1, 3, 2)
        tris.append(tri)
        tm.append(((t[ia] + t[ib] + t[ic]) / 3).ravel())
        dm.append(((dp[ia] + dp[ib] + dp[ic]) / 3).ravel())
    all_tris, all_tm, order = (
        np.concatenate(tris),
        np.concatenate(tm),
        np.argsort(np.concatenate(dm)),
    )
    rgb = np.minimum(color66(all_tm) * (0.78 + 0.28 * all_tm)[:, None], 255) / 255
    fc = np.c_[rgb, np.full(len(all_tm), 0.94)]
    return all_tris[order], fc[order]


def _contours(ax: Axes, cam: Camera, g: Any, t: Any, width: float) -> None:
    segs = []
    generator = contourpy.contour_generator(g, g, t)
    for lv in CONTOURS:
        for line in cast(list[Any], generator.lines(lv)):
            sx, sy, _ = cam(line[:, 0], line[:, 1], np.full(len(line), 26 * lv + 0.08))
            segs.append(np.c_[sx, sy])
    ax.add_collection(
        LineCollection(
            segs, colors=[(5 / 255, 10 / 255, 12 / 255, 0.30)], linewidths=width, zorder=3
        )
    )


def _inside(ax: Axes, text: Any, right: float) -> None:
    """Pull a centred caption left until it ends at right: the Czech caption is longer than
    the methodology's English one, which fits its corner."""
    box = text.get_window_extent()
    (_, _), (x1, _) = ax.transData.inverted().transform([(box.x0, 0), (box.x1, 0)])
    if x1 > right:
        text.set_x(text.get_position()[0] - (x1 - right))


def _number(v: float, digits: int, texts: FigureTexts) -> str:
    s = f"{v:.{digits}f}"
    return s.replace(".", ",") if texts.decimal_comma else s


def _statement(ax: Axes, cam: Camera, title: str, body: str, s: float) -> None:
    """The map de-emphasised behind its statement (weakly determined, or no reliable structure)."""
    w, h = cam.w, cam.h
    ax.add_patch(Rectangle((0, 0), w, h, color=BG, alpha=0.62, zorder=9.6))
    bw, bh = min(w - 40 * s, 330 * s), 78 * s
    ax.add_patch(
        FancyBboxPatch(
            (w / 2 - bw / 2, h * 0.42 - 24 * s),
            bw,
            bh,
            boxstyle="round,pad=0,rounding_size=6",
            fc=BG,
            ec=(1, 1, 1, 0.25),
            lw=0.8,
            alpha=0.92,
            zorder=9.65,
        )
    )
    ax.text(
        w / 2,
        h * 0.42 - 10 * s,
        title,
        ha="center",
        va="center",
        color="white",
        fontsize=12 * s,
        weight="bold",
        zorder=9.7,
    )
    body = body[:1].upper() + body[1:]
    ax.text(
        w / 2,
        h * 0.42 + 6 * s,
        "\n".join(textwrap.wrap(body, 60)),
        ha="center",
        va="top",
        color="#cfd6de",
        fontsize=6.6 * s,
        zorder=9.7,
        linespacing=1.3,
    )


def _statement_texts(artifact: SociomapArtifactV3, texts: FigureTexts) -> tuple[str, str] | None:
    c = artifact.credibility
    if c is None or not c.weakly_determined:
        return None
    if c.split_half is None:
        return texts.none_title, texts.none_body
    return texts.weak_title, texts.weak_body.format(percent=f"{100 * c.split_half:.0f}")


def _labels(ax: Axes, nx: Any, ny: Any, names: list[str], order: list[int]) -> int:
    """Greedy, non-overlapping labels in the given priority order; returns how many fit."""
    placed: list[tuple[float, float, float, float]] = []
    for i in order:
        wbox = len(names[i]) * 6.2 + 6
        x0, y0 = nx[i] - wbox / 2, ny[i] - 12 - 7
        box = (x0, y0, x0 + wbox, y0 + 14)
        if any(
            not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in placed
        ):
            continue
        placed.append(box)
        ax.text(
            nx[i],
            ny[i] - 12,
            names[i],
            color="white",
            fontsize=11 * 0.75,
            ha="center",
            va="center",
            weight="bold",
            zorder=8,
            path_effects=[patheffects.withStroke(linewidth=2.2, foreground=(0, 0, 0, 0.75))],
        )
    return len(placed)


def _ramp(ax: Axes, x0: float, y0: float, wl: float, s: float, start: float) -> None:
    grad = np.linspace(0, 1, 120)
    for q in range(119):
        ax.add_patch(
            Rectangle(
                (x0 + wl * grad[q], y0),
                wl / 119 + 0.3,
                8 * s,
                color=color66(start + (1 - start) * grad[q]) / 255,
                zorder=9,
                lw=0,
            )
        )


def render_objects(
    ax: Axes,
    artifact: SociomapArtifactV3,
    names: list[str],
    cam: Camera,
    *,
    scale: tuple[float, float] | None,
    texts: FigureTexts = CZECH,
    legend_scale: float = LEGEND_SCALE,
) -> dict[str, Any]:
    """The object map (``render``) from the stored artifact. ``scale``: the declared rating ends the
    legend prints the means on; ``None`` prints them on 0-1."""
    assert isinstance(artifact.terrain, EnvelopeTerrain) and artifact.layout is not None
    w, h = cam.w, cam.h
    _background(ax, cam)
    pm = _frame(artifact, artifact.layout.points)
    m = len(pm)
    rel = artifact.heights.relative or (None,) * m
    shown = np.array([v is not None for v in artifact.heights.values])
    t = np.array([0.0 if v is None else v for v in rel])
    g = _grid(artifact.terrain.parameters.grid_resolution)
    tt = np.array([[0.0 if v is None else v for v in row] for row in artifact.terrain.height])
    z = 26 * tt
    if cam.pitch >= 0.08:
        corners = [(-SPAN, -SPAN), (SPAN, -SPAN), (SPAN, SPAN), (-SPAN, SPAN)]
        polys, deps, cols = [], [], []
        for q in range(4):
            (x0, y0), (x1, y1) = corners[q], corners[(q + 1) % 4]
            for u in range(12):  # alternating stripes
                a0, a1 = u / 12, (u + 1) / 12
                xa, ya = x0 + (x1 - x0) * a0, y0 + (y1 - y0) * a0
                xb, yb = x0 + (x1 - x0) * a1, y0 + (y1 - y0) * a1
                sx, sy, d = cam([xa, xb, xb, xa], [ya, yb, yb, ya], [0, 0, -3, -3])
                polys.append(np.c_[sx, sy])
                deps.append(d.mean())
                cols.append("#06151a" if u % 2 else "#071c22")
        o = np.argsort(deps)
        ax.add_collection(
            PolyCollection(
                [polys[i] for i in o],
                facecolors=[cols[i] for i in o],
                edgecolors=(1, 1, 1, 0.05),
                linewidths=0.3,
                zorder=1,
            )
        )
    tris, fc = _triangles(cam, g, tt)
    # The self-coloured edge hides anti-aliasing seams; the faint white one is the hairline.
    ax.add_collection(
        PolyCollection(
            tris, facecolors=fc, edgecolors=fc, linewidths=0.35, zorder=2, antialiased=True
        )
    )
    ax.add_collection(
        PolyCollection(
            tris, facecolors="none", edgecolors=(1, 1, 1, 0.025), linewidths=0.28, zorder=2.05
        )
    )
    _contours(ax, cam, g, tt, 0.75 * 0.75)
    zn = np.array([_terrain_at(g, z, p[0], p[1]) + 0.8 for p in pm])
    nx, ny, nd = cam(pm[:, 0], pm[:, 1], zn)
    # The 5 strongest RELIABLE pairs of PRIMARY objects, width 1 + 5 min(1, |r| / 0.5).
    rel_r, status = artifact.relations.r, artifact.relations.status
    primary = [artifact.roles[o] == "primary" for o in artifact.object_ids]
    cand = sorted(
        (
            (abs(rel_r[i][j]), i, j)  # type: ignore[arg-type]
            for i in range(m)
            for j in range(i + 1, m)
            if status[i][j] == "reliable"
            and rel_r[i][j] is not None
            and shown[i]
            and shown[j]
            and primary[i]
            and primary[j]
        ),
        reverse=True,
    )
    rad = 5.7 + 4.5
    for _, i, j in cand[:5]:
        r = float(rel_r[i][j])  # type: ignore[arg-type]
        ks = min(1.0, abs(r) / 0.5)
        lw = 1 + 5 * ks
        p0, p1 = np.array([nx[i], ny[i]]), np.array([nx[j], ny[j]])
        dvec = p1 - p0
        length = float(np.hypot(*dvec))
        if length <= 2 * rad:
            continue
        nrm = np.array([-dvec[1], dvec[0]]) / length
        side = 1 if i < j else -1
        cp = (p0 + p1) / 2 + nrm * min(34, 10 + 0.10 * length) * side
        along = np.linspace(0, 1, 120)[:, None]
        bez = (1 - along) ** 2 * p0 + 2 * (1 - along) * along * cp + along**2 * p1
        keep = (np.hypot(*(bez - p0).T) >= rad) & (np.hypot(*(bez - p1).T) >= rad)
        bez = bez[keep]
        ax.plot(
            bez[:, 0],
            bez[:, 1],
            color="white",
            alpha=0.5 + 0.4 * ks,
            lw=(lw + 2.4) * 0.75,
            solid_capstyle="round",
            zorder=4,
        )
        ax.plot(
            bez[:, 0],
            bez[:, 1],
            color=WARM if r > 0 else COOL,
            alpha=0.6 + 0.4 * ks,
            lw=lw * 0.75,
            solid_capstyle="round",
            zorder=5,
        )
    for i in np.argsort(nd):
        if not shown[i]:
            continue
        ax.add_patch(
            Circle((nx[i], ny[i]), (5.7 + 2.5) * node_scale(m), color="white", alpha=0.9, zorder=6)
        )
        ax.add_patch(
            Circle((nx[i], ny[i]), 5.7 * node_scale(m), color=color66(t[i]) / 255, zorder=6.1)
        )
    order = sorted(np.where(shown)[0].tolist(), key=lambda i: -(1 + 0.5 * t[i]))
    n_lab = _labels(ax, nx, ny, names, order)
    s = legend_scale
    values = np.array([v for v in artifact.heights.values if v is not None], float)
    if scale is not None:
        values = scale[0] + values * (scale[1] - scale[0])
    lo, hi = (values.min(), values.max()) if len(values) else (math.nan, math.nan)
    x0, y0, wl = 14 * s, h - 54 * s, 150 * s
    # The lowest hill's height is the declared floor of the relative heights.
    floor = artifact.spec.terrain.relative_height_floor if artifact.spec.terrain else None
    floor = 0.0 if floor is None else floor
    _ramp(ax, x0, y0, wl, s, floor)
    tx: dict[str, Any] = {"color": "#cfd6de", "fontsize": 7.2 * s, "zorder": 9}
    ax.text(x0, y0 - 6 * s, texts.height_title, va="bottom", weight="bold", **tx)
    if n_lab < shown.sum():
        ax.text(
            x0,
            y0 - 20 * s,
            texts.labelled.format(shown=n_lab, total=int(shown.sum())),
            va="bottom",
            color="#8b96a3",
            fontsize=6.4 * s,
            zorder=9,
        )
    ax.text(x0, y0 + 11 * s, _number(lo, 1, texts), va="top", **tx)
    ax.text(x0 + wl, y0 + 11 * s, _number(hi, 1, texts), va="top", ha="right", **tx)
    lowest = texts.lowest.format(floor=f"{100 * floor:.0f}")
    ax.text(x0, y0 + 24 * s, lowest, va="top", color="#8b96a3", fontsize=6.4 * s, zorder=9)
    ax.text(
        w - 14 * s,
        h - 46 * s,
        texts.line_key,
        ha="right",
        va="bottom",
        color="#8b96a3",
        fontsize=6.4 * s,
        zorder=9,
        linespacing=1.4,
    )
    if artifact.objects_not_placed:
        ax.text(
            x0,
            y0 + 35 * s,
            texts.not_placed_objects(len(artifact.objects_not_placed)),
            va="top",
            color="#8b96a3",
            fontsize=6.4 * s,
            zorder=9,
        )
    unc_px = None
    radius = None if artifact.credibility is None else artifact.credibility.uncertainty_radius
    if radius is not None:
        ps = pm[shown]
        iu = np.triu_indices(len(ps), 1)
        rms = (
            float(np.sqrt((((ps[:, None] - ps[None]) ** 2).sum(-1)[iu]).mean()))
            if len(ps) > 1
            else 0.0
        )
        unc_px = float(radius) * rms * cam.sc
        cx, cy = w - 18 * s - unc_px, 18 * s + unc_px + 10 * s
        ax.add_patch(
            Circle((cx, cy), unc_px, fill=False, ec="white", lw=1.0, ls=(0, (3, 2)), zorder=9.5)
        )
        ax.add_patch(Circle((cx, cy), 2.0, color="white", zorder=9.5))
        caption = ax.text(
            cx,
            cy - unc_px - 4 * s,
            texts.uncertainty,
            ha="center",
            va="bottom",
            color="#cfd6de",
            fontsize=6.0 * s,
            zorder=9.5,
        )
        _inside(ax, caption, w - 4)
    statement = _statement_texts(artifact, texts)
    if statement:
        _statement(ax, cam, *statement, s)
    elif artifact.sparse_design is not None and artifact.sparse_design.flag:
        ax.text(
            14 * s,
            14 * s,
            texts.sparse,
            ha="left",
            va="top",
            color="#ffd27a",
            fontsize=6.4 * s,
            zorder=9.5,
        )
    return {
        "pm": pm,
        "lines": cand[:5],
        "labelled": n_lab,
        "uncertainty_px": unc_px,
        "statement": bool(statement),
    }


def render_respondents(
    ax: Axes,
    artifact: SociomapArtifactV3,
    names: list[str],
    cam: Camera,
    *,
    texts: FigureTexts = CZECH,
    legend_scale: float = LEGEND_SCALE,
) -> dict[str, Any]:
    """The respondent map (``render_respondents``) from the stored artifact: the stored density of
    the clearly placed respondents, every placed respondent as a dot (a weakly placed one
    fainter), coloured by taste segment when the set shows segments; the objects as labelled
    grey nodes. No uncertainty circle (the panel's respondent map has none)."""
    resp = artifact.respondents
    assert isinstance(resp, RespondentMap) and artifact.layout is not None
    w, h = cam.w, cam.h
    _background(ax, cam)
    pm = _frame(artifact, artifact.layout.points)
    m = len(pm)
    status = np.array(resp.placement)
    placed = np.array(
        [
            p != "NOT_PLACED" and x is not None and y is not None
            for p, x, y in zip(resp.placement, resp.x, resp.y, strict=True)
        ]
    )
    pr = _frame(
        artifact, [(x, y) for x, y, ok in zip(resp.x, resp.y, placed, strict=True) if ok]
    ).reshape(-1, 2)
    shown = np.array([v is not None for v in artifact.heights.values])
    g = _grid(resp.density.parameters.grid_resolution)
    tt = np.asarray(resp.density.height, float)
    z = 26 * tt
    if cam.pitch >= 0.08:
        corners = [(-SPAN, -SPAN), (SPAN, -SPAN), (SPAN, SPAN), (-SPAN, SPAN)]
        polys, deps = [], []
        for q in range(4):
            (x0, y0), (x1, y1) = corners[q], corners[(q + 1) % 4]
            sx, sy, d = cam([x0, x1, x1, x0], [y0, y1, y1, y0], [0, 0, -3, -3])
            polys.append(np.c_[sx, sy])
            deps.append(d.mean())
        o = np.argsort(deps)
        ax.add_collection(
            PolyCollection(
                [polys[i] for i in o],
                facecolors="#071c22",
                edgecolors=(1, 1, 1, 0.05),
                linewidths=0.3,
                zorder=1,
            )
        )
    tris, fc = _triangles(cam, g, tt)
    ax.add_collection(
        PolyCollection(
            tris, facecolors=fc, edgecolors=fc, linewidths=0.35, zorder=2, antialiased=True
        )
    )
    _contours(ax, cam, g, tt, 0.56)
    seg = resp.segments
    shown_segments = seg is not None and seg.decision == "SEGMENTS"
    if len(pr):
        zr = np.array([_terrain_at(g, z, p[0], p[1]) + 0.4 for p in pr])
        rx, ry, _ = cam(pr[:, 0], pr[:, 1], zr)
        fa = status[placed] == "FADED"
        if shown_segments:
            assert seg is not None and seg.label is not None and seg.coloured is not None
            sl = np.where(np.asarray(seg.coloured), np.asarray(seg.label), -1)[placed]
            cols = np.array(
                [SEG_COLORS[j % len(SEG_COLORS)] if j >= 0 else SEG_GREY for j in sl], dtype=object
            )
            for msk, alpha in ((~fa, 0.85), (fa, 0.25)):
                ax.scatter(rx[msk], ry[msk], s=4.2, c=list(cols[msk]), alpha=alpha, lw=0, zorder=4)
        else:
            ax.scatter(rx[~fa], ry[~fa], s=3.5, color="white", alpha=0.75, lw=0, zorder=4)
            ax.scatter(rx[fa], ry[fa], s=3.5, color="white", alpha=0.22, lw=0, zorder=4)
    zn = np.array([_terrain_at(g, z, p[0], p[1]) + 0.8 for p in pm])
    nx, ny, nd = cam(pm[:, 0], pm[:, 1], zn)
    for i in np.argsort(nd):
        if not shown[i]:
            continue
        ax.add_patch(
            Circle((nx[i], ny[i]), (5.2 + 2.2) * node_scale(m), color="white", alpha=0.95, zorder=6)
        )
        ax.add_patch(Circle((nx[i], ny[i]), 5.2 * node_scale(m), color="#3a3f47", zorder=6.1))
    n_lab = _labels(ax, nx, ny, names, np.where(shown)[0].tolist())
    s = legend_scale
    x0, y0, wl = 14 * s, h - 54 * s, 150 * s
    _ramp(ax, x0, y0, wl, s, 0.0)
    tx: dict[str, Any] = {"color": "#cfd6de", "fontsize": 7.2 * s, "zorder": 9}
    ax.text(x0, y0 - 6 * s, texts.density_title, va="bottom", weight="bold", **tx)
    ax.text(x0, y0 + 11 * s, texts.few, va="top", **tx)
    ax.text(x0 + wl, y0 + 11 * s, texts.many, va="top", ha="right", **tx)
    n_np = int((~placed).sum())
    if n_lab < shown.sum():
        ax.text(
            14 * s,
            h - 84 * s,
            texts.labelled.format(shown=n_lab, total=int(shown.sum())),
            color="#8b96a3",
            fontsize=6.4 * s,
            zorder=9,
        )
    ax.text(
        w - 14 * s,
        h - 46 * s,
        texts.dots_key + (("\n" + texts.respondents_not_placed(n_np)) if n_np else ""),
        ha="right",
        va="bottom",
        color="#8b96a3",
        fontsize=6.4 * s,
        zorder=9,
        linespacing=1.4,
    )
    if seg is not None:
        label = dict(zip(artifact.object_ids, names, strict=True))
        tx2: dict[str, Any] = {"fontsize": 6.8 * s, "zorder": 9, "va": "top"}
        overlap = shown_segments and seg.distinct is False
        ax.text(
            14 * s,
            14 * s,
            texts.segments_title + (texts.segments_overlap if overlap else ""),
            color="#cfd6de",
            weight="bold",
            **tx2,
        )
        if shown_segments:
            for j, share in enumerate(seg.shares):
                ax.add_patch(
                    Circle(
                        (18 * s, (29 + 12 * j) * s),
                        3.2 * s,
                        color=SEG_COLORS[j % len(SEG_COLORS)],
                        zorder=9,
                    )
                )
                likes = (
                    [label.get(o, o) for o in seg.profiles[j].likes]
                    if j < len(seg.profiles)
                    else []
                )
                row = texts.segment_row.format(n=j + 1, share=f"{100 * share:.0f}")
                row += texts.segment_likes.format(labels=", ".join(likes)) if likes else ""
                ax.text(26 * s, (25 + 12 * j) * s, row, color="#cfd6de", **tx2)
            k = len(seg.shares)
            ax.add_patch(Circle((18 * s, (29 + 12 * k) * s), 3.2 * s, color=SEG_GREY, zorder=9))
            ax.text(26 * s, (25 + 12 * k) * s, texts.segment_grey, color="#8b96a3", **tx2)
        else:
            if seg.decision == "BORDERLINE" and seg.hint is not None:
                line = texts.segments_hint.format(k=seg.hint.k)
            else:
                line = (
                    texts.segments_too_few
                    if seg.reason == "TOO_FEW_RESPONDENTS"
                    else texts.segments_none
                )
            ax.text(14 * s, 26 * s, line, color="#8b96a3", **tx2)
    statement = _statement_texts(artifact, texts)
    if statement:
        _statement(ax, cam, *statement, s)
    return {"pm": pm, "pr": pr, "labelled": n_lab, "statement": bool(statement)}


def _rating_ends(artifact: SociomapArtifactV3) -> tuple[float, float] | None:
    """The declared ends the means print on, when every object shares them; else the 0-1 scale."""
    ends = {(item.scale_min, item.scale_max) for item in artifact.items}
    return next(iter(ends)) if len(ends) == 1 else None


def signed_off_snapshots(
    artifact: SociomapArtifactV3, labels: Mapping[str, str]
) -> dict[str, bytes]:
    """The report's figures of a signed-off map: the object map from above (``top``) and from the
    side (``3d``), and the respondent map (``respondents``) where it is stored."""
    names = [labels.get(o, o) for o in artifact.object_ids]
    images: dict[str, bytes] = {}
    views: list[tuple[str, str, bool]] = [("top", "top", False), ("3d", "side", False)]
    if isinstance(artifact.respondents, RespondentMap):
        views.append(("respondents", "side", True))
    for key, view, respondents in views:
        with drawing():
            fig = new_figure(WIDTH_PX * 25.4 / 96, HEIGHT_PX * 25.4 / 96)
            ax = fig.add_axes((0, 0, 1, 1))
            cam = Camera(WIDTH_PX, HEIGHT_PX, **VIEWS[view])
            if respondents:
                render_respondents(ax, artifact, names, cam)
            else:
                render_objects(ax, artifact, names, cam, scale=_rating_ends(artifact))
            _svg, png = export(fig)
        images[key] = png
    return images
