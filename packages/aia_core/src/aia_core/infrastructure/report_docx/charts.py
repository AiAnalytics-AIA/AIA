"""Charts: a figure block drawn from the ledger with the design system's viz tokens.

The rules every chart keeps, whatever its kind:

* **Values come from the ledger, exactly.** A bar's length is ``row.value``; its
  label is ``numbers.with_unit`` of the same row — the printed number is the one
  the evidence rounded. A suppressed ref is left out and counted in the source
  line; a ``None`` ref is simply no value.
* **Colour by job, in fixed order.** Series take ``viz-cat-1..6`` by position,
  never cycled (validation caps a chart at six); a Likert chart takes the
  diverging ramp around its neutral grey; a heatmap the sequential ramp.
* **One axis**, recessive: hairline grid, no box. Direct value labels at bar tips,
  and a legend for two or more series. Text wears ink, never a series colour.
* **Modelled series are hatched** (lines are dashed) and say so in the legend,
  so a modelled number never reads as a measured one — in greyscale too.

Each chart is exported as SVG (text as paths) with a PNG fallback, and sized from
the PNG, so the picture in Word is exactly the drawing.
"""

from __future__ import annotations

import io
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Final, Literal

from matplotlib.axes import Axes
from matplotlib.figure import Figure as MplFigure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from PIL import Image

from aia_core.domain.report import numbers
from aia_core.domain.report.copy import t
from aia_core.domain.report.model import Chart, ChartKind, Series
from aia_core.domain.report.print_tokens import COLORS, PAGE
from aia_core.infrastructure.report_docx import plotting
from aia_core.infrastructure.report_docx.context import RenderContext

TEXT_WIDTH_MM: Final = PAGE.width_mm - PAGE.margin_inside_mm - PAGE.margin_outside_mm
WIDE_TEXT_WIDTH_MM: Final = PAGE.height_mm - PAGE.margin_inside_mm - PAGE.margin_outside_mm
HATCH: Final = "////"
_BAR_MM: Final = 4.2  # one bar's thickness; the band's rest is air
_LABEL_PAD: Final = 0.012  # value label offset, as a share of the axis span


@dataclass(frozen=True, slots=True)
class Point:
    """One plotted value: the number, its printed label, its interval."""

    value: float
    label: str
    lower: float | None
    upper: float | None


@dataclass(frozen=True, slots=True)
class Drawn:
    svg: bytes
    png: bytes
    width_mm: float
    height_mm: float
    omitted: int  # suppressed points left out


def _cat(i: int) -> str:
    return COLORS[f"viz-cat-{i + 1}"]


def _diverging(n: int) -> list[str]:
    """``n`` steps of the 7-step diverging ramp, symmetric about its grey midpoint."""
    picks = {
        2: [2, 6],
        3: [2, 4, 6],
        4: [1, 2, 6, 7],
        5: [1, 2, 4, 6, 7],
        6: [1, 2, 3, 5, 6, 7],
    }[n]
    return [COLORS[f"viz-div-{i}"] for i in picks]


def points(ctx: RenderContext, series: Series) -> tuple[list[Point | None], int]:
    """The series' values from the ledger; suppressed refs become gaps, counted."""
    out: list[Point | None] = []
    omitted = 0
    for ref in series.refs:
        if ref is None:
            out.append(None)
        elif ctx.ledger.is_suppressed(ref):
            out.append(None)
            omitted += 1
        else:
            row = ctx.ledger.row(ref)
            iv = row.interval
            out.append(
                Point(
                    row.value,
                    numbers.with_unit(row.value, row.decimals, row.unit),
                    None if iv is None else iv.lower,
                    None if iv is None else iv.upper,
                )
            )
    return out, omitted


def _tick_formatter(decimals: int) -> Callable[[float, float], str]:
    def fmt(value: float, _pos: float) -> str:
        return numbers.number(round(value, decimals), decimals)

    return fmt


def _clean(ax: Axes, *, value_axis: str) -> None:
    """Recessive furniture: no box, a hairline baseline, grid along values only."""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left" if value_axis == "x" else "bottom"].set_visible(True)
    ax.spines["bottom" if value_axis == "x" else "left"].set_visible(value_axis != "x")
    ax.tick_params(length=0, pad=3)
    ax.set_axisbelow(True)


def _legend(fig: MplFigure, handles: list[Patch | Line2D]) -> None:
    if len(handles) < 2:
        return
    fig.legend(
        handles=handles,
        loc="lower left",
        bbox_to_anchor=(0.0, 1.0),
        ncols=min(len(handles), 3),
        frameon=False,
        handlelength=1.2,
        handleheight=0.9,
        columnspacing=1.4,
        borderaxespad=0.0,
    )


