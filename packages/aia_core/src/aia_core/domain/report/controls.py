"""Text code wrote from one stored source, put under that source's locked control (pure).

A chapter code composes whole from one record (the method chapter from the run's) prints its
numbers in prose, lists and table cells. :func:`under` gives every such block that prints a digit,
holds no ledger value and has no control yet the chapter's source tag (artifact-report RPT8a,
part 3): a guard against a stray keystroke in the editor, never a refusal (ADR 0035, amended).
A ledger value keeps its own control, so a block holding one is left as it is.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from aia_core.domain.report.model import (
    Block,
    BulletList,
    Callout,
    Inline,
    Paragraph,
    Section,
    Table,
    TableRow,
    Text,
    TextCell,
    Value,
    block_inlines,
)


def _digits(text: str) -> bool:
    return any(c.isdigit() for c in text)


def _prints_a_number(content: Iterable[Inline]) -> bool:
    inlines = tuple(content)
    return not any(isinstance(i, Value) for i in inlines) and any(
        isinstance(i, Text) and _digits(i.text) for i in inlines
    )


def _row(row: TableRow, tag: str) -> TableRow:
    cells = tuple(
        replace(c, control=tag)
        if isinstance(c, TextCell) and c.control is None and _digits(c.text)
        else c
        for c in row.cells
    )
    return row if cells == row.cells else replace(row, cells=cells)


def _block(block: Block, tag: str) -> Block:
    if isinstance(block, Paragraph | Callout | BulletList) and block.control is None:
        return replace(block, control=tag) if _prints_a_number(block_inlines(block)) else block
    if isinstance(block, Table):
        rows = tuple(_row(row, tag) for row in block.rows)
        notes = block.notes_control
        if notes is None and any(_digits(n) for n in block.notes):
            notes = tag
        return replace(block, rows=rows, notes_control=notes)
    return block


def under_blocks(blocks: Iterable[Block], tag: str) -> tuple[Block, ...]:
    """``blocks``, each that prints a number code wrote from ``tag``'s source put under it."""
    return tuple(_block(block, tag) for block in blocks)


def under(section: Section, tag: str) -> Section:
    """``section`` with :func:`under_blocks` applied to its blocks."""
    return replace(section, blocks=under_blocks(section.blocks, tag))
