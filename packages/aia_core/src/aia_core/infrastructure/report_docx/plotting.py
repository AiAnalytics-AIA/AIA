"""Matplotlib, set up once for the report: vendored fonts, tokens, deterministic output.

Every image the report draws (charts, evidence marks) goes through
:func:`export`, which writes the same figure as SVG and as a PNG fallback. The
SVG's text is converted to paths, so it needs no font on the reader's machine;
both outputs carry no date or random id, so equal content is equal bytes.

Matplotlib is imported here only, lazily by the report renderer: it is part of
the ``report`` extra, never of ``aia_core``'s core.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache
from typing import Any, Final, cast

import matplotlib

matplotlib.use("Agg")  # no display, ever; set before anything imports pyplot

from matplotlib import font_manager
from matplotlib.figure import Figure

from aia_core.domain.report.print_tokens import COLORS, STYLES
from aia_core.infrastructure.report_docx.embed import FACES, FONT_DIR

#: The chart face: the one the tables use, so a figure reads like its table.
CHART_FONT: Final = "IBM Plex Sans"
CHART_FONT_STRONG: Final = "IBM Plex Sans SmBld"
PNG_DPI: Final = 300
MM: Final = 1 / 25.4  # inches per millimetre


@cache
def _register_fonts() -> None:
    for name in (CHART_FONT, CHART_FONT_STRONG):
        for filename in FACES[name].values():
            font_manager.fontManager.addfont(str(FONT_DIR / filename))


def rc() -> dict[str, Any]:
    """The rcParams every report image is drawn under, from the print tokens."""
    size = STYLES["doc-caption"].size_pt
    return {
        "font.family": CHART_FONT,
        "font.size": size,
        "axes.edgecolor": COLORS["viz-axis"],
        "axes.labelcolor": COLORS["doc-ink"],
        "axes.linewidth": 0.6,
        "xtick.color": COLORS["viz-axis"],
        "ytick.color": COLORS["viz-axis"],
        "xtick.labelcolor": COLORS["doc-ink"],
        "ytick.labelcolor": COLORS["doc-ink"],
        "text.color": COLORS["doc-ink"],
        "grid.color": COLORS["viz-grid"],
        "grid.linewidth": 0.5,
        "hatch.color": COLORS["evidence-hatch"],
        "hatch.linewidth": 0.6,
        "svg.fonttype": "path",
        "svg.hashsalt": "aia-report",
        "path.simplify": False,
    }


@contextmanager
def drawing() -> Iterator[None]:
    _register_fonts()
    with matplotlib.rc_context(cast(Any, rc())):
        yield


def new_figure(width_mm: float, height_mm: float) -> Figure:
    fig = Figure(figsize=(width_mm * MM, height_mm * MM), facecolor="none")
    return fig


def export(fig: Figure) -> tuple[bytes, bytes]:
    """The figure as ``(svg, png)``, both deterministic."""
    svg = io.BytesIO()
    fig.savefig(svg, format="svg", metadata={"Date": None, "Creator": None})
    png = io.BytesIO()
    fig.savefig(png, format="png", dpi=PNG_DPI, metadata={"Software": None})
    return svg.getvalue(), png.getvalue()
