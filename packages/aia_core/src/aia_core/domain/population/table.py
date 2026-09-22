"""The parsed, text-preserving shape of a panel and its dictionary.

Produced by the infrastructure parser and judged by the domain. Every cell is the
exact text of the source file, or ``None`` for an empty cell -- nothing is typed,
trimmed, filled or inferred. That is the lossless representation of a CSV, and it
is why ``occupation_isco08`` cannot lose its leading zeros here: no code path in
this layer ever turns text into a number except the weight parser, which is
strict and fails on anything it cannot read exactly.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

__all__ = ["ParsedDictionary", "ParsedPanel"]

Cell = str | None


@dataclass(frozen=True, slots=True)
class ParsedDictionary:
    """The ordered field names declared by a field dictionary."""

    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ParsedPanel:
    """A panel as columns of raw text, aligned with ``header`` by position.

    Columns are stored by position rather than by name so that a duplicated
    header name survives parsing and is *reported* by validation, instead of one
    copy silently overwriting the other in a mapping.
    """

    header: tuple[str, ...]
    columns: tuple[tuple[Cell, ...], ...]
    row_count: int
    _index: Mapping[str, int] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if len(self.columns) != len(self.header):
            raise ValueError("a parsed panel needs exactly one column per header name")
        for position, column in enumerate(self.columns):
            if len(column) != self.row_count:
                raise ValueError(
                    f"column {self.header[position]!r} has {len(column)} cells, "
                    f"expected {self.row_count}"
                )
        index: dict[str, int] = {}
        for position, name in enumerate(self.header):
            index.setdefault(name, position)
        object.__setattr__(self, "_index", index)

    def has(self, name: str) -> bool:
        """True when ``name`` is a header name."""
        return name in self._index

    def column(self, name: str) -> tuple[Cell, ...]:
        """Return the raw cells of the first column called ``name``."""
        try:
            return self.columns[self._index[name]]
        except KeyError:
            raise KeyError(f"no column {name!r} in the parsed panel") from None
