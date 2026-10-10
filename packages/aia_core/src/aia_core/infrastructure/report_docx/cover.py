"""The original Claude Design population-field cover, packaged for offline export."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import cast

from docx.text.paragraph import Paragraph
from lxml import etree
from matplotlib.patches import Circle, Rectangle

from aia_core.infrastructure.report_docx.context import RenderContext
from aia_core.infrastructure.report_docx.images import add_vector_image
from aia_core.infrastructure.report_docx.plotting import drawing, export, new_figure

ASSET = Path(__file__).parent / "assets" / "report-cover-field.svg"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"


@cache
def _artwork() -> tuple[bytes, bytes]:
    svg = ASSET.read_bytes()
    root = etree.fromstring(svg)
    _, _, width, height = (float(v) for v in root.attrib["viewBox"].split())
    # Word owns the paper. An opaque full-page rectangle can cover the footer
    # in readers that put header/footer text behind body-anchored drawings.
    for shape in list(root):
        if (
            etree.QName(shape).localname == "rect"
            and float(shape.get("width", "0")) == width
            and float(shape.get("height", "0")) == height
        ):
            root.remove(shape)
    svg = etree.tostring(root)
    with drawing():
        fig = new_figure(210, 297)
        ax = fig.add_axes((0, 0, 1, 1))
        ax.set_xlim(0, width)
        ax.set_ylim(height, 0)
        ax.axis("off")
        for shape in root:
            attrs = shape.attrib
            color = attrs.get("fill", "none")
            alpha = float(attrs.get("fill-opacity", "1"))
            if etree.QName(shape).localname == "circle":
                ax.add_patch(
                    Circle(
                        (float(attrs["cx"]), float(attrs["cy"])),
                        float(attrs["r"]),
                        color=color,
                        alpha=alpha,
                    )
                )
            elif etree.QName(shape).localname == "rect":
                ax.add_patch(
                    Rectangle(
                        (float(attrs.get("x", "0")), float(attrs.get("y", "0"))),
                        float(attrs["width"]),
                        float(attrs["height"]),
                        color=color,
                        alpha=alpha,
                    )
                )
        _drawn, png = export(fig)
    return svg, png


def add_cover_field(ctx: RenderContext, paragraph: Paragraph) -> None:
    """Place the original A4 field behind live, editable cover text, on this page only."""
    svg, png = _artwork()
    add_vector_image(
        paragraph,
        ctx.svgs,
        svg=svg,
        png=png,
        width_mm=210,
        height_mm=297,
        alt="Dekorativní populační pole AIA",
        name="AIA report cover field",
    )
    inline = cast(etree._Element, next(paragraph._p.iter(f"{{{WP}}}inline")))
    inline.tag = f"{{{WP}}}anchor"
    for name, value in {
        "simplePos": "0",
        "relativeHeight": "0",
        "behindDoc": "1",
        "locked": "0",
        "layoutInCell": "1",
        "allowOverlap": "1",
    }.items():
        inline.set(name, value)
    simple = etree.Element(f"{{{WP}}}simplePos", x="0", y="0")
    inline.insert(0, simple)
    for index, direction in enumerate(("H", "V"), start=1):
        position = etree.Element(f"{{{WP}}}position{direction}", relativeFrom="page")
        offset = etree.SubElement(position, f"{{{WP}}}posOffset")
        offset.text = "0"
        inline.insert(index, position)
    # Schema: simplePos, positionH/V, extent, effectExtent?, wrap, docPr, graphic.
    doc_pr = inline.find(f"{{{WP}}}docPr")
    assert doc_pr is not None
    inline.insert(list(inline).index(doc_pr), etree.Element(f"{{{WP}}}wrapNone"))
    # No w:rPr formatting: the artwork lives entirely in the drawing anchor.
