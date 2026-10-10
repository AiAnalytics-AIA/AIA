"""Print-quality snapshots of frozen contract-3 maps; no layout or terrain is fitted."""

from __future__ import annotations

from collections.abc import Mapping
from textwrap import fill
from typing import Any, cast

import numpy as np
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.tri import Triangulation

from aia_core.domain.report.print_tokens import COLORS
from aia_core.domain.sociomap import SociomapArtifactV3
from aia_core.domain.sociomap.terrain import EnvelopeTerrain
from aia_core.infrastructure.report_docx.plotting import drawing, export, new_figure


def draw_object_map_snapshot(
    artifact: SociomapArtifactV3, labels: Mapping[str, str], *, perspective: bool = False
) -> bytes:
    """Use the stored points, scale and finite terrain triangles in a fixed print camera."""
    layout = artifact.layout
    if layout is None:
        raise ValueError("a not-mappable result has no snapshot")
    if perspective and not isinstance(artifact.terrain, EnvelopeTerrain):
        raise ValueError("a 3D snapshot needs stored terrain")
    with drawing():
        fig = new_figure(160, 90 if perspective else 120)
        # An opaque print ground avoids transparency seams in Word/PDF readers.
        fig.set_facecolor("white")
        ax = fig.add_subplot(111, projection="3d" if perspective else None)
        palette = LinearSegmentedColormap.from_list(
            "aia_map", [COLORS[f"viz-seq-{k}"] for k in range(1, 8)]
        )
        terrain = artifact.terrain
        if isinstance(terrain, EnvelopeTerrain):
            axis = np.asarray(terrain.parameters.axis())
            xx, yy = np.meshgrid(axis, axis)
            zz = np.array([[np.nan if h is None else h for h in row] for row in terrain.height])
            size = len(axis)
            faces: list[tuple[int, int, int]] = []
            for row in range(size - 1):
                for column in range(size - 1):
                    a = row * size + column
                    faces.extend(((a, a + 1, a + size), (a + 1, a + size + 1, a + size)))
            tri = Triangulation(xx.ravel(), yy.ravel(), np.array(faces))
            finite = np.isfinite(zz.ravel())
            tri.set_mask(~np.all(finite[tri.triangles], axis=1))
            safe_z = np.nan_to_num(zz.ravel(), nan=0.0)
            if perspective:
                cast(Any, ax).plot_trisurf(
                    tri,
                    safe_z,
                    cmap=palette,
                    vmin=0,
                    vmax=1,
                    linewidth=0,
                    antialiased=True,
                    alpha=0.9,
                )
            else:
                ax.tripcolor(tri, safe_z, cmap=palette, vmin=0, vmax=1, shading="gouraud")
        norm = Normalize(0, 1)
        for index, (_oid, point, height) in enumerate(
            zip(artifact.object_ids, layout.points, artifact.heights.values, strict=True), start=1
        ):
            x, y = point
            color = palette(norm(height)) if height is not None else COLORS["doc-muted"]
            if perspective:
                cast(Any, ax).scatter(
                    [x], [y], [height or 0], color=color, edgecolors=COLORS["doc-ink"], s=45
                )
                cast(Any, ax).text(x, y, (height or 0) + 0.035, str(index), fontsize=9)
            else:
                ax.scatter([x], [y], color=color, edgecolors=COLORS["doc-ink"], s=70, zorder=3)
                ax.annotate(
                    str(index), (x, y), xytext=(6, 6), textcoords="offset points", fontsize=9
                )
        extent = layout.extent
        ax.set_xlim(-extent, extent)
        ax.set_ylim(-extent, extent)
        ax.set_xlabel("x · jednotná vzdálenostní škála", fontsize=7)
        ax.set_ylabel("y · jednotná vzdálenostní škála", fontsize=7)
        ax.tick_params(labelsize=7)
        if perspective:
            cast(Any, ax).set_zlim(0, 1.08)
            cast(Any, ax).set_zlabel("Průměr hodnocení · 0\u20131", fontsize=7)
            cast(Any, ax).view_init(elev=32, azim=-58)
            cast(Any, ax).set_box_aspect((1, 1, 0.55))
        else:
            ax.set_aspect("equal")
            ax.grid(alpha=0.2)
        names = "\n\n".join(
            f"{i}. {fill(labels.get(oid, oid), 22)}"
            for i, oid in enumerate(artifact.object_ids, start=1)
        )
        fig.subplots_adjust(left=0.07, bottom=0.14, right=0.65 if perspective else 0.75, top=0.95)
        fig.text(0.80 if perspective else 0.77, 0.82, names, va="top", fontsize=7)
        fig.text(
            0.07,
            0.035,
            "Výška a barva: průměr hodnocení na škále 0\u20131. Mezery: bez povrchu.",
            fontsize=7,
        )
        _svg, png = export(fig)
    return png


def object_map_snapshots(result: Mapping[str, object]) -> dict[tuple[str, str, str], bytes]:
    """Render every stored contract-3 map's available views, with integrity checked first."""
    from typing import Any, cast

    from aia_core.domain.sociomap import read_artifact

    images: dict[tuple[str, str, str], bytes] = {}
    for battery in cast(list[dict[str, Any]], result.get("batteries", [])):
        labels = {o["id"]: o["label"] for o in battery["objects"]}
        for method, payload in battery.get("maps", {}).items():
            artifact = read_artifact(payload)
            if not isinstance(artifact, SociomapArtifactV3):
                raise ValueError("an object map must use contract 3")
            if artifact.layout is None:
                continue
            images[(battery["battery_id"], method, "top")] = draw_object_map_snapshot(
                artifact, labels
            )
            if isinstance(artifact.terrain, EnvelopeTerrain):
                images[(battery["battery_id"], method, "3d")] = draw_object_map_snapshot(
                    artifact, labels, perspective=True
                )
    return images
