"""The tags of a report's locked content controls (artifact-report RPT8a): one grammar, written by
the DOCX renderer and read by the save census (RPT8b), so the two never drift.

A tag names where a printed span came from:

- ``<ref>``: a ledger value with its marks (in prose, a table cell, a KPI tile);
- ``<ref>#interval``: a table cell's interval line;
- ``<ref>#n``: a base n (a caption's, or a KPI tile's line under it);
- ``appendix:<ref>#<column>``: one cell of the evidence appendix's row for ``ref``;
- ``figure:<id>``: a figure's picture, its refs the stored figure's;
- ``count:suppressed:<id>``: what suppression removed from that table or figure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

#: The evidence appendix's columns, in their order.
APPENDIX_COLUMNS: Final = (
    "ref",
    "value",
    "interval",
    "effective_n",
    "support",
    "basis",
    "grade",
    "disclosures",
)

Kind = Literal["value", "interval", "base_n", "appendix", "figure", "suppressed"]


def value_tag(ref: str) -> str:
    return ref


def interval_tag(ref: str) -> str:
    return f"{ref}#interval"


def base_n_tag(ref: str) -> str:
    return f"{ref}#n"


def appendix_tag(ref: str, column: str) -> str:
    if column not in APPENDIX_COLUMNS:
        raise ValueError(f"no appendix column {column!r}")
    return f"appendix:{ref}#{column}"


def figure_tag(figure_id: str) -> str:
    return f"figure:{figure_id}"


def suppressed_tag(owner: str) -> str:
    if not owner:
        raise ValueError("a suppressed count names the table or figure it belongs to")
    return f"count:suppressed:{owner}"


@dataclass(frozen=True)
class ControlTag:
    """A parsed tag: what kind of span, and the ref or block it names (``column`` for the
    appendix)."""

    kind: Kind
    name: str
    column: str | None = None


_APPENDIX = re.compile(rf"^appendix:(?P<ref>[^#:]+)#(?P<column>{'|'.join(APPENDIX_COLUMNS)})$")
_REF = re.compile(r"^(?P<ref>[^#:]+)(?:#(?P<part>n|interval))?$")


def parse_tag(tag: str) -> ControlTag | None:
    """``tag`` read back, or ``None`` for a tag outside the grammar (never guessed)."""
    if m := _APPENDIX.match(tag):
        return ControlTag("appendix", m["ref"], m["column"])
    if tag.startswith("figure:") and len(tag) > len("figure:"):
        return ControlTag("figure", tag.removeprefix("figure:"))
    if tag.startswith("count:suppressed:") and len(tag) > len("count:suppressed:"):
        return ControlTag("suppressed", tag.removeprefix("count:suppressed:"))
    if m := _REF.match(tag):
        if m["part"] == "n":
            return ControlTag("base_n", m["ref"])
        if m["part"] == "interval":
            return ControlTag("interval", m["ref"])
        return ControlTag("value", m["ref"])
    return None
