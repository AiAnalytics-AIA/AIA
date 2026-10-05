"""The experimental Sociomapping map as a report image (plan sociomapping-engine I2).

Draws only what the stored artifact holds: each placed object at its layout position in the
0-1 frame, coloured by its height (average answer on the set's scale) on the sequential
palette, labelled, with a legend that names the scale. Nothing is interpolated between the
objects (no WIND surface exists, M4) and no respondent is drawn (M3). Deterministic bytes.
"""

from __future__ import annotations

from collections.abc import Sequence

from matplotlib.patches import Rectangle

from aia_core.domain.report.print_tokens import COLORS
from aia_core.infrastructure.report_docx.plotting import drawing, export, new_figure

SEQUENCE = tuple(COLORS[f"viz-seq-{k}"] for k in range(1, 8))


def height_band(value: float, low: float, high: float) -> int:
    """The palette step (0-6) of a height on its scale; the scale's ends are steps 0 and 6."""
    if high <= low:
        return 3
    share = min(1.0, max(0.0, (value - low) / (high - low)))
    return min(6, int(share * 7))


def draw_sociomapping_map(
    labels: Sequence[str],
    positions: Sequence[Sequence[float]],
    heights: Sequence[float],
    scale: tuple[float, float],
    scale_labels: tuple[str, str] | None = None,
) -> bytes:
    """The map as PNG bytes. ``heights`` are on the set's scale, one per position."""
    if not (len(labels) == len(positions) == len(heights)):
        raise ValueError("one label, position and height per placed object")
    low, high = scale
    with drawing():
        fig = new_figure(160, 132)
        ax = fig.add_axes((0.04, 0.16, 0.92, 0.80))
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for side in ax.spines.values():
            side.set_color(COLORS["viz-grid"])
        for label, (x, y), h in zip(labels, positions, heights, strict=True):
            color = SEQUENCE[height_band(h, low, high)]
            ax.scatter(
                [x], [y], s=150, color=color, edgecolors=COLORS["doc-ink"], linewidths=0.6, zorder=3
            )
            ax.annotate(
                label,
                (x, y),
                xytext=(7, 5),
                textcoords="offset points",
                fontsize=8,
                color=COLORS["doc-ink"],
                zorder=4,
            )
        legend = fig.add_axes((0.18, 0.06, 0.64, 0.035))
        legend.set_xlim(0, 7)
        legend.set_ylim(0, 1)
        legend.set_xticks([0, 7])
        ends = (
            (f"{low:g} {scale_labels[0]}", f"{high:g} {scale_labels[1]}")
            if scale_labels
            else (f"{low:g}", f"{high:g}")
        )
        legend.set_xticklabels(ends, fontsize=7)
        legend.set_yticks([])
        for k, color in enumerate(SEQUENCE):
            legend.add_patch(Rectangle((k, 0), 1, 1, color=color, linewidth=0))
        legend.set_title("Výška: průměrná odpověď na škále sady", fontsize=7, pad=3)
        _svg, png = export(fig)
    return png
