"""A JSON-stat 2.0 dataset as a table: the cube flattened, nothing rounded, filters by code.

JSON-stat (https://json-stat.org/format/) is the cube format statistical offices
answer in: ``id`` and ``size`` name the dimensions in order, ``dimension`` gives each
one's categories (``index``, ``label``, and for a metric ``unit``), ``role`` says
which dimension is time and which the metric, and ``value`` (with ``status``) holds
the cells in row-major order -- the last dimension varies fastest. ČSÚ's DataStat
answers its predefined selections in JSON-stat (``docs/architecture/
deep-research-connectors.md``); Eurostat's API does too, so the reader is shared.

Only a ``"version": "2.0"``, ``"class": "dataset"`` document is read; anything else is
a contract failure, never a best guess. The table it becomes:

* **columns** are the time dimension's categories, or the last dimension's when no
  dimension has the time role; each column's period is its time category's label;
* **rows** are every combination of the other dimensions, labelled by the categories
  that vary; a dimension with one category is a note (``Území: Česko``), not a row part;
* a **unit** comes from the metric dimension's category, on the column or the row
  that dimension falls on;
* **values** are the numbers' JSON text, verbatim (``3.10`` stays ``3.10``); a status
  (``p``, preliminary) stays with its value.

Filters and a period are applied to the cube here, by category code: the request
fetched the whole selection, and the table holds what was asked of it.
"""

from __future__ import annotations

import itertools
import json
import math
from collections.abc import Mapping
from typing import Any, Final

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.datasets import MAX_DATASET_CELLS, DatasetQuery
from ..domain.deep_research.grounding import normalise_text
from .dataset_connectors import contract_failure
from .web_retrieval import ToolCallFailed

__all__ = ["MAX_CUBE_CELLS", "jsonstat_table"]

#: Cells of a whole cube this reader walks before filtering; a bigger cube is refused.
MAX_CUBE_CELLS: Final = 500_000


def _failed(reason: str, message: str) -> ToolCallFailed:
    """The provider answered; what it answered cannot be what was asked. Fixed text."""
    return ToolCallFailed(message, reason=reason, delivery=Delivery.RESPONDED)


def _text(value: Any) -> str:
    if not isinstance(value, str):
        raise contract_failure("JSON-stat with textual labels")
    text = normalise_text(value)
    if not text:
        raise contract_failure("JSON-stat with non-empty labels")
    return text


def _categories(dimension: Mapping[str, Any]) -> list[str]:
    category = dimension.get("category")
    if not isinstance(category, Mapping):
        raise contract_failure("JSON-stat with categories")
    index = category.get("index")
    if index is None:
        labels = category.get("label")
        if isinstance(labels, Mapping) and len(labels) == 1:
            return [str(next(iter(labels)))]
        raise contract_failure("JSON-stat with a category index")
    if isinstance(index, list):
        codes = [str(c) for c in index]
    elif isinstance(index, Mapping):
        try:
            positions = {str(code): int(pos) for code, pos in index.items()}
        except (TypeError, ValueError) as exc:
            raise contract_failure("JSON-stat with integer category positions") from exc
        if sorted(positions.values()) != list(range(len(positions))):
            raise contract_failure("JSON-stat with a dense category index")
        codes = sorted(positions, key=lambda code: positions[code])
    else:
        raise contract_failure("JSON-stat with a category index")
    if len(set(codes)) != len(codes):
        raise contract_failure("JSON-stat with distinct category codes")
    return codes


def _label(dimension: Mapping[str, Any], code: str) -> str:
    labels = dimension["category"].get("label") or {}
    return _text(labels.get(code, code)) if isinstance(labels, Mapping) else code


def _unit(dimension: Mapping[str, Any], code: str) -> str | None:
    units = dimension["category"].get("unit") or {}
    unit = units.get(code) if isinstance(units, Mapping) else None
    if not isinstance(unit, Mapping):
        return None
    raw = unit.get("label") or unit.get("symbol")
    return _text(raw) if raw is not None else None


