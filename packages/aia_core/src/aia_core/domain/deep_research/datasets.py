"""A public dataset as a table, and how one of its cells becomes a groundable quote.

Plan ``deep-research-web-search.md`` § 5.3 (the ``dataset`` tool), § 7 rung 4 (the
publisher's data interface) and § 8.2 (a table number is grounded to its cell). A
connector (ČSÚ DataStat, NKOD, later Eurostat …) answers a :class:`DatasetQuery`
with a :class:`DatasetResult`: whatever the provider's own format, a table of
labelled columns and rows whose every cell carries its row and column labels, its
unit and its period, plus who published it and under which licence.

The table is the evidence; its text is a rendering of it. :meth:`DatasetResult.render`
is deterministic and versioned (:data:`DATASET_RENDERING_VERSION`): one line per
cell, ``[<locator>] <row> | <column> | period <p> | unit <u> = <value>``, so a quote
of a cell carries its headers, and the same table is always the same text -- the
same snapshot id. A cell's **locator** is ``<dataset_id>!<row_key>/<column_key>``;
``grounding.ground_cell`` checks a quote against exactly that cell.

Values are kept as the provider published them, as text: never re-rounded, never
re-formatted. A missing value is said in words, never as a number.

Pure: stdlib and Pydantic only. Imports nothing else of Deep Research, because
``contracts.SourceSnapshot`` carries a :class:`DatasetResult`.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..ai_contracts import canonical_json

__all__ = [
    "DATASET_MEDIA_TYPE",
    "DATASET_RENDERING_VERSION",
    "MAX_DATASET_CELLS",
    "MAX_DATASET_TEXT_CHARS",
    "NO_VALUE",
    "DatasetCell",
    "DatasetColumn",
    "DatasetQuery",
    "DatasetResult",
    "DatasetRow",
    "DimensionFilter",
    "cell_locator",
    "parse_locator",
]

#: The rendering's version. A change to :meth:`DatasetResult.render` is a new version:
#: the text is what snapshot ids and quotes are computed from.
DATASET_RENDERING_VERSION: Final = "aia-dataset-table-1"
#: The content type a dataset snapshot declares. Not a fetchable type: it names the rendering.
DATASET_MEDIA_TYPE: Final = "text/vnd.aia.dataset-table"
#: Cells one result may hold. A bigger answer is refused, never truncated: a truncated
#: table would say less than the dataset while looking complete.
MAX_DATASET_CELLS: Final = 5_000
#: The rendering's ceiling; the same as a web snapshot's text (``web.MAX_TEXT_CHARS``).
MAX_DATASET_TEXT_CHARS: Final = 200_000
#: How a cell without a value is rendered: words, so no number can be read from it.
NO_VALUE: Final = "no value"

#: A row, column, dimension or category key: a locator segment, so no ``!`` or ``/``.
_KEY: Final = r"^[A-Za-z0-9_.:+-]{1,120}$"
#: A dataset id: a provider code or an IRI. No whitespace, no ``!`` (the locator's separator).
_DATASET_ID: Final = r"^[^\s!\[\]{}<>\"|\\^`]{1,300}$"
_CONNECTOR_ID: Final = r"^[a-z0-9][a-z0-9.-]{1,62}$"
#: A period as a provider codes it: ``2024``, ``2024-Q2``, ``2024M03``, ``2023/2024``.
_PERIOD: Final = r"^[0-9]{4}[0-9A-Za-z/_.-]{0,20}$"
_FORBIDDEN_IN_TEXT: Final = re.compile(r"[\x00-\x1f\x7f\u2028\u2029]")


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _one_line(value: str, *, what: str) -> str:
    """A label as rendered: one line, single spaces, nothing to strip."""
    if _FORBIDDEN_IN_TEXT.search(value):
        raise ValueError(f"a {what} is one line of text without control characters")
    if value != " ".join(value.split()):
        raise ValueError(f"a {what} has single spaces and no leading or trailing space")
    return value


# --------------------------------------------------------------------------- #
# The query
# --------------------------------------------------------------------------- #


class DimensionFilter(_Closed):
    """Keep only these categories of one dimension (codes, as the provider codes them)."""

    dimension: str = Field(pattern=_KEY)
    values: tuple[str, ...] = Field(min_length=1, max_length=200)

    @field_validator("values")
    @classmethod
    def _codes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(re.fullmatch(_KEY, v) is None for v in value):
            raise ValueError("a category code is a key: letters, digits and _.:+-")
        if len(set(value)) != len(value):
            raise ValueError("each category at most once")
        return value


class DatasetQuery(_Closed):
    """One question to one connector: a dataset, the categories to keep, a period.

    Written by code from what an agent proposed (a connector and a dataset it names),
    never a provider request an agent wrote: the connector builds the request. Its
    :meth:`text` is what the retrieval gate classifies and journals, like a search
    query's text.
    """

    connector_id: str = Field(pattern=_CONNECTOR_ID)
    dataset_id: str = Field(pattern=_DATASET_ID)
    filters: tuple[DimensionFilter, ...] = Field(default=(), max_length=20)
    period: str | None = Field(default=None, pattern=_PERIOD)

    @field_validator("filters")
    @classmethod
    def _distinct(cls, value: tuple[DimensionFilter, ...]) -> tuple[DimensionFilter, ...]:
        if len({f.dimension for f in value}) != len(value):
            raise ValueError("each dimension is filtered at most once")
        return value

    def text(self) -> str:
        """The query as one deterministic line: dataset id, filters by dimension, period."""
        parts = [self.dataset_id]
        parts += [
            f"{f.dimension}={','.join(f.values)}"
            for f in sorted(self.filters, key=lambda f: f.dimension)
        ]
        if self.period is not None:
            parts.append(f"period={self.period}")
        return " ".join(parts)

    def fingerprint(self) -> str:
        return hashlib.sha256(
            canonical_json([self.connector_id, self.text()]).encode("utf-8")
        ).hexdigest()


# --------------------------------------------------------------------------- #
# The table
# --------------------------------------------------------------------------- #


class DatasetColumn(_Closed):
    """One column: its key, its label, and the unit or period every cell in it shares."""

    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1, max_length=500)
    unit: str | None = Field(default=None, min_length=1, max_length=100)
    period: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("label", "unit", "period")
    @classmethod
    def _line(cls, value: str | None) -> str | None:
        return None if value is None else _one_line(value, what="column label, unit or period")


class DatasetRow(_Closed):
    """One row: its key, its label, the unit or period it fixes, and one value per column.

    ``statuses`` are the provider's per-value flags (preliminary, estimate …), one per
    value or none at all; a flag travels with its cell into every quote of it.
    """

    key: str = Field(pattern=_KEY)
    label: str = Field(min_length=1, max_length=1000)
    unit: str | None = Field(default=None, min_length=1, max_length=100)
    period: str | None = Field(default=None, min_length=1, max_length=100)
    values: tuple[str | None, ...]
    statuses: tuple[str | None, ...] = ()

    @field_validator("label", "unit", "period")
    @classmethod
    def _line(cls, value: str | None) -> str | None:
        return None if value is None else _one_line(value, what="row label, unit or period")

    @field_validator("values", "statuses")
    @classmethod
    def _cells(cls, value: tuple[str | None, ...]) -> tuple[str | None, ...]:
        for v in value:
            if v is not None:
                if not v or len(v) > 2000:
                    raise ValueError("a value or status is 1 to 2000 characters, or absent")
                _one_line(v, what="value or status")
        return value

    @model_validator(mode="after")
    def _status_per_value(self) -> DatasetRow:
        if self.statuses and len(self.statuses) != len(self.values):
            raise ValueError("statuses are one per value, or none")
        return self


def cell_locator(dataset_id: str, row_key: str, column_key: str) -> str:
    """``<dataset_id>!<row_key>/<column_key>``: where one cell is, in any rendering."""
    return f"{dataset_id}!{row_key}/{column_key}"


def parse_locator(locator: str) -> tuple[str, str, str] | None:
    """(dataset id, row key, column key) of a well-formed locator, or None."""
    dataset_id, bang, cell = locator.rpartition("!")
    row_key, slash, column_key = cell.partition("/")
    if not (bang and slash) or re.fullmatch(_DATASET_ID, dataset_id) is None:
        return None
    if re.fullmatch(_KEY, row_key) is None or re.fullmatch(_KEY, column_key) is None:
        return None
    return dataset_id, row_key, column_key


class DatasetCell(_Closed):
    """One cell with everything a reader needs to cite it, and its line in the rendering."""

    locator: str
    dataset_id: str
    row_key: str
    column_key: str
    row_label: str
    column_label: str
    unit: str | None
    period: str | None
    value: str | None
    status: str | None

    def text(self) -> str:
        """The cell as a quote: its headers, period, unit, value and status, without the locator."""
        parts = [self.row_label, self.column_label]
        if self.period is not None:
            parts.append(f"period {self.period}")
        if self.unit is not None:
            parts.append(f"unit {self.unit}")
        line = " | ".join(parts) + " = " + (self.value if self.value is not None else NO_VALUE)
        if self.status is not None:
            line += f" | status {self.status}"
        return line

    def line(self) -> str:
        """The cell's line in the rendering: ``[<locator>] `` and :meth:`text`."""
        return f"[{self.locator}] {self.text()}"


