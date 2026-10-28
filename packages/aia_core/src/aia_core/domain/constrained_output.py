"""An output contract's schema reduced to what Bedrock's constrained decoding accepts.

Brief-analysis-schema-repair chunk 4 (the product owner, 2026-10-28, W1Q6). With ``strict`` on its
tool, a model on Bedrock can only write an answer its schema's grammar allows: an array cannot
arrive as a string holding JSON (findings F1 and F3). The grammar takes a subset of JSON Schema
Draft 2020-12, as AWS documents it and the product owner read it on 2026-10-28:

* **Supported:** the basic types, ``enum``, ``const``, ``anyOf``, ``allOf``, internal ``$ref`` /
  ``$defs``, ``required``, the listed string formats, and ``pattern`` without lookaround,
  backreferences or word boundaries. Every object must say ``additionalProperties: false``.
* **Not supported:** ``minLength`` / ``maxLength``, ``minimum`` / ``maximum`` /
  ``exclusiveMinimum`` / ``exclusiveMaximum`` / ``multipleOf``, ``minItems`` above 1, recursion
  and external ``$ref``. ``prefixItems``, ``oneOf`` and ``maxItems`` are not named, so they are
  treated as unsupported.
* **Limits:** at most 12 optional properties and 16 union-typed ones in one schema.

The reduced schema keeps every type, shape and required field and drops the bounds the grammar
cannot hold: string and list lengths, numeric bounds, and a tuple's fixed length (it is sent as
an array of its items). AIA's strict validator still applies the **whole** contract after the
call (``validate_structured_output``), so nothing the contract refused is accepted. A schema the
grammar cannot express at all is refused here, by name, and goes out as it does today.

Pure: no I/O. The reduced schema is code's, built from the contract, never from a request.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Final

__all__ = [
    "MAX_OPTIONAL_PROPERTIES",
    "MAX_UNION_PROPERTIES",
    "Reduced",
    "reduce_for_grammar",
]

#: Bedrock's limits on one schema (AWS's page, read 2026-10-28).
MAX_OPTIONAL_PROPERTIES: Final = 12
MAX_UNION_PROPERTIES: Final = 16

#: Bounds the grammar cannot hold; dropped, and still checked by the contract after the call.
_DROPPED: Final = frozenset(
    {
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "maxItems",
    }
)
#: Keywords the grammar takes as they are (``minItems`` only at 0 or 1, checked apart).
_KEPT: Final = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "const",
        "anyOf",
        "allOf",
        "$ref",
        "$defs",
        "title",
        "description",
        "default",
        "format",
        "pattern",
        "minItems",
        "prefixItems",
    }
)
_FORMATS: Final = frozenset(
    {"date-time", "time", "date", "duration", "email", "hostname", "uri", "ipv4", "ipv6", "uuid"}
)
#: Lookaround, a backreference (numbered or named), a word boundary, or a large repeat: outside
#: the grammar. Read conservatively: a valid pattern it cannot tell apart is refused, never sent.
_UNSUPPORTED_PATTERN: Final = re.compile(
    r"\(\?[=!<]|\(\?P=|\\[1-9]|\\[bB]|\{\d{3,}(,\d*)?\}|\{\d+,\d{3,}\}"
)
_DEF_REF: Final = re.compile(r"^#/\$defs/([^/]+)$")


@dataclass(frozen=True, slots=True)
class Reduced:
    """The grammar's schema, or why there is none (``refusal``)."""

    schema: dict[str, Any] | None
    refusal: str | None = None


class _Refused(Exception):
    pass


def reduce_for_grammar(schema: Mapping[str, Any]) -> Reduced:
    """The contract's schema as the grammar takes it, or the first reason it cannot."""
    reduced = deepcopy(dict(schema))
    try:
        _reduce(reduced)
        defs = _defs(reduced)
        _refuse_recursion(defs)
        optional, unions = _counts(reduced, defs)
    except _Refused as refused:
        return Reduced(None, str(refused))
    if optional > MAX_OPTIONAL_PROPERTIES:
        return Reduced(None, f"optional_properties:{optional}>{MAX_OPTIONAL_PROPERTIES}")
    if unions > MAX_UNION_PROPERTIES:
        return Reduced(None, f"union_properties:{unions}>{MAX_UNION_PROPERTIES}")
    return Reduced(reduced)


