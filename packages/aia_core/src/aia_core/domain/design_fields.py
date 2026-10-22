"""A design's items field by field: the unit two edits conflict on (the owner's D-06; WCE1).

:mod:`.design_items` says which **items** differ; this module says which ``(item, field)`` pairs
do, on the same keys (the items' stable ids, :mod:`.item_ids`). It is what an operation touches
(``edit_ops.touches``) and what the field-level merge will compare (WCE5). Each item has:

* ``item``: its existence. An added or removed item differs here and only here;
* its own fields: a plan-list entry's ``text``; a question's every field and ``section``, the
  section that holds it (a move between sections); a section's every field but its questions,
  which are items in their own right; a tracked set's and a battery's every field; a single value
  (a brief field, a plan field, the audience, the dimensions, ``n``) one field, ``text`` for the
  brief's and the plan's wording, ``value`` otherwise;
* and order is an item of its own (``order:sections``, ``order:section:<id>`` for a section's
  questions, ``order:<kind>`` for each plan list), whose one field ``order`` differs only when the
  items both sides have stand in a different order: adding or removing an item is no move.

So two people adding different questions to one section touch two different keys, rewording a
question and changing its options touch two fields of one item, and a section moved is the
``order`` of the sections. An item's id and its id lists are never fields. Pure: no I/O.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final

from .design_items import Document, Documents, ItemKey, item_values, normalise

__all__ = ["ITEM", "ORDER", "Touch", "changed_fields", "item_fields"]

#: One ``(item, field)``: the unit two edits conflict on.
Touch = tuple[ItemKey, str]
#: The field that is an item's existence, and the one field of an order item.
ITEM: Final = "item"
ORDER: Final = "order"

_TEXT_KINDS: Final = frozenset({"objective", "research_question", "hypothesis"})
_WHOLE_KINDS: Final = frozenset({"question", "section", "battery", "tracked_set"})
#: Single values whose field is their wording.
_WORDING: Final = frozenset({("plan", "problem_summary"), ("field", "problem_summary")})


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _scalar_field(key: ItemKey) -> str:
    return "text" if key.kind == "brief" or (key.kind, key.key) in _WORDING else "value"


def item_fields(docs: Documents, *, previous: Documents | None = None) -> dict[Touch, Any]:
    """Every ``(item, field)`` of a design and its value, its ids read against ``previous``."""
    values = item_values(docs, previous=previous)
    out: dict[Touch, Any] = {}
    sections: list[str] = []
    lists: dict[tuple[Document, str], list[str]] = {}
    for key, value in values.items():
        out[(key, ITEM)] = True
        if key.kind in _TEXT_KINDS:
            out[(key, "text")] = value
            lists.setdefault((key.document, key.kind), []).append(key.key)
        elif key.kind in _WHOLE_KINDS and isinstance(value, Mapping):
            for name, field in value.items():
                if name == "id" or (key.kind == "section" and name == "questions"):
                    continue
                out[(key, str(name))] = field
            if key.kind in ("section", "battery"):
                sections.append(key.key)
            if key.kind == "section" and isinstance(value.get("questions"), list):
                held = [str(q) for q in value["questions"]]
                out[(ItemKey("content", "order", f"section:{key.key}"), ORDER)] = held
                for q in held:
                    out[(ItemKey("content", "question", q), "section")] = key.key
        else:
            out[(key, _scalar_field(key))] = value
    if sections:
        out[(ItemKey("content", "order", "sections"), ORDER)] = sections
    for (document, kind), keys in lists.items():
        out[(ItemKey(document, "order", kind), ORDER)] = keys
    return out


def _moved(a: Sequence[Any], b: Sequence[Any]) -> bool:
    """Whether the entries both orders hold stand differently: an addition or a removal alone
    is no move."""
    common = set(a) & set(b)
    return [x for x in a if x in common] != [x for x in b if x in common]


def changed_fields(
    before: Documents | Mapping[str, Any], after: Documents | Mapping[str, Any]
) -> frozenset[Touch]:
    """The ``(item, field)`` pairs that differ between two designs, ``after``'s ids read against
    ``before``'s. An item added or removed differs in ``item`` alone; a field present on one side
    only differs; a plan-list entry's wording differs when its normalised text does."""
    b_docs = before if isinstance(before, Documents) else Documents.of(before)
    a_docs = after if isinstance(after, Documents) else Documents.of(after)
    a = item_fields(b_docs)
    b = item_fields(a_docs, previous=b_docs)
    out: set[Touch] = set()
    for touch in a.keys() | b.keys():
        key, field = touch
        if field == ORDER:
            if _moved(a.get(touch) or [], b.get(touch) or []):
                out.add(touch)
            continue
        here, there = (key, ITEM) in a, (key, ITEM) in b
        if field == ITEM:
            if here != there:
                out.add(touch)
            continue
        if not (here and there):
            continue  # an added or removed item differs in its existence alone
        if touch not in a or touch not in b:
            out.add(touch)
        elif key.kind in _TEXT_KINDS and field == "text":
            x, y = a[touch], b[touch]
            if not (isinstance(x, str) and isinstance(y, str) and normalise(x) == normalise(y)):
                out.add(touch)
        elif _canonical(a[touch]) != _canonical(b[touch]):
            out.add(touch)
    return frozenset(out)
