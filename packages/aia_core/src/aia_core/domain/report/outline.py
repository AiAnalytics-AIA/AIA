"""The report's outline: every number the document furniture prints (pure).

Chapter, section and appendix numbers, figure and table numbers, and the label a
cross-reference prints ("graf 3", "tabulka 2", "kapitola 2.1"), computed in one
pass before rendering. They are structure, not evidence, and they are written
as text, so the same document numbers identically in Word, LibreOffice and a
previewer, and a reference to a later figure resolves.
"""

from __future__ import annotations

import string
from dataclasses import dataclass

from aia_core.domain.report.model import (
    Figure,
    Heading,
    ReportDocument,
    SociomapFigure,
    Table,
)


@dataclass(frozen=True, slots=True)
class OutlineEntry:
    """One TOC or list entry: its level (1-3), printed number, title and anchor id."""

    level: int
    number: str
    title: str
    anchor: str


@dataclass(frozen=True, slots=True)
class Outline:
    headings: tuple[OutlineEntry, ...]
    figures: tuple[OutlineEntry, ...]
    tables: tuple[OutlineEntry, ...]
    #: id → the label a cross-reference prints, e.g. "graf 3".
    labels: dict[str, str]
    #: section index → its printed number ("1", "A").
    chapter_numbers: tuple[str, ...]
    #: (section index, block index) → the heading number ("2.1", "A.1.2").
    heading_numbers: dict[tuple[int, int], str]
    #: (section index, block index) → the figure or table number.
    item_numbers: dict[tuple[int, int], int]


def appendix_letter(index: int) -> str:
    """0 → A, 25 → Z, 26 → AA. A report with 27 appendices is still numbered."""
    letters = string.ascii_uppercase
    out = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        out = letters[rem] + out
    return out


def anchor_for(kind: str, *parts: object) -> str:
    return f"{kind}-" + "-".join(str(p) for p in parts)


def build_outline(doc: ReportDocument) -> Outline:
    headings: list[OutlineEntry] = []
    figures: list[OutlineEntry] = []
    tables: list[OutlineEntry] = []
    labels: dict[str, str] = {}
    chapter_numbers: list[str] = []
    heading_numbers: dict[tuple[int, int], str] = {}
    item_numbers: dict[tuple[int, int], int] = {}

    chapter = 0
    appendix = 0
    figure_n = 0
    table_n = 0
    for si, section in enumerate(doc.sections):
        if section.appendix:
            number = appendix_letter(appendix)
            appendix += 1
            label = f"příloha {number}"
        else:
            chapter += 1
            number = str(chapter)
            label = f"kapitola {number}"
        chapter_numbers.append(number)
        anchor = section.id or anchor_for("ch", number)
        headings.append(OutlineEntry(1, number, section.title, anchor))
        if section.id:
            labels[section.id] = label

        h2 = 0
        h3 = 0
        for bi, block in enumerate(section.blocks):
            if isinstance(block, Heading):
                if block.level == 2:
                    h2 += 1
                    h3 = 0
                    hnum = f"{number}.{h2}"
                else:
                    h3 += 1
                    hnum = f"{number}.{max(h2, 1)}.{h3}"
                heading_numbers[(si, bi)] = hnum
                hanchor = block.id or anchor_for("h", hnum)
                headings.append(OutlineEntry(block.level, hnum, block.text, hanchor))
                if block.id:
                    labels[block.id] = f"oddíl {hnum}"
            elif isinstance(block, Figure | SociomapFigure):
                figure_n += 1
                item_numbers[(si, bi)] = figure_n
                figures.append(OutlineEntry(1, str(figure_n), block.title, block.id))
                labels[block.id] = f"graf {figure_n}"
            elif isinstance(block, Table):
                table_n += 1
                item_numbers[(si, bi)] = table_n
                tables.append(OutlineEntry(1, str(table_n), block.title, block.id))
                labels[block.id] = f"tabulka {table_n}"
    return Outline(
        tuple(headings),
        tuple(figures),
        tuple(tables),
        labels,
        tuple(chapter_numbers),
        heading_numbers,
        item_numbers,
    )
