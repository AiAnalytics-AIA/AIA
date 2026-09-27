"""Vector images in a DOCX: SVG with a PNG fallback, and alt text.

Word 2016+ shows an SVG carried as ``asvg:svgBlip`` inside the ``a:extLst`` of an
ordinary PNG ``a:blip``; an older reader shows the PNG. LibreOffice reads the SVG.
The alt text a screen reader announces is ``wp:docPr/@descr``.

Identical images (every evidence mark of one grade) are stored once: python-docx
deduplicates the PNG by hash, and :class:`SvgParts` does the same for the SVG.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Final

from docx.document import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import Part
from docx.oxml.ns import qn
from docx.shared import Mm
from docx.text.paragraph import Paragraph
from lxml import etree

SVG_EXT_URI: Final = "{96DAC541-7B7A-43D3-8B79-37D633B846F1}"
ASVG_NS: Final = "http://schemas.microsoft.com/office/drawing/2016/SVG/main"
_A_NS: Final = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R_NS: Final = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


class SvgParts:
    """The document's SVG image parts, one per distinct image."""

    def __init__(self, document: Document) -> None:
        self._document = document
        self._by_hash: dict[str, str] = {}

    def rid(self, svg: bytes) -> str:
        digest = hashlib.sha256(svg).hexdigest()
        if digest not in self._by_hash:
            n = len(self._by_hash) + 1
            part = Part(
                PackURI(f"/word/media/vector{n}.svg"),
                "image/svg+xml",
                svg,
                self._document.part.package,
            )
            self._by_hash[digest] = self._document.part.relate_to(part, RT.IMAGE)
        return self._by_hash[digest]


def add_vector_image(
    paragraph: Paragraph,
    svgs: SvgParts,
    *,
    svg: bytes,
    png: bytes,
    width_mm: float,
    height_mm: float,
    alt: str,
    name: str,
) -> None:
    """An inline picture: the PNG, the SVG over it, the alt text on its docPr."""
    shape = paragraph.add_run().add_picture(BytesIO(png), width=Mm(width_mm), height=Mm(height_mm))
    inline: etree._Element = shape._inline
    # Word reads absent wrap distances as 0; LibreOffice as about 3 mm a side.
    for side in ("distT", "distB", "distL", "distR"):
        inline.set(side, "0")
    doc_pr = inline.find(qn("wp:docPr"))
    assert doc_pr is not None
    doc_pr.set("name", name)
    doc_pr.set("descr", alt)
    blip = next(inline.iter(f"{{{_A_NS}}}blip"))
    ext_lst = etree.SubElement(blip, f"{{{_A_NS}}}extLst")
    ext = etree.SubElement(ext_lst, f"{{{_A_NS}}}ext", uri=SVG_EXT_URI)
    svg_blip = etree.SubElement(ext, f"{{{ASVG_NS}}}svgBlip", nsmap={"asvg": ASVG_NS})
    svg_blip.set(f"{{{_R_NS}}}embed", svgs.rid(svg))