def _series_label(series: Series) -> str:
    return f"{series.name} ({t('basis_MODELED')})" if series.modelled else series.name


def _patch(series: Series, color: str) -> Patch:
    if series.modelled:
        return Patch(facecolor=COLORS["doc-paper"], edgecolor=color, hatch=HATCH,
                     label=_series_label(series))  # fmt: skip
    return Patch(facecolor=color, edgecolor="none", label=_series_label(series))


def _bar_style(series: Series, color: str) -> dict[str, object]:
    if series.modelled:
        return {"color": COLORS["doc-paper"], "edgecolor": color, "hatch": HATCH, "linewidth": 0.8}
    return {"color": color, "edgecolor": COLORS["doc-paper"], "linewidth": 0.6}


# ---------------------------------------------------------------------- the kinds


def _bars(ax: Axes, fig: MplFigure, chart: Chart, data: list[list[Point | None]]) -> None:
    """Horizontal bars, grouped when there are several series. Labels at the tips."""
    n_series = len(chart.series)
    band = 1.0
    thick = min(0.8 / n_series, 0.42)
    values = [p.value for s in data for p in s if p is not None]
    span = max([abs(v) for v in values] + [1.0])
    for si, (series, pts) in enumerate(zip(chart.series, data, strict=True)):
        color = _cat(si)
        for ci, p in enumerate(pts):
            if p is None:
                continue
            y = ci * band + (si - (n_series - 1) / 2) * thick
            ax.barh(y, p.value, height=thick * 0.92, **_bar_style(series, color))  # type: ignore[arg-type]
            x = p.value + (span * _LABEL_PAD if p.value >= 0 else -span * _LABEL_PAD)
            ax.text(x, y, p.label, va="center", ha="left" if p.value >= 0 else "right")
    ax.set_yticks([i * band for i in range(len(chart.categories))], list(chart.categories))
    ax.invert_yaxis()
    low = min([0.0, *values])
    ax.set_xlim(low * 1.18 if low < 0 else 0, span * 1.18)
    ax.xaxis.set_visible(False)  # every bar is labelled: the axis would repeat them
    _clean(ax, value_axis="x")
    ax.axvline(0, color=COLORS["viz-axis"], linewidth=0.6)
    _legend(fig, [_patch(s, _cat(i)) for i, s in enumerate(chart.series)])


def _stacked(ax: Axes, fig: MplFigure, chart: Chart, data: list[list[Point | None]]) -> None:
    """100 % stacks: segments separated by a paper gap; labels inside when they fit."""
    colors = [_cat(i) for i in range(len(chart.series))]
    _stack(ax, chart, data, colors, start=[0.0] * len(chart.categories))
    ax.set_xlim(0, 100)
    ax.xaxis.set_visible(False)
    _clean(ax, value_axis="x")
    ax.spines["left"].set_visible(False)
    _legend(fig, [_patch(s, colors[i]) for i, s in enumerate(chart.series)])


def _stack(
    ax: Axes,
    chart: Chart,
    data: list[list[Point | None]],
    colors: Sequence[str],
    start: list[float],
) -> None:
    left = list(start)
    for si, (series, pts) in enumerate(zip(chart.series, data, strict=True)):
        for ci, p in enumerate(pts):
            if p is None:
                continue
            style = _bar_style(series, colors[si])
            style["edgecolor"] = COLORS["doc-paper"] if not series.modelled else colors[si]
            style["linewidth"] = 1.2 if not series.modelled else 0.8
            ax.barh(ci, p.value, left=left[ci], height=0.6, **style)  # type: ignore[arg-type]
            if p.value >= 9:  # the label fits inside with room on both sides
                ink = COLORS["doc-paper"] if not series.modelled and si in (0, 3, 4) else None
                ax.text(left[ci] + p.value / 2, ci, p.label, ha="center", va="center",
                        color=ink or COLORS["doc-ink"])  # fmt: skip
            left[ci] += p.value
    ax.set_yticks(range(len(chart.categories)), list(chart.categories))
    ax.invert_yaxis()


