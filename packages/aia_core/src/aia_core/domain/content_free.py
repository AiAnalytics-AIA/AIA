"""What a deleted client's kept rows may still say (settings-backends SB5; MVPQ-07: kept rows
are content-free -- identifiers, codes, digests, numbers and times; no text, no client name).

:func:`rename` replaces a deleted client's and its studies' names with their ids, inside any
string; :func:`content_free` then erases every string that is not an AIA identifier, an
enumerated code, a digest or a time. Numbers, booleans and nulls stay. Pure.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Final

__all__ = ["ERASED", "ID_PREFIXES", "content_free", "rename"]

ERASED: Final = "erased"

#: The prefixes AIA's own identifiers carry (``new_*_id`` and the repositories' ids). A
#: string of another shape -- "SKODA", "Coca-Cola" -- is text and is erased.
ID_PREFIXES: Final = frozenset(
    {
        "ART", "ATT", "AUE", "CALL", "CLI", "CNF", "CON", "CWJ", "DRP", "DRS", "DRT", "EOB",
        "EOP", "EV", "FWJ", "GAP", "GATE", "IND", "KNF", "KNL", "KNP", "KNW", "LDT", "LEAD",
        "LMM", "LRV", "MTV", "ORG", "PL", "PRJ", "PRM", "PV", "REV", "ROW", "RSV", "RUN", "SMK",
        "SNP", "SRC", "SRO", "STP", "STU", "TOOL", "USR", "WAL", "WRK",
    }
)  # fmt: skip
_ID: Final = re.compile(r"^(?P<prefix>[A-Z]{2,5})-[0-9A-Za-z]{4,64}$")
#: An enumerated code: upper case with at least one underscore (MEMBER_ADDED, CLASS_C_...).
_CODE: Final = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
_DIGEST: Final = re.compile(r"^[0-9a-f]{12,128}$")
_TIME: Final = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ][0-9:.]+(?:Z|[+-]\d{2}:?\d{2})?)?$")
#: A name shorter than this is not searched for inside other text: "S" is in every id.
_MIN_NAME: Final = 4


def _kept(text: str) -> bool:
    m = _ID.match(text)
    if m and m.group("prefix") in ID_PREFIXES:
        return True
    return bool(_CODE.match(text) or _DIGEST.match(text) or _TIME.match(text))


def rename(value: Any, names: Mapping[str, str]) -> Any:
    """``value`` with each of ``names`` (a name -> its id) replaced by its id: a whole string,
    or, for a name of four characters or more, inside a longer one; nested."""
    if isinstance(value, str):
        if value in names:
            return names[value]
        for name in sorted((n for n in names if len(n) >= _MIN_NAME), key=len, reverse=True):
            if name in value:
                value = value.replace(name, names[name])
        return value
    if isinstance(value, list):
        return [rename(v, names) for v in value]
    if isinstance(value, dict):
        return {k: rename(v, names) for k, v in value.items()}
    return value


def content_free(value: Any) -> Any:
    """``value`` with every string that is no AIA id, code, digest or time replaced by
    :data:`ERASED`, nested; numbers, booleans and nulls stay; keys stay (they are the code's)."""
    if isinstance(value, str):
        return value if _kept(value) else ERASED
    if isinstance(value, list):
        return [content_free(v) for v in value]
    if isinstance(value, dict):
        return {k: content_free(v) for k, v in value.items()}
    return value