class DatasetResult(_Closed):
    """A connector's answer, normalised as a table, with its publisher and licence.

    ``licence`` is what the provider states for the data, verbatim, or None when it
    states nothing -- never a guess. ``source_url`` is the request the connector made
    (its host is the connector's one host). ``unit`` and ``period`` apply to every
    cell; a column's or a row's own unit or period applies to its cells; a cell
    whose unit (or period) is set twice is refused, as ambiguous.
    """

    rendering_version: Literal["aia-dataset-table-1"] = DATASET_RENDERING_VERSION
    connector_id: str = Field(pattern=_CONNECTOR_ID)
    dataset_id: str = Field(pattern=_DATASET_ID)
    query: DatasetQuery
    title: str = Field(min_length=1, max_length=500)
    publisher: str = Field(min_length=1, max_length=300)
    licence: str | None = Field(default=None, min_length=1, max_length=300)
    licence_url: str | None = Field(default=None, max_length=500)
    source_url: str = Field(pattern=r"^https://[^\s]+$", max_length=4000)
    retrieved_at: datetime
    unit: str | None = Field(default=None, min_length=1, max_length=100)
    period: str | None = Field(default=None, min_length=1, max_length=100)
    notes: tuple[str, ...] = Field(default=(), max_length=20)
    columns: tuple[DatasetColumn, ...] = Field(min_length=1, max_length=MAX_DATASET_CELLS)
    rows: tuple[DatasetRow, ...] = Field(max_length=MAX_DATASET_CELLS)

    @field_validator("title", "publisher", "licence", "unit", "period")
    @classmethod
    def _line(cls, value: str | None) -> str | None:
        return None if value is None else _one_line(value, what="title, publisher or licence")

    @field_validator("notes")
    @classmethod
    def _notes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for note in value:
            if not 1 <= len(note) <= 2000:
                raise ValueError("a note is 1 to 2000 characters")
            _one_line(note, what="note")
        return value

    @model_validator(mode="after")
    def _table(self) -> DatasetResult:
        if self.query.connector_id != self.connector_id:
            raise ValueError("a result answers a query to its own connector")
        if self.query.dataset_id != self.dataset_id:
            raise ValueError("a result answers a query for its own dataset")
        width = len(self.columns)
        if len(self.rows) * width > MAX_DATASET_CELLS:
            raise ValueError(f"a result holds at most {MAX_DATASET_CELLS} cells")
        for what, items in (("column", self.columns), ("row", self.rows)):
            if len({i.key for i in items}) != len(items):
                raise ValueError(f"each {what} key at most once")
            # A cell's quote names its row and column by label; two rows with one
            # label would make two cells say the same thing.
            if len({i.label for i in items}) != len(items):
                raise ValueError(f"each {what} label at most once")
        for row in self.rows:
            if len(row.values) != width:
                raise ValueError("every row has one value per column")
        for attr in ("unit", "period"):
            levels = [
                bool(getattr(self, attr)),
                any(getattr(c, attr) for c in self.columns),
                any(getattr(r, attr) for r in self.rows),
            ]
            if sum(levels) > 1:
                raise ValueError(f"a cell's {attr} is set at one level: result, column or row")
        if len(self.render()) > MAX_DATASET_TEXT_CHARS:
            raise ValueError(f"the rendering exceeds {MAX_DATASET_TEXT_CHARS} characters")
        return self

    def cells(self) -> tuple[DatasetCell, ...]:
        """Every cell, row by row, in column order."""
        out: list[DatasetCell] = []
        for row in self.rows:
            for i, column in enumerate(self.columns):
                out.append(
                    DatasetCell(
                        locator=cell_locator(self.dataset_id, row.key, column.key),
                        dataset_id=self.dataset_id,
                        row_key=row.key,
                        column_key=column.key,
                        row_label=row.label,
                        column_label=column.label,
                        unit=self.unit or column.unit or row.unit,
                        period=self.period or column.period or row.period,
                        value=row.values[i],
                        status=row.statuses[i] if row.statuses else None,
                    )
                )
        return tuple(out)

    def cell(self, locator: str) -> DatasetCell | None:
        parsed = parse_locator(locator)
        if parsed is None or parsed[0] != self.dataset_id:
            return None
        return next((c for c in self.cells() if c.locator == locator), None)

    def render(self) -> str:
        """The table as text: a header, then one line per cell. Deterministic."""
        head = [
            f"Dataset {self.dataset_id}: {self.title}",
            f"Publisher: {self.publisher}",
            f"Licence: {self.licence or 'not stated by the provider'}",
            f"Connector: {self.connector_id}",
            f"Query: {self.query.text()}",
        ]
        head += [f"Note: {note}" for note in self.notes]
        return "\n".join(head + [c.line() for c in self.cells()])