def _diverging_chart(
    ax: Axes, fig: MplFigure, chart: Chart, data: list[list[Point | None]]
) -> None:
    """Likert: the first half disagrees (left of 0), a middle neutral straddles it."""
    n = len(chart.series)
    colors = _diverging(n)
    neutral = n // 2 if n % 2 else None
    negative = list(range(n // 2))
    for ci in range(len(chart.categories)):
        left = 0.0
        for si in negative:
            p = data[si][ci]
            left -= p.value if p else 0.0
        if neutral is not None and data[neutral][ci] is not None:
            left -= data[neutral][ci].value / 2  # type: ignore[union-attr]
        for si, series in enumerate(chart.series):
            p = data[si][ci]
            if p is None:
                continue
            style = _bar_style(series, colors[si])
            style["edgecolor"] = COLORS["doc-paper"] if not series.modelled else colors[si]
            ax.barh(ci, p.value, left=left, height=0.6, **style)  # type: ignore[arg-type]
            if p.value >= 9:
                ax.text(left + p.value / 2, ci, p.label, ha="center", va="center")
            left += p.value
    ax.set_yticks(range(len(chart.categories)), list(chart.categories))
    ax.invert_yaxis()
    ax.axvline(0, color=COLORS["viz-axis"], linewidth=0.8)
    ax.set_xlim(-100, 100)
    ax.xaxis.set_visible(False)
    _clean(ax, value_axis="x")
    ax.spines["left"].set_visible(False)
    _legend(fig, [_patch(s, colors[i]) for i, s in enumerate(chart.series)])


def _line(ax: Axes, fig: MplFigure, chart: Chart, data: list[list[Point | None]]) -> None:
    """A trend: 2 px lines, end label; a modelled series is dashed."""
    xs = list(range(len(chart.categories)))
    handles: list[Patch | Line2D] = []
    for si, (series, pts) in enumerate(zip(chart.series, data, strict=True)):
        color = _cat(si)
        style: Literal["--", "-"] = "--" if series.modelled else "-"
        xy = [(x, p.value) for x, p in zip(xs, pts, strict=True) if p is not None]
        if not xy:
            continue
        ax.plot([x for x, _ in xy], [y for _, y in xy], linestyle=style, color=color,
                linewidth=1.4, marker="o", markersize=3.5,
                markeredgecolor=COLORS["doc-paper"], markeredgewidth=0.8)  # fmt: skip
        last = next(p for p in reversed(pts) if p is not None)
        ax.annotate(last.label, (xy[-1][0], xy[-1][1]), xytext=(4, 0),
                    textcoords="offset points", va="center")  # fmt: skip
        handles.append(Line2D([], [], color=color, linestyle=style, linewidth=1.4,
                              label=_series_label(series)))  # fmt: skip
    ax.set_xticks(xs, list(chart.categories))
    ax.set_xlim(-0.3, len(xs) - 0.4)
    ax.set_ylim(bottom=0)
    ax.yaxis.set_major_formatter(_tick_formatter(0))
    ax.grid(axis="y")
    _clean(ax, value_axis="y")
    ax.set_ylabel(chart.value_label)
    _legend(fig, handles)


def _dots(ax: Axes, fig: MplFigure, chart: Chart, data: list[list[Point | None]]) -> None:
    """Point and interval: the honest default for an estimate."""
    n = len(chart.series)
    handles: list[Patch | Line2D] = []
    values = [x for s in data for p in s if p is not None
              for x in (p.value, p.lower, p.upper) if x is not None]  # fmt: skip
    top = max([*values, 1.0])
    for si, (series, pts) in enumerate(zip(chart.series, data, strict=True)):
        color = _cat(si)
        for ci, p in enumerate(pts):
            if p is None:
                continue
            y = ci + (si - (n - 1) / 2) * 0.22
            if p.lower is not None and p.upper is not None:
                ax.hlines(y, p.lower, p.upper, color=color, linewidth=1.4,
                          linestyles="--" if series.modelled else "-")  # fmt: skip
            face = COLORS["doc-paper"] if series.modelled else color
            ax.plot(p.value, y, "o", markersize=5, markerfacecolor=face, markeredgecolor=color,
                    markeredgewidth=1.2)  # fmt: skip
            end = p.upper if p.upper is not None else p.value
            ax.text(end + top * _LABEL_PAD * 1.5, y, p.label, va="center")
        handles.append(Line2D([], [], color=color, marker="o", linestyle="-",
                              markerfacecolor=COLORS["doc-paper"] if series.modelled else color,
                              label=_series_label(series)))  # fmt: skip
    ax.set_yticks(range(len(chart.categories)), list(chart.categories))
    ax.set_ylim(len(chart.categories) - 0.4, -0.6)  # top to bottom, clear of the axis
    ax.set_xlim(0, top * 1.2)
    ax.xaxis.set_major_formatter(_tick_formatter(0))
    ax.grid(axis="x")
    _clean(ax, value_axis="x")
    ax.spines["bottom"].set_visible(True)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel(chart.value_label)
    _legend(fig, handles)


def _heatmap(ax: Axes, fig: MplFigure, chart: Chart, data: list[list[Point | None]]) -> None:
    """Categories by series, coloured by a 7-step sequential ramp; every cell labelled."""
    values = [p.value for s in data for p in s if p is not None]
    low, high = (min(values), max(values)) if values else (0.0, 1.0)
    for si in range(len(chart.series)):
        for ci in range(len(chart.categories)):
            p = data[si][ci]
            if p is None:
                ax.add_patch(_cell(si, ci, COLORS["doc-paper"]))
                ax.text(si, ci, t("no_value"), ha="center", va="center")
                continue
            step = 1 if high == low else 1 + math.floor(6 * (p.value - low) / (high - low))
            ax.add_patch(_cell(si, ci, COLORS[f"viz-seq-{step}"]))
            ink = COLORS["doc-paper"] if step >= 4 else COLORS["doc-ink"]
            ax.text(si, ci, p.label, ha="center", va="center", color=ink)
    ax.set_xlim(-0.5, len(chart.series) - 0.5)
    ax.set_ylim(len(chart.categories) - 0.5, -0.5)
    ax.set_xticks(range(len(chart.series)), [_series_label(s) for s in chart.series])
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(chart.categories)), list(chart.categories))
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)