def _cell_text(value: Any) -> str | None:
    """A value as published: its JSON number text, a string as is, null as absent."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise contract_failure("JSON-stat with numeric values")
    if isinstance(value, str):
        return _text(value)
    raise contract_failure("JSON-stat with numeric values")


def _at(container: Any, index: int, size: int) -> Any:
    """``value`` or ``status`` at a flat index: an array, a sparse object, or one for all."""
    if isinstance(container, list):
        if len(container) != size:
            raise contract_failure("JSON-stat with one value per cell")
        return container[index]
    if isinstance(container, Mapping):
        return container.get(str(index))
    return container


def jsonstat_table(
    body: bytes,
    *,
    query: DatasetQuery,
    max_cells: int = MAX_DATASET_CELLS,
    time_dimension: str | None = None,
) -> dict[str, Any]:
    """The fields of a :class:`DatasetResult` (title, notes, columns, rows) from a JSON-stat body.

    Raises :class:`ToolCallFailed` (``RESPONDED``) for a document this reader does not
    hold to the format, a filter or period the cube does not have, or a table over
    ``max_cells``. Numbers are parsed as their text, so nothing is re-rounded.

    ``time_dimension`` names the time dimension for a provider whose documents declare
    no ``role`` (Eurostat): it applies only when the document declares no time role,
    and a document without a dimension of that id is refused. A declared role wins.
    """
    try:
        doc = json.loads(body, parse_float=lambda s: s, parse_int=lambda s: s)
    except (UnicodeDecodeError, ValueError) as exc:
        raise contract_failure("JSON") from exc
    if not isinstance(doc, Mapping) or doc.get("class") != "dataset":
        raise contract_failure("a JSON-stat dataset")
    if doc.get("version") != "2.0":
        raise contract_failure("JSON-stat 2.0")
    ids, sizes, dims = doc.get("id"), doc.get("size"), doc.get("dimension")
    if (
        not isinstance(ids, list)
        or not isinstance(sizes, list)
        or not isinstance(dims, Mapping)
        or not ids
        or len(ids) != len(sizes)
        or len(set(ids)) != len(ids)
        or any(not isinstance(d, str) or not isinstance(dims.get(d), Mapping) for d in ids)
    ):
        raise contract_failure("a JSON-stat dataset with its dimensions")
    try:
        size = [int(s) for s in sizes]
    except (TypeError, ValueError) as exc:
        raise contract_failure("a JSON-stat dataset with integer sizes") from exc
    total = math.prod(size)
    if total > MAX_CUBE_CELLS:
        raise _failed("dataset_too_large", f"the cube holds more than {MAX_CUBE_CELLS} cells")
    codes = {d: _categories(dims[d]) for d in ids}
    if any(len(codes[d]) != n for d, n in zip(ids, size, strict=True)):
        raise contract_failure("a JSON-stat dataset whose sizes match its categories")

    raw_role = doc.get("role")
    role: Mapping[str, Any] = raw_role if isinstance(raw_role, Mapping) else {}
    for name in ("time", "metric"):
        if not isinstance(role.get(name) or [], list):
            raise contract_failure("JSON-stat with roles as lists")
    time_dims = [d for d in (role.get("time") or []) if d in codes]
    if not time_dims and time_dimension is not None:
        if time_dimension not in codes:
            raise contract_failure("JSON-stat with the provider's time dimension")
        time_dims = [time_dimension]
    metric_dims = [d for d in (role.get("metric") or []) if d in codes]
    if len(time_dims) > 1 or len(metric_dims) > 1:
        raise contract_failure("JSON-stat with at most one time and one metric dimension")

    kept: dict[str, list[str]] = {d: list(codes[d]) for d in ids}
    for wanted in query.filters:
        if wanted.dimension not in kept:
            raise _failed("filter_dimension_unknown", "a filter names a dimension the data lacks")
        missing = [v for v in wanted.values if v not in codes[wanted.dimension]]
        if missing:
            raise _failed("filter_category_unknown", "a filter names a category the data lacks")
        kept[wanted.dimension] = [c for c in codes[wanted.dimension] if c in wanted.values]
    time_dim = time_dims[0] if time_dims else None
    if query.period is not None:
        if time_dim is None:
            raise _failed("period_unsupported", "the data has no time dimension")
        match = [c for c in kept[time_dim] if query.period in (c, _label(dims[time_dim], c))]
        if not match:
            raise _failed("period_unknown", "the data has no such period")
        kept[time_dim] = match

    column_dim = time_dim or ids[-1]
    row_dims = [d for d in ids if d != column_dim]
    varying = [d for d in row_dims if len(kept[d]) > 1]
    fixed = [d for d in row_dims if len(kept[d]) == 1]
    cells = math.prod(len(kept[d]) for d in ids)
    if cells > max_cells:
        raise _failed("dataset_too_large", f"the table holds more than {max_cells} cells")

    metric = metric_dims[0] if metric_dims else None
    notes = [f"{_text(dims[d].get('label', d))}: {_label(dims[d], kept[d][0])}" for d in fixed]
    for note in doc.get("note") or []:
        if isinstance(note, str) and normalise_text(note):
            notes.append(normalise_text(note)[:2000])
    columns = [
        {
            "key": code,
            "label": _label(dims[column_dim], code),
            "period": _label(dims[column_dim], code) if column_dim == time_dim else None,
            "unit": _unit(dims[column_dim], code) if column_dim == metric else None,
        }
        for code in kept[column_dim]
    ]

    stride: dict[str, int] = {}
    step = 1
    for d, n in zip(reversed(ids), reversed(size), strict=True):
        stride[d] = step
        step *= n
    position = {d: {c: i for i, c in enumerate(codes[d])} for d in ids}
    values, statuses = doc.get("value"), doc.get("status")
    if not isinstance(values, list | Mapping):
        raise contract_failure("a JSON-stat dataset with values")

    rows: list[dict[str, Any]] = []
    for combo in itertools.product(*(kept[d] for d in row_dims)):
        chosen = dict(zip(row_dims, combo, strict=True))
        label_dims = varying or row_dims
        row_values: list[str | None] = []
        row_status: list[str | None] = []
        for code in kept[column_dim]:
            flat = sum(position[d][c] * stride[d] for d, c in {**chosen, column_dim: code}.items())
            row_values.append(_cell_text(_at(values, flat, total)))
            status = _at(statuses, flat, total) if statuses is not None else None
            row_status.append(_text(status) if status is not None else None)
        unit = _unit(dims[metric], chosen[metric]) if metric in chosen else None
        rows.append(
            {
                "key": ".".join(combo) if combo else "all",
                "label": " / ".join(_label(dims[d], chosen[d]) for d in label_dims)
                if label_dims
                else _text(doc.get("label", query.dataset_id)),
                "unit": unit,
                "values": row_values,
                "statuses": row_status if any(s is not None for s in row_status) else [],
            }
        )
    title = doc.get("label")
    return {
        "title": _text(title) if title is not None else query.dataset_id,
        "notes": notes[:20],
        "columns": columns,
        "rows": rows,
    }
