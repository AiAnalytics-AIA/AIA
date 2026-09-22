"""Parse a population panel and its field dictionary without interpreting either.

The reference read the panel with ``pd.read_csv(..., dtype={'occupation_isco08':
'string'})`` and relied on that one override to stop pandas destroying the leading
zeros of ISCO-08 codes (R9). A per-column override is a rule somebody forgets on
the next loader. This parser does not infer types at all: every cell comes back as
its exact text, an empty cell as ``None``, and nothing else. Typed views are
explicit transformations downstream; the weight parser is the only one so far.

Deliberate differences from ``pd.read_csv`` defaults, all on the side of keeping
the bytes' meaning:

* ``"NA"``, ``"NaN"``, ``"null"`` and pandas' other NA tokens stay text. Import
  rule: *preserve nulls as nulls; do not fill*. Only an empty cell is null.
* No whitespace stripping, no thousands separators, no date parsing.
* A row with the wrong number of cells is an error, not a padded or truncated row.

Stdlib only (``gzip``, ``csv``). A columnar backend is a later, separate decision.
"""

from __future__ import annotations

import csv
import gzip
import io
import zlib

from aia_core.domain.population import ImportRejected, ParsedDictionary, ParsedPanel

__all__ = ["parse_dictionary", "parse_panel"]

_GZIP_MAGIC = b"\x1f\x8b"


def _text(data: bytes, what: str) -> str:
    try:
        # utf-8-sig tolerates a byte-order mark, which would otherwise glue itself
        # onto the first header name and fail the schema check for a cosmetic reason.
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportRejected(
            f"{what} is not valid UTF-8 at byte {exc.start}", failures=(f"{what}.encoding",)
        ) from exc


def parse_panel(data: bytes) -> ParsedPanel:
    """Parse gzip-compressed UTF-8 CSV with a header row into raw text columns."""
    if not data.startswith(_GZIP_MAGIC):
        raise ImportRejected("the panel is not gzip-compressed", failures=("panel.format",))
    try:
        raw = gzip.decompress(data)
    except (OSError, EOFError, zlib.error) as exc:
        raise ImportRejected(
            f"the panel is not a readable gzip stream: {exc}", failures=("panel.format",)
        ) from exc

    reader = csv.reader(io.StringIO(_text(raw, "panel"), newline=""), strict=True)
    try:
        header = next(reader)
    except StopIteration:
        raise ImportRejected("the panel is empty", failures=("panel.header",)) from None
    except csv.Error as exc:
        raise ImportRejected(
            f"the panel header is malformed: {exc}", failures=("panel.header",)
        ) from exc

    width = len(header)
    # Per-column interning: most fields are low-cardinality codes, so sharing one
    # string object per distinct value cuts memory by an order of magnitude on the
    # 18,766 x 400 panel without changing a single value.
    interned: list[dict[str, str]] = [{} for _ in range(width)]
    rows: list[list[str | None]] = []
    try:
        for line_number, row in enumerate(reader, start=2):
            if len(row) != width:
                raise ImportRejected(
                    f"panel row {line_number} has {len(row)} cells; the header has {width}",
                    failures=("panel.ragged_row",),
                )
            rows.append(
                [
                    None if cell == "" else interned[i].setdefault(cell, cell)
                    for i, cell in enumerate(row)
                ]
            )
    except csv.Error as exc:
        raise ImportRejected(f"the panel is malformed: {exc}", failures=("panel.csv",)) from exc

    columns = tuple(zip(*rows, strict=True)) if rows else tuple(() for _ in header)
    return ParsedPanel(header=tuple(header), columns=columns, row_count=len(rows))


def parse_dictionary(data: bytes, *, field_column: str = "field") -> ParsedDictionary:
    """Return the ordered field names from a field-dictionary CSV."""
    reader = csv.DictReader(io.StringIO(_text(data, "dictionary"), newline=""), strict=True)
    try:
        if reader.fieldnames is None or field_column not in reader.fieldnames:
            raise ImportRejected(
                f"the dictionary has no {field_column!r} column",
                failures=("dictionary.header",),
            )
        names: list[str] = []
        for line_number, row in enumerate(reader, start=2):
            name = row.get(field_column)
            if not name:
                raise ImportRejected(
                    f"dictionary row {line_number} names no field",
                    failures=("dictionary.empty_field",),
                )
            names.append(name)
    except csv.Error as exc:
        raise ImportRejected(
            f"the dictionary is malformed: {exc}", failures=("dictionary.csv",)
        ) from exc
    return ParsedDictionary(fields=tuple(names))