def _cell(x: int, y: int, color: str) -> Patch:
    from matplotlib.patches import Rectangle

    return Rectangle((x - 0.5, y - 0.5), 1, 1, facecolor=color,
                     edgecolor=COLORS["doc-paper"], linewidth=1.5)  # fmt: skip


_KINDS: Final[
    dict[ChartKind, Callable[[Axes, MplFigure, Chart, list[list[Point | None]]], None]]
] = {
    ChartKind.BAR: _bars,
    ChartKind.GROUPED_BAR: _bars,
    ChartKind.STACKED_100: _stacked,
    ChartKind.DIVERGING: _diverging_chart,
    ChartKind.LINE: _line,
    ChartKind.DOT_INTERVAL: _dots,
    ChartKind.HEATMAP: _heatmap,
}


def _height_mm(chart: Chart) -> float:
    rows = len(chart.categories)
    if chart.kind is ChartKind.LINE:
        return 62.0
    if chart.kind is ChartKind.GROUPED_BAR:
        return 12 + rows * max(len(chart.series), 1) * _BAR_MM * 1.25
    if chart.kind is ChartKind.HEATMAP:
        return 14 + rows * 7.5
    return 12 + rows * 7.5


def draw_chart(ctx: RenderContext, chart: Chart, *, landscape: bool = False) -> Drawn:
    """Draw ``chart`` from the ledger; return SVG, PNG, the printed size and omissions."""
    data: list[list[Point | None]] = []
    omitted = 0
    for series in chart.series:
        pts, gone = points(ctx, series)
        data.append(pts)
        omitted += gone
    # A category left with nothing to show because suppression removed it goes,
    # label and all: removed, not greyed (it is counted in the source line).
    keep = [
        ci
        for ci in range(len(chart.categories))
        if any(pts[ci] is not None for pts in data)
        or not any(r is not None and ctx.ledger.is_suppressed(r)
                   for s in chart.series for r in (s.refs[ci],))
    ]  # fmt: skip
    if len(keep) != len(chart.categories):
        chart = replace(
            chart,
            categories=tuple(chart.categories[i] for i in keep),
            series=tuple(replace(s, refs=tuple(s.refs[i] for i in keep)) for s in chart.series),
        )
        data = [[pts[i] for i in keep] for pts in data]
    width = WIDE_TEXT_WIDTH_MM if landscape else TEXT_WIDTH_MM
    with plotting.drawing():
        fig = plotting.new_figure(width, _height_mm(chart))
        ax = fig.add_axes((0.22, 0.08, 0.74, 0.84))
        ax.set_facecolor("none")
        _KINDS[chart.kind](ax, fig, chart, data)
        svg = io.BytesIO()
        fig.savefig(svg, format="svg", bbox_inches="tight", pad_inches=0.04,
                    metadata={"Date": None, "Creator": None})  # fmt: skip
        png = io.BytesIO()
        fig.savefig(png, format="png", dpi=plotting.PNG_DPI, bbox_inches="tight",
                    pad_inches=0.04, metadata={"Software": None})  # fmt: skip
    with Image.open(io.BytesIO(png.getvalue())) as im:
        px_w, px_h = im.size
    scale = 25.4 / plotting.PNG_DPI
    w_mm, h_mm = px_w * scale, px_h * scale
    if w_mm > width:  # never wider than the text block
        h_mm *= width / w_mm
        w_mm = width
    return Drawn(svg.getvalue(), png.getvalue(), w_mm, h_mm, omitted)