def _reduce(node: Any) -> None:
    if isinstance(node, list):
        for child in node:
            _reduce(child)
        return
    if not isinstance(node, dict):
        return
    for key in list(node):
        if key in _DROPPED:
            del node[key]
        elif key not in _KEPT:
            raise _Refused(f"keyword:{key}")
    if "$ref" in node and not _DEF_REF.match(str(node["$ref"])):
        raise _Refused("ref_outside_defs")
    if isinstance(node.get("minItems"), int) and node["minItems"] > 1:
        del node["minItems"]
    if "prefixItems" in node:
        _tuple_as_array(node)
    if "format" in node and node["format"] not in _FORMATS:
        raise _Refused(f"format:{node['format']}")
    if "pattern" in node and _UNSUPPORTED_PATTERN.search(str(node["pattern"])):
        raise _Refused("pattern")
    types = node.get("type")
    is_object = (
        "properties" in node or types == "object" or (isinstance(types, list) and "object" in types)
    )
    if is_object and node.get("additionalProperties") is not False:
        raise _Refused("open_object")
    for key in ("properties", "$defs"):
        for child in (node.get(key) or {}).values():
            _reduce(child)
    for key in ("items", "anyOf", "allOf"):
        if key in node:
            _reduce(node[key])


def _tuple_as_array(node: dict[str, Any]) -> None:
    """A fixed-length tuple as an array of its items; its length stays the contract's to check."""
    items = node.pop("prefixItems")
    if not items:
        raise _Refused("empty_tuple")
    if node.get("items") is not False and "items" in node:
        raise _Refused("tuple_with_rest")
    distinct = [i for n, i in enumerate(items) if i not in items[:n]]
    node["items"] = distinct[0] if len(distinct) == 1 else {"anyOf": distinct}


def _defs(schema: dict[str, Any]) -> dict[str, Any]:
    """The schema's definitions; a ``$ref`` naming none, anywhere in the schema, is refused."""
    defs: dict[str, Any] = dict(schema.get("$defs") or {})
    for name in [*_refs(schema), *(ref for body in defs.values() for ref in _refs(body))]:
        if name not in defs:
            raise _Refused("dangling_ref")
    return defs


def _refs(node: Any) -> list[str]:
    """Every ``#/$defs/<name>`` a node references, in its own body, not through others."""
    found: list[str] = []
    stack: list[Any] = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            match = _DEF_REF.match(str(current.get("$ref", "")))
            if match:
                found.append(match.group(1))
            stack.extend(v for k, v in current.items() if k != "$defs")
        elif isinstance(current, list):
            stack.extend(current)
    return found


def _refuse_recursion(defs: dict[str, Any]) -> None:
    """A definition that reaches itself (a three-colour walk, linear in the definitions)."""
    graph = {name: set(_refs(body)) for name, body in defs.items()}
    done: set[str] = set()
    on_path: set[str] = set()

    def visit(name: str) -> None:
        if name in done:
            return
        if name in on_path:
            raise _Refused("recursive")
        on_path.add(name)
        for target in graph.get(name, ()):
            visit(target)
        on_path.discard(name)
        done.add(name)

    for name in graph:
        visit(name)


def _counts(schema: dict[str, Any], defs: dict[str, Any]) -> tuple[int, int]:
    """Optional properties across every object, and every union, as the schema expands: a
    definition counts each time it is referenced, never once for all of them."""
    optional = unions = 0
    stack: list[Any] = [{k: v for k, v in schema.items() if k != "$defs"}]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
            continue
        if not isinstance(node, dict):
            continue
        match = _DEF_REF.match(str(node.get("$ref", "")))
        if match:
            stack.append(defs[match.group(1)])
        if "anyOf" in node or isinstance(node.get("type"), list):
            unions += 1
        properties = node.get("properties")
        if isinstance(properties, dict):
            optional += len(set(properties) - set(node.get("required") or ()))
            stack.extend(properties.values())
        for key in ("items", "anyOf", "allOf"):
            if key in node:
                stack.append(node[key])
    return optional, unions
