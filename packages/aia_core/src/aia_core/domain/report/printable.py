"""A report's printed text as XML 1.0 can hold it (pure).

A report prints what people typed: a research question, a question's wording, a study's name.
A character XML 1.0 cannot hold (a bell, a lone surrogate, the vertical tab Word writes for a
pasted line break) made lxml refuse the run and the whole draft fail. Word's line, page and column
breaks print as a space, because a report's text also runs into one-line places (the running head,
a heading, a caption) where a line break would split it; its non-breaking hyphen prints as a
hyphen. Every other such character is dropped.

:func:`printable` is applied twice with the same result: by the renderer before it writes, and
by the document model before it is stored (``document_model.py``), so the stored model holds the
text the DOCX printed. What names something is left as it is (an ``id``, a ``ref``, a ``target``,
the evidence ledger, the section-source manifest), so every ref still finds its row; whatever is
printed, an identifier printed as text included, is cleaned.
"""

from __future__ import annotations

import re
from dataclasses import fields, is_dataclass, replace
from enum import Enum
from typing import Any, Final

_WORD: Final = {"\x0b": " ", "\x0c": " ", "\x0e": " ", "\x1e": "-"}
_NOT_XML: Final = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")
#: Fields that name, never print: rewriting one would part it from what it names.
_NAMES: Final = frozenset(
    {
        "id",
        "ref",
        "refs",
        "base_ref",
        "target",
        "control",
        "notes_control",
        "ledger",
        "sources",
        "outputs",
    }
)


def xml_text(s: str) -> str:
    """``s`` as XML 1.0 can hold it: Word's breaks a space, its hyphen a hyphen, the rest
    dropped; ``s`` itself when it holds none."""
    if _NOT_XML.search(s) is None:
        return s
    return _NOT_XML.sub(lambda m: _WORD.get(m.group(), ""), s)


def printable[T](value: T) -> T:
    """``value`` with its printed text made :func:`xml_text`, through dataclasses and tuples;
    ``value`` itself when nothing changed."""
    return _walk(value)  # type: ignore[no-any-return]


def _walk(value: Any) -> Any:
    if isinstance(value, Enum):
        return value
    if isinstance(value, str):
        return xml_text(value)
    if isinstance(value, tuple):
        items = tuple(_walk(v) for v in value)
        return value if all(a is b for a, b in zip(items, value, strict=True)) else items
    if is_dataclass(value) and not isinstance(value, type):
        changed = {
            f.name: new
            for f in fields(value)
            if f.name not in _NAMES and (new := _walk(old := getattr(value, f.name))) is not old
        }
        return replace(value, **changed) if changed else value
    return value
