"""Evidence marks: the grade of a printed number, as a small vector glyph.

One shape per print grade, in the one ``evidence-mark`` ink, so the marks
survive greyscale printing and never borrow a data colour:

* measured — a filled disc;
* calibrated — a disc inside a ring;
* modelled — a ring hatched through (the hatching of modelled chart series);
* holdout-pending — a half-filled disc;
* unknown — no glyph at all: the text ``?`` (OI-9). An unknown grade must never
  look like a weaker variant of a known one.

Each mark is drawn once per document and embedded as SVG with a PNG fallback;
every occurrence shares the two parts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from docx.text.paragraph import Paragraph
from matplotlib.patches import Circle, Wedge

from aia_core.domain.report.copy import t
from aia_core.domain.report.evidence import PrintGrade
from aia_core.domain.report.print_tokens import COLORS
from aia_core.infrastructure.report_docx import plotting
from aia_core.infrastructure.report_docx.images import SvgParts, add_vector_image
from aia_core.infrastructure.report_docx.styles import S

MARK_MM: Final = 2.5
UNKNOWN_GLYPH: Final = "?"


def grade_label(grade: PrintGrade) -> str:
    return t(f"grade_{grade.value.replace('-', '_')}")


def draw_mark(grade: PrintGrade) -> tuple[bytes, bytes]:
    """``(svg, png)`` for one grade. ``UNKNOWN`` has no image, by design."""
    if grade is PrintGrade.UNKNOWN:
        raise ValueError("an unknown grade prints '?', never a glyph")
    ink = COLORS["evidence-mark"]
    with plotting.drawing():
        fig = plotting.new_figure(MARK_MM, MARK_MM)
        ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
        ax.set_xlim(-1, 1)
        ax.set_ylim(-1, 1)
        ax.set_aspect("equal")
        ax.axis("off")
        if grade is PrintGrade.MEASURED:
            ax.add_patch(Circle((0, 0), 0.8, facecolor=ink, edgecolor="none"))
        elif grade is PrintGrade.CALIBRATED:
            ax.add_patch(Circle((0, 0), 0.8, facecolor="none", edgecolor=ink, linewidth=0.7))
            ax.add_patch(Circle((0, 0), 0.4, facecolor=ink, edgecolor="none"))
        elif grade is PrintGrade.MODELLED:
            ax.add_patch(
                Circle((0, 0), 0.8, facecolor="none", edgecolor=ink, linewidth=0.7, hatch="//////")
            )
        else:  # HOLDOUT_PENDING
            ax.add_patch(Circle((0, 0), 0.8, facecolor="none", edgecolor=ink, linewidth=0.7))
            ax.add_patch(Wedge((0, 0), 0.8, 90, 270, facecolor=ink, edgecolor="none"))
        return plotting.export(fig)


@dataclass(slots=True)
class Marks:
    """Places marks in one document; each grade is drawn once."""

    svgs: SvgParts
    _drawn: dict[PrintGrade, tuple[bytes, bytes]] = field(default_factory=dict)

    def add(self, paragraph: Paragraph, grade: PrintGrade) -> None:
        if grade is PrintGrade.UNKNOWN:
            paragraph.add_run(UNKNOWN_GLYPH, style=S.GRADE)
            return
        if grade not in self._drawn:
            self._drawn[grade] = draw_mark(grade)
        svg, png = self._drawn[grade]
        add_vector_image(
            paragraph,
            self.svgs,
            svg=svg,
            png=png,
            width_mm=MARK_MM,
            height_mm=MARK_MM,
            alt=grade_label(grade),
            name=f"mark-{grade.value}",
        )
